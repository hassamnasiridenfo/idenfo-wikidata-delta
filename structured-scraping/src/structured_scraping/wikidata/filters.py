"""Wikidata-specific filtering utilities for PEP data."""

import re
from datetime import datetime


def filter_relevant_peps( # noqa: C901 # Function complexity is high, but necessary for detailed filtering
    results: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Filter PEP records to include only relevant, living individuals.

    Applies the following criteria:
    1. Exclude any record with a 'deathDate'.
    2. If 'birthDate' is present, include only if year >= 1925.
    3. If 'birthDate' is missing, but position 'startTime' or 'endTime' is present,
       include only if any such date's year >= 1925.
    4. Exclude any record missing all of 'deathDate', 'birthDate', 'startTime', and 'endTime'.

    Args:
        results (list[dict[str, str]]): List of PEP result dicts with optional date fields.

    Returns:
        list[dict[str, str]]: Filtered list of PEP records matching the criteria.

    Raises:
        ValueError: If parsing a date string fails due to incorrect format.

    """
    # Constant for minimum year threshold
    min_year_threshold = 1925

    def parse_year(date_str: str | None) -> int | None:
        if not date_str:
            return None
        
        try:
            # First try to extract year with regex
            year_match = re.search(r"\b(19|20)\d{2}\b", date_str)
            if year_match:
                return int(year_match.group())
            
            # Try simple date format
            if len(date_str) == 10 and date_str.count("-") == 2:  # YYYY-MM-DD # noqa: PLR2004 # Magic vals for date fmt
                return int(date_str[:4])
            
            # Try full ISO format with Z suffix
            if date_str.endswith("Z"):
                dt = datetime.strptime(date_str.replace("Z", "+00:00"), "%Y-%m-%dT%H:%M:%S%z")
                return dt.year
                
            raise ValueError(f"Cannot parse date: {date_str}")
            
        except (ValueError, IndexError) as e:
            raise ValueError(f"Invalid date format: {date_str}") from e

    filtered: list[dict[str, str]] = []
    for record in results:
        # Exclude deceased
        if record.get("deathDate"):
            continue
        # Check birthDate
        birth_year = parse_year(record.get("birthDate"))
        if birth_year is not None:
            if birth_year < min_year_threshold:
                continue
            filtered.append(record)
            continue
        # No birthDate, check position dates
        start_year = parse_year(record.get("startTime"))
        end_year = parse_year(record.get("endTime"))
        # Exclude if both dates are missing
        if start_year is None and end_year is None:
            continue
        # Exclude if all known years are before min_year_threshold
        known_years = [y for y in (start_year, end_year) if y is not None]
        if all(y < min_year_threshold for y in known_years):
            continue
        filtered.append(record)
    return filtered


def filter_living_peps(results: list[dict[str, str]]) -> list[dict[str, str]]:
    """Filter PEP records to include only living individuals.
    
    This is a simpler filter that only excludes records with death dates.
    
    Args:
        results (list[dict[str, str]]): List of PEP result dicts.
        
    Returns:
        list[dict[str, str]]: Filtered list containing only living individuals.
        
    """
    return [record for record in results if not record.get("deathDate")]


def filter_by_birth_year(
    results: list[dict[str, str]],
    min_year: int = 1900,
    max_year: int | None = None,
) -> list[dict[str, str]]:
    """Filter PEP records by birth year range.
    
    Args:
        results (list[dict[str, str]]): List of PEP result dicts.
        min_year (int, optional): Minimum birth year (inclusive). Defaults to 1900.
        max_year (int | None, optional): Maximum birth year (inclusive). Defaults to None.
        
    Returns:
        list[dict[str, str]]: Filtered list of records within the birth year range.
        
    """
    def get_birth_year(record: dict[str, str]) -> int | None:
        birth_date = record.get("birthDate")
        if not birth_date:
            return None
        try:
            dt = datetime.strptime(birth_date.replace("Z", "+00:00"), "%Y-%m-%dT%H:%M:%S%z")
        except ValueError:
            return None
        else:
            return dt.year

    filtered: list[dict[str, str]] = []
    for record in results:
        birth_year = get_birth_year(record)
        if birth_year is None:
            continue  # Skip records without birth dates
        if birth_year < min_year:
            continue
        if max_year is not None and birth_year > max_year:
            continue
        filtered.append(record)
    
    return filtered


def filter_by_position_date(
    results: list[dict[str, str]],
    min_year: int = 1900,
    date_field: str = "startTime",
) -> list[dict[str, str]]:
    """Filter PEP records by position date.
    
    Args:
        results (list[dict[str, str]]): List of PEP result dicts.
        min_year (int, optional): Minimum year for position dates. Defaults to 1900.
        date_field (str, optional): Field to check ('startTime' or 'endTime'). Defaults to 'startTime'.
        
    Returns:
        list[dict[str, str]]: Filtered list of records with positions after min_year.
        
    """
    def get_position_year(record: dict[str, str]) -> int | None:
        position_date = record.get(date_field)
        if not position_date:
            return None
        try:
            dt = datetime.strptime(position_date.replace("Z", "+00:00"), "%Y-%m-%dT%H:%M:%S%z")
        except ValueError:
            return None
        else:
            return dt.year

    filtered: list[dict[str, str]] = []
    for record in results:
        position_year = get_position_year(record)
        if position_year is None:
            continue  # Skip records without position dates
        if position_year >= min_year:
            filtered.append(record)
    
    return filtered
