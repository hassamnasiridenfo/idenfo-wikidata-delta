"""Unified error classification and handling for SPARQL operations.

This module provides a centralized approach to classifying and handling different
types of SPARQL errors, making error handling consistent across all components.
"""

import json
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Classification of SPARQL error types."""
    
    BACKEND_TIMEOUT = "backend_timeout"
    JSON_CORRUPTION = "json_corruption"
    RATE_LIMITING = "rate_limiting"
    NETWORK_ERROR = "network_error"
    OTHER = "other"


class SPARQLErrorInfo:
    """Information about a classified SPARQL error.
    
    Attributes:
        error_type (ErrorType): The classified type of error.
        original_error (Exception): The original exception that occurred.
        elapsed_time (float): Time elapsed before the error occurred.
        is_retryable (bool): Whether this error should be retried.
        should_use_resilient_processing (bool): Whether to fall back to resilient processing.
        message (str): Human-readable error message.
        
    """
    
    def __init__(
        self,
        error_type: ErrorType,
        original_error: Exception,
        elapsed_time: float,
        is_retryable: bool = False,
        should_use_resilient_processing: bool = False,
        message: str = "",
    ) -> None:
        """Initialize the SPARQLErrorInfo.
        
        Args:
            error_type (ErrorType): The classified type of error.
            original_error (Exception): The original exception that occurred.
            elapsed_time (float): Time elapsed before the error occurred.
            is_retryable (bool, optional): Whether this error should be retried.
            should_use_resilient_processing (bool, optional): Whether to use resilient processing.
            message (str, optional): Human-readable error message.
            
        """
        self.error_type = error_type
        self.original_error = original_error
        self.elapsed_time = elapsed_time
        self.is_retryable = is_retryable
        self.should_use_resilient_processing = should_use_resilient_processing
        self.message = message or str(original_error)


def classify_sparql_error(error: Exception, elapsed_time: float) -> SPARQLErrorInfo:
    """Classify a SPARQL error and determine appropriate handling strategy.
    
    Args:
        error (Exception): The exception that occurred during SPARQL execution.
        elapsed_time (float): Time elapsed before the error occurred.
        
    Returns:
        SPARQLErrorInfo: Classified error information with handling recommendations.
        
    """
    error_str = str(error).lower()
    cause = getattr(error, "__cause__", None)
    
    # Backend timeout detection
    if (
        isinstance(cause, TimeoutError)
        or "timed out" in error_str
        or "backend timeout" in error_str
    ):
        return SPARQLErrorInfo(
            error_type=ErrorType.BACKEND_TIMEOUT,
            original_error=error,
            elapsed_time=elapsed_time,
            is_retryable=False,  # Backend timeouts indicate query too complex
            should_use_resilient_processing=False,
            message=f"Backend timeout after {elapsed_time:.1f}s - query too complex for server",
        )

    # JSON corruption detection, but check for backend timeout masquerading as JSON error
    if (
        isinstance(cause, json.JSONDecodeError)
        or "jsondecode" in error_str
        or "invalid control character" in error_str
        or "expecting property name" in error_str
        or "unterminated string" in error_str
        or "expecting ',' delimiter" in error_str
        or "expecting ':' delimiter" in error_str
        or "expecting value" in error_str
        or "extra data" in error_str
    ):
        # If the error string or the original exception contains 'timeout', treat as BACKEND_TIMEOUT
        # This covers cases where backend returns 'timeout' instead of JSON
        if "timeout" in error_str:
            return SPARQLErrorInfo(
                error_type=ErrorType.BACKEND_TIMEOUT,
                original_error=error,
                elapsed_time=elapsed_time,
                is_retryable=False,
                should_use_resilient_processing=False,
                message=(
                    f"Backend timeout after {elapsed_time:.1f}s - query too complex for server "
                    f"(received non-JSON 'timeout' response)"
                ),
            )
        return SPARQLErrorInfo(
            error_type=ErrorType.JSON_CORRUPTION,
            original_error=error,
            elapsed_time=elapsed_time,
            is_retryable=False,  # JSON corruption needs different handling
            should_use_resilient_processing=True,
            message="JSON corruption detected - falling back to resilient processing",
        )
    
    # Rate limiting detection
    if (("429" in error_str) or
        ("too many requests" in error_str) or
        ("rate limit" in error_str) or
        ("503" in error_str) or  # Service unavailable
        ("502" in error_str) or  # Bad gateway
        ("504" in error_str)):   # Gateway timeout
        return SPARQLErrorInfo(
            error_type=ErrorType.RATE_LIMITING,
            original_error=error,
            elapsed_time=elapsed_time,
            is_retryable=True,
            should_use_resilient_processing=False,
            message="Server overload or rate limiting - will retry with backoff",
        )
    
    # Generic network errors
    if any(keyword in error_str for keyword in [
        "connection", "network", "dns", "resolve", "unreachable",
    ]):
        return SPARQLErrorInfo(
            error_type=ErrorType.NETWORK_ERROR,
            original_error=error,
            elapsed_time=elapsed_time,
            is_retryable=True,
            should_use_resilient_processing=False,
            message="Network connectivity issue - will retry",
        )
    
    # Unknown error type
    return SPARQLErrorInfo(
        error_type=ErrorType.OTHER,
        original_error=error,
        elapsed_time=elapsed_time,
        is_retryable=False,
        should_use_resilient_processing=False,
        message=f"Unknown error type: {error}",
    )


def log_error_info(error_info: SPARQLErrorInfo, context: str = "") -> None:
    """Log error information with appropriate log level and context.
    
    Args:
        error_info (SPARQLErrorInfo): The classified error information.
        context (str, optional): Additional context for the log message.
        
    """
    context_prefix = f"{context}: " if context else ""

    # Always log the error type and original error message at debug level for traceability
    logger.debug(
        "%s[ErrorType: %s] Original error message: %s",
        context_prefix,
        error_info.error_type.value,
        str(error_info.original_error),
    )

    # Log error details based on classification
    if error_info.error_type == ErrorType.BACKEND_TIMEOUT:
        logger.error(
            "%s[ErrorType: %s] Backend timeout detected after %.1f seconds. "
            "Query complexity exceeds server processing capacity.",
            context_prefix,
            error_info.error_type.value,
            error_info.elapsed_time,
        )
        logger.info("Consider breaking down the query into smaller, more specific queries.")
        original_error_str = str(error_info.original_error).lower()
        if (
            "json" in original_error_str
            or "invalid control character" in original_error_str
        ):
            logger.warning(
                "%s[ErrorType: %s] JSON corruption was likely a symptom of backend timeout (not a true JSON error)",
                context_prefix,
                error_info.error_type.value,
            )

    elif error_info.error_type == ErrorType.JSON_CORRUPTION:
        logger.warning(
            "%s[ErrorType: %s] JSON parsing error detected, falling back to resilient processing: %s",
            context_prefix,
            error_info.error_type.value,
            error_info.message,
        )

    elif error_info.error_type == ErrorType.RATE_LIMITING:
        logger.warning(
            "%s[ErrorType: %s] Server overload detected after %.1f seconds: %s",
            context_prefix,
            error_info.error_type.value,
            error_info.elapsed_time,
            error_info.message,
        )

    elif error_info.error_type == ErrorType.NETWORK_ERROR:
        logger.warning(
            "%s[ErrorType: %s] Network issue after %.1f seconds: %s",
            context_prefix,
            error_info.error_type.value,
            error_info.elapsed_time,
            error_info.message,
        )

    else:
        logger.error(
            "%s[ErrorType: %s] Unknown error after %.1f seconds: %s",
            context_prefix,
            error_info.error_type.value,
            error_info.elapsed_time,
            error_info.message,
        )

    # Summary log for clarity
    logger.info(
        "%s[ErrorType: %s] Final error classification: %s",
        context_prefix,
        error_info.error_type.value,
        error_info.message,
    )


def should_stop_processing(error_info: SPARQLErrorInfo) -> bool:
    """Determine if processing should be stopped based on error type.
    
    Args:
        error_info (SPARQLErrorInfo): The classified error information.
        
    Returns:
        bool: True if processing should be stopped, False otherwise.
        
    """
    return error_info.error_type == ErrorType.BACKEND_TIMEOUT
