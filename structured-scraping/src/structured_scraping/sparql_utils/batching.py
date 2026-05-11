"""Batching and pagination operations for large SPARQL queries.

This module provides functions for handling large SPARQL queries through
batching, pagination, and resilient processing that can handle data corruption
and server-side issues.
"""

import json
import logging
import re
import time
from pathlib import Path

from .core import SPARQLError, extract_bindings
from .io import save_results_to_csv
from .retry import query_sparql_endpoint_with_retry

logger = logging.getLogger(__name__)


def _extract_variables_from_select(select_clause: str) -> list[str]:
    """Extract variable names from a SPARQL SELECT clause.

    Args:
        select_clause (str): The SELECT clause content.

    Returns:
        list[str]: List of variable names (including ? prefix).

    """
    variables: list[str] = []
    
    # Split by whitespace and commas, then extract variable names
    parts = re.split(r"[,\s]+", select_clause)
    for part_orig in parts:
        part = part_orig.strip()
        if not part:
            continue
            
        # Handle simple variables like ?person
        var_match = re.match(r"\?(\w+)", part)
        if var_match:
            variables.append(f"?{var_match.group(1)}")
            continue
        
        # Handle expressions with AS clause like (COUNT(*) AS ?count)
        as_match = re.search(r"AS\s+\?(\w+)", part, re.IGNORECASE)
        if as_match:
            variables.append(f"?{as_match.group(1)}")
            continue
    
    return variables


def _choose_ordering_variable(variables: list[str]) -> str:
    """Choose the best variable for ordering from a list of SPARQL variables.

    Prefers URI variables over label/literal variables for stable ordering.

    Args:
        variables (list[str]): List of variable names (including ? prefix).

    Returns:
        str: The chosen variable for ordering.

    Raises:
        ValueError: If no suitable variable is found.

    """
    if not variables:
        raise ValueError("No variables provided for ordering")
    
    uri_variables: list[str] = []
    literal_variables: list[str] = []
    
    # Categorize variables
    for var in variables:
        var_name = var[1:].lower()  # Remove ? and convert to lowercase
        
        # Skip obvious literal/label variables
        literal_suffixes = ["label", "description", "name", "count", "date", "time"]
        if any(suffix in var_name for suffix in literal_suffixes):
            literal_variables.append(var)
        else:
            uri_variables.append(var)
    
    # Choose the best ordering variable
    if uri_variables:
        return uri_variables[0]
    if literal_variables:
        return literal_variables[0]
    return variables[0]


def _ensure_ordered_query(base_query: str) -> str:
    """Ensure a SPARQL query has an ORDER BY clause for consistent batching.

    This function analyzes the query to determine if it already has an ORDER BY
    clause. If not, it automatically adds one based on the variables being selected,
    preferring URI variables over literal variables for stable ordering.

    Args:
        base_query (str): The base SPARQL query string.

    Returns:
        str: The query with an ORDER BY clause added if necessary.

    Raises:
        ValueError: If the query structure cannot be parsed or no suitable
            ordering variable is found.

    """
    # Normalize whitespace and remove comments
    normalized_query = re.sub(r"\s+", " ", base_query.strip())
    
    # Check if query already has ORDER BY
    if re.search(r"\bORDER\s+BY\b", normalized_query, re.IGNORECASE):
        return base_query
    
    # Extract SELECT variables
    select_match = re.search(r"SELECT\s+(.*?)\s+WHERE", normalized_query, re.IGNORECASE | re.DOTALL)
    if not select_match:
        raise ValueError("Could not find SELECT...WHERE pattern in query")
    
    select_clause = select_match.group(1).strip()
    
    # Handle SELECT * case
    if select_clause == "*":
        # For SELECT *, use the first triple pattern subject variable
        triple_match = re.search(r"WHERE\s*\{\s*\?(\w+)", normalized_query, re.IGNORECASE)
        if triple_match:
            order_var = f"?{triple_match.group(1)}"
        else:
            raise ValueError("Cannot determine ordering variable for SELECT * query")
    else:
        # Extract and choose the best ordering variable
        variables = _extract_variables_from_select(select_clause)
        order_var = _choose_ordering_variable(variables)
    
    # Add ORDER BY clause before any existing LIMIT
    limit_match = re.search(r"\s+(LIMIT\s+\d+)\s*$", normalized_query, re.IGNORECASE)
    if limit_match:
        # Insert ORDER BY before LIMIT
        limit_clause = limit_match.group(1)
        query_without_limit = normalized_query[:limit_match.start()]
        return f"{query_without_limit} ORDER BY {order_var} {limit_clause}"
    
    # Simply append ORDER BY
    return f"{base_query} ORDER BY {order_var}"


def batched_sparql_query(
    endpoint_url: str,
    base_query: str,
    batch_size: int = 10000,
    pause_s: float = 1.0,
    timeout: int | None = None,
    user_agent: str | None = None,
    max_retries: int = 3,
    base_delay: float = 2.0,
) -> list[dict[str, str]]:
    """Run a SPARQL query in batches using LIMIT/OFFSET to avoid timeouts.

    This function automatically handles pagination by repeatedly executing
    the query with increasing OFFSET values until no more results are returned.
    It includes rate limiting protection with exponential backoff retry logic.

    Args:
        endpoint_url (str): The URL of the SPARQL endpoint.
        base_query (str): The base SPARQL query string (without LIMIT/OFFSET).
        batch_size (int, optional): The number of results to fetch per batch.
            Defaults to 10000.
        pause_s (float, optional): The pause between batches in seconds.
            Defaults to 1.0.
        timeout (int | None, optional): Query timeout in seconds per batch.
            Defaults to None.
        user_agent (str | None, optional): Custom user agent string.
            Defaults to None.
        max_retries (int, optional): Maximum number of retries for rate limiting.
            Defaults to 3.
        base_delay (float, optional): Base delay for exponential backoff in seconds.
            Defaults to 2.0.

    Returns:
        list[dict[str, str]]: A list of all result bindings from all batches,
            where each dictionary maps variable names to their string values.

    Raises:
        SPARQLError: If any batch query execution fails after retries.
        KeyError: If the SPARQL results don't have the expected structure.

    """
    all_results: list[dict[str, str]] = []
    offset = 0
    batch_count = 0

    logger.info(
        "Starting batched SPARQL query with batch_size=%d, pause_s=%.1f, max_retries=%d",
        batch_size,
        pause_s,
        max_retries,
    )

    # Ensure the base query has an ORDER BY clause for consistent batching
    ordered_query = _ensure_ordered_query(base_query)

    while True:
        batch_count += 1
        
        # Construct the paged query
        paged_query = f"{ordered_query} LIMIT {batch_size} OFFSET {offset}"
        
        logger.info(
            "Executing batch %d (offset %d-%d)",
            batch_count,
            offset,
            offset + batch_size - 1,
        )

        try:
            # Execute the batch query with retry logic
            sparql_results = query_sparql_endpoint_with_retry(
                endpoint_url=endpoint_url,
                query=paged_query,
                return_format="json",
                timeout=timeout,
                user_agent=user_agent,
                max_retries=max_retries,
                base_delay=base_delay,
            )

            # Extract bindings from this batch
            batch_results = extract_bindings(sparql_results)

            # If no results, we're done
            if not batch_results:
                logger.info("No more results found, stopping pagination")
                break

            # Add batch results to our collection
            all_results.extend(batch_results)
            
            logger.info("Retrieved %d results in batch %d", len(batch_results), batch_count)

            # Update offset for next batch
            offset += batch_size

            # Rate limiting pause (except for the last batch)
            if pause_s > 0:
                logger.debug("Pausing %.1f seconds before next batch", pause_s)
                time.sleep(pause_s)

        except Exception:
            logger.exception("Error in batch %d", batch_count)
            raise

    logger.info(
        "Batched query completed: %d total results from %d batches",
        len(all_results),
        batch_count,
    )

    return all_results


def batched_sparql_query_to_csv(
    endpoint_url: str,
    base_query: str,
    file_path: str | Path,
    batch_size: int = 10000,
    pause_s: float = 1.0,
    fieldnames: list[str] | None = None,
    encoding: str = "utf-8-sig",
    timeout: int | None = None,
    user_agent: str | None = None,
    max_retries: int = 3,
    base_delay: float = 2.0,
) -> int:
    """Run a batched SPARQL query and save all results to CSV.

    This is a convenience function that combines batched_sparql_query() and
    save_results_to_csv() for efficient processing of large datasets with
    built-in retry logic for rate limiting.

    Args:
        endpoint_url (str): The URL of the SPARQL endpoint.
        base_query (str): The base SPARQL query string (without LIMIT/OFFSET).
        file_path (str | Path): The path where the CSV file will be saved.
        batch_size (int, optional): The number of results to fetch per batch.
            Defaults to 10000.
        pause_s (float, optional): The pause between batches in seconds.
            Defaults to 1.0.
        fieldnames (list[str] | None, optional): The column headers for the CSV.
            If None, will be inferred from the first result row. Defaults to None.
        encoding (str, optional): The file encoding to use. Defaults to "utf-8-sig"
            which includes a Byte Order Mark (BOM) for better Excel compatibility.
        timeout (int | None, optional): Query timeout in seconds per batch.
            Defaults to None.
        user_agent (str | None, optional): Custom user agent string.
            Defaults to None.
        max_retries (int, optional): Maximum number of retries for rate limiting.
            Defaults to 3.
        base_delay (float, optional): Base delay for exponential backoff in seconds.
            Defaults to 2.0.

    Returns:
        int: The total number of rows saved to the CSV file.

    Raises:
        SPARQLError: If any batch query execution fails after retries.
        KeyError: If the SPARQL results don't have the expected structure.
        ValueError: If results is empty and fieldnames is not provided.
        OSError: If there's an error writing to the file.

    """
    # Execute batched query
    all_results = batched_sparql_query(
        endpoint_url=endpoint_url,
        base_query=base_query,
        batch_size=batch_size,
        pause_s=pause_s,
        timeout=timeout,
        user_agent=user_agent,
        max_retries=max_retries,
        base_delay=base_delay,
    )

    # Save to CSV
    save_results_to_csv(all_results, file_path, fieldnames, encoding)

    return len(all_results)


def resilient_batched_sparql_query(
    endpoint_url: str,
    base_query: str,
    batch_size: int = 10000,
    pause_s: float = 1.0,
    timeout: int | None = None,
    user_agent: str | None = None,
    max_retries: int = 3,
    base_delay: float = 2.0,
    min_subdivision_size: int = 1,
) -> tuple[list[dict[str, str]], int]:
    """Run a SPARQL query in batches with resilience against corrupted individual records.

    This function extends batched_sparql_query() with the ability to subdivide batches
    when encountering JSON corruption or other errors, using binary search to isolate
    and skip only the problematic records rather than entire batches.

    Args:
        endpoint_url (str): The URL of the SPARQL endpoint.
        base_query (str): The base SPARQL query string (without LIMIT/OFFSET).
        batch_size (int, optional): The number of results to fetch per batch.
            Defaults to 10000.
        pause_s (float, optional): The pause between batches in seconds.
            Defaults to 1.0.
        timeout (int | None, optional): Query timeout in seconds per batch.
            Defaults to None.
        user_agent (str | None, optional): Custom user agent string.
            Defaults to None.
        max_retries (int, optional): Maximum number of retries for rate limiting.
            Defaults to 3.
        base_delay (float, optional): Base delay for exponential backoff in seconds.
            Defaults to 2.0.
        min_subdivision_size (int, optional): Minimum batch size before giving up
            on subdivision and skipping records. Defaults to 1.

    Returns:
        tuple[list[dict[str, str]], int]: A tuple containing:
            - A list of all successful result bindings from all batches
            - The number of records that were skipped due to corruption

    Raises:
        SPARQLError: If a non-recoverable error occurs (not JSON corruption).
        KeyError: If the SPARQL results don't have the expected structure.

    """
    all_results: list[dict[str, str]] = []
    offset = 0
    batch_count = 0
    total_skipped = 0

    logger.info(
        "Starting resilient batched SPARQL query with batch_size=%d, pause_s=%.1f, max_retries=%d",
        batch_size,
        pause_s,
        max_retries,
    )

    # Ensure the base query has an ORDER BY clause for consistent batching
    ordered_query = _ensure_ordered_query(base_query)

    while True:
        batch_count += 1
        
        logger.info(
            "Processing batch %d (offset %d-%d)",
            batch_count,
            offset,
            offset + batch_size - 1,
        )

        # Process this batch with subdivision if needed
        batch_results, skipped_in_batch = _process_batch_with_subdivision(
            endpoint_url=endpoint_url,
            base_query=ordered_query,
            offset=offset,
            batch_size=batch_size,
            timeout=timeout,
            user_agent=user_agent,
            max_retries=max_retries,
            base_delay=base_delay,
            min_subdivision_size=min_subdivision_size,
        )

        # If no results and no skipped records, we're done
        if not batch_results and skipped_in_batch == 0:
            logger.info("No more results found, stopping pagination")
            break

        # Add successful results
        if batch_results:
            all_results.extend(batch_results)
            logger.info("Retrieved %d results in batch %d", len(batch_results), batch_count)

        # Track skipped records
        if skipped_in_batch > 0:
            total_skipped += skipped_in_batch
            logger.warning("Skipped %d corrupted records in batch %d", skipped_in_batch, batch_count)

        # Update offset for next batch
        offset += batch_size

        # Rate limiting pause
        # if pause_s > 0:
        #     logger.debug("Pausing %.1f seconds before next batch", pause_s)
        #     time.sleep(pause_s)

    logger.info(
        "Resilient batched query completed: %d total results from %d batches, %d records skipped",
        len(all_results),
        batch_count,
        total_skipped,
    )

    return all_results, total_skipped


def _process_batch_with_subdivision(
    endpoint_url: str,
    base_query: str,
    offset: int,
    batch_size: int,
    timeout: int | None,
    user_agent: str | None,
    max_retries: int,
    base_delay: float,
    min_subdivision_size: int,
) -> tuple[list[dict[str, str]], int]:
    """Process a batch with subdivision to isolate corrupted records.

    This is a helper function for resilient_batched_sparql_query() that uses
    binary search subdivision to isolate and skip only corrupted records.

    Args:
        endpoint_url (str): The URL of the SPARQL endpoint.
        base_query (str): The base SPARQL query string.
        offset (int): Starting offset for this batch.
        batch_size (int): Size of the batch to process.
        timeout (int | None): Query timeout in seconds.
        user_agent (str | None): Custom user agent string.
        max_retries (int): Maximum number of retries.
        base_delay (float): Base delay for exponential backoff.
        min_subdivision_size (int): Minimum size before giving up on subdivision.

    Returns:
        tuple[list[dict[str, str]], int]: A tuple containing:
            - List of successful result bindings
            - Number of records skipped due to corruption

    """
    # Construct the paged query
    paged_query = f"{base_query} LIMIT {batch_size} OFFSET {offset}"
    
    try:
        # Try the full batch first
        sparql_results = query_sparql_endpoint_with_retry(
            endpoint_url=endpoint_url,
            query=paged_query,
            return_format="json",
            timeout=timeout,
            user_agent=user_agent,
            max_retries=max_retries,
            base_delay=base_delay,
        )
        
    except (json.JSONDecodeError, KeyError) as e:
        # JSON corruption or structure error - try subdivision
        if batch_size <= min_subdivision_size:
            # Can't subdivide further, skip these records
            logger.warning(
                "Skipping %d corrupted records at offset %d: %s",
                batch_size,
                offset,
                str(e),
            )
            return [], batch_size
        
        # Subdivide the batch and try each half
        logger.info(
            "Subdividing batch at offset %d (size %d) due to JSON error: %s",
            offset,
            batch_size,
            str(e),
        )
        
        half_size = batch_size // 2
        results: list[dict[str, str]] = []
        skipped = 0
        
        # Process first half
        first_half_results, first_half_skipped = _process_batch_with_subdivision(
            endpoint_url=endpoint_url,
            base_query=base_query,
            offset=offset,
            batch_size=half_size,
            timeout=timeout,
            user_agent=user_agent,
            max_retries=max_retries,
            base_delay=base_delay,
            min_subdivision_size=min_subdivision_size,
        )
        results.extend(first_half_results)
        skipped += first_half_skipped
        
        # Process second half
        second_half_results, second_half_skipped = _process_batch_with_subdivision(
            endpoint_url=endpoint_url,
            base_query=base_query,
            offset=offset + half_size,
            batch_size=batch_size - half_size,
            timeout=timeout,
            user_agent=user_agent,
            max_retries=max_retries,
            base_delay=base_delay,
            min_subdivision_size=min_subdivision_size,
        )
        results.extend(second_half_results)
        skipped += second_half_skipped
        
        return results, skipped
        
    except SPARQLError as e:
        from .errors import (  # noqa: PLC0415 # Import here to avoid circular imports
            classify_sparql_error,
            log_error_info,
            should_stop_processing,
        )
        
        # Classify the error using our unified system
        error_info = classify_sparql_error(e, 0.0)  # We don't track time in batching
        log_error_info(error_info, f"Batch at offset {offset} (size {batch_size})")
        
        # Check if this should stop processing entirely
        if should_stop_processing(error_info):
            # Re-raise to stop processing
            raise
        else:
            # Other SPARQL errors - let them bubble up for retry logic
            raise
        
    except Exception:
        # Other errors (network, rate limiting, etc.) should bubble up
        # as they're handled by the retry logic in query_sparql_endpoint_with_retry
        raise
    else:
        # Extract bindings from this batch
        batch_results = extract_bindings(sparql_results)
        return batch_results, 0

def resilient_batched_sparql_query_by_decade(
    endpoint_url: str,
    base_query_template: str,  # Should include placeholder like {filter_clause}
    batch_size: int = 10000,
    pause_s: float = 1.0,
    timeout: int | None = None,
    user_agent: str | None = None,
    max_retries: int = 3,
    base_delay: float = 2.0,
    min_subdivision_size: int = 1,
    start_decade: int = 1920,
    end_decade: int = 2030,
) -> tuple[list[dict[str, str]], int]:
    """Run batched SPARQL queries over each birth decade from start_decade to end_decade."""
    all_results: list[dict[str, str]] = []
    total_skipped = 0

    for decade in range(start_decade, end_decade + 1, 10):
        next_decade = decade + 10
        logger.info("Querying for people born between %d and %d", decade, next_decade)

        # Create filter clause for this decade
        date_filter = (
            f'FILTER ("{decade}-01-01"^^xsd:dateTime <= ?birthDate && '
            f'?birthDate < "{next_decade}-01-01"^^xsd:dateTime).'
        )
        # Insert the clause into the base query template
        query = base_query_template.format(date_filter = date_filter)
                                           

        # Call the original resilient query
        results, skipped = resilient_batched_sparql_query(
            endpoint_url=endpoint_url,
            base_query=query,
            batch_size=batch_size,
            pause_s=pause_s,
            timeout=timeout,
            user_agent=user_agent,
            max_retries=max_retries,
            base_delay=base_delay,
            min_subdivision_size=min_subdivision_size,
        )

        all_results.extend(results)
        total_skipped += skipped

    return all_results, total_skipped
