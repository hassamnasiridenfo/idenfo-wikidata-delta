#!/usr/bin/env python3
"""Example script demonstrating Wikidata SPARQL queries.

This script shows how to use the structured_scraping library to query Wikidata
using SPARQL queries.
"""

from structured_scraping.wikidata import (
    get_entity_info,
    get_instances_of,
    query_wdqs_simple,
    search_entities_by_label,
)
from structured_scraping.wikidata.queries import CATS_QUERY


def main() -> None:
    """Run example Wikidata queries."""
    print("=== Wikidata SPARQL Example Queries ===\n")
    
    # Example 1: Get instances of cats using a predefined query
    print("1. Getting instances of cats using predefined query:")
    try:
        cats = query_wdqs_simple(CATS_QUERY)
        for cat in cats[:5]:  # Show first 5 results
            print(f"  - {cat.get('itemLabel', 'N/A')}")
        print(f"  ... and {len(cats) - 5} more\n")
    except Exception as e:
        print(f"  Error: {e}\n")
    
    # Example 2: Get entity information for "cat" (Q146)
    print("2. Getting information about cats (Q146):")
    try:
        cat_info = get_entity_info("Q146")
        for info in cat_info:
            print(f"  - {info.get('itemLabel', 'N/A')}: {info.get('itemDescription', 'N/A')}")
        print()
    except Exception as e:
        print(f"  Error: {e}\n")
    
    # Example 3: Search for entities by label
    print("3. Searching for entities with 'python' in the label:")
    try:
        python_entities = search_entities_by_label("python", limit=5)
        for entity in python_entities:
            print(f"  - {entity.get('itemLabel', 'N/A')}: {entity.get('itemDescription', 'N/A')}")
        print()
    except Exception as e:
        print(f"  Error: {e}\n")
    
    # Example 4: Get instances of programming languages (Q9143)
    print("4. Getting programming languages:")
    try:
        languages = get_instances_of("Q9143", limit=10)
        for lang in languages:
            print(f"  - {lang.get('itemLabel', 'N/A')}")
        print()
    except Exception as e:
        print(f"  Error: {e}\n")


if __name__ == "__main__":
    main()
