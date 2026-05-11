"""Tests for the wikidata countries module.

This module tests country identification and name resolution functionality
using actual Wikidata data.
"""

import pytest

from structured_scraping.wikidata.countries import (
    get_country_id,
    get_country_name,
    list_supported_countries,
)


class TestCountryFunctions:
    """Test country identification and name resolution functions."""

    def test_get_country_id_valid_country(self) -> None:
        """Test getting country ID for a valid country name."""
        # Test various ways to specify Qatar
        assert get_country_id("qatar") == "Q846"  # lowercase country name
        assert get_country_id("qa") == "Q846"     # country code
        assert get_country_id("Q846") == "Q846"   # Wikidata ID
        assert get_country_id("qatar") == "Q846"  # Case insensitive
        assert get_country_id("QATAR") == "Q846"
        
        # Test a few other countries for robustness
        assert get_country_id("Denmark") == "Q35"
        assert get_country_id("Ireland") == "Q27"

    def test_get_country_id_invalid_country(self) -> None:
        """Test getting country ID for an invalid country name."""
        with pytest.raises(ValueError, match="Unknown country"):
            get_country_id("NonexistentCountry")
        
        with pytest.raises(ValueError, match="Unknown country"):
            get_country_id("")

    def test_get_country_name_valid_id(self) -> None:
        """Test getting country name for a valid country ID."""
        assert get_country_name("Q846") == "Qatar"
        assert get_country_name("Q35") == "Denmark"
        assert get_country_name("Q27") == "Ireland"

    def test_get_country_name_invalid_id(self) -> None:
        """Test getting country name for an invalid country ID."""
        with pytest.raises(ValueError, match="Unknown country ID"):
            get_country_name("Q999999")

    def test_list_supported_countries(self) -> None:
        """Test listing all supported countries."""
        countries = list_supported_countries()
        
        # Verify it returns a list
        assert isinstance(countries, list)
        
        # Verify it contains dictionaries with expected keys
        assert len(countries) > 0
        assert all(isinstance(country, dict) for country in countries)
        assert all("name" in country for country in countries)
        assert all("wikidata_id" in country for country in countries)
        assert all("code" in country for country in countries)
        
        # Verify some expected countries are present
        country_names = [c["name"] for c in countries]
        assert "Qatar" in country_names
        
        # Verify Qatar has the correct data
        qatar_entries = [c for c in countries if c["name"] == "Qatar"]
        assert len(qatar_entries) > 0
        qatar = qatar_entries[0]
        assert qatar["wikidata_id"] == "Q846"
        
        # Verify no duplicates by wikidata_id
        wikidata_ids = [c["wikidata_id"] for c in countries]
        assert len(wikidata_ids) == len(set(wikidata_ids))

    def test_country_id_name_consistency(self) -> None:
        """Test that country ID and name functions are consistent."""
        # Test round trip: name -> ID -> name
        test_countries = ["qatar", "denmark", "ireland"]  # Use lowercase to test case handling
        
        for country in test_countries:
            country_id = get_country_id(country)
            retrieved_name = get_country_name(country_id)
            # The retrieved name should be properly capitalized
            assert retrieved_name.lower() == country.lower()

    def test_case_sensitivity(self) -> None:
        """Test that country name matching is case insensitive."""
        # All these should return the same ID
        variations = ["qatar", "QATAR", "Qatar", "QaTaR"]
        expected_id = "Q846"
        
        for variation in variations:
            assert get_country_id(variation) == expected_id
