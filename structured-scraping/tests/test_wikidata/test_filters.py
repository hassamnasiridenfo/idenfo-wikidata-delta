"""Tests for the wikidata filters module.

This module tests PEP relevance filtering functionality.
"""

import pytest

from structured_scraping.wikidata.filters import (
    filter_relevant_peps,
    filter_living_peps,
    filter_by_birth_year,
    filter_by_position_date,
)


class TestFilterRelevantPeps:
    """Test PEP relevance filtering functions."""

    def test_filter_relevant_peps_excludes_deceased(self) -> None:
        """Test that deceased people are excluded."""
        mock_data = [
            {
                "person": "Q1",
                "personLabel": "Living Person",
                "birthDate": "1970-01-01T00:00:00Z",
                "deathDate": "",
            },
            {
                "person": "Q2",
                "personLabel": "Dead Person",
                "birthDate": "1950-01-01T00:00:00Z",
                "deathDate": "2020-01-01T00:00:00Z",
            },
        ]
        
        filtered_data = filter_relevant_peps(mock_data)
        
        assert len(filtered_data) == 1
        assert filtered_data[0]["personLabel"] == "Living Person"

    def test_filter_relevant_peps_birth_date_threshold(self) -> None:
        """Test birth date filtering with 1925 threshold."""
        mock_data = [
            {
                "person": "Q1",
                "personLabel": "Old Person",
                "birthDate": "1920-01-01T00:00:00Z",
            },
            {
                "person": "Q2",
                "personLabel": "Modern Person",
                "birthDate": "1950-01-01T00:00:00Z",
            },
            {
                "person": "Q3",
                "personLabel": "Recent Person",
                "birthDate": "1990-01-01T00:00:00Z",
            },
        ]
        
        filtered_data = filter_relevant_peps(mock_data)
        
        assert len(filtered_data) == 2
        labels = [p["personLabel"] for p in filtered_data]
        assert "Old Person" not in labels
        assert "Modern Person" in labels
        assert "Recent Person" in labels

    def test_filter_relevant_peps_various_date_formats(self) -> None:
        """Test parsing of various date formats."""
        mock_data = [
            {
                "person": "Q1",
                "personLabel": "ISO Format",
                "birthDate": "1970-01-01T00:00:00Z",
            },
            {
                "person": "Q2",
                "personLabel": "Simple Format",
                "birthDate": "1980-05-15",
            },
            {
                "person": "Q3",
                "personLabel": "Year in Text",
                "birthDate": "Born in 1990",
            },
        ]
        
        filtered_data = filter_relevant_peps(mock_data)
        
        assert len(filtered_data) == 3
        labels = [p["personLabel"] for p in filtered_data]
        assert "ISO Format" in labels
        assert "Simple Format" in labels
        assert "Year in Text" in labels

    def test_filter_relevant_peps_position_dates_fallback(self) -> None:
        """Test using position dates when birth date is missing."""
        mock_data = [
            {
                "person": "Q1",
                "personLabel": "Position After 1925",
                "startTime": "1950-01-01T00:00:00Z",
                "endTime": "1960-01-01T00:00:00Z",
            },
            {
                "person": "Q2",
                "personLabel": "Position Before 1925",
                "startTime": "1920-01-01T00:00:00Z",
                "endTime": "1922-01-01T00:00:00Z",
            },
            {
                "person": "Q3",
                "personLabel": "Mixed Dates",
                "startTime": "1920-01-01T00:00:00Z",
                "endTime": "1950-01-01T00:00:00Z",
            },
        ]
        
        filtered_data = filter_relevant_peps(mock_data)
        
        assert len(filtered_data) == 2
        labels = [p["personLabel"] for p in filtered_data]
        assert "Position After 1925" in labels
        assert "Position Before 1925" not in labels
        assert "Mixed Dates" in labels  # Has at least one date >= 1925

    def test_filter_relevant_peps_missing_all_dates(self) -> None:
        """Test exclusion of records with no date information."""
        mock_data = [
            {
                "person": "Q1",
                "personLabel": "No Dates",
                "position": "Some Position",
            },
            {
                "person": "Q2",
                "personLabel": "Has Birth Date",
                "birthDate": "1970-01-01T00:00:00Z",
            },
        ]
        
        filtered_data = filter_relevant_peps(mock_data)
        
        assert len(filtered_data) == 1
        assert filtered_data[0]["personLabel"] == "Has Birth Date"

    def test_filter_relevant_peps_invalid_date_format(self) -> None:
        """Test handling of invalid date formats."""
        mock_data = [
            {
                "person": "Q1",
                "personLabel": "Invalid Date",
                "birthDate": "invalid-date-format",
            },
        ]
        
        with pytest.raises(ValueError, match="Invalid date format"):
            filter_relevant_peps(mock_data)

    def test_filter_relevant_peps_empty_input(self) -> None:
        """Test filtering with empty input."""
        result = filter_relevant_peps([])
        assert result == []

    def test_filter_relevant_peps_preserves_structure(self) -> None:
        """Test that filtering preserves data structure."""
        mock_data = [
            {
                "person": "http://www.wikidata.org/entity/Q123456",
                "personLabel": "Test Person",
                "personDescription": "politician",
                "birthDate": "1970-01-01T00:00:00Z",
                "nationality": "http://www.wikidata.org/entity/Q846",
                "nationalityLabel": "Qatar",
            }
        ]
        
        filtered_data = filter_relevant_peps(mock_data)
        
        assert len(filtered_data) == 1
        assert filtered_data[0] == mock_data[0]  # Should be identical

    def test_filter_relevant_peps_simple_date_format(self) -> None:
        """Test parsing of simple YYYY-MM-DD date format."""
        mock_data = [
            {
                "person": "Q1",
                "personLabel": "Simple Date Format",
                "birthDate": "1970-12-25",  # Simple YYYY-MM-DD format
            },
        ]
        
        filtered_data = filter_relevant_peps(mock_data)
        
        assert len(filtered_data) == 1
        assert filtered_data[0]["personLabel"] == "Simple Date Format"

    def test_filter_relevant_peps_iso_date_with_z_suffix(self) -> None:
        """Test parsing of ISO date format with Z suffix."""
        mock_data = [
            {
                "person": "Q1",
                "personLabel": "ISO Date with Z",
                "birthDate": "1970-12-25T15:30:45Z",  # Full ISO format with Z
            },
        ]
        
        filtered_data = filter_relevant_peps(mock_data)
        
        assert len(filtered_data) == 1
        assert filtered_data[0]["personLabel"] == "ISO Date with Z"

    def test_filter_relevant_peps_date_before_1900(self) -> None:
        """Test parsing of dates before 1900 (not matched by regex)."""
        mock_data = [
            {
                "person": "Q1",
                "personLabel": "Very Old Person",
                "birthDate": "1800-12-25",  # Won't match regex but is simple format
            },
        ]
        
        # This should be filtered out due to age, but parsing should work
        filtered_data = filter_relevant_peps(mock_data)
        
        assert len(filtered_data) == 0  # Filtered out because born before 1925

    def test_filter_relevant_peps_date_after_2099(self) -> None:
        """Test parsing of dates after 2099 (not matched by regex)."""
        mock_data = [
            {
                "person": "Q1",
                "personLabel": "Future Person",
                "birthDate": "2150-12-25",  # Won't match regex but is simple format
            },
        ]
        
        # This should pass the birth year test
        filtered_data = filter_relevant_peps(mock_data)
        
        assert len(filtered_data) == 1
        assert filtered_data[0]["personLabel"] == "Future Person"

    def test_filter_relevant_peps_complex_iso_date(self) -> None:
        """Test parsing of complex ISO date format that doesn't match regex."""
        mock_data = [
            {
                "person": "Q1", 
                "personLabel": "Complex ISO Date",
                "birthDate": "2150-12-25T15:30:45Z",  # Future date with full ISO format
            },
        ]
        
        # This should be parsed correctly and included
        filtered_data = filter_relevant_peps(mock_data)
        
        assert len(filtered_data) == 1
        assert filtered_data[0]["personLabel"] == "Complex ISO Date"

    def test_filter_relevant_peps_malformed_data_graceful_handling(self) -> None:
        """Test that malformed data is handled gracefully without crashing."""
        malformed_data = [
            {"invalid": "data"},  # Missing required fields
            {},  # Empty dict
            {"person": "incomplete"},  # Missing dates
        ]
        
        # Should handle malformed data gracefully and exclude them
        result = filter_relevant_peps(malformed_data)
        
        assert isinstance(result, list)
        assert len(result) == 0  # All should be filtered out due to missing dates

    def test_filter_relevant_peps_edge_case_birth_year_1925(self) -> None:
        """Test the exact threshold year 1925."""
        mock_data = [
            {
                "person": "Q1",
                "personLabel": "Born 1925",
                "birthDate": "1925-01-01T00:00:00Z",
            },
            {
                "person": "Q2",
                "personLabel": "Born 1924",
                "birthDate": "1924-12-31T23:59:59Z",
            },
        ]
        
        filtered_data = filter_relevant_peps(mock_data)
        
        assert len(filtered_data) == 1
        assert filtered_data[0]["personLabel"] == "Born 1925"

    def test_filter_relevant_peps_position_dates_one_valid(self) -> None:
        """Test position dates where only one is valid (>= 1925)."""
        mock_data = [
            {
                "person": "Q1",
                "personLabel": "Mixed Position Dates",
                "startTime": "1920-01-01T00:00:00Z",  # Before 1925
                "endTime": "1930-01-01T00:00:00Z",    # After 1925
            },
        ]
        
        filtered_data = filter_relevant_peps(mock_data)
        
        assert len(filtered_data) == 1
        assert filtered_data[0]["personLabel"] == "Mixed Position Dates"

    def test_filter_relevant_peps_position_dates_both_invalid(self) -> None:
        """Test position dates where both are invalid (< 1925)."""
        mock_data = [
            {
                "person": "Q1",
                "personLabel": "Both Position Dates Old",
                "startTime": "1920-01-01T00:00:00Z",  # Before 1925
                "endTime": "1922-01-01T00:00:00Z",    # Before 1925
            },
        ]
        
        filtered_data = filter_relevant_peps(mock_data)
        
        assert len(filtered_data) == 0  # Should be filtered out


class TestFilterLivingPeps:
    """Test filter_living_peps function."""

    def test_filter_living_peps_excludes_deceased(self) -> None:
        """Test that deceased people are excluded."""
        mock_data = [
            {
                "person": "Q1",
                "personLabel": "Living Person",
                "birthDate": "1970-01-01T00:00:00Z",
                "deathDate": "",
            },
            {
                "person": "Q2",
                "personLabel": "Dead Person",
                "birthDate": "1950-01-01T00:00:00Z",
                "deathDate": "2020-01-01T00:00:00Z",
            },
            {
                "person": "Q3",
                "personLabel": "Another Living Person",
                "birthDate": "1980-01-01T00:00:00Z",
            },
        ]
        
        filtered_data = filter_living_peps(mock_data)
        
        assert len(filtered_data) == 2
        labels = [p["personLabel"] for p in filtered_data]
        assert "Living Person" in labels
        assert "Dead Person" not in labels
        assert "Another Living Person" in labels

    def test_filter_living_peps_empty_input(self) -> None:
        """Test filtering with empty input."""
        result = filter_living_peps([])
        assert result == []

    def test_filter_living_peps_all_living(self) -> None:
        """Test with all living people."""
        mock_data = [
            {
                "person": "Q1",
                "personLabel": "Person 1",
                "birthDate": "1970-01-01T00:00:00Z",
            },
            {
                "person": "Q2",
                "personLabel": "Person 2",
                "birthDate": "1980-01-01T00:00:00Z",
            },
        ]
        
        filtered_data = filter_living_peps(mock_data)
        
        assert len(filtered_data) == 2
        assert filtered_data == mock_data

    def test_filter_living_peps_all_deceased(self) -> None:
        """Test with all deceased people."""
        mock_data = [
            {
                "person": "Q1",
                "personLabel": "Dead Person 1",
                "birthDate": "1950-01-01T00:00:00Z",
                "deathDate": "2020-01-01T00:00:00Z",
            },
            {
                "person": "Q2",
                "personLabel": "Dead Person 2",
                "birthDate": "1960-01-01T00:00:00Z",
                "deathDate": "2021-01-01T00:00:00Z",
            },
        ]
        
        filtered_data = filter_living_peps(mock_data)
        
        assert len(filtered_data) == 0
        assert filtered_data == []


class TestFilterByBirthYear:
    """Test filter_by_birth_year function."""

    def test_filter_by_birth_year_default_range(self) -> None:
        """Test filtering with default year range (1900+)."""
        mock_data = [
            {
                "person": "Q1",
                "personLabel": "Old Person",
                "birthDate": "1850-01-01T00:00:00Z",
            },
            {
                "person": "Q2",
                "personLabel": "Modern Person",
                "birthDate": "1950-01-01T00:00:00Z",
            },
            {
                "person": "Q3",
                "personLabel": "Recent Person",
                "birthDate": "1990-01-01T00:00:00Z",
            },
        ]
        
        filtered_data = filter_by_birth_year(mock_data)
        
        assert len(filtered_data) == 2
        labels = [p["personLabel"] for p in filtered_data]
        assert "Old Person" not in labels
        assert "Modern Person" in labels
        assert "Recent Person" in labels

    def test_filter_by_birth_year_custom_range(self) -> None:
        """Test filtering with custom year range."""
        mock_data = [
            {
                "person": "Q1",
                "personLabel": "Person 1950",
                "birthDate": "1950-01-01T00:00:00Z",
            },
            {
                "person": "Q2",
                "personLabel": "Person 1970",
                "birthDate": "1970-01-01T00:00:00Z",
            },
            {
                "person": "Q3",
                "personLabel": "Person 1990",
                "birthDate": "1990-01-01T00:00:00Z",
            },
        ]
        
        filtered_data = filter_by_birth_year(mock_data, min_year=1960, max_year=1980)
        
        assert len(filtered_data) == 1
        assert filtered_data[0]["personLabel"] == "Person 1970"

    def test_filter_by_birth_year_missing_birth_dates(self) -> None:
        """Test filtering with missing birth dates."""
        mock_data = [
            {
                "person": "Q1",
                "personLabel": "No Birth Date",
                "position": "Some Position",
            },
            {
                "person": "Q2",
                "personLabel": "Has Birth Date",
                "birthDate": "1970-01-01T00:00:00Z",
            },
        ]
        
        filtered_data = filter_by_birth_year(mock_data)
        
        assert len(filtered_data) == 1
        assert filtered_data[0]["personLabel"] == "Has Birth Date"

    def test_filter_by_birth_year_invalid_date_format(self) -> None:
        """Test handling of invalid birth date formats."""
        mock_data = [
            {
                "person": "Q1",
                "personLabel": "Invalid Date",
                "birthDate": "invalid-date-format",
            },
            {
                "person": "Q2",
                "personLabel": "Valid Date",
                "birthDate": "1970-01-01T00:00:00Z",
            },
        ]
        
        filtered_data = filter_by_birth_year(mock_data)
        
        assert len(filtered_data) == 1
        assert filtered_data[0]["personLabel"] == "Valid Date"

    def test_filter_by_birth_year_empty_input(self) -> None:
        """Test filtering with empty input."""
        result = filter_by_birth_year([])
        assert result == []

    def test_filter_by_birth_year_only_max_year(self) -> None:
        """Test filtering with only max year specified."""
        mock_data = [
            {
                "person": "Q1",
                "personLabel": "Person 1950",
                "birthDate": "1950-01-01T00:00:00Z",
            },
            {
                "person": "Q2",
                "personLabel": "Person 1990",
                "birthDate": "1990-01-01T00:00:00Z",
            },
        ]
        
        filtered_data = filter_by_birth_year(mock_data, max_year=1970)
        
        assert len(filtered_data) == 1
        assert filtered_data[0]["personLabel"] == "Person 1950"


class TestFilterByPositionDate:
    """Test filter_by_position_date function."""

    def test_filter_by_position_date_start_time(self) -> None:
        """Test filtering by startTime."""
        mock_data = [
            {
                "person": "Q1",
                "personLabel": "Old Position",
                "startTime": "1850-01-01T00:00:00Z",
            },
            {
                "person": "Q2",
                "personLabel": "Modern Position",
                "startTime": "1950-01-01T00:00:00Z",
            },
            {
                "person": "Q3",
                "personLabel": "Recent Position",
                "startTime": "1990-01-01T00:00:00Z",
            },
        ]
        
        filtered_data = filter_by_position_date(mock_data, min_year=1920, date_field="startTime")
        
        assert len(filtered_data) == 2
        labels = [p["personLabel"] for p in filtered_data]
        assert "Old Position" not in labels
        assert "Modern Position" in labels
        assert "Recent Position" in labels

    def test_filter_by_position_date_end_time(self) -> None:
        """Test filtering by endTime."""
        mock_data = [
            {
                "person": "Q1",
                "personLabel": "Old End",
                "endTime": "1850-01-01T00:00:00Z",
            },
            {
                "person": "Q2",
                "personLabel": "Modern End",
                "endTime": "1950-01-01T00:00:00Z",
            },
        ]
        
        filtered_data = filter_by_position_date(mock_data, min_year=1920, date_field="endTime")
        
        assert len(filtered_data) == 1
        assert filtered_data[0]["personLabel"] == "Modern End"

    def test_filter_by_position_date_missing_dates(self) -> None:
        """Test filtering with missing position dates."""
        mock_data = [
            {
                "person": "Q1",
                "personLabel": "No Position Date",
                "position": "Some Position",
            },
            {
                "person": "Q2",
                "personLabel": "Has Position Date",
                "startTime": "1970-01-01T00:00:00Z",
            },
        ]
        
        filtered_data = filter_by_position_date(mock_data)
        
        assert len(filtered_data) == 1
        assert filtered_data[0]["personLabel"] == "Has Position Date"

    def test_filter_by_position_date_invalid_date_format(self) -> None:
        """Test handling of invalid position date formats."""
        mock_data = [
            {
                "person": "Q1",
                "personLabel": "Invalid Date",
                "startTime": "invalid-date-format",
            },
            {
                "person": "Q2",
                "personLabel": "Valid Date",
                "startTime": "1970-01-01T00:00:00Z",
            },
        ]
        
        filtered_data = filter_by_position_date(mock_data)
        
        assert len(filtered_data) == 1
        assert filtered_data[0]["personLabel"] == "Valid Date"

    def test_filter_by_position_date_empty_input(self) -> None:
        """Test filtering with empty input."""
        result = filter_by_position_date([])
        assert result == []

    def test_filter_by_position_date_custom_min_year(self) -> None:
        """Test filtering with custom minimum year."""
        mock_data = [
            {
                "person": "Q1",
                "personLabel": "Position 1950",
                "startTime": "1950-01-01T00:00:00Z",
            },
            {
                "person": "Q2",
                "personLabel": "Position 1990",
                "startTime": "1990-01-01T00:00:00Z",
            },
        ]
        
        filtered_data = filter_by_position_date(mock_data, min_year=1970)
        
        assert len(filtered_data) == 1
        assert filtered_data[0]["personLabel"] == "Position 1990"
