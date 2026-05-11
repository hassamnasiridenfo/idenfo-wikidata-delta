"""Wikidata-specific SPARQL utilities and query functions.

This module provides convenient functions for querying Wikidata's SPARQL endpoint
(WDQS - Wikidata Query Service) with common patterns and utilities.
"""
import logging                  # noqa: I001
from typing import Any

from structured_scraping.sparql_utils import (
    extract_bindings,
    query_sparql_endpoint_with_retry,
)

# Import filter functions for convenience
from .filters import (
    filter_by_birth_year,       # type: ignore # noqa: F401
    filter_by_position_date,    # type: ignore # noqa: F401
    filter_living_peps,         # type: ignore # noqa: F401
    filter_relevant_peps,       # type: ignore # noqa: F401
)

logger = logging.getLogger(__name__)

# Wikidata Query Service endpoint
WDQS_ENDPOINT = "https://query.wikidata.org/sparql"

# Default user agent for Wikidata queries (recommended by Wikidata)
DEFAULT_USER_AGENT = "structured-scraping/1.0.0 (https://github.com/Idenfo/structured-scraping/; solomon@idenfo.com)"

def query_wdqs(
    sparql: str,
    timeout: int | None = 30,
    user_agent: str | None = None,
) -> dict[str, Any]:
    """Run a SPARQL query against WDQS and return JSON results.

    Args:
        sparql (str): The SPARQL query string to execute.
        timeout (int | None, optional): Query timeout in seconds. Defaults to 30.
        user_agent (str | None, optional): Custom user agent string.
            Defaults to a standard user agent for this library.

    Returns:
        dict[str, Any]: The JSON results from the SPARQL query.

    Raises:
        SPARQLError: If the query execution fails.

    """
    if user_agent is None:
        user_agent = DEFAULT_USER_AGENT

    logger.info("Executing Wikidata SPARQL query")
    return query_sparql_endpoint_with_retry(
        endpoint_url=WDQS_ENDPOINT,
        query=sparql,
        return_format="json",
        timeout=timeout,
        user_agent=user_agent,
    )


def query_wdqs_simple(sparql: str, timeout: int | None = 30) -> list[dict[str, str]]:
    """Run a SPARQL query against WDQS and return simplified results.

    This function automatically parses the JSON results into a list of
    dictionaries for easier consumption.

    Args:
        sparql (str): The SPARQL query string to execute.
        timeout (int | None, optional): Query timeout in seconds. Defaults to 30.

    Returns:
        list[dict[str, str]]: A list of dictionaries containing the parsed results.
            Each dictionary maps variable names to their string values.

    Raises:
        SPARQLError: If the query execution fails.

    """
    results = query_wdqs(sparql, timeout=timeout)
    return extract_bindings(results)


def get_entity_info(entity_id: str, language: str = "en") -> list[dict[str, str]]:
    """Get basic information about a Wikidata entity.

    Args:
        entity_id (str): The Wikidata entity ID (e.g., "Q146" for "cat").
        language (str, optional): The language code for labels. Defaults to "en".

    Returns:
        list[dict[str, str]]: Basic information about the entity including
            label, description, and aliases.

    Raises:
        SPARQLError: If the query execution fails.

    """
    sparql = f"""
    SELECT ?item ?itemLabel ?itemDescription WHERE {{
      VALUES ?item {{ wd:{entity_id} }}
      SERVICE wikibase:label {{
        bd:serviceParam wikibase:language "{language}".
      }}
    }}
    """
    return query_wdqs_simple(sparql)


def search_entities_by_label(
    label: str,
    language: str = "en",
    limit: int = 10,
) -> list[dict[str, str]]:
    """Search for Wikidata entities by label.

    Args:
        label (str): The label to search for.
        language (str, optional): The language code for labels. Defaults to "en".
        limit (int, optional): Maximum number of results to return. Defaults to 10.

    Returns:
        list[dict[str, str]]: A list of matching entities with their labels and descriptions.

    Raises:
        SPARQLError: If the query execution fails.

    """
    sparql = f"""
    SELECT ?item ?itemLabel ?itemDescription WHERE {{
      ?item rdfs:label "{label}"@{language} .
      SERVICE wikibase:label {{
        bd:serviceParam wikibase:language "{language}".
      }}
    }}
    LIMIT {limit}
    """
    return query_wdqs_simple(sparql)


def get_instances_of(
    class_id: str,
    language: str = "en",
    limit: int = 100,
) -> list[dict[str, str]]:
    """Get instances of a specific Wikidata class.

    Args:
        class_id (str): The Wikidata class ID (e.g., "Q146" for "cat").
        language (str, optional): The language code for labels. Defaults to "en".
        limit (int, optional): Maximum number of results to return. Defaults to 100.

    Returns:
        list[dict[str, str]]: A list of instances with their labels.

    Raises:
        SPARQLError: If the query execution fails.

    """
    sparql = f"""
    SELECT ?item ?itemLabel WHERE {{
      ?item wdt:P31 wd:{class_id} .
      SERVICE wikibase:label {{
        bd:serviceParam wikibase:language "{language}".
      }}
    }}
    LIMIT {limit}
    """
    return query_wdqs_simple(sparql)
