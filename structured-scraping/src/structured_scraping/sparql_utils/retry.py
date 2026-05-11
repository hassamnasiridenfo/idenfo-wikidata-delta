"""Retry logic and rate limiting for SPARQL queries.

This module provides robust retry mechanisms for SPARQL queries, including
intelligent handling of rate limiting, temporary server errors, and
exponential backoff strategies.
"""

import json
import logging
import random
import time
from typing import Any
from urllib.error import HTTPError

from .constants import (
    HTTP_BAD_GATEWAY,
    HTTP_GATEWAY_TIMEOUT,
    HTTP_SERVICE_UNAVAILABLE,
    HTTP_TOO_MANY_REQUESTS,
)
from .core import (
    SPARQLError,
    query_sparql_endpoint,
)

logger = logging.getLogger(__name__)


def _parse_retry_after(retry_after_value: str) -> float:
    """Parse the Retry-After header value and return seconds to wait.
    
    The Retry-After header can contain either:
    - A number of seconds (e.g., "120")
    - An HTTP date (e.g., "Wed, 21 Oct 2015 07:28:00 GMT")
    
    Args:
        retry_after_value (str): The Retry-After header value.
        
    Returns:
        float: Number of seconds to wait.
        
    """
    try:
        # Try parsing as seconds (most common)
        return float(retry_after_value)
    except ValueError:
        # If it's not a number, it's likely an HTTP date format
        # For simplicity, use a reasonable default for date-based headers
        logger.warning("Retry-After header contains date format, using default delay of 30s")
        return 30.0


def _get_error_message(error: BaseException | None) -> str:
    """Generate an appropriate error message based on the error type.
    
    Args:
        error (BaseException | None): The original error.
        
    Returns:
        str: A descriptive error message.
        
    """
    if isinstance(error, HTTPError):
        error_messages = {
            HTTP_TOO_MANY_REQUESTS: "Rate limited (429)",
            HTTP_GATEWAY_TIMEOUT: "Gateway timeout (504)",
            HTTP_SERVICE_UNAVAILABLE: "Service unavailable (503)",
            HTTP_BAD_GATEWAY: "Bad gateway (502)",
        }
        return error_messages.get(error.code, f"Server error ({error.code})")
    if isinstance(error, TimeoutError):
        return "Network timeout (server overwhelmed)"
    if isinstance(error, json.JSONDecodeError):
        return "JSON decode error (server data corruption)"
    return "Server error"


def query_sparql_endpoint_with_retry(
    endpoint_url: str,
    query: str,
    return_format: str = "json",
    timeout: int | None = None,
    user_agent: str | None = None,
    max_retries: int = 3,
    base_delay: float = 2.0,
) -> dict[str, Any]:
    """Execute a SPARQL query with retry logic for rate limiting.

    This function wraps query_sparql_endpoint() with intelligent retry logic
    that respects HTTP 429 "Too Many Requests" responses, including proper
    handling of the Retry-After header when present.

    Args:
        endpoint_url (str): The URL of the SPARQL endpoint.
        query (str): The SPARQL query string to execute.
        return_format (str, optional): The return format ('json', 'xml', 'csv', 'tsv').
            Defaults to 'json'.
        timeout (int, optional): Query timeout in seconds. Defaults to None.
        user_agent (str, optional): Custom user agent string. Defaults to None.
        max_retries (int, optional): Maximum number of retries for rate limiting.
            Defaults to 3.
        base_delay (float, optional): Base delay for exponential backoff in seconds.
            Defaults to 2.0.

    Returns:
        dict[str, Any]: The query results in the specified format.

    Raises:
        SPARQLError: If the query execution fails after all retries.

    """
    for attempt in range(max_retries + 1):
        try:
            return query_sparql_endpoint(
                endpoint_url=endpoint_url,
                query=query,
                return_format=return_format,
                timeout=timeout,
                user_agent=user_agent,
                _disable_resilient_fallback=True,  # Prevent recursion in resilient batched processing
            )
            
        except SPARQLError as e:
            # Import here to avoid circular imports
            from .errors import classify_sparql_error
            
            # Classify the error using our unified system
            error_info = classify_sparql_error(e, attempt * base_delay)
            
            # Check if this is a retryable error
            if not error_info.is_retryable or attempt >= max_retries:
                if not error_info.is_retryable:
                    logger.warning("Non-retryable error, not retrying: %s", e)
                else:
                    logger.exception("Max retries (%d) exceeded for retryable error", max_retries)
                raise
            
            # Handle rate limiting with Retry-After header awareness
            retry_delay = base_delay * (2 ** attempt)  # Default exponential backoff
            
            # Try to extract Retry-After header from the original HTTPError
            original_error = e.__cause__
            retry_after_used = False
            
            if isinstance(original_error, HTTPError) and hasattr(original_error, "headers") and original_error.headers:
                retry_after = original_error.headers.get("Retry-After")
                if retry_after:
                    retry_delay = _parse_retry_after(retry_after)
                    retry_after_used = True
            
            # Generate appropriate error message
            error_message = _get_error_message(original_error)
            
            if retry_after_used:
                logger.warning(
                    "%s. Retry-After header indicates %.1f seconds. "
                    "Waiting before retry attempt %d/%d",
                    error_message,
                    retry_delay,
                    attempt + 1,
                    max_retries + 1,
                )
            else:
                # No Retry-After header, use exponential backoff with jitter
                jitter = random.uniform(0.1, 0.3) * retry_delay  # Add 10-30% jitter  # noqa: S311
                retry_delay = retry_delay + jitter
                
                logger.warning(
                    "%s. No Retry-After header. "
                    "Using exponential backoff: %.1f seconds. "
                    "Retry attempt %d/%d",
                    error_message,
                    retry_delay,
                    attempt + 1,
                    max_retries + 1,
                )
            
            time.sleep(retry_delay)
    
    # This should never be reached
    raise SPARQLError("Unknown error in retry logic", endpoint_url, query)
