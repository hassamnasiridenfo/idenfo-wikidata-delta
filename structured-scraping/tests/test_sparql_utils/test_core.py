"""Tests for the core SPARQL utilities."""
import json
from typing import Any, Dict
from unittest.mock import Mock, patch, mock_open

import pytest
from SPARQLWrapper import JSON, XML, CSV, TSV

from structured_scraping.sparql_utils.core import (
    count_results,
    count_sparql_query,
    extract_bindings,
    query_sparql_endpoint,
    SPARQLError,
    _validate_return_format,
    _setup_sparql_wrapper,
    _is_json_error,
    _save_debug_info,
    _reconstruct_sparql_result,
    _try_resilient_fallback,
    _handle_sparql_error,
)


class TestSPARQLError:
    """Test the SPARQLError exception class."""

    def test_init(self) -> None:
        """Test SPARQLError initialization."""
        message = "Test error"
        endpoint = "http://example.com/sparql"
        query = "SELECT * WHERE { ?s ?p ?o }"
        
        error = SPARQLError(message, endpoint, query)
        
        assert str(error) == message
        assert error.endpoint == endpoint
        assert error.query == query

    def test_inheritance(self) -> None:
        """Test that SPARQLError inherits from Exception."""
        error = SPARQLError("Test", "http://example.com", "SELECT")
        assert isinstance(error, Exception)


class TestQuerySparqlEndpoint:
    """Test the query_sparql_endpoint function."""

    @patch("structured_scraping.sparql_utils.core.SPARQLWrapper")
    def test_successful_query(self, mock_sparql_wrapper: Mock) -> None:
        """Test successful SPARQL query execution."""
        # Setup mock
        mock_instance = Mock()
        mock_sparql_wrapper.return_value = mock_instance
        mock_result = {"results": {"bindings": [{"test": {"value": "value"}}]}}
        mock_instance.query.return_value.convert.return_value = mock_result
        
        # Execute query
        result = query_sparql_endpoint(
            endpoint_url="http://example.com/sparql",
            query="SELECT * WHERE { ?s ?p ?o }",
            return_format="json",
        )
        
        # Verify results
        assert result == mock_result
        mock_sparql_wrapper.assert_called_once_with("http://example.com/sparql")
        mock_instance.setQuery.assert_called_once_with("SELECT * WHERE { ?s ?p ?o }")

    @patch("structured_scraping.sparql_utils.core.SPARQLWrapper")
    def test_with_timeout_and_user_agent(self, mock_sparql_wrapper: Mock) -> None:
        """Test query with timeout and user agent."""
        mock_instance = Mock()
        mock_sparql_wrapper.return_value = mock_instance
        mock_instance.query.return_value.convert.return_value = {}
        
        query_sparql_endpoint(
            endpoint_url="http://example.com/sparql",
            query="SELECT * WHERE { ?s ?p ?o }",
            timeout=30,
            user_agent="TestAgent/1.0",
        )
        
        mock_instance.setTimeout.assert_called_once_with(30)
        mock_instance.addCustomHttpHeader.assert_called_once_with("User-Agent", "TestAgent/1.0")

    def test_invalid_return_format(self) -> None:
        """Test that invalid return format raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported return format"):
            query_sparql_endpoint(
                endpoint_url="http://example.com/sparql",
                query="SELECT * WHERE { ?s ?p ?o }",
                return_format="invalid",
            )

    @patch("structured_scraping.sparql_utils.core.SPARQLWrapper")
    def test_query_execution_failure(self, mock_sparql_wrapper: Mock) -> None:
        """Test that query execution failure raises SPARQLError with classified error message."""
        mock_instance = Mock()
        mock_sparql_wrapper.return_value = mock_instance
        mock_instance.query.side_effect = Exception("Network error")
        
        with pytest.raises(SPARQLError, match="Network connectivity issue"):
            query_sparql_endpoint(
                endpoint_url="http://example.com/sparql",
                query="SELECT * WHERE { ?s ?p ?o }",
            )

    @patch("structured_scraping.sparql_utils.core.SPARQLWrapper")
    def test_timeout_error_classification(self, mock_sparql_wrapper: Mock) -> None:
        """Test that timeout errors are properly classified as backend timeouts."""
        mock_instance = Mock()
        mock_sparql_wrapper.return_value = mock_instance
        timeout_error = TimeoutError("The read operation timed out")
        mock_instance.query.side_effect = Exception("Network timeout") 
        mock_instance.query.side_effect.__cause__ = timeout_error
        
        with pytest.raises(SPARQLError, match="Backend timeout after .* - query too complex"):
            query_sparql_endpoint(
                endpoint_url="http://example.com/sparql",
                query="SELECT * WHERE { ?s ?p ?o }",
            )

    @patch("structured_scraping.sparql_utils.core.SPARQLWrapper")
    @patch("structured_scraping.sparql_utils.batching.resilient_batched_sparql_query")
    def test_json_corruption_fallback(self, mock_resilient: Mock, mock_sparql_wrapper: Mock) -> None:
        """Test that JSON corruption triggers resilient processing fallback."""
        # Setup main query to fail with JSON corruption
        mock_instance = Mock()
        mock_sparql_wrapper.return_value = mock_instance
        json_error = json.JSONDecodeError("Expecting property name", "", 0)
        mock_instance.query.side_effect = json_error
        
        # Setup resilient processing to succeed
        mock_resilient.return_value = ([{"test": "value"}], 0)
        
        result = query_sparql_endpoint(
            endpoint_url="http://example.com/sparql",
            query="SELECT * WHERE { ?s ?p ?o }",
        )
        
        # Should call resilient processing and return reconstructed results
        mock_resilient.assert_called_once()
        assert "results" in result
        assert "bindings" in result["results"]


class TestExtractBindings:
    """Test the extract_bindings function."""

    def test_extract_simple_bindings(self) -> None:
        """Test extraction of simple variable bindings."""
        sparql_results = {
            "results": {
                "bindings": [
                    {"subject": {"value": "http://example.com/1"}, "predicate": {"value": "http://example.com/prop"}},
                    {"subject": {"value": "http://example.com/2"}, "predicate": {"value": "http://example.com/prop"}},
                ]
            }
        }
        
        bindings = extract_bindings(sparql_results)
        
        expected = [
            {"subject": "http://example.com/1", "predicate": "http://example.com/prop"},
            {"subject": "http://example.com/2", "predicate": "http://example.com/prop"},
        ]
        assert bindings == expected

    def test_extract_empty_bindings(self) -> None:
        """Test extraction from empty results."""
        sparql_results = {"results": {"bindings": []}}
        
        bindings = extract_bindings(sparql_results)
        
        assert bindings == []

    def test_invalid_structure_missing_results(self) -> None:
        """Test that missing 'results' key raises KeyError."""
        sparql_results = {"bindings": []}
        
        with pytest.raises(KeyError, match="Invalid SPARQL results structure"):
            extract_bindings(sparql_results)

    def test_invalid_structure_missing_bindings(self) -> None:
        """Test that missing 'bindings' key raises KeyError."""
        sparql_results = {"results": {}}
        
        with pytest.raises(KeyError, match="Invalid SPARQL results structure"):
            extract_bindings(sparql_results)


class TestCountResults:
    """Test the count_results function."""

    def test_count_multiple_results(self) -> None:
        """Test counting multiple results."""
        sparql_results = {
            "results": {
                "bindings": [
                    {"test": {"value": "1"}},
                    {"test": {"value": "2"}},
                    {"test": {"value": "3"}},
                ]
            }
        }
        
        count = count_results(sparql_results)
        assert count == 3

    def test_count_empty_results(self) -> None:
        """Test counting empty results."""
        sparql_results = {"results": {"bindings": []}}
        
        count = count_results(sparql_results)
        assert count == 0

    def test_invalid_structure(self) -> None:
        """Test that invalid structure raises KeyError."""
        sparql_results = {"results": {}}
        
        with pytest.raises(KeyError, match="Invalid SPARQL results structure"):
            count_results(sparql_results)


class TestCountSparqlQuery:
    """Test the count_sparql_query function."""

    @patch("structured_scraping.sparql_utils.core.query_sparql_endpoint")
    def test_successful_count(self, mock_query: Mock) -> None:
        """Test successful count query execution."""
        mock_query.return_value = {
            "results": {
                "bindings": [
                    {"count": {"value": "42"}}
                ]
            }
        }
        
        with patch("structured_scraping.sparql_utils.queries.convert_to_count_query") as mock_convert:
            mock_convert.return_value = "SELECT (COUNT(*) AS ?count) WHERE { ?s ?p ?o }"
            
            count = count_sparql_query(
                endpoint_url="http://example.com/sparql",
                query="SELECT * WHERE { ?s ?p ?o }",
            )
            
            assert count == 42
            mock_convert.assert_called_once_with("SELECT * WHERE { ?s ?p ?o }")

    @patch("structured_scraping.sparql_utils.core.query_sparql_endpoint")
    def test_empty_count_result(self, mock_query: Mock) -> None:
        """Test count query with empty results."""
        mock_query.return_value = {"results": {"bindings": []}}
        
        with patch("structured_scraping.sparql_utils.queries.convert_to_count_query"):
            count = count_sparql_query(
                endpoint_url="http://example.com/sparql",
                query="SELECT * WHERE { ?s ?p ?o }",
            )
            
            assert count == 0

    @patch("structured_scraping.sparql_utils.core.query_sparql_endpoint")
    def test_invalid_count_result(self, mock_query: Mock) -> None:
        """Test count query with invalid result structure."""
        mock_query.return_value = {"results": {"bindings": [{"invalid": {"value": "test"}}]}}
        
        with patch("structured_scraping.sparql_utils.queries.convert_to_count_query"):
            with pytest.raises(ValueError, match="Failed to parse count result"):
                count_sparql_query(
                    endpoint_url="http://example.com/sparql",
                    query="SELECT * WHERE { ?s ?p ?o }",
                )


class TestValidateReturnFormat:
    """Test the _validate_return_format helper function."""

    def test_valid_json_format(self) -> None:
        """Test validation of JSON format."""
        result = _validate_return_format("json")
        assert result["json"] == JSON

    def test_valid_xml_format(self) -> None:
        """Test validation of XML format."""
        result = _validate_return_format("xml")
        assert result["xml"] == XML

    def test_valid_csv_format(self) -> None:
        """Test validation of CSV format."""
        result = _validate_return_format("csv")
        assert result["csv"] == CSV

    def test_valid_tsv_format(self) -> None:
        """Test validation of TSV format."""
        result = _validate_return_format("tsv")
        assert result["tsv"] == TSV

    def test_case_insensitive_format(self) -> None:
        """Test that format validation is case insensitive."""
        result = _validate_return_format("JSON")
        assert result["json"] == JSON

    def test_invalid_format_raises_error(self) -> None:
        """Test that invalid format raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported return format: invalid"):
            _validate_return_format("invalid")

    def test_empty_format_raises_error(self) -> None:
        """Test that empty format raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported return format"):
            _validate_return_format("")


class TestSetupSparqlWrapper:
    """Test the _setup_sparql_wrapper helper function."""

    @patch("structured_scraping.sparql_utils.core.SPARQLWrapper")
    def test_basic_setup(self, mock_sparql_wrapper: Mock) -> None:
        """Test basic SPARQL wrapper setup."""
        mock_instance = Mock()
        mock_sparql_wrapper.return_value = mock_instance
        format_mapping = {"json": JSON}

        result = _setup_sparql_wrapper(
            endpoint_url="http://example.com/sparql",
            query="SELECT * WHERE { ?s ?p ?o }",
            return_format="json",
            timeout=None,
            user_agent=None,
            format_mapping=format_mapping,
        )

        assert result == mock_instance
        mock_sparql_wrapper.assert_called_once_with("http://example.com/sparql")
        mock_instance.setQuery.assert_called_once_with("SELECT * WHERE { ?s ?p ?o }")
        mock_instance.setReturnFormat.assert_called_once_with(JSON)

    @patch("structured_scraping.sparql_utils.core.SPARQLWrapper")
    def test_setup_with_timeout(self, mock_sparql_wrapper: Mock) -> None:
        """Test SPARQL wrapper setup with timeout."""
        mock_instance = Mock()
        mock_sparql_wrapper.return_value = mock_instance
        format_mapping = {"json": JSON}

        _setup_sparql_wrapper(
            endpoint_url="http://example.com/sparql",
            query="SELECT * WHERE { ?s ?p ?o }",
            return_format="json",
            timeout=30,
            user_agent=None,
            format_mapping=format_mapping,
        )

        mock_instance.setTimeout.assert_called_once_with(30)

    @patch("structured_scraping.sparql_utils.core.SPARQLWrapper")
    def test_setup_with_user_agent(self, mock_sparql_wrapper: Mock) -> None:
        """Test SPARQL wrapper setup with user agent."""
        mock_instance = Mock()
        mock_sparql_wrapper.return_value = mock_instance
        format_mapping = {"json": JSON}

        _setup_sparql_wrapper(
            endpoint_url="http://example.com/sparql",
            query="SELECT * WHERE { ?s ?p ?o }",
            return_format="json",
            timeout=None,
            user_agent="TestAgent/1.0",
            format_mapping=format_mapping,
        )

        mock_instance.addCustomHttpHeader.assert_called_once_with("User-Agent", "TestAgent/1.0")

    @patch("structured_scraping.sparql_utils.core.SPARQLWrapper")
    def test_setup_with_all_options(self, mock_sparql_wrapper: Mock) -> None:
        """Test SPARQL wrapper setup with all options."""
        mock_instance = Mock()
        mock_sparql_wrapper.return_value = mock_instance
        format_mapping = {"xml": XML}

        _setup_sparql_wrapper(
            endpoint_url="http://example.com/sparql",
            query="SELECT * WHERE { ?s ?p ?o }",
            return_format="xml",
            timeout=60,
            user_agent="TestAgent/2.0",
            format_mapping=format_mapping,
        )

        mock_instance.setTimeout.assert_called_once_with(60)
        mock_instance.addCustomHttpHeader.assert_called_once_with("User-Agent", "TestAgent/2.0")
        mock_instance.setReturnFormat.assert_called_once_with(XML)


class TestIsJsonError:
    """Test the _is_json_error helper function."""

    def test_json_decode_error(self) -> None:
        """Test detection of JSONDecodeError."""
        error = json.JSONDecodeError("Expecting value", "", 0)
        assert _is_json_error(error) is True

    def test_value_error_with_json_keyword(self) -> None:
        """Test detection of ValueError with JSON keywords."""
        error = ValueError("Failed to decode JSON")
        assert _is_json_error(error) is True

    def test_generic_error_with_json_message(self) -> None:
        """Test detection of generic error with JSON-related message."""
        error = Exception("Expecting property name in line 1")
        assert _is_json_error(error) is True

    def test_error_with_expecting_value(self) -> None:
        """Test detection of error with 'expecting value' message."""
        error = Exception("Expecting value: line 1 column 1")
        assert _is_json_error(error) is True

    def test_error_with_unterminated_string(self) -> None:
        """Test detection of error with 'unterminated string' message."""
        error = Exception("Unterminated string starting at: line 1 column 5")
        assert _is_json_error(error) is True

    def test_non_json_error(self) -> None:
        """Test that non-JSON errors are not detected as JSON errors."""
        error = Exception("Network timeout")
        assert _is_json_error(error) is False

    def test_connection_error(self) -> None:
        """Test that connection errors are not detected as JSON errors."""
        error = ConnectionError("Connection refused")
        assert _is_json_error(error) is False

    def test_case_insensitive_detection(self) -> None:
        """Test that JSON error detection is case insensitive."""
        error = Exception("Failed to decode JSON data")
        assert _is_json_error(error) is True


class TestSaveDebugInfo:
    """Test the _save_debug_info helper function."""

    @patch("structured_scraping.sparql_utils.core.Path.open", new_callable=mock_open)
    @patch("structured_scraping.sparql_utils.core.time.time", return_value=1234567890)
    def test_save_json_error_debug_info(self, mock_time: Mock, mock_file: Mock) -> None:
        """Test saving debug info for JSON errors."""
        json_error = json.JSONDecodeError("Expecting value", "", 0)
        
        _save_debug_info(
            exception=json_error,
            endpoint_url="http://example.com/sparql",
            query="SELECT * WHERE { ?s ?p ?o }",
        )

        mock_file.assert_called_once()
        handle = mock_file.return_value.__enter__.return_value
        
        # Check that error details were written
        write_calls = handle.write.call_args_list
        written_content = "".join(call[0][0] for call in write_calls)
        
        assert "Error: Expecting value" in written_content
        assert "Exception Type: JSONDecodeError" in written_content
        assert "Endpoint: http://example.com/sparql" in written_content
        assert "Query: SELECT * WHERE { ?s ?p ?o }" in written_content
        assert "Timestamp: 1234567890" in written_content

    @patch("structured_scraping.sparql_utils.core.logger")
    def test_skip_non_json_error(self, mock_logger: Mock) -> None:
        """Test that non-JSON errors are skipped."""
        network_error = Exception("Network timeout")
        
        _save_debug_info(
            exception=network_error,
            endpoint_url="http://example.com/sparql",
            query="SELECT * WHERE { ?s ?p ?o }",
        )

        mock_logger.debug.assert_called_once_with(
            "Non-JSON error (%s: %s), no debug file created", 
            "Exception", 
            "Network timeout"
        )

    @patch("structured_scraping.sparql_utils.core.Path.open", side_effect=OSError("Permission denied"))
    @patch("structured_scraping.sparql_utils.core.logger")
    def test_file_write_error_handling(self, mock_logger: Mock, mock_file: Mock) -> None:
        """Test handling of file write errors."""
        json_error = json.JSONDecodeError("Expecting value", "", 0)
        
        _save_debug_info(
            exception=json_error,
            endpoint_url="http://example.com/sparql",
            query="SELECT * WHERE { ?s ?p ?o }",
        )

        mock_logger.exception.assert_called_once_with("Failed to save error details")


class TestReconstructSparqlResult:
    """Test the _reconstruct_sparql_result helper function."""

    def test_reconstruct_with_results(self) -> None:
        """Test reconstruction with actual results."""
        all_results = [
            {"subject": "http://example.com/1", "predicate": "http://example.com/prop"},
            {"subject": "http://example.com/2", "predicate": "http://example.com/prop"},
        ]

        result = _reconstruct_sparql_result(all_results)

        expected = {
            "head": {"vars": ["subject", "predicate"]},
            "results": {
                "bindings": [
                    {"subject": {"value": "http://example.com/1"}, "predicate": {"value": "http://example.com/prop"}},
                    {"subject": {"value": "http://example.com/2"}, "predicate": {"value": "http://example.com/prop"}},
                ]
            },
        }
        assert result == expected

    def test_reconstruct_with_empty_results(self) -> None:
        """Test reconstruction with empty results."""
        all_results: list[dict[str, str]] = []

        result = _reconstruct_sparql_result(all_results)

        expected = {
            "head": {"vars": []},
            "results": {"bindings": []},
        }
        assert result == expected

    def test_reconstruct_with_single_result(self) -> None:
        """Test reconstruction with single result."""
        all_results = [{"name": "John", "age": "30"}]

        result = _reconstruct_sparql_result(all_results)

        expected = {
            "head": {"vars": ["name", "age"]},
            "results": {
                "bindings": [
                    {"name": {"value": "John"}, "age": {"value": "30"}},
                ]
            },
        }
        assert result == expected


class TestTryResilientFallback:
    """Test the _try_resilient_fallback helper function."""

    @patch("structured_scraping.sparql_utils.batching.resilient_batched_sparql_query")
    def test_successful_resilient_processing(self, mock_resilient: Mock) -> None:
        """Test successful resilient fallback processing."""
        mock_resilient.return_value = ([{"test": "value1"}, {"test": "value2"}], 0)

        result = _try_resilient_fallback(
            endpoint_url="http://example.com/sparql",
            query="SELECT * WHERE { ?s ?p ?o }",
            timeout=30,
            user_agent="TestAgent/1.0",
        )

        mock_resilient.assert_called_once_with(
            endpoint_url="http://example.com/sparql",
            base_query="SELECT * WHERE { ?s ?p ?o }",
            batch_size=1000,
            pause_s=1.0,
            timeout=30,
            user_agent="TestAgent/1.0",
            max_retries=3,
            min_subdivision_size=1,
        )

        assert "results" in result
        assert "bindings" in result["results"]
        assert len(result["results"]["bindings"]) == 2

    @patch("structured_scraping.sparql_utils.batching.resilient_batched_sparql_query")
    def test_resilient_processing_with_skipped_records(self, mock_resilient: Mock) -> None:
        """Test resilient processing with some skipped records."""
        mock_resilient.return_value = ([{"test": "value"}], 3)

        result = _try_resilient_fallback(
            endpoint_url="http://example.com/sparql",
            query="SELECT * WHERE { ?s ?p ?o }",
            timeout=None,
            user_agent=None,
        )

        assert "results" in result
        assert len(result["results"]["bindings"]) == 1

    @patch("structured_scraping.sparql_utils.batching.resilient_batched_sparql_query")
    def test_resilient_processing_failure(self, mock_resilient: Mock) -> None:
        """Test resilient processing failure."""
        mock_resilient.side_effect = Exception("Resilient processing failed")

        with pytest.raises(SPARQLError, match="Resilient processing failed after JSON corruption"):
            _try_resilient_fallback(
                endpoint_url="http://example.com/sparql",
                query="SELECT * WHERE { ?s ?p ?o }",
                timeout=None,
                user_agent=None,
            )


class TestHandleSparqlError:
    """Test the _handle_sparql_error helper function."""

    @patch("structured_scraping.sparql_utils.errors.classify_sparql_error")
    @patch("structured_scraping.sparql_utils.errors.log_error_info")
    def test_backend_timeout_error(self, mock_log: Mock, mock_classify: Mock) -> None:
        """Test handling of backend timeout errors."""
        mock_error_info = Mock()
        mock_error_info.error_type.value = "backend_timeout"
        mock_classify.return_value = mock_error_info

        with pytest.raises(SPARQLError, match="Backend timeout after .* - query too complex"):
            _handle_sparql_error(
                exception=Exception("Timeout"),
                elapsed_time=45.5,
                endpoint_url="http://example.com/sparql",
                query="SELECT * WHERE { ?s ?p ?o }",
                return_format="json",
                timeout=None,
                user_agent=None,
                disable_resilient_fallback=False,
            )

    @patch("structured_scraping.sparql_utils.errors.classify_sparql_error")
    @patch("structured_scraping.sparql_utils.errors.log_error_info")
    @patch("structured_scraping.sparql_utils.core._try_resilient_fallback")
    def test_json_corruption_with_resilient_fallback(self, mock_fallback: Mock, mock_log: Mock, mock_classify: Mock) -> None:
        """Test handling of JSON corruption with resilient fallback."""
        mock_error_info = Mock()
        mock_error_info.error_type.value = "json_corruption"
        mock_error_info.should_use_resilient_processing = True
        mock_classify.return_value = mock_error_info
        
        mock_fallback.return_value = {"results": {"bindings": []}}

        result = _handle_sparql_error(
            exception=json.JSONDecodeError("Invalid JSON", "", 0),
            elapsed_time=5.0,
            endpoint_url="http://example.com/sparql",
            query="SELECT * WHERE { ?s ?p ?o }",
            return_format="json",
            timeout=None,
            user_agent=None,
            disable_resilient_fallback=False,
        )

        mock_fallback.assert_called_once()
        assert result == {"results": {"bindings": []}}

    @patch("structured_scraping.sparql_utils.errors.classify_sparql_error")
    @patch("structured_scraping.sparql_utils.errors.log_error_info")
    def test_json_corruption_fallback_disabled(self, mock_log: Mock, mock_classify: Mock) -> None:
        """Test handling of JSON corruption with fallback disabled."""
        mock_error_info = Mock()
        mock_error_info.error_type.value = "json_corruption"
        mock_error_info.should_use_resilient_processing = True
        mock_classify.return_value = mock_error_info

        with pytest.raises(SPARQLError, match="JSON corruption detected"):
            _handle_sparql_error(
                exception=json.JSONDecodeError("Invalid JSON", "", 0),
                elapsed_time=5.0,
                endpoint_url="http://example.com/sparql",
                query="SELECT * WHERE { ?s ?p ?o }",
                return_format="json",
                timeout=None,
                user_agent=None,
                disable_resilient_fallback=True,
            )

    @patch("structured_scraping.sparql_utils.errors.classify_sparql_error")
    @patch("structured_scraping.sparql_utils.errors.log_error_info")
    def test_generic_error_handling(self, mock_log: Mock, mock_classify: Mock) -> None:
        """Test handling of generic errors."""
        mock_error_info = Mock()
        mock_error_info.error_type.value = "network_error"
        mock_error_info.message = "Network connectivity issue"
        mock_error_info.should_use_resilient_processing = False
        mock_classify.return_value = mock_error_info

        with pytest.raises(SPARQLError, match="Network connectivity issue"):
            _handle_sparql_error(
                exception=Exception("Connection failed"),
                elapsed_time=2.0,
                endpoint_url="http://example.com/sparql",
                query="SELECT * WHERE { ?s ?p ?o }",
                return_format="json",
                timeout=None,
                user_agent=None,
                disable_resilient_fallback=False,
            )
