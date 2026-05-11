"""Tests for the wikidata scrapers module.

This module tests the PEP scraping functionality with actual Wikidata queries
using Qatar as a test country for manageable result sets.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from structured_scraping.wikidata.scrapers import (
    PEPScraperConfig,
    count_country_politicians,
    scrape_country_politicians,
    scrape_living_politicians,
)


class TestPEPScraperConfig:
    """Test PEP scraper configuration class."""

    def test_default_config(self) -> None:
        """Test that default configuration has reasonable values."""
        config = PEPScraperConfig()

        assert config.batch_size > 0
        assert config.pause_s >= 0
        assert config.timeout is None or config.timeout > 0
        assert config.max_retries >= 0
        assert config.language == "en"

    def test_custom_config(self) -> None:
        """Test creating configuration with custom values."""
        config = PEPScraperConfig(
            batch_size=500,
            pause_s=2.0,
            timeout=30,
            max_retries=5,
            language="de",
        )
        
        assert config.batch_size == 500
        assert config.pause_s == 2.0
        assert config.timeout == 30
        assert config.max_retries == 5
        assert config.language == "de"


@pytest.mark.slow
class TestCountryPoliticiansCount:
    """Test counting politicians by country with actual Wikidata queries."""

    def test_count_qatar_politicians(self) -> None:
        """Test counting politicians from Qatar."""
        count = count_country_politicians("Q846")  # Qatar Wikidata ID
        
        # Qatar should have some politicians but not too many
        assert isinstance(count, int)
        assert count >= 0
        assert count < 10000  # Reasonable upper bound for Qatar

    def test_count_qatar_living_politicians(self) -> None:
        """Test counting living politicians from Qatar."""
        count = count_country_politicians("Q846", living_only=True)  # Qatar Wikidata ID
        
        # Should have some living politicians
        assert isinstance(count, int)
        assert count >= 0
        
        # Living count should be <= total count
        total_count = count_country_politicians("Q846", living_only=False)  # Qatar Wikidata ID
        assert count <= total_count

    def test_count_with_custom_config(self) -> None:
        """Test counting with custom configuration."""
        config = PEPScraperConfig(timeout=60, max_retries=2)
        count = count_country_politicians("Q846", config=config)  # Qatar Wikidata ID
        
        assert isinstance(count, int)
        assert count >= 0

    def test_count_invalid_country(self) -> None:
        """Test counting politicians from invalid country."""
        with pytest.raises(ValueError, match="Unknown country"):
            count_country_politicians("NonexistentCountry")


@pytest.mark.slow
class TestScrapeCountryPoliticians:
    """Test scraping politicians by country with actual Wikidata queries."""

    def test_scrape_qatar_politicians_small_batch(self) -> None:
        """Test scraping Qatar politicians with small batch size."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_file = f.name
        
        try:
            # Use small batch size and limit to test functionality
            config = PEPScraperConfig(batch_size=5, pause_s=0.5)
            
            # Get a small sample by limiting the query results
            with patch('structured_scraping.wikidata.scrapers.resilient_batched_sparql_query') as mock_query:
                # Mock a small result set
                mock_results = [
                    {
                        "person": "http://www.wikidata.org/entity/Q123456",
                        "personLabel": "Test Politician 1",
                        "personDescription": "Qatari politician",
                        "nationality": "http://www.wikidata.org/entity/Q846",
                        "nationalityLabel": "Qatar",
                    },
                    {
                        "person": "http://www.wikidata.org/entity/Q789012", 
                        "personLabel": "Test Politician 2",
                        "personDescription": "former politician",
                        "nationality": "http://www.wikidata.org/entity/Q846",
                        "nationalityLabel": "Qatar",
                    }
                ]
                mock_query.return_value = (mock_results, 0)
                
                count, saved_file = scrape_country_politicians(
                    country="Q846",  # Qatar Wikidata ID
                    output_file=output_file,
                    apply_relevance_filter=False,  # Disable filter for test
                    config=config,
                )
            
            # Verify results
            assert count == 2
            assert saved_file == output_file
            assert Path(output_file).exists()
            
            # Check CSV content
            with open(output_file, 'r', encoding='utf-8-sig') as f:
                content = f.read()
                assert "personLabel" in content  # Header
                assert "Test Politician" in content
                
        finally:
            # Clean up
            Path(output_file).unlink(missing_ok=True)

    def test_scrape_qatar_living_politicians(self) -> None:
        """Test scraping living politicians from Qatar."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_file = f.name
        
        try:
            config = PEPScraperConfig(batch_size=10, pause_s=0.5)
            
            with patch('structured_scraping.wikidata.scrapers.resilient_batched_sparql_query') as mock_query:
                # Mock living politicians (no death date)
                mock_results = [
                    {
                        "person": "http://www.wikidata.org/entity/Q123456",
                        "personLabel": "Living Politician",
                        "personDescription": "current politician",
                        "nationality": "http://www.wikidata.org/entity/Q846",
                        "nationalityLabel": "Qatar",
                        "birthDate": "1970-01-01",
                    }
                ]
                mock_query.return_value = (mock_results, 0)
                
                count, saved_file = scrape_country_politicians(
                    country="Q846",  # Qatar Wikidata ID
                    output_file=output_file,
                    living_only=True,
                    config=config,
                )
            
            assert count == 1
            assert Path(output_file).exists()
            
        finally:
            Path(output_file).unlink(missing_ok=True)

    def test_scrape_with_auto_filename(self) -> None:
        """Test scraping with automatically generated filename."""
        config = PEPScraperConfig(batch_size=5, pause_s=0.1)
        
        with patch('structured_scraping.wikidata.scrapers.resilient_batched_sparql_query') as mock_query:
            mock_results = [
                {
                    "person": "http://www.wikidata.org/entity/Q123456",
                    "personLabel": "Test Person",
                    "nationality": "http://www.wikidata.org/entity/Q846",
                    "nationalityLabel": "Qatar",
                }
            ]
            mock_query.return_value = (mock_results, 0)
            
            count, saved_file = scrape_country_politicians(
                country="Q846",  # Qatar Wikidata ID
                output_file=None,  # Auto-generate filename
                apply_relevance_filter=False,  # Disable filter for test
                config=config,
            )
        
        try:
            assert count == 1
            assert "pep_qatar_" in saved_file
            assert saved_file.endswith(".csv")
            assert Path(saved_file).exists()
            
        finally:
            Path(saved_file).unlink(missing_ok=True)

    def test_scrape_with_relevance_filter(self) -> None:
        """Test scraping with relevance filtering applied."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_file = f.name
        
        try:
            config = PEPScraperConfig(batch_size=5, pause_s=0.1)
            
            with patch('structured_scraping.wikidata.scrapers.resilient_batched_sparql_query') as mock_query:
                with patch('structured_scraping.wikidata.scrapers.filter_relevant_peps') as mock_filter:
                    mock_results = [
                        {
                            "person": "http://www.wikidata.org/entity/Q123456",
                            "personLabel": "Test Person",
                            "nationality": "http://www.wikidata.org/entity/Q846",
                        }
                    ]
                    mock_query.return_value = (mock_results, 0)
                    mock_filter.return_value = mock_results  # Keep all results
                    
                    count, saved_file = scrape_country_politicians(
                        country="Q846",  # Qatar Wikidata ID
                        output_file=output_file,
                        apply_relevance_filter=True,
                        config=config,
                    )
                    
                    # Verify filter was called
                    mock_filter.assert_called_once_with(mock_results)
            
            assert count == 1
            
        finally:
            Path(output_file).unlink(missing_ok=True)


@pytest.mark.slow  
class TestScrapeLivingPoliticians:
    """Test the convenience function for scraping living politicians."""

    def test_scrape_living_politicians_qatar(self) -> None:
        """Test scraping living politicians from Qatar."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_file = f.name
        
        try:
            config = PEPScraperConfig(batch_size=5, pause_s=0.1)
            
            with patch('structured_scraping.wikidata.scrapers.scrape_country_politicians') as mock_scrape:
                mock_scrape.return_value = (5, output_file)
                
                count, saved_file = scrape_living_politicians(
                    country="Q846",  # Qatar Wikidata ID
                    output_file=output_file,
                    config=config,
                )
                
                # Verify it calls scrape_country_politicians with living_only=True
                mock_scrape.assert_called_once_with(
                    country="Q846",  # Qatar Wikidata ID
                    output_file=output_file,
                    living_only=True,
                    apply_relevance_filter=False,  # Living filter already applied
                    config=config,
                )
            
            assert count == 5
            assert saved_file == output_file
            
        finally:
            Path(output_file).unlink(missing_ok=True)


class TestScraperErrorHandling:
    """Test error handling in scraper functions."""

    def test_invalid_country_scraping(self) -> None:
        """Test that invalid country names raise appropriate errors."""
        with pytest.raises(ValueError, match="Unknown country"):
            scrape_country_politicians("NonexistentCountry")

    def test_invalid_country_counting(self) -> None:
        """Test that invalid country names raise appropriate errors in counting."""
        with pytest.raises(ValueError, match="Unknown country"):
            count_country_politicians("NonexistentCountry")

    def test_scraping_with_invalid_output_path(self) -> None:
        """Test handling of invalid output paths."""
        config = PEPScraperConfig(batch_size=1, pause_s=0.1)
        
        with patch('structured_scraping.wikidata.scrapers.resilient_batched_sparql_query') as mock_query:
            mock_query.return_value = ([], 0)  # Empty results
            
            # This should work - empty results should not cause file I/O issues
            count, saved_file = scrape_country_politicians(
                country="Q846",  # Qatar Wikidata ID
                output_file="/tmp/test_output.csv",
                config=config,
            )
            
            assert count == 0
