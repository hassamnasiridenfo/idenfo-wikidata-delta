"""Tests for the wikidata queries.pep module.

This module tests SPARQL query templates for PEP data.
"""

import re

from structured_scraping.wikidata.queries.pep import (
    ALIAS_POLITICIANS_QUERY,
    BASIC_POLITICIANS_QUERY,
    CRIMINAL_POLITICIANS_QUERY,
    DOB_POLITICIANS_QUERY,
    EXTENDED_POLITICIANS_BY_NATIONALITY_QUERY,
    EXTENDED_POLITICIANS_QUERY,
    MAIN_QUERY,
    NATIONALITY_POLITICIANS_QUERY,
    RCA_POLITICIANS_QUERY,
    RESIDENCE_POLITICIANS_QUERY,
    ROLE_POLITICIANS_QUERY,
)


class TestPepQueries:
    """Test PEP SPARQL query templates."""
    
    def test_basic_politicians_query_structure(self) -> None:
        """Test that basic query has correct structure."""
        query = BASIC_POLITICIANS_QUERY

        # Check for essential SPARQL elements
        assert "SELECT" in query
        assert "WHERE" in query
        assert "?person" in query
        assert "?personLabel" in query
        assert "wdt:P31 wd:Q5" in query  # Instance of human
        assert "wdt:P106 wd:Q82955" in query  # Occupation: politician
        assert "SERVICE wikibase:label" in query
        # Query should not have LIMIT clause (handled by scraping code)
        assert "LIMIT" not in query

    def test_extended_politicians_query_structure(self) -> None:
        """Test that extended query has correct structure."""
        query = EXTENDED_POLITICIANS_QUERY
        
        # Check for essential SPARQL elements
        assert "SELECT" in query
        assert "WHERE" in query
        assert "?person" in query
        assert "?personLabel" in query
        assert "wdt:P31 wd:Q5" in query  # Instance of human
        assert "wdt:P106 wd:Q82955" in query  # Occupation: politician
        assert "SERVICE wikibase:label" in query
        # Query should not have LIMIT clause (handled by scraping code)
        assert "LIMIT" not in query
        
        # Check for extended fields
        assert "?birthDate" in query
        assert "?deathDate" in query
        assert "?nationality" in query
        assert "?position" in query
        assert "OPTIONAL" in query

    def test_extended_politicians_by_nationality_query_structure(self) -> None:
        """Test that nationality-filtered query has correct structure."""
        query = EXTENDED_POLITICIANS_BY_NATIONALITY_QUERY
        
        # Check for essential SPARQL elements
        assert "SELECT" in query
        assert "WHERE" in query
        assert "?person" in query
        assert "?personLabel" in query
        assert "wdt:P31 wd:Q5" in query  # Instance of human
        assert "wdt:P106 wd:Q82955" in query  # Occupation: politician
        assert "SERVICE wikibase:label" in query
        # Query should not have LIMIT clause (handled by scraping code)
        assert "LIMIT" not in query
        
        # Check for nationality filter
        assert "wdt:P27 wd:{nationality_qid}" in query
        assert "?nationality" in query

    def test_query_formatting_with_limit(self) -> None:
        """Test that queries can be formatted with manually added limits."""
        # Test basic query with manual limit
        formatted_query = BASIC_POLITICIANS_QUERY + " LIMIT 100"
        assert "LIMIT 100" in formatted_query
        
        # Test extended query with manual limit  
        formatted_query = EXTENDED_POLITICIANS_QUERY + " LIMIT 50"
        assert "LIMIT 50" in formatted_query

    def test_nationality_query_formatting(self) -> None:
        """Test that nationality query can be formatted with parameters."""
        # Format with Qatar's QID
        formatted_query = EXTENDED_POLITICIANS_BY_NATIONALITY_QUERY.format(
            nationality_qid="Q846"
        ) + " LIMIT 25"
        
        assert "wdt:P27 wd:Q846" in formatted_query
        assert "LIMIT 25" in formatted_query
        assert "{nationality_qid}" not in formatted_query
        assert "{limit}" not in formatted_query

    def test_queries_have_valid_sparql_syntax(self) -> None:
        """Test that queries have basic SPARQL syntax validity."""
        queries = [
            BASIC_POLITICIANS_QUERY,
            EXTENDED_POLITICIANS_QUERY,
            EXTENDED_POLITICIANS_BY_NATIONALITY_QUERY,
        ]
        
        for query in queries:
            # Check balanced braces
            open_braces = query.count("{")
            close_braces = query.count("}")
            assert open_braces == close_braces, f"Unbalanced braces in query: {query[:100]}..."
            
            # Check that SELECT comes before WHERE
            select_pos = query.find("SELECT")
            where_pos = query.find("WHERE")
            assert select_pos < where_pos, f"SELECT should come before WHERE in query: {query[:100]}..."
            
            # Check for proper SERVICE block
            if "SERVICE" in query:
                assert "wikibase:label" in query
                assert "bd:serviceParam" in query

    def test_queries_contain_required_variables(self) -> None:
        """Test that queries define all referenced variables."""
        # Basic query should define core variables
        basic_vars = re.findall(r'\?(\w+)', BASIC_POLITICIANS_QUERY)
        assert "person" in basic_vars
        assert "personLabel" in basic_vars
        assert "personDescription" in basic_vars
        
        # Extended query should define additional variables
        extended_vars = re.findall(r'\?(\w+)', EXTENDED_POLITICIANS_QUERY)
        assert "person" in extended_vars
        assert "birthDate" in extended_vars
        assert "nationality" in extended_vars
        assert "position" in extended_vars

    def test_queries_use_correct_property_codes(self) -> None:
        """Test that queries use correct Wikidata property codes."""
        queries = [
            BASIC_POLITICIANS_QUERY,
            EXTENDED_POLITICIANS_QUERY,
            EXTENDED_POLITICIANS_BY_NATIONALITY_QUERY,
        ]
        
        for query in queries:
            # P31 = instance of
            assert "wdt:P31" in query
            # P106 = occupation  
            assert "wdt:P106" in query
            # Q5 = human
            assert "wd:Q5" in query
            # Q82955 = politician
            assert "wd:Q82955" in query
            
        # Nationality-specific query should have P27 (country of citizenship)
        assert "wdt:P27" in EXTENDED_POLITICIANS_BY_NATIONALITY_QUERY

    def test_main_query_ties_occupation_to_person_before_union(self) -> None:
        """Test the Main query avoids a Cartesian product for bureaucracy occupations."""
        assert re.search(
            r"\?person\s+wdt:P106\s+\?occupation\s*\.\s*\{\s*VALUES\s+\?occupation",
            MAIN_QUERY,
            flags=re.DOTALL,
        )
        assert not re.search(
            r"\{\s*\?person\s+wdt:P106\s+\?occupation\s*\.\s*VALUES\s+\?occupation",
            MAIN_QUERY,
            flags=re.DOTALL,
        )

    def test_excel_scrape_queries_do_not_use_wdqs_label_service(self) -> None:
        """Test QLever-facing Excel scrape queries use explicit label lookups."""
        excel_scrape_queries = [
            MAIN_QUERY,
            DOB_POLITICIANS_QUERY,
            NATIONALITY_POLITICIANS_QUERY,
            ALIAS_POLITICIANS_QUERY,
            RESIDENCE_POLITICIANS_QUERY,
            CRIMINAL_POLITICIANS_QUERY,
            ROLE_POLITICIANS_QUERY,
            RCA_POLITICIANS_QUERY,
        ]

        for query in excel_scrape_queries:
            assert "SERVICE wikibase:label" not in query
