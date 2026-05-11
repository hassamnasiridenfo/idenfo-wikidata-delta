"""Tests for the sparql_utils.queries module."""

import pytest

from structured_scraping.sparql_utils.queries import (
    convert_to_count_query,
    create_count_query_from_main,
)


class TestConvertToCountQuery:
    """Test the convert_to_count_query function."""

    def test_simple_select_query(self) -> None:
        """Test conversion of a simple SELECT query."""
        query = "SELECT ?s ?p ?o WHERE { ?s ?p ?o }"
        
        result = convert_to_count_query(query)
        
        assert "SELECT (COUNT(*) AS ?count)" in result
        assert "WHERE { ?s ?p ?o }" in result

    def test_query_with_distinct(self) -> None:
        """Test conversion of a query with DISTINCT."""
        query = "SELECT DISTINCT ?person WHERE { ?person a foaf:Person }"
        
        result = convert_to_count_query(query)
        
        assert "SELECT (COUNT(*) AS ?count)" in result
        assert "WHERE { ?person a foaf:Person }" in result

    def test_query_with_limit(self) -> None:
        """Test that LIMIT clause is removed in count query."""
        query = "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 100"
        
        result = convert_to_count_query(query)
        
        assert "LIMIT" not in result
        assert "SELECT (COUNT(*) AS ?count)" in result

    def test_query_with_order_by(self) -> None:
        """Test that ORDER BY clause is removed in count query."""
        query = "SELECT ?s ?p ?o WHERE { ?s ?p ?o } ORDER BY ?s"
        
        result = convert_to_count_query(query)
        
        assert "ORDER BY" not in result
        assert "SELECT (COUNT(*) AS ?count)" in result

    def test_query_with_service_wikibase_label(self) -> None:
        """Test that SERVICE wikibase:label clause is removed."""
        query = """
        SELECT ?item ?itemLabel WHERE {
            ?item wdt:P31 wd:Q5 .
            SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
        }
        """
        
        result = convert_to_count_query(query)
        
        assert "SERVICE wikibase:label" not in result
        assert "SELECT (COUNT(*) AS ?count)" in result

    def test_query_with_comments(self) -> None:
        """Test that comments are properly handled."""
        query = """
        # This is a comment
        SELECT ?s ?p ?o WHERE {
            ?s ?p ?o . # inline comment
        }
        """
        
        result = convert_to_count_query(query)
        
        assert "#" not in result
        assert "SELECT (COUNT(*) AS ?count)" in result

    def test_invalid_query_no_select(self) -> None:
        """Test that query without SELECT raises ValueError."""
        query = "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }"
        
        with pytest.raises(ValueError, match="Could not find SELECT...WHERE pattern"):
            convert_to_count_query(query)

    def test_invalid_query_no_where(self) -> None:
        """Test that query without WHERE raises ValueError."""
        query = "SELECT ?s ?p ?o"
        
        with pytest.raises(ValueError, match="Could not find SELECT...WHERE pattern in query"):
            convert_to_count_query(query)

    def test_complex_nested_query(self) -> None:
        """Test conversion of complex nested query."""
        query = """
        SELECT ?person ?birthPlace WHERE {
            ?person wdt:P31 wd:Q5 .
            ?person wdt:P19 ?birthPlace .
            OPTIONAL {
                ?person wdt:P570 ?deathDate .
                FILTER(?deathDate > "2000-01-01"^^xsd:date)
            }
        }
        """
        
        result = convert_to_count_query(query)
        
        assert "SELECT (COUNT(*) AS ?count)" in result
        assert "OPTIONAL" in result
        assert "FILTER" in result


class TestCreateCountQueryFromMain:
    """Test the create_count_query_from_main function."""

    def test_simple_main_query(self) -> None:
        """Test creating count query from simple main query."""
        main_query = """
        SELECT DISTINCT ?politician ?politicianLabel ?countryLabel WHERE {
            ?politician wdt:P31 wd:Q5 .
            ?politician wdt:P27 ?country .
        }
        """
        
        result = create_count_query_from_main(main_query)
        
        assert "SELECT (COUNT(*) AS ?count) WHERE {" in result
        assert "SELECT DISTINCT ?politician ?politicianLabel ?countryLabel" in result
        assert "?politician wdt:P31 wd:Q5" in result

    def test_main_query_with_nested_braces(self) -> None:
        """Test main query with nested braces in WHERE clause."""
        main_query = """
        SELECT ?item WHERE {
            ?item wdt:P31 wd:Q5 .
            OPTIONAL {
                ?item wdt:P570 ?death .
            }
        }
        """
        
        result = create_count_query_from_main(main_query)
        
        assert "SELECT (COUNT(*) AS ?count) WHERE {" in result
        assert "OPTIONAL {" in result
        assert "?item wdt:P570 ?death" in result

    def test_invalid_main_query_no_where(self) -> None:
        """Test that main query without WHERE clause raises ValueError."""
        main_query = "SELECT ?s ?p ?o"
        
        with pytest.raises(ValueError, match="Could not find WHERE clause"):
            create_count_query_from_main(main_query)

    def test_invalid_main_query_no_select(self) -> None:
        """Test that main query without SELECT clause raises ValueError."""
        main_query = "WHERE { ?s ?p ?o }"
        
        with pytest.raises(ValueError, match="Could not find SELECT clause"):
            create_count_query_from_main(main_query)

    def test_main_query_with_service_block(self) -> None:
        """Test main query with SERVICE block preservation."""
        main_query = """
        SELECT ?item ?itemLabel WHERE {
            ?item wdt:P31 wd:Q5 .
            SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
        }
        """
        
        result = create_count_query_from_main(main_query)
        
        # The SERVICE block should be preserved in the main query
        assert "SERVICE wikibase:label" in result
        assert "SELECT (COUNT(*) AS ?count) WHERE {" in result
