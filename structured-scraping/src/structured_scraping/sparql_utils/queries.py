"""SPARQL query transformation and parsing utilities.

This module provides functions for transforming and parsing SPARQL queries,
including conversion to count queries and query structure analysis.
"""

import re


def convert_to_count_query(query: str) -> str:
    """Convert a SELECT query to a COUNT query.
    
    This function modifies a SPARQL SELECT query to return only the count
    of matching results instead of the actual results.
    
    Args:
        query (str): The original SPARQL SELECT query.
        
    Returns:
        str: The modified query that returns a count.
        
    Raises:
        ValueError: If the query format is not supported for counting.
        
    """
    # Remove SPARQL comments (lines starting with #)
    lines = query.split("\n")
    cleaned_lines: list[str] = []
    for line in lines:
        # Remove inline comments
        cleaned_line = line.split("#")[0].strip() if "#" in line else line.strip()
        if cleaned_line:  # Only keep non-empty lines
            cleaned_lines.append(cleaned_line)
    
    cleaned_query = " ".join(cleaned_lines)
    
    # Remove extra whitespace and normalize
    normalized_query = re.sub(r"\s+", " ", cleaned_query.strip())
    
    # Find the SELECT clause and the WHERE clause
    select_match = re.search(r"SELECT\s+(.+?)\s+WHERE\s*\{", normalized_query, re.IGNORECASE | re.DOTALL)
    if not select_match:
        raise ValueError("Could not find SELECT...WHERE pattern in query")
    
    # Find the WHERE clause content (everything from WHERE onwards)
    where_start = normalized_query.upper().find("WHERE")
    if where_start == -1:
        raise ValueError("Could not find WHERE clause in query")
    
    # Extract everything from WHERE onwards
    where_and_after = normalized_query[where_start:]
    
    # Remove SERVICE wikibase:label clause - not needed for counting and can cause malformed queries
    # This removes the entire SERVICE block including nested braces
    service_pattern = r"SERVICE\s+wikibase:label\s*\{\s*[^{}]*\}\s*"
    where_and_after = re.sub(service_pattern, "", where_and_after, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove LIMIT clause if present (for counting, we want total count regardless of original limit)
    where_and_after = re.sub(r"\s+LIMIT\s+\d+\s*$", "", where_and_after, flags=re.IGNORECASE)
    
    # Remove ORDER BY clause if present (not needed for counting)
    where_and_after = re.sub(r"\s+ORDER\s+BY\s+[^}]+(?=\s*$|\s*LIMIT)", "", where_and_after, flags=re.IGNORECASE)
    
    # Clean up any extra whitespace
    where_and_after = re.sub(r"\s+", " ", where_and_after).strip()
    
    # Construct the count query
    return f"SELECT (COUNT(*) AS ?count) {where_and_after}"


def create_count_query_from_main(main_query: str) -> str:
    """Convert a main SPARQL query to a count query using the same WHERE clause.
    
    This ensures the count uses exactly the same logic as the main query,
    maintaining perfect consistency between counting and scraping operations.
    This is a fundamental principle - counts should always use the same query
    logic as the actual data retrieval.
    
    Args:
        main_query (str): The main SPARQL query with SELECT and WHERE clauses
        
    Returns:
        str: A count query using the same WHERE clause as the main query
        
    Raises:
        ValueError: If the main query doesn't have a valid WHERE clause
        
    """
    # Extract the WHERE clause from the main query
    where_start = main_query.find("WHERE {")
    if where_start == -1:
        raise ValueError("Could not find WHERE clause in main query")
    
    # Find the matching closing brace for the WHERE clause
    brace_count = 0
    where_content_start = where_start + len("WHERE {")
    where_end = where_content_start
    
    for i, char in enumerate(main_query[where_content_start:], where_content_start):
        if char == "{":
            brace_count += 1
        elif char == "}":
            if brace_count == 0:
                where_end = i
                break
            brace_count -= 1
    
    where_clause = main_query[where_start:where_end + 1]
    
    # Extract SELECT portion and convert to simple SELECT for subquery
    select_start = main_query.find("SELECT")
    if select_start == -1:
        raise ValueError("Could not find SELECT clause in main query")
    
    select_portion = main_query[select_start:where_start].strip()
    # Remove DISTINCT if present and simplify SELECT for counting
    simplified_select = select_portion.replace("SELECT DISTINCT", "SELECT").replace("SELECT", "SELECT DISTINCT")
    
    # Create count query using the same WHERE clause
    return f"""
SELECT (COUNT(*) AS ?count) WHERE {{
  {{
    {simplified_select}
    {where_clause}
  }}
}}
"""
