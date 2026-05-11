"""Tests for the sparql_utils.batching module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from structured_scraping.sparql_utils.batching import (
    _process_batch_with_subdivision,
    batched_sparql_query,
    batched_sparql_query_to_csv,
    resilient_batched_sparql_query,
)


class TestBatchedSparqlQuery:
    """Test the batched_sparql_query function."""

    @patch("structured_scraping.sparql_utils.batching.query_sparql_endpoint_with_retry")
    @patch("structured_scraping.sparql_utils.batching.extract_bindings")
    @patch("structured_scraping.sparql_utils.batching.time.sleep")
    def test_successful_batching(
        self, mock_sleep: Mock, mock_extract: Mock, mock_query: Mock
    ) -> None:
        """Test successful batched query execution."""
        # First batch has results, second batch is empty (stops pagination)
        mock_query.side_effect = [
            {"results": {"bindings": [{"test": {"value": "1"}}]}},  # First batch
            {"results": {"bindings": []}},  # Second batch (empty)
        ]
        mock_extract.side_effect = [
            [{"test": "1"}],  # First batch extracted
            [],  # Second batch extracted (empty)
        ]
        
        result = batched_sparql_query(
            endpoint_url="http://example.com/sparql",
            base_query="SELECT ?test WHERE { ?s ?p ?test }",
            batch_size=1000,
            pause_s=0.5,
        )
        
        assert result == [{"test": "1"}]
        assert mock_query.call_count == 2
        assert mock_extract.call_count == 2
        mock_sleep.assert_called_once_with(0.5)

    @patch("structured_scraping.sparql_utils.batching.query_sparql_endpoint_with_retry")
    @patch("structured_scraping.sparql_utils.batching.extract_bindings")
    def test_multiple_batches(self, mock_extract: Mock, mock_query: Mock) -> None:
        """Test query with multiple batches."""
        # Three batches: two with data, one empty
        mock_query.side_effect = [
            {"results": {"bindings": []}},  # Simulated results
            {"results": {"bindings": []}},
            {"results": {"bindings": []}},
        ]
        mock_extract.side_effect = [
            [{"test": "1"}],  # First batch
            [{"test": "2"}],  # Second batch
            [],  # Third batch (empty)
        ]
        
        result = batched_sparql_query(
            endpoint_url="http://example.com/sparql",
            base_query="SELECT ?test WHERE { ?s ?p ?test }",
            batch_size=1,
            pause_s=0,  # No pause for faster test
        )
        
        assert result == [{"test": "1"}, {"test": "2"}]
        assert mock_query.call_count == 3

    @patch("structured_scraping.sparql_utils.batching.query_sparql_endpoint_with_retry")
    def test_query_construction(self, mock_query: Mock) -> None:
        """Test that queries are constructed correctly with ORDER BY, LIMIT and OFFSET."""
        mock_query.side_effect = Exception("Stop execution")  # Stop after first call
        
        try:
            batched_sparql_query(
                endpoint_url="http://example.com/sparql",
                base_query="SELECT ?s WHERE { ?s ?p ?o }",
                batch_size=5000,
            )
        except Exception:
            pass  # Expected
        
        # Check the constructed query includes ORDER BY for consistent batching
        mock_query.assert_called_once()
        call_args = mock_query.call_args
        query = call_args[1]["query"]
        assert "SELECT ?s WHERE { ?s ?p ?o } ORDER BY ?s LIMIT 5000 OFFSET 0" == query

    @patch("structured_scraping.sparql_utils.batching.query_sparql_endpoint_with_retry")
    def test_error_handling(self, mock_query: Mock) -> None:
        """Test that errors are properly propagated."""
        mock_query.side_effect = Exception("Test error")
        
        with pytest.raises(Exception, match="Test error"):
            batched_sparql_query(
                endpoint_url="http://example.com/sparql",
                base_query="SELECT ?s WHERE { ?s ?p ?o }",
            )


class TestBatchedSparqlQueryToCSV:
    """Test the batched_sparql_query_to_csv function."""

    @patch("structured_scraping.sparql_utils.batching.save_results_to_csv")
    @patch("structured_scraping.sparql_utils.batching.batched_sparql_query")
    def test_query_and_save_to_csv(self, mock_batch_query: Mock, mock_save: Mock) -> None:
        """Test querying and saving results to CSV."""
        mock_results = [{"test": "value1"}, {"test": "value2"}]
        mock_batch_query.return_value = mock_results
        
        result = batched_sparql_query_to_csv(
            endpoint_url="http://example.com/sparql",
            base_query="SELECT ?test WHERE { ?s ?p ?test }",
            file_path="test.csv",
            batch_size=1000,
            fieldnames=["test"],
            encoding="utf-8",
        )
        
        assert result == 2  # Number of results
        
        mock_batch_query.assert_called_once_with(
            endpoint_url="http://example.com/sparql",
            base_query="SELECT ?test WHERE { ?s ?p ?test }",
            batch_size=1000,
            pause_s=1.0,
            timeout=None,
            user_agent=None,
            max_retries=3,
            base_delay=2.0,
        )
        
        mock_save.assert_called_once_with(
            mock_results, "test.csv", ["test"], "utf-8"
        )


class TestResilientBatchedSparqlQuery:
    """Test the resilient_batched_sparql_query function."""

    @patch("structured_scraping.sparql_utils.batching._process_batch_with_subdivision")
    @patch("structured_scraping.sparql_utils.batching.time.sleep")
    def test_successful_resilient_query(self, mock_sleep: Mock, mock_process: Mock) -> None:
        """Test successful resilient batched query."""
        # Two batches: one with results, one empty
        mock_process.side_effect = [
            ([{"test": "1"}, {"test": "2"}], 0),  # First batch: 2 results, 0 skipped
            ([], 0),  # Second batch: empty (stops pagination)
        ]
        
        results, skipped = resilient_batched_sparql_query(
            endpoint_url="http://example.com/sparql",
            base_query="SELECT ?test WHERE { ?s ?p ?test }",
            batch_size=1000,
            pause_s=0.1,
        )
        
        assert results == [{"test": "1"}, {"test": "2"}]
        assert skipped == 0
        assert mock_process.call_count == 2

    @patch("structured_scraping.sparql_utils.batching._process_batch_with_subdivision")
    def test_resilient_query_with_skipped_records(self, mock_process: Mock) -> None:
        """Test resilient query with some skipped records."""
        mock_process.side_effect = [
            ([{"test": "1"}], 2),  # First batch: 1 result, 2 skipped
            ([{"test": "2"}], 1),  # Second batch: 1 result, 1 skipped
            ([], 0),  # Third batch: empty (stops pagination)
        ]
        
        results, skipped = resilient_batched_sparql_query(
            endpoint_url="http://example.com/sparql",
            base_query="SELECT ?test WHERE { ?s ?p ?test }",
            batch_size=100,
            pause_s=0,
        )
        
        assert results == [{"test": "1"}, {"test": "2"}]
        assert skipped == 3  # Total skipped across all batches


class TestProcessBatchWithSubdivision:
    """Test the _process_batch_with_subdivision function."""

    @patch("structured_scraping.sparql_utils.batching.query_sparql_endpoint_with_retry")
    @patch("structured_scraping.sparql_utils.batching.extract_bindings")
    def test_successful_batch_processing(self, mock_extract: Mock, mock_query: Mock) -> None:
        """Test successful batch processing without subdivision."""
        mock_query.return_value = {"results": {"bindings": []}}
        mock_extract.return_value = [{"test": "value"}]
        
        results, skipped = _process_batch_with_subdivision(
            endpoint_url="http://example.com/sparql",
            base_query="SELECT ?test WHERE { ?s ?p ?test }",
            offset=0,
            batch_size=1000,
            timeout=None,
            user_agent=None,
            max_retries=3,
            base_delay=2.0,
            min_subdivision_size=1,
        )
        
        assert results == [{"test": "value"}]
        assert skipped == 0

    @patch("structured_scraping.sparql_utils.batching.query_sparql_endpoint_with_retry")
    def test_json_decode_error_subdivision(self, mock_query: Mock) -> None:
        """Test subdivision when JSON decode error occurs."""
        # First call fails with JSON error, subdivision calls succeed
        json_error = json.JSONDecodeError("Invalid JSON", "doc", 0)
        
        def side_effect(*args, **kwargs):
            query = kwargs.get("query", "")
            if "LIMIT 1000" in query:  # Original large batch
                raise json_error
            elif "LIMIT 500" in query:  # Subdivided batches
                return {"results": {"bindings": []}}
            else:
                return {"results": {"bindings": []}}
        
        mock_query.side_effect = side_effect
        
        with patch("structured_scraping.sparql_utils.batching.extract_bindings") as mock_extract:
            mock_extract.return_value = [{"test": "value"}]
            
            results, skipped = _process_batch_with_subdivision(
                endpoint_url="http://example.com/sparql",
                base_query="SELECT ?test WHERE { ?s ?p ?test }",
                offset=0,
                batch_size=1000,
                timeout=None,
                user_agent=None,
                max_retries=3,
                base_delay=2.0,
                min_subdivision_size=1,
            )
            
            # Should have subdivided and processed both halves
            assert len(results) == 2  # Two subdivisions, each returning one result
            assert skipped == 0

    @patch("structured_scraping.sparql_utils.batching.query_sparql_endpoint_with_retry")
    def test_min_subdivision_size_reached(self, mock_query: Mock) -> None:
        """Test that records are skipped when min subdivision size is reached."""
        json_error = json.JSONDecodeError("Invalid JSON", "doc", 0)
        mock_query.side_effect = json_error
        
        results, skipped = _process_batch_with_subdivision(
            endpoint_url="http://example.com/sparql",
            base_query="SELECT ?test WHERE { ?s ?p ?test }",
            offset=0,
            batch_size=1,  # Already at minimum size
            timeout=None,
            user_agent=None,
            max_retries=3,
            base_delay=2.0,
            min_subdivision_size=1,
        )
        
        assert results == []
        assert skipped == 1

    @patch("structured_scraping.sparql_utils.batching.query_sparql_endpoint_with_retry")
    def test_non_json_error_propagated(self, mock_query: Mock) -> None:
        """Test that non-JSON errors are propagated up."""
        network_error = Exception("Network error")
        mock_query.side_effect = network_error
        
        with pytest.raises(Exception, match="Network error"):
            _process_batch_with_subdivision(
                endpoint_url="http://example.com/sparql",
                base_query="SELECT ?test WHERE { ?s ?p ?test }",
                offset=0,
                batch_size=1000,
                timeout=None,
                user_agent=None,
                max_retries=3,
                base_delay=2.0,
                min_subdivision_size=1,
            )


class TestEnsureOrderedQuery:
    """Test the _ensure_ordered_query helper function."""

    def test_query_already_has_order_by(self) -> None:
        """Test that queries with existing ORDER BY are not modified."""
        query = "SELECT ?person ?personLabel WHERE { ?person wdt:P31 wd:Q5 } ORDER BY ?person"
        
        from structured_scraping.sparql_utils.batching import _ensure_ordered_query
        result = _ensure_ordered_query(query)
        
        assert result == query

    def test_simple_query_gets_order_by(self) -> None:
        """Test that simple queries get ORDER BY added."""
        query = "SELECT ?person ?personLabel WHERE { ?person wdt:P31 wd:Q5 }"
        
        from structured_scraping.sparql_utils.batching import _ensure_ordered_query
        result = _ensure_ordered_query(query)
        
        expected = "SELECT ?person ?personLabel WHERE { ?person wdt:P31 wd:Q5 } ORDER BY ?person"
        assert result == expected

    def test_prefers_uri_variables_over_labels(self) -> None:
        """Test that URI variables are preferred over label variables for ordering."""
        query = "SELECT ?personLabel ?person WHERE { ?person wdt:P31 wd:Q5 }"
        
        from structured_scraping.sparql_utils.batching import _ensure_ordered_query
        result = _ensure_ordered_query(query)
        
        # Should prefer ?person over ?personLabel
        expected = "SELECT ?personLabel ?person WHERE { ?person wdt:P31 wd:Q5 } ORDER BY ?person"
        assert result == expected

    def test_query_with_existing_limit(self) -> None:
        """Test that ORDER BY is inserted before existing LIMIT."""
        query = "SELECT ?person WHERE { ?person wdt:P31 wd:Q5 } LIMIT 100"
        
        from structured_scraping.sparql_utils.batching import _ensure_ordered_query
        result = _ensure_ordered_query(query)
        
        expected = "SELECT ?person WHERE { ?person wdt:P31 wd:Q5 } ORDER BY ?person LIMIT 100"
        assert result == expected

    def test_select_star_query(self) -> None:
        """Test that SELECT * queries get ordering based on first triple pattern."""
        query = "SELECT * WHERE { ?subject ?predicate ?object }"
        
        from structured_scraping.sparql_utils.batching import _ensure_ordered_query
        result = _ensure_ordered_query(query)
        
        expected = "SELECT * WHERE { ?subject ?predicate ?object } ORDER BY ?subject"
        assert result == expected

    def test_complex_query_with_expressions(self) -> None:
        """Test queries with complex SELECT expressions."""
        query = "SELECT (COUNT(*) AS ?count) ?person WHERE { ?person wdt:P31 wd:Q5 }"
        
        from structured_scraping.sparql_utils.batching import _ensure_ordered_query
        result = _ensure_ordered_query(query)
        
        # Should prefer ?person over ?count (which is derived)
        expected = "SELECT (COUNT(*) AS ?count) ?person WHERE { ?person wdt:P31 wd:Q5 } ORDER BY ?person"
        assert result == expected

    def test_invalid_query_raises_error(self) -> None:
        """Test that invalid queries raise appropriate errors."""
        query = "INVALID SPARQL QUERY"
        
        from structured_scraping.sparql_utils.batching import _ensure_ordered_query
        
        with pytest.raises(ValueError, match="Could not find SELECT...WHERE pattern"):
            _ensure_ordered_query(query)
