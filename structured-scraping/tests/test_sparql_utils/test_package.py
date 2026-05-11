"""Tests for the sparql_utils package imports and public API."""

import pytest


class TestPackageImports:
    """Test that all expected functions and classes can be imported from the package."""

    def test_import_core_functionality(self) -> None:
        """Test importing core functionality."""
        from structured_scraping.sparql_utils import (
            SPARQLError,
            count_results,
            count_sparql_query,
            extract_bindings,
            query_sparql_endpoint,
        )
        
        # Basic smoke test - just ensure they're callable
        assert callable(count_results)
        assert callable(count_sparql_query)
        assert callable(extract_bindings)
        assert callable(query_sparql_endpoint)
        assert issubclass(SPARQLError, Exception)

    def test_import_query_transformation(self) -> None:
        """Test importing query transformation functions."""
        from structured_scraping.sparql_utils import (
            convert_to_count_query,
            create_count_query_from_main,
        )
        
        assert callable(convert_to_count_query)
        assert callable(create_count_query_from_main)

    def test_import_retry_functionality(self) -> None:
        """Test importing retry functionality."""
        from structured_scraping.sparql_utils import query_sparql_endpoint_with_retry
        
        assert callable(query_sparql_endpoint_with_retry)

    def test_import_io_functionality(self) -> None:
        """Test importing I/O functionality."""
        from structured_scraping.sparql_utils import (
            query_and_save_to_csv,
            save_results_to_csv,
            save_sparql_results_to_csv,
        )
        
        assert callable(query_and_save_to_csv)
        assert callable(save_results_to_csv)
        assert callable(save_sparql_results_to_csv)

    def test_import_batching_functionality(self) -> None:
        """Test importing batching functionality."""
        from structured_scraping.sparql_utils import (
            batched_sparql_query,
            batched_sparql_query_to_csv,
            resilient_batched_sparql_query,
        )
        
        assert callable(batched_sparql_query)
        assert callable(batched_sparql_query_to_csv)
        assert callable(resilient_batched_sparql_query)

    def test_import_http_constants(self) -> None:
        """Test importing HTTP status constants."""
        from structured_scraping.sparql_utils import (
            HTTP_BAD_GATEWAY,
            HTTP_GATEWAY_TIMEOUT,
            HTTP_SERVICE_UNAVAILABLE,
            HTTP_TOO_MANY_REQUESTS,
        )
        
        assert HTTP_TOO_MANY_REQUESTS == 429
        assert HTTP_BAD_GATEWAY == 502
        assert HTTP_SERVICE_UNAVAILABLE == 503
        assert HTTP_GATEWAY_TIMEOUT == 504

    def test_all_exports_available(self) -> None:
        """Test that all items in __all__ are available."""
        import structured_scraping.sparql_utils as sparql_utils
        
        # Get all items from __all__
        all_items = sparql_utils.__all__
        
        # Check that each item is actually available
        for item in all_items:
            assert hasattr(sparql_utils, item), f"Item '{item}' not found in module"
            assert getattr(sparql_utils, item) is not None

    def test_backwards_compatibility(self) -> None:
        """Test that the refactored package maintains backwards compatibility."""
        # This would be the same import that worked with the old single module
        from structured_scraping.sparql_utils import (
            SPARQLError,
            batched_sparql_query,
            count_sparql_query,
            query_sparql_endpoint,
            save_results_to_csv,
        )
        
        # Ensure these are still the same objects/functions
        assert callable(query_sparql_endpoint)
        assert callable(count_sparql_query)
        assert callable(batched_sparql_query)
        assert callable(save_results_to_csv)
        assert issubclass(SPARQLError, Exception)


class TestPackageStructure:
    """Test the internal package structure."""

    def test_submodules_exist(self) -> None:
        """Test that all expected submodules exist."""
        import structured_scraping.sparql_utils.core
        import structured_scraping.sparql_utils.queries
        import structured_scraping.sparql_utils.retry
        import structured_scraping.sparql_utils.io
        import structured_scraping.sparql_utils.batching
        
        # Basic smoke test
        assert hasattr(structured_scraping.sparql_utils.core, "query_sparql_endpoint")
        assert hasattr(structured_scraping.sparql_utils.queries, "convert_to_count_query")
        assert hasattr(structured_scraping.sparql_utils.retry, "query_sparql_endpoint_with_retry")
        assert hasattr(structured_scraping.sparql_utils.io, "save_results_to_csv")
        assert hasattr(structured_scraping.sparql_utils.batching, "batched_sparql_query")
