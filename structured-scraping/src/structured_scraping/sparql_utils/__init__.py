"""SPARQL utilities package for querying RDF endpoints.

This package provides comprehensive utilities for executing SPARQL queries against
various RDF endpoints, with features including retry logic, batching, rate limiting,
and file I/O operations.

The package is organized into several modules:
- core: Basic SPARQL operations and exception handling
- queries: Query transformation and parsing utilities
- retry: Retry logic and rate limiting for robust queries
- io: File I/O operations for saving results
- batching: Batching and pagination for large datasets
"""

# Batching operations
from .batching import (
    batched_sparql_query,
    batched_sparql_query_to_csv,
    resilient_batched_sparql_query,
    resilient_batched_sparql_query_by_decade,
)

# Constants
from .constants import (
    HTTP_BAD_GATEWAY,
    HTTP_GATEWAY_TIMEOUT,
    HTTP_SERVICE_UNAVAILABLE,
    HTTP_TOO_MANY_REQUESTS,
)

# Core functionality
from .core import (
    SPARQLError,
    count_results,
    count_sparql_query,
    extract_bindings,
    query_sparql_endpoint,
)

# File I/O operations
from .io import (
    query_and_save_to_csv,
    save_results_to_csv,
    save_sparql_results_to_csv,
)

# Query transformation
from .queries import convert_to_count_query, create_count_query_from_main

# Retry and resilience
from .retry import query_sparql_endpoint_with_retry

__all__ = [
    "HTTP_BAD_GATEWAY",
    "HTTP_GATEWAY_TIMEOUT",
    "HTTP_SERVICE_UNAVAILABLE",
    "HTTP_TOO_MANY_REQUESTS",
    "SPARQLError",
    "batched_sparql_query",
    "batched_sparql_query_to_csv",
    "convert_to_count_query",
    "count_results",
    "count_sparql_query",
    "create_count_query_from_main",
    "extract_bindings",
    "query_and_save_to_csv",
    "query_sparql_endpoint",
    "query_sparql_endpoint_with_retry",
    "resilient_batched_sparql_query",
    "resilient_batched_sparql_query_by_decade",
    "save_results_to_csv",
    "save_sparql_results_to_csv",
]
