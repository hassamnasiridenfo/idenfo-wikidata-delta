"""File I/O operations for SPARQL results.

This module provides functions for saving SPARQL query results to various
file formats, with a focus on CSV output for data analysis.
"""

import csv
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def save_results_to_csv(
    results: list[dict[str, str]],
    file_path: str | Path,
    fieldnames: list[str] | None = None,
    encoding: str = "utf-8-sig",
) -> None:
    """Save SPARQL query results to a CSV file.
    
    Args:
        results (list[dict[str, str]]): The query results as a list of dictionaries.
            This should be the output from extract_bindings() or query_wdqs_simple().
        file_path (str | Path): The path where the CSV file will be saved.
        fieldnames (list[str] | None, optional): The column headers for the CSV.
            If None, will be inferred from all result rows to include all possible fields.
            Defaults to None.
        encoding (str, optional): The file encoding to use. Defaults to "utf-8-sig"
            which includes a Byte Order Mark (BOM) for better Excel compatibility.
        
    Returns:
        None
        
    Raises:
        ValueError: If results is empty and fieldnames is not provided.
        OSError: If there's an error writing to the file.
        
    """
    if not results and fieldnames is None:
        # For empty results with no fieldnames, create an empty CSV with no headers
        fieldnames = []
    
    # Convert Path to string if necessary
    file_path = str(file_path)
    
    # Determine fieldnames if not provided
    if fieldnames is None:
        # Collect all unique field names from all results
        all_fields: set[str] = set()
        for result in results:
            all_fields.update(result.keys())
        fieldnames = sorted(all_fields)  # Sort for consistent ordering
    
    try:
        file_path_obj = Path(file_path)
        with file_path_obj.open("w", newline="", encoding=encoding) as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(results)
            
        logger.info("Saved %d rows to CSV file: %s", len(results), file_path)
        
    except OSError as e:
        error_msg = f"Failed to write CSV file {file_path}: {e!s}"
        logger.exception(error_msg)
        raise OSError(error_msg) from e


def save_sparql_results_to_csv(
    sparql_results: dict[str, Any],
    file_path: str | Path,
    fieldnames: list[str] | None = None,
    encoding: str = "utf-8-sig",
) -> None:
    """Save raw SPARQL JSON results to a CSV file.
    
    This function combines extract_bindings() and save_results_to_csv() for convenience.
    
    Args:
        sparql_results (dict[str, Any]): The raw SPARQL results in JSON format.
        file_path (str | Path): The path where the CSV file will be saved.
        fieldnames (list[str] | None, optional): The column headers for the CSV.
            If None, will be inferred from the first result row. Defaults to None.
        encoding (str, optional): The file encoding to use. Defaults to "utf-8-sig"
            which includes a Byte Order Mark (BOM) for better Excel compatibility.
        
    Returns:
        None
        
    Raises:
        KeyError: If the SPARQL results don't have the expected structure.
        ValueError: If results is empty and fieldnames is not provided.
        OSError: If there's an error writing to the file.
        
    """
    from .core import extract_bindings  # type: ignore # Delayed import to avoid circular dependency

    # Extract bindings from raw SPARQL results
    extracted_results = extract_bindings(sparql_results)
    
    # Save to CSV
    save_results_to_csv(extracted_results, file_path, fieldnames, encoding)


def query_and_save_to_csv(
    endpoint_url: str,
    query: str,
    file_path: str | Path,
    fieldnames: list[str] | None = None,
    encoding: str = "utf-8",
    timeout: int | None = None,
    user_agent: str | None = None,
) -> int:
    """Execute a SPARQL query and directly save results to CSV.
    
    This is a convenience function that combines query execution and CSV saving.
    
    Args:
        endpoint_url (str): The URL of the SPARQL endpoint.
        query (str): The SPARQL query string to execute.
        file_path (str | Path): The path where the CSV file will be saved.
        fieldnames (list[str] | None, optional): The column headers for the CSV.
            If None, will be inferred from the first result row. Defaults to None.
        encoding (str, optional): The file encoding to use. Defaults to "utf-8".
        timeout (int | None, optional): Query timeout in seconds. Defaults to None.
        user_agent (str | None, optional): Custom user agent string. Defaults to None.
        
    Returns:
        int: The number of rows saved to the CSV file.
        
    Raises:
        SPARQLError: If the query execution fails.
        KeyError: If the SPARQL results don't have the expected structure.
        ValueError: If results is empty and fieldnames is not provided.
        OSError: If there's an error writing to the file.
        
    """
    from .core import count_results, query_sparql_endpoint_with_retry  # type: ignore # noqa: I001 # Delayed import to avoid circular dependency

    # Execute the query
    sparql_results = query_sparql_endpoint_with_retry(
        endpoint_url=endpoint_url,
        query=query,
        return_format="json",
        timeout=timeout,
        user_agent=user_agent,
    )
    
    # Save to CSV
    save_sparql_results_to_csv(sparql_results, file_path, fieldnames, encoding)
    
    # Return the number of rows saved
    return count_results(sparql_results)
