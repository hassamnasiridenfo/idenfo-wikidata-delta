"""Core SPARQL operations and exception handling.

This module provides the fundamental SPARQL query execution functionality
and core exception classes for the sparql_utils package.
"""

import logging
import re
import time
from pathlib import Path
from typing import Any
#Changes
# core.py ke TOP pe imports mein add karo
# import os
# import requests
# from dotenv import load_dotenv
# load_dotenv()

from SPARQLWrapper import CSV, JSON, TSV, XML, SPARQLWrapper

logger = logging.getLogger(__name__)

_QLEVER_WIKIDATA_ENDPOINT_MARKER = "qlever.cs.uni-freiburg.de/api/wikidata"
_WIKIDATA_PREFIX_DECLARATIONS = {
    "bd": "PREFIX bd: <http://www.bigdata.com/rdf#>",
    "p": "PREFIX p: <http://www.wikidata.org/prop/>",
    "pq": "PREFIX pq: <http://www.wikidata.org/prop/qualifier/>",
    "ps": "PREFIX ps: <http://www.wikidata.org/prop/statement/>",
    "rdfs": "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>",
    "schema": "PREFIX schema: <http://schema.org/>",
    "skos": "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>",
    "wd": "PREFIX wd: <http://www.wikidata.org/entity/>",
    "wdt": "PREFIX wdt: <http://www.wikidata.org/prop/direct/>",
    "wikibase": "PREFIX wikibase: <http://wikiba.se/ontology#>",
    "xsd": "PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>",
}


def _prepare_query_for_endpoint(endpoint_url: str, query: str) -> str:
    """Apply endpoint-specific query compatibility fixes before execution."""
    if _QLEVER_WIKIDATA_ENDPOINT_MARKER not in endpoint_url:
        return query

    declared_prefixes = {
        match.group(1).lower()
        for match in re.finditer(
            r"^\s*PREFIX\s+([A-Za-z][\w-]*):",
            query,
            flags=re.IGNORECASE | re.MULTILINE,
        )
    }
    missing_declarations = [
        declaration
        for prefix, declaration in _WIKIDATA_PREFIX_DECLARATIONS.items()
        if prefix not in declared_prefixes
    ]
    if not missing_declarations:
        return query

    return "\n".join(missing_declarations) + "\n\n" + query.lstrip()


class SPARQLError(Exception):
    """Exception raised when SPARQL query execution fails.
    
    Attributes:
        message (str): The error message.
        endpoint (str): The SPARQL endpoint URL.
        query (str): The SPARQL query that failed.
        
    """
    
    def __init__(self, message: str, endpoint: str, query: str) -> None:
        """Initialize the SPARQLError.
        
        Args:
            message (str): The error message.
            endpoint (str): The SPARQL endpoint URL.
            query (str): The SPARQL query that failed.
            
        """
        super().__init__(message)
        self.endpoint = endpoint
        self.query = query


def _validate_return_format(return_format: str) -> dict[str, Any]:
    """Validate the return format and return the format mapping.
    
    Args:
        return_format (str): The return format to validate.
        
    Returns:
        dict[str, Any]: The format mapping.
        
    Raises:
        ValueError: If an unsupported return format is specified.
        
    """
    format_mapping = {
        "json": JSON,
        "xml": XML,
        "csv": CSV,
        "tsv": TSV,
    }
    
    if return_format.lower() not in format_mapping:
        raise ValueError(
            f"Unsupported return format: {return_format}. "
            f"Supported formats: {list(format_mapping.keys())}",
        )
    
    return format_mapping


def _setup_sparql_wrapper(
    endpoint_url: str,
    query: str,
    return_format: str,
    timeout: int | None,
    user_agent: str | None,
    format_mapping: dict[str, Any],
) -> SPARQLWrapper:
    """Set up and configure the SPARQL wrapper.
    
    Args:
        endpoint_url (str): The URL of the SPARQL endpoint.
        query (str): The SPARQL query string to execute.
        return_format (str): The return format.
        timeout (int | None): Query timeout in seconds.
        user_agent (str | None): Custom user agent string.
        format_mapping (dict[str, Any]): The format mapping.
        
    Returns:
        SPARQLWrapper: The configured SPARQL wrapper.
        
    """
    sparql = SPARQLWrapper(endpoint_url)
    sparql.setQuery(query)
    sparql.setReturnFormat(format_mapping[return_format.lower()])
    
    # Set optional parameters
    if timeout is not None:
        sparql.setTimeout(timeout)
    
    if user_agent is not None:
        sparql.addCustomHttpHeader("User-Agent", user_agent)
    
    return sparql


def _is_json_error(exception: Exception) -> bool:
    """Check if an exception is related to JSON parsing.
    
    Args:
        exception (Exception): The exception to check.
        
    Returns:
        bool: True if the exception is JSON-related, False otherwise.
        
    """
    error_str = str(exception)
    exception_type = type(exception).__name__
    
    json_keywords = [
        "json", "expecting value", "decode", "expecting property name",
        "jsondecodeerror", "expecting", "delimiter",
        "unterminated string", "invalid control character", "extra data",
    ]
    
    return (
        exception_type.lower() in ["jsondecodeerror", "valueerror"] or
        any(keyword in error_str.lower() for keyword in json_keywords)
    )


def _save_debug_info(
    exception: Exception,
    endpoint_url: str,
    query: str,
) -> None:
    """Save debug information for JSON parsing errors.
    
    Args:
        exception (Exception): The exception that occurred.
        endpoint_url (str): The SPARQL endpoint URL.
        query (str): The SPARQL query that failed.
        
    """
    if not _is_json_error(exception):
        error_str = str(exception)
        exception_type = type(exception).__name__
        logger.debug("Non-JSON error (%s: %s), no debug file created", exception_type, error_str[:100])
        return
    
    debug_filename = f"sparql_raw_response_{int(time.time())}.txt"
    
    try:
        with Path(debug_filename).open("w", encoding="utf-8") as f:
            f.write(f"Error: {exception!s}\n")
            f.write(f"Exception Type: {type(exception).__name__}\n")
            f.write(f"Endpoint: {endpoint_url}\n")
            f.write(f"Query: {query}\n")
            f.write(f"Timestamp: {time.time()}\n")
            f.write("Response data not accessible from exception context\n")
        
        logger.warning("SPARQL error details saved to %s for debugging.", debug_filename)
    except OSError:
        logger.exception("Failed to save error details")


def _reconstruct_sparql_result(all_results: list[dict[str, str]]) -> dict[str, Any]:
    """Reconstruct SPARQL result structure from processed results.
    
    Args:
        all_results (list[dict[str, str]]): The processed results.
        
    Returns:
        dict[str, Any]: The reconstructed SPARQL result.
        
    """
    return {
        "head": {"vars": list(all_results[0].keys()) if all_results else []},
        "results": {"bindings": [
            {var: {"value": val} for var, val in row.items()}
            for row in all_results
        ]},
    }


def _try_resilient_fallback(
    endpoint_url: str,
    query: str,
    timeout: int | None,
    user_agent: str | None,
) -> dict[str, Any]:
    """Try resilient fallback processing for corrupted JSON.
    
    Args:
        endpoint_url (str): The SPARQL endpoint URL.
        query (str): The SPARQL query that failed.
        timeout (int | None): Query timeout in seconds.
        user_agent (str | None): Custom user agent string.
        
    Returns:
        dict[str, Any]: The reconstructed result from resilient processing.
        
    Raises:
        SPARQLError: If resilient processing also fails.
        
    """
    from .batching import resilient_batched_sparql_query  # Import here to avoid circular imports
    
    try:
        all_results, skipped_count = resilient_batched_sparql_query(
            endpoint_url=endpoint_url,
            base_query=query,
            batch_size=1000,  # Use a smaller batch size to avoid timeouts
            pause_s=1.0,
            timeout=timeout,
            user_agent=user_agent,
            max_retries=3,
            min_subdivision_size=1,
        )
    except Exception as exc:
        # If resilient processing also fails, raise the original error
        logger.exception("Resilient processing also failed")
        raise SPARQLError(
            "Resilient processing failed after JSON corruption. See logs for details.",
            endpoint_url,
            query,
        ) from exc
    else:
        if skipped_count > 0:
            logger.warning("Resilient processing skipped %d corrupted records", skipped_count)
        
        result = _reconstruct_sparql_result(all_results)
        logger.info("Resilient processing successful, retrieved %d records", len(all_results))
        return result


def _handle_sparql_error(
    exception: Exception,
    elapsed_time: float,
    endpoint_url: str,
    query: str,
    return_format: str,
    timeout: int | None,
    user_agent: str | None,
    disable_resilient_fallback: bool,
) -> dict[str, Any]:
    """Handle SPARQL query errors with appropriate fallback strategies.
    
    Args:
        exception (Exception): The original exception.
        elapsed_time (float): Time elapsed during query execution.
        endpoint_url (str): The SPARQL endpoint URL.
        query (str): The SPARQL query that failed.
        return_format (str): The return format.
        timeout (int | None): Query timeout in seconds.
        user_agent (str | None): Custom user agent string.
        disable_resilient_fallback (bool): Whether to disable resilient fallback.
        
    Returns:
        dict[str, Any]: The result if resilient processing succeeds.
        
    Raises:
        SPARQLError: If the error cannot be handled.
        
    """
    # Import here to avoid circular imports
    from .errors import classify_sparql_error, log_error_info  # Import here to avoid circular imports
    
    # Classify the error and determine handling strategy
    error_info = classify_sparql_error(exception, elapsed_time)
    log_error_info(error_info, "Core query")
    
    # Handle backend timeouts - don't retry or use resilient processing
    if error_info.error_type.value == "backend_timeout":
        raise SPARQLError(
            f"Backend timeout after {elapsed_time:.1f}s - query too complex for server",
            endpoint_url,
            query,
        ) from exception

    # Handle JSON corruption with resilient processing fallback
    if (not disable_resilient_fallback and
        return_format.lower() == "json" and
        error_info.should_use_resilient_processing):
        return _try_resilient_fallback(endpoint_url, query, timeout, user_agent)
    
    if error_info.error_type.value == "json_corruption":
        # Not eligible for resilient processing, raise the classified error
        raise SPARQLError(
            "JSON corruption detected. No resilient fallback attempted.",
            endpoint_url,
            query,
        ) from exception
    
    raise SPARQLError(error_info.message, endpoint_url, query) from exception

# PROXY FUNCTION BY HASSAM NASIR
# def _query_with_proxy(
#     endpoint_url: str,
#     query: str,
#     user_agent: str | None,
#     timeout: int | None,
#     proxy_url: str,
# ) -> dict:
#     """
#     Execute SPARQL query via HTTP directly using proxy.
#     SPARQLWrapper does not support proxies natively — 
#     this bypasses it using requests library.
#     """
#     headers = {
#         "Accept": "application/sparql-results+json",
#         "Content-Type": "application/x-www-form-urlencoded",
#     }
#     if user_agent:
#         headers["User-Agent"] = user_agent

#     proxies = {
#         "http":  proxy_url,
#         "https": proxy_url,
#     }

#     params = {"query": query, "format": "json"}

#     logger.info("Executing SPARQL query via proxy")
#     logger.debug("Proxy: %s", proxy_url[:40] + "...")  # partial log for security

#     response = requests.post(
#         endpoint_url,
#         data=params,
#         headers=headers,
#         proxies=proxies,
#         timeout=timeout or 60,
#     )

#     if response.status_code == 429:
#         from urllib.error import HTTPError
#         raise HTTPError(
#             url=endpoint_url,
#             code=429,
#             msg=response.text[:200],
#             hdrs=response.headers,  # type: ignore
#             fp=None,
#         )

#     if response.status_code != 200:
#         raise SPARQLError(
#             f"HTTP {response.status_code}: {response.text[:200]}",
#             endpoint_url,
#             query,
#         )

#     return response.json()

def query_sparql_endpoint(
    endpoint_url: str,
    query: str,
    return_format: str = "json",
    timeout: int | None = None,
    user_agent: str | None = None,
    _disable_resilient_fallback: bool = False,
) -> dict[str, Any]:
    """Execute a SPARQL query against a given endpoint.
    
    Args:
        endpoint_url (str): The URL of the SPARQL endpoint.
        query (str): The SPARQL query string to execute.
        return_format (str, optional): The return format ('json', 'xml', 'csv', 'tsv').
            Defaults to 'json'.
        timeout (int, optional): Query timeout in seconds. Defaults to None.
        user_agent (str, optional): Custom user agent string. Defaults to None.
        _disable_resilient_fallback (bool, optional): Internal parameter to disable
            resilient fallback processing to avoid recursion. Defaults to False.
        
    Returns:
        dict[str, Any]: The query results in the specified format.
        
    Raises:
        SPARQLError: If the query execution fails.
        ValueError: If an unsupported return format is specified.
        
    """
    # Validate return format
    format_mapping = _validate_return_format(return_format)
    prepared_query = _prepare_query_for_endpoint(endpoint_url, query)
    
    start_time = time.time()
    try:
        # Set up the SPARQL wrapper
        sparql = _setup_sparql_wrapper(
            endpoint_url, prepared_query, return_format, timeout, user_agent, format_mapping,
        )
        
        # Execute the query with timing
        logger.info("Executing SPARQL query against %s", endpoint_url)
        logger.debug("Query: %s", prepared_query)
        logger.debug("User-Agent: %s", user_agent or "Default SPARQL User-Agent")
        
        # Execute query with enhanced error handling and raw response capture
        try:
            result = sparql.query().convert()
        except Exception as e:
            _save_debug_info(e, endpoint_url, prepared_query)
            # Re-raise the original error
            raise
#Hassam Change
        # try:
        #   # Proxy use karo agar set hai — Wikidata throttling bypass
        #      proxy_url = os.getenv("my_http_proxy")
    
        #      if proxy_url:
        # # Direct requests call with proxy — SPARQLWrapper bypass
        #         result = _query_with_proxy(
        #         endpoint_url=endpoint_url,
        #         query=query,
        #         user_agent=user_agent,
        #         timeout=timeout,
        #         proxy_url=proxy_url,
        #                            )
        #      else:
        #        result = sparql.query().convert()
        
        # except Exception as e:
        #        _save_debug_info(e, endpoint_url, query)

        #        raise



        
    except Exception as e:  # noqa: BLE001  # Need broad exception handling for SPARQL errors
        elapsed_time = time.time() - start_time
        return _handle_sparql_error(
            e, elapsed_time, endpoint_url, prepared_query, return_format,
            timeout, user_agent, _disable_resilient_fallback,
        )
    else:
        elapsed_time = time.time() - start_time
        logger.info("SPARQL query executed successfully in %.1f seconds", elapsed_time)
        return result  # type: ignore  # SPARQLWrapper returns dict-like object


def extract_bindings(sparql_results: dict[str, Any]) -> list[dict[str, str]]:
    """Extract variable bindings from SPARQL JSON results.
    
    Args:
        sparql_results (dict[str, Any]): The SPARQL results in JSON format.
        
    Returns:
        list[dict[str, str]]: A list of dictionaries containing variable bindings,
            where each dictionary maps variable names to their string values.
            
    Raises:
        KeyError: If the results don't have the expected structure.
        
    """
    try:
        bindings = sparql_results["results"]["bindings"]
        extracted: list[dict[str, str]] = []
        
        for binding in bindings:
            row: dict[str, str] = {}
            for var, value_obj in binding.items():
                row[var] = value_obj["value"]
            extracted.append(row)
            
    except KeyError as e:
        raise KeyError(
            f"Invalid SPARQL results structure: missing key {e}",
        ) from e
    else:
        return extracted


def count_results(sparql_results: dict[str, Any]) -> int:
    """Count the number of results in SPARQL JSON results.
    
    Args:
        sparql_results (dict[str, Any]): The SPARQL results in JSON format.
        
    Returns:
        int: The number of result bindings.
        
    Raises:
        KeyError: If the results don't have the expected structure.
        
    """
    try:
        return len(sparql_results["results"]["bindings"])
    except KeyError as e:
        raise KeyError(
            f"Invalid SPARQL results structure: missing key {e}",
        ) from e


def count_sparql_query(
    endpoint_url: str,
    query: str,
    timeout: int | None = None,
    user_agent: str | None = None,
) -> int:
    """Count the number of results for a SPARQL query without retrieving them.
    
    This function modifies the input query to return only a count, which is much
    more efficient than retrieving all results when you only need the total number.
    
    Note: Any LIMIT clause in the original query is removed, so the returned count
    represents the total number of matching records, regardless of the original limit.
    
    Args:
        endpoint_url (str): The URL of the SPARQL endpoint.
        query (str): The SPARQL query to count results for.
        timeout (int | None, optional): Query timeout in seconds. Defaults to None.
        user_agent (str | None, optional): Custom user agent string. Defaults to None.
        
    Returns:
        int: The total number of results that would be returned by the query
             (ignoring any LIMIT clause in the original query).
        
    Raises:
        SPARQLError: If the query execution fails.
        ValueError: If the count result cannot be parsed.
        
    """
    from .queries import convert_to_count_query  # Import here to avoid circular imports
    from .retry import query_sparql_endpoint_with_retry  # Import here to avoid circular imports
    
    # Convert SELECT query to COUNT query
    count_query = convert_to_count_query(query)
    
    # Execute the count query
    result = query_sparql_endpoint_with_retry(
        endpoint_url=endpoint_url,
        query=count_query,
        return_format="json",
        timeout=timeout,
        user_agent=user_agent,
    )
    
    # Extract the count from the result
    try:
        bindings = result["results"]["bindings"]
        if not bindings:
            return 0
        
        count_value = bindings[0]["count"]["value"]
        return int(count_value)
        
    except (KeyError, IndexError, ValueError) as e:
        raise ValueError(f"Failed to parse count result: {e}") from e
