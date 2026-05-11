"""Tests for the sparql_utils.retry module."""

import json
import time
from unittest.mock import Mock, patch
from urllib.error import HTTPError

import pytest

from structured_scraping.sparql_utils.core import SPARQLError
from structured_scraping.sparql_utils.errors import classify_sparql_error, ErrorType
from structured_scraping.sparql_utils.retry import (
    _get_error_message,
    _parse_retry_after,
    query_sparql_endpoint_with_retry,
)


class TestParseRetryAfter:
    """Test the _parse_retry_after function."""

    def test_parse_seconds(self) -> None:
        """Test parsing retry-after value as seconds."""
        result = _parse_retry_after("120")
        assert result == 120.0

    def test_parse_float_seconds(self) -> None:
        """Test parsing retry-after value as float seconds."""
        result = _parse_retry_after("30.5")
        assert result == 30.5

    def test_parse_date_format(self) -> None:
        """Test parsing retry-after value as HTTP date (fallback to default)."""
        result = _parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT")
        assert result == 30.0


class TestGetErrorMessage:
    """Test the _get_error_message function."""

    def test_http_error_429(self) -> None:
        """Test error message for HTTP 429."""
        error = HTTPError(url="", code=429, msg="", hdrs={}, fp=None)
        result = _get_error_message(error)
        assert result == "Rate limited (429)"

    def test_http_error_502(self) -> None:
        """Test error message for HTTP 502."""
        error = HTTPError(url="", code=502, msg="", hdrs={}, fp=None)
        result = _get_error_message(error)
        assert result == "Bad gateway (502)"

    def test_http_error_503(self) -> None:
        """Test error message for HTTP 503."""
        error = HTTPError(url="", code=503, msg="", hdrs={}, fp=None)
        result = _get_error_message(error)
        assert result == "Service unavailable (503)"

    def test_http_error_504(self) -> None:
        """Test error message for HTTP 504."""
        error = HTTPError(url="", code=504, msg="", hdrs={}, fp=None)
        result = _get_error_message(error)
        assert result == "Gateway timeout (504)"

    def test_http_error_unknown(self) -> None:
        """Test error message for unknown HTTP error."""
        error = HTTPError(url="", code=418, msg="", hdrs={}, fp=None)
        result = _get_error_message(error)
        assert result == "Server error (418)"

    def test_json_decode_error(self) -> None:
        """Test error message for JSON decode error."""
        error = json.JSONDecodeError("msg", "doc", 0)
        result = _get_error_message(error)
        assert result == "JSON decode error (server data corruption)"

    def test_other_error(self) -> None:
        """Test error message for other types of errors."""
        error = ValueError("Some error")
        result = _get_error_message(error)
        assert result == "Server error"

    def test_none_error(self) -> None:
        """Test error message for None."""
        result = _get_error_message(None)
        assert result == "Server error"


class TestErrorClassificationIntegration:
    """Test that error classification works properly with retry logic."""

    def test_rate_limiting_error_classification(self) -> None:
        """Test that rate limiting errors are properly classified."""
        # Use error message that includes "429" for rate limiting detection
        sparql_error = SPARQLError("HTTP Error 429: Too Many Requests", "http://example.com", "SELECT")
        
        error_info = classify_sparql_error(sparql_error, elapsed_time=10.0)
        assert error_info.error_type == ErrorType.RATE_LIMITING

    def test_backend_timeout_classification(self) -> None:
        """Test that backend timeout errors are properly classified."""
        timeout_error = TimeoutError("The read operation timed out")
        sparql_error = SPARQLError("Test", "http://example.com", "SELECT")
        sparql_error.__cause__ = timeout_error
        
        error_info = classify_sparql_error(sparql_error, elapsed_time=30.0)
        assert error_info.error_type == ErrorType.BACKEND_TIMEOUT

    def test_json_corruption_classification(self) -> None:
        """Test that JSON corruption errors are properly classified."""
        json_error = json.JSONDecodeError("msg", "doc", 0)
        sparql_error = SPARQLError("Test", "http://example.com", "SELECT")
        sparql_error.__cause__ = json_error
        
        error_info = classify_sparql_error(sparql_error, elapsed_time=5.0)
        assert error_info.error_type == ErrorType.JSON_CORRUPTION

    def test_network_error_classification(self) -> None:
        """Test that network errors are properly classified."""
        # Use error message that contains network-related keywords
        sparql_error = SPARQLError("Connection refused", "http://example.com", "SELECT")
        
        error_info = classify_sparql_error(sparql_error, elapsed_time=2.0)
        assert error_info.error_type == ErrorType.NETWORK_ERROR

    def test_other_error_classification(self) -> None:
        """Test that unknown errors are classified as OTHER."""
        sparql_error = SPARQLError("Unknown error", "http://example.com", "SELECT")
        
        error_info = classify_sparql_error(sparql_error, elapsed_time=1.0)
        assert error_info.error_type == ErrorType.OTHER


class TestQuerySparqlEndpointWithRetry:
    """Test the query_sparql_endpoint_with_retry function."""

    @patch("structured_scraping.sparql_utils.retry.query_sparql_endpoint")
    def test_successful_query_no_retry(self, mock_query: Mock) -> None:
        """Test successful query execution without retries."""
        expected_result = {"results": {"bindings": []}}
        mock_query.return_value = expected_result
        
        result = query_sparql_endpoint_with_retry(
            endpoint_url="http://example.com/sparql",
            query="SELECT * WHERE { ?s ?p ?o }",
        )
        
        assert result == expected_result
        assert mock_query.call_count == 1

    @patch("structured_scraping.sparql_utils.retry.query_sparql_endpoint")
    @patch("structured_scraping.sparql_utils.retry.time.sleep")
    def test_retry_on_rate_limit(self, mock_sleep: Mock, mock_query: Mock) -> None:
        """Test retry behavior on rate limiting."""
        # First call fails with rate limit, second succeeds
        http_error = HTTPError(url="", code=429, msg="", hdrs=None, fp=None)  # type: ignore # None is acceptable for hdrs
        sparql_error = SPARQLError("HTTP Error 429: Too Many Requests", "http://example.com", "SELECT")
        sparql_error.__cause__ = http_error
        
        expected_result = {"results": {"bindings": []}}
        mock_query.side_effect = [sparql_error, expected_result]
        
        result = query_sparql_endpoint_with_retry(
            endpoint_url="http://example.com/sparql",
            query="SELECT * WHERE { ?s ?p ?o }",
            max_retries=3,
            base_delay=1.0,
        )
        
        assert result == expected_result
        assert mock_query.call_count == 2
        mock_sleep.assert_called_once()

    @patch("structured_scraping.sparql_utils.retry.query_sparql_endpoint")
    @patch("structured_scraping.sparql_utils.retry.time.sleep")
    def test_retry_with_retry_after_header(self, mock_sleep: Mock, mock_query: Mock) -> None:
        """Test retry behavior with rate limiting."""
        # Create HTTP error that will be retried
        http_error = HTTPError(url="", code=429, msg="", hdrs=None, fp=None)  # type: ignore # None is acceptable for hdrs
        sparql_error = SPARQLError("HTTP Error 429: Too Many Requests", "http://example.com", "SELECT")
        sparql_error.__cause__ = http_error
        
        expected_result = {"results": {"bindings": []}}
        mock_query.side_effect = [sparql_error, expected_result]
        
        result = query_sparql_endpoint_with_retry(
            endpoint_url="http://example.com/sparql",
            query="SELECT * WHERE { ?s ?p ?o }",
            max_retries=3,
        )
        
        assert result == expected_result
        # Just verify that sleep was called (indicating retry happened)
        mock_sleep.assert_called_once()

    @patch("structured_scraping.sparql_utils.retry.query_sparql_endpoint")
    def test_max_retries_exceeded(self, mock_query: Mock) -> None:
        """Test that SPARQLError is raised when max retries exceeded."""
        http_error = HTTPError(url="", code=429, msg="", hdrs=None, fp=None)  # type: ignore # None is acceptable for hdrs
        sparql_error = SPARQLError("HTTP Error 429: Too Many Requests", "http://example.com", "SELECT")
        sparql_error.__cause__ = http_error
        
        mock_query.side_effect = sparql_error
        
        with pytest.raises(SPARQLError):
            query_sparql_endpoint_with_retry(
                endpoint_url="http://example.com/sparql",
                query="SELECT * WHERE { ?s ?p ?o }",
                max_retries=2,
            )
        
        assert mock_query.call_count == 3  # Initial + 2 retries

    @patch("structured_scraping.sparql_utils.retry.query_sparql_endpoint")
    def test_non_retryable_error(self, mock_query: Mock) -> None:
        """Test that non-retryable errors are not retried."""
        sparql_error = SPARQLError("Query syntax error", "http://example.com", "SELECT")
        sparql_error.__cause__ = ValueError("Syntax error")
        
        mock_query.side_effect = sparql_error
        
        with pytest.raises(SPARQLError):
            query_sparql_endpoint_with_retry(
                endpoint_url="http://example.com/sparql",
                query="SELECT * WHERE { ?s ?p ?o }",
                max_retries=3,
            )
        
        assert mock_query.call_count == 1  # No retries

    @patch("structured_scraping.sparql_utils.retry.query_sparql_endpoint")
    @patch("structured_scraping.sparql_utils.retry.time.sleep")
    @patch("structured_scraping.sparql_utils.retry.random.uniform")
    def test_exponential_backoff_with_jitter(
        self, mock_uniform: Mock, mock_sleep: Mock, mock_query: Mock
    ) -> None:
        """Test exponential backoff with jitter."""
        # Setup mocks
        mock_uniform.return_value = 0.2  # 20% jitter
        
        http_error = HTTPError(url="", code=503, msg="", hdrs=None, fp=None)  # type: ignore # None is acceptable for hdrs
        sparql_error = SPARQLError("HTTP 503 Service unavailable", "http://example.com", "SELECT")
        sparql_error.__cause__ = http_error
        
        expected_result = {"results": {"bindings": []}}
        mock_query.side_effect = [sparql_error, sparql_error, expected_result]
        
        result = query_sparql_endpoint_with_retry(
            endpoint_url="http://example.com/sparql",
            query="SELECT * WHERE { ?s ?p ?o }",
            max_retries=3,
            base_delay=2.0,
        )
        
        assert result == expected_result
        
        # Check that sleep was called with exponential backoff + jitter
        expected_calls = [
            # First retry: 2.0 * 2^0 + jitter = 2.0 + 0.4 = 2.4
            pytest.approx(2.4, rel=1e-2),
            # Second retry: 2.0 * 2^1 + jitter = 4.0 + 0.8 = 4.8
            pytest.approx(4.8, rel=1e-2),
        ]
        
        actual_calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert len(actual_calls) == 2
        for actual, expected in zip(actual_calls, expected_calls):
            assert actual == expected
