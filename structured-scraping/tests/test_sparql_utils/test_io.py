"""Tests for the sparql_utils.io module."""

import csv
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from structured_scraping.sparql_utils.io import (
    query_and_save_to_csv,
    save_results_to_csv,
    save_sparql_results_to_csv,
)


class TestSaveResultsToCSV:
    """Test the save_results_to_csv function."""

    def test_save_simple_results(self) -> None:
        """Test saving simple results to CSV."""
        results = [
            {"name": "Alice", "age": "30"},
            {"name": "Bob", "age": "25"},
        ]
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            save_results_to_csv(results, tmp_path, fieldnames=["name", "age"])
            
            # Verify the CSV content
            with Path(tmp_path).open("r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                
            assert len(rows) == 2
            assert rows[0]["name"] == "Alice"
            assert rows[0]["age"] == "30"
            assert rows[1]["name"] == "Bob"
            assert rows[1]["age"] == "25"
        finally:
            Path(tmp_path).unlink()

    def test_save_results_infer_fieldnames(self) -> None:
        """Test saving results with inferred fieldnames."""
        results = [
            {"name": "Alice", "city": "New York"},
            {"name": "Bob", "age": "25"},  # Different fields
        ]
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            save_results_to_csv(results, tmp_path)  # No fieldnames provided
            
            # Verify the CSV content
            with Path(tmp_path).open("r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                rows = list(reader)
                
            # Should include all fields, sorted
            assert set(fieldnames) == {"age", "city", "name"}
            assert len(rows) == 2
        finally:
            Path(tmp_path).unlink()

    def test_save_empty_results_with_fieldnames(self) -> None:
        """Test saving empty results when fieldnames are provided."""
        results: list[dict[str, str]] = []
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            save_results_to_csv(results, tmp_path, fieldnames=["name", "age"])
            
            # Verify the CSV has headers but no data
            with Path(tmp_path).open("r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                
            assert reader.fieldnames == ["name", "age"]
            assert len(rows) == 0
        finally:
            Path(tmp_path).unlink()

    def test_save_empty_results_no_fieldnames(self) -> None:
        """Test that saving empty results without fieldnames creates empty CSV."""
        results: list[dict[str, str]] = []
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
            tmp_path = tmp.name
            
        try:
            # Should not raise an error - creates empty CSV with no headers
            save_results_to_csv(results, tmp_path)
            
            # Verify file exists and is empty (no header, no data)
            with open(tmp_path, 'r', encoding='utf-8-sig') as f:
                content = f.read().strip()
                assert content == "", "Empty results should create empty CSV file"
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_save_with_path_object(self) -> None:
        """Test saving results using Path object."""
        results = [{"test": "value"}]
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        
        try:
            save_results_to_csv(results, tmp_path, fieldnames=["test"])
            
            # Verify the file was created
            assert tmp_path.exists()
            with tmp_path.open("r", encoding="utf-8-sig") as f:
                content = f.read()
                assert "test" in content
                assert "value" in content
        finally:
            tmp_path.unlink()

    def test_save_with_custom_encoding(self) -> None:
        """Test saving results with custom encoding."""
        results = [{"name": "José", "city": "São Paulo"}]
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            save_results_to_csv(
                results, tmp_path, fieldnames=["name", "city"], encoding="utf-8"
            )
            
            # Verify the CSV content with correct encoding
            with Path(tmp_path).open("r", encoding="utf-8") as f:
                content = f.read()
                assert "José" in content
                assert "São Paulo" in content
        finally:
            Path(tmp_path).unlink()

    def test_save_io_error(self) -> None:
        """Test that I/O errors are properly handled."""
        results = [{"test": "value"}]
        invalid_path = "/invalid/path/that/does/not/exist.csv"
        
        with pytest.raises(OSError, match="Failed to write CSV file"):
            save_results_to_csv(results, invalid_path, fieldnames=["test"])


class TestSaveSparqlResultsToCSV:
    """Test the save_sparql_results_to_csv function."""

    @patch("structured_scraping.sparql_utils.core.extract_bindings")
    @patch("structured_scraping.sparql_utils.io.save_results_to_csv")
    def test_save_sparql_results(self, mock_save: Mock, mock_extract: Mock) -> None:
        """Test saving raw SPARQL results to CSV."""
        sparql_results = {
            "results": {
                "bindings": [
                    {"name": {"value": "Alice"}, "age": {"value": "30"}},
                ]
            }
        }
        extracted_results = [{"name": "Alice", "age": "30"}]
        mock_extract.return_value = extracted_results
        
        save_sparql_results_to_csv(
            sparql_results, "test.csv", fieldnames=["name", "age"], encoding="utf-8"
        )
        
        mock_extract.assert_called_once_with(sparql_results)
        mock_save.assert_called_once_with(
            extracted_results, "test.csv", ["name", "age"], "utf-8"
        )


class TestQueryAndSaveToCSV:
    """Test the query_and_save_to_csv function."""

    @patch("structured_scraping.sparql_utils.core.count_results")
    @patch("structured_scraping.sparql_utils.core.query_sparql_endpoint")
    @patch("structured_scraping.sparql_utils.io.save_sparql_results_to_csv")
    def test_query_and_save(
        self, mock_save_sparql: Mock, mock_query: Mock, mock_count: Mock
    ) -> None:
        """Test querying and saving results to CSV."""
        sparql_results = {"results": {"bindings": [{"test": {"value": "value"}}]}}
        mock_query.return_value = sparql_results
        mock_count.return_value = 1
        
        result = query_and_save_to_csv(
            endpoint_url="http://example.com/sparql",
            query="SELECT * WHERE { ?s ?p ?o }",
            file_path="test.csv",
            fieldnames=["test"],
            encoding="utf-8",
            timeout=30,
            user_agent="TestAgent",
        )
        
        assert result == 1
        
        mock_query.assert_called_once_with(
            endpoint_url="http://example.com/sparql",
            query="SELECT * WHERE { ?s ?p ?o }",
            return_format="json",
            timeout=30,
            user_agent="TestAgent",
        )
        
        mock_save_sparql.assert_called_once_with(
            sparql_results, "test.csv", ["test"], "utf-8"
        )
        
        mock_count.assert_called_once_with(sparql_results)
