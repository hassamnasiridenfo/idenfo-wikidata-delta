"""Structured Scraping - A Python package for structured web scraping."""

from .sparql_utils import (
    batched_sparql_query,
    batched_sparql_query_to_csv,
    count_sparql_query,
    query_and_save_to_csv,
    save_results_to_csv,
    save_sparql_results_to_csv,
)
from .wikidata.countries import get_country_id, get_country_name, list_supported_countries
from .wikidata.filters import filter_relevant_peps
from .wikidata.scrapers import (
    PEPScraperConfig,
    count_country_politicians,
    scrape_country_politicians_by_decade,
    scrape_living_politicians,
)

__version__ = "1.0.0"
__author__ = "Sol Warsop"
__email__ = "solomon@idenfo.com"

__all__ = [
    "PEPScraperConfig",
    "batched_sparql_query",
    "batched_sparql_query_to_csv",
    "count_country_politicians",
    "count_sparql_query",
    "filter_relevant_peps",
    "get_country_id",
    "get_country_name",
    "list_supported_countries",
    "query_and_save_to_csv",
    "save_results_to_csv",
    "save_sparql_results_to_csv",
    "scrape_country_politicians_by_decade",
    "scrape_living_politicians",
]
