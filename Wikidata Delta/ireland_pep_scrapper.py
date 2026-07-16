"""Utilities to convert PEP exports into a 44-column Ireland template."""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import string
import sys
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:

    from collections.abc import Callable

BASE_DIR = Path(__file__).parent
RAW_DIR = BASE_DIR / "ie_gen_excels"
CLEANED_DIR = BASE_DIR / "ie_gen_excels"
UTILS_DIR = BASE_DIR

# Ensure directories exist
RAW_DIR.mkdir(parents=True, exist_ok=True)
CLEANED_DIR.mkdir(parents=True, exist_ok=True)
# ============================================
# LOGGING SETUP (Scraper-specific log file)
# ============================================

#  PATHS
RAW_FILE_PATH = os.path.join(RAW_DIR, "pep_ireland_living_relevant_raw.xlsx")
CLEAN_XLSX   = os.path.join(CLEANED_DIR, "pep_ireland_living_relevant_cleaned.xlsx")
RCA_FILE_PATH = os.path.join(CLEANED_DIR, "pep_ireland_living_relevant_rca_lookup.xlsx")
COUNTRY_FILE = os.path.join(UTILS_DIR, "Updated CountryList.xlsx")
LOG_FILE = BASE_DIR / "ie_gen_excels"/ "ie_pep_gen.log"



logger = logging.getLogger("Ireland_PEP_Scrapper")
if not logger.hasHandlers():
    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(LOG_FILE)
    formatter = logging.Formatter(
        "\n%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%d-%m-%Y %I:%M:%S %p",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


RELATIONSHIP_TYPE_MAP: dict[str, str] = {
    "FatherLabel": "Father",
    "MotherLabel": "Mother",
    "SiblingLabel": "Sibling",
    "SpouseLabel": "Partner",
    "ChildLabel": "Child",
    "RelativeLabel": "Relative",
    "SignificantPersonLabel": "Associate",
}


EXCLUDED_RELATIONSHIP_COLUMNS: set[str] = {"fatherlabel", "father"}
EXCLUDED_RELATIONSHIP_LABELS: set[str] = {"Father"}


EXTRA_INFORMATION_PREFIX_CONFIG: list[tuple[str, list[str]]] = [
    ("Educated At:", ["educatedatlabel", "educatedat"]),
    ("Work Location:", ["worklocationlabel", "worklocation"]),
    ("Academic Degree:", ["academicdegreelabel", "academicdegree"]),
    ("Affiliation:", ["affiliationstringlabel", "affiliationstring"]),
    ("Reference ID:", ["id", "ID"]),
]


STATIC_COLUMN_VALUES: dict[str, str | int | float] = {
    "Source List": "Idenfo",
    "Category": "General Ireland",
    "List Category": "Politically Exposed Person",
    "List Type": "Individual",
    "Scraper Tag": "ie_gen",
    "Status": 1,
}


STRUCTURED_COLUMN_DEFAULT_PLACEHOLDERS: dict[str, str] = {
    "Alias": "[]",
    "Alias Type": "[]",
    "Date of Birth": "[]",
    "Designation": "[]",
    "Relation With": "[]",
    "Relationship Type": "[]",
    "Start Date": "[]",
    "End Date": "[]",
    "Extra Information": "{}",
    "ID Type": "[]",
    "ID Number": "[]",
    "Street": "[]",
    "City": "[]",
    "State": "[]",
    "Country of Residence": "[]",
    "ZIP": "[]",
    "Other Details": "[]",
}


ADDRESS_LIST_COLUMNS: tuple[str, ...] = (
    "D Type",
    "ID Number",
    "Street",
    "City",
    "State",
    "Country of Residence",
    "ZIP",
    "Other Details",
)


LIST_OUTPUT_COLUMNS: tuple[str, ...] = (
    "Alias",
    "Alias Type",
    "Date of Birth",
    "Designation",
    "Relation With",
    "Relationship Type",
    "Start Date",
    "End Date",
    "ID Type",
    "ID Number",
    "Street",
    "City",
    "State",
    "Country of Residence",
    "ZIP",
    "Other Details",
    "Primary Address",
    "Primary Occupation",
    "Nationality",
)
def get_standard_logger_message(func_name, err, message):
    return f"""{func_name}| Error: {err} Message: {message}"""


def _capitalise_first_character(text: str) -> str:
    """Ensure the first alphabetical character of a string is uppercase.

    Args:
        text (str): Input string requiring capitalisation.

    Returns:
        str: String with its first alphabetical character converted to uppercase.

    """
    if not text:
        return text

    stripped = text.lstrip()
    if not stripped:
        return text.strip()

    capitalised = stripped[0].upper() + stripped[1:]
    leading_length = len(text) - len(stripped)
    if leading_length == 0:
        return capitalised
    return text[:leading_length] + capitalised


ALIAS_COLUMN_TYPE_MAP: dict[str, str] = {
    "aka": "Also Known As",
    "nativename": "Also Known As",
    "birthname": "Also Known As",
    "nonenglishlabel": "Also Known As",
}


COUNTRY_LIST_FILENAME = "Updated CountryList.xlsx"
COUNTRY_LIST_TITLE_COLUMNS: tuple[str, ...] = (
    "Country Title 1",
    "Country Title 2",
    "Country Title 3",
)
COUNTRY_LIST_NATIONALITY_COLUMN = "Nationality"


def _format_bracketed_entries(entries: list[str]) -> str | None:
    """Format a list of entries using the bracketed string notation.

    Args:
        entries (list[str]): Entries to format.

    Returns:
        str | None: Bracketed string representation or ``None`` when empty.

    """
    cleaned = [entry.strip() for entry in entries if entry and entry.strip()]
    if not cleaned:
        return None
    capitalised_entries = [_capitalise_first_character(entry) for entry in cleaned]
    return json.dumps(capitalised_entries, ensure_ascii=False, separators=(",", ":"))


def _safe_sheet(sheets: dict[str, pd.DataFrame], name: str) -> pd.DataFrame:
    """Return a sheet by name, falling back to an empty DataFrame if missing.

    Args:
        sheets (dict[str, pd.DataFrame]): Mapping of sheet names to dataframes.
        name (str): Name of the sheet to retrieve.

    Returns:
        pd.DataFrame: The requested sheet or an empty dataframe if unavailable.

    """
    return sheets.get(name, pd.DataFrame())


def _normalise_id_column(frame: pd.DataFrame) -> pd.DataFrame:
    """Coerce the ID column to strings while preserving missing values.

    Args:
        frame (pd.DataFrame): Dataframe that may contain an ``ID`` column.

    Returns:
        pd.DataFrame: Dataframe with ``ID`` coerced to pandas ``string`` dtype.

    """
    if frame.empty or "ID" not in frame.columns:
        return frame

    normalised = frame.copy()
    normalised["ID"] = normalised["ID"].astype("string")
    missing_mask = frame["ID"].isna()
    normalised.loc[missing_mask, "ID"] = pd.NA
    return normalised


def _collect_unique_ids(frames: list[pd.DataFrame]) -> list[str]:
    """Collect all unique string IDs present across the provided frames.

    Args:
        frames (list[pd.DataFrame]): Dataframes potentially containing ``ID`` columns.

    Returns:
        list[str]: Ordered list of unique identifiers as strings.

    """
    seen: set[str] = set()
    ordered: list[str] = []
    for frame in frames:
        if frame.empty or "ID" not in frame.columns:
            continue
        for identifier in frame["ID"]:
            if pd.isna(identifier):
                continue
            identifier_str = str(identifier)
            if identifier_str not in seen:
                seen.add(identifier_str)
                ordered.append(identifier_str)
    return ordered


def _map_single_value(
    frame: pd.DataFrame,
    key_column: str,
    value_column: str,
    value_transform: Callable[[object], str | None] | None = None,
) -> dict[str, str]:
    """Build a mapping from a key column to a single value column.

    Args:
        frame (pd.DataFrame): Source dataframe containing the relevant columns.
        key_column (str): Column whose values should be treated as keys.
        value_column (str): Column whose values should be treated as values.
        value_transform (Callable[[object], str | None] | None, optional): Optional
            callable used to normalise the value before insertion into the mapping.

    Returns:
        dict[str, str]: Mapping from keys to values, excluding missing pairs.

    """
    if (
        frame.empty
        or key_column not in frame.columns
        or value_column not in frame.columns
    ):
        return {}

    subset = (
        frame[[key_column, value_column]]
        .dropna(subset=[key_column, value_column])
        .copy()
    )
    if subset.empty:
        return {}

    subset[key_column] = subset[key_column].astype(str)

    mapping: dict[str, str] = {}
    for key, raw_value in zip(subset[key_column], subset[value_column], strict=True):
        candidate_value = (
            raw_value if value_transform is None else value_transform(raw_value)
        )
        if candidate_value is None:
            continue
        candidate_text = (
            candidate_value.strip()
            if isinstance(candidate_value, str)
            else str(candidate_value).strip()
        )
        if candidate_text:
            mapping[key] = candidate_text

    return mapping


def _normalise_birth_date_value(raw_value: object) -> str | None:
    """Convert a raw birth date value into ``YYYY-MM-DD`` format.

    Args:
        raw_value (object): Original birth date entry from the DOB sheet.

    Returns:
        str | None: Normalised ISO date string or ``None`` when conversion fails.

    """
    if raw_value is None:
        return None

    candidate_value: object | None
    if isinstance(raw_value, str):
        trimmed = raw_value.strip()
        if not trimmed:
            candidate_value = None
        else:
            match = re.search(r"\d{4}-\d{2}-\d{2}", trimmed)
            candidate_value = match.group(0) if match else trimmed.strip('"[]')
    else:
        candidate_value = raw_value

    if candidate_value in {None, ""}:
        return None

    try:
        parsed = pd.to_datetime(candidate_value, errors="coerce")  # type: ignore[arg-type] # pandas accepts scalar inputs when coercing to datetime
    except (TypeError, ValueError):
        return None

    if isinstance(parsed, pd.Series):
        squeezed = parsed.squeeze()
        parsed = squeezed.iloc[0] if isinstance(squeezed, pd.Series) else squeezed

    try:
        timestamp = pd.Timestamp(parsed)  # type: ignore[arg-type] # pandas coerces common datetime scalars to Timestamp
    except (TypeError, ValueError):
        return None

    if pd.isna(timestamp):
        return None

    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert(None)

    return _format_bracketed_entries([timestamp.date().isoformat()])


def _should_skip_party_prefix(party_name: str) -> bool:
    """Return ``True`` when a political party should not receive a prefix.

    Args:
        party_name (str): Original party label sourced from the role sheet.

    Returns:
        bool: ``True`` when the party name contains an exempt substring.

    """
    lowered = party_name.lower()
    exempt_terms = (
        "social democrats",
        "progressive democrats",
        "independent politician",
    )
    return any(term in lowered for term in exempt_terms)


def _collect_party_designations(pep_role: pd.DataFrame) -> dict[str, list[str]]:
    """Collect political party designations keyed by identifier.

    Args:
        pep_role (pd.DataFrame): Role sheet dataframe.

    Returns:
        dict[str, list[str]]: Mapping of identifier to ordered designation entries.

    """
    collected: dict[str, list[str]] = {}
    if (
        pep_role.empty
        or "ID" not in pep_role.columns
        or "politicalPartyLabel" not in pep_role.columns
    ):
        return collected

    subset = (
        pep_role[["ID", "politicalPartyLabel"]]
        .dropna(subset=["ID", "politicalPartyLabel"])
        .astype({"ID": str})
    )
    if subset.empty:
        return collected

    for identifier, raw_party in zip(
        subset["ID"], subset["politicalPartyLabel"], strict=True
    ):
        flattened_party = _flatten_bracketed_value(raw_party)
        party_text = (
            flattened_party.strip()
            if isinstance(flattened_party, str)
            else str(raw_party).strip()
        )
        if not party_text:
            continue
        entry = (
            party_text
            if _should_skip_party_prefix(party_text)
            else f"Member of {party_text}"
        )
        entries = collected.setdefault(identifier, [])
        if entry not in entries:
            entries.append(entry)

    return collected


def _apply_political_party_designations(
    ireland_df: pd.DataFrame,
    pep_role: pd.DataFrame,
) -> pd.DataFrame:
    """Append political party entries to the ``Designation`` column.

    Args:
        ireland_df (pd.DataFrame): Ireland dataframe that may contain
            ``Designation`` values.
        pep_role (pd.DataFrame): Role sheet providing ``politicalPartyLabel``
            columns used to derive membership text.

    Returns:
        pd.DataFrame: Dataframe with ``Designation`` updated to include
        prefixed political party entries.

    """
    if ireland_df.empty or "ID" not in ireland_df.columns:
        return ireland_df

    party_map = _collect_party_designations(pep_role)
    if not party_map:
        if "Designation" not in ireland_df.columns:
            updated = ireland_df.copy()
            updated["Designation"] = None
            return updated
        return ireland_df

    updated = ireland_df.copy()
    if "Designation" not in updated.columns:
        updated["Designation"] = None

    for row_index, identifier in enumerate(updated["ID"]):
        if pd.isna(identifier):
            continue
        party_entries = party_map.get(str(identifier))
        if not party_entries:
            continue
        updated.loc[row_index, "Designation"] = _merge_relation_entries(
            updated.loc[row_index, "Designation"],
            party_entries,
        )

    return updated


def _apply_case_details_column(
    ireland_df: pd.DataFrame,
    pep_case: pd.DataFrame,
) -> pd.DataFrame:
    """Populate ``Case Details`` with conviction and detention information.

    Args:
        ireland_df (pd.DataFrame): Ireland dataframe shaped to the template.
        pep_case (pd.DataFrame): Case details sheet containing conviction and
            detention information keyed by ``ID``.

    Returns:
        pd.DataFrame: Dataframe with ``Case Details`` updated to include
        prefixed conviction and detention entries when available.

    """
    if ireland_df.empty or "ID" not in ireland_df.columns:
        return ireland_df

    prefix_config = [
        ("Convicted of:", ["convictedoflabel", "convictedof"]),
        ("Place of Detention:", ["placeofdetentionlabel", "placeofdetention"]),
    ]
    entries_by_identifier = _collect_prefixed_extra_information(
        [pep_case],
        prefix_config,
    )
    if not entries_by_identifier:
        if "Case Details" not in ireland_df.columns:
            ireland_df["Case Details"] = None
        return ireland_df

    updated = ireland_df.copy()
    if "Case Details" not in updated.columns:
        updated["Case Details"] = None

    for row_index, identifier in enumerate(updated["ID"]):
        if pd.isna(identifier):
            continue
        entries = entries_by_identifier.get(str(identifier))
        if not entries:
            continue
        updated.loc[row_index, "Case Details"] = _merge_relation_entries(
            updated.loc[row_index, "Case Details"],
            entries,
        )

    return updated


def _map_grouped_values(
    frame: pd.DataFrame,
    key_column: str,
    value_column: str,
    separator: str = ", ",
) -> dict[str, str]:
    """Group values by key and join them with the provided separator.

    Args:
        frame (pd.DataFrame): Source dataframe containing the relevant columns.
        key_column (str): Column whose values should be grouped.
        value_column (str): Column whose values should be concatenated per group.
        separator (str, optional): Separator inserted between grouped values. Defaults to ", ".

    Returns:
        dict[str, str]: Mapping from keys to concatenated value strings.

    """
    if (
        frame.empty
        or key_column not in frame.columns
        or value_column not in frame.columns
    ):
        return {}

    prepared = (
        frame[[key_column, value_column]]
        .dropna(subset=[key_column, value_column])
        .astype({key_column: str, value_column: str})
    )
    if prepared.empty:
        return {}

    def _collapse(series: pd.Series) -> str:
        seen_values: set[str] = set()
        ordered_values: list[str] = []
        for value in series:
            if value not in seen_values:
                seen_values.add(value)
                ordered_values.append(value)
        return separator.join(ordered_values)

    grouped = prepared.groupby(key_column, dropna=False)[value_column].agg(_collapse)
    return grouped.to_dict()


def _normalise_designation_value(raw_value: object) -> str | None:
    """Serialise designation entries into a single bracketed list string.

    Args:
        raw_value (object): Original designation value prior to normalisation.

    Returns:
        str | None: Bracketed JSON-style list string or ``None`` when empty.

    Raises:
        None.

    """
    if _value_is_missing(raw_value):
        return None

    if isinstance(raw_value, str):
        trimmed_value = raw_value.strip()
        if not trimmed_value or trimmed_value in {"[]", "{}"}:
            return None

    entries = _normalise_relation_entries(raw_value)
    cleaned_entries: list[str] = []
    for entry in entries:
        stripped_entry = entry.strip()
        if not stripped_entry or stripped_entry in {"[]", "{}"}:
            continue
        cleaned_entries.append(stripped_entry)

    if not cleaned_entries:
        return None

    formatted = _format_bracketed_entries(cleaned_entries)
    return formatted if formatted is not None else None


def _extract_ascii_initial(token: str) -> str:
    """Return an ASCII initial for the supplied token, defaulting when absent.

    Args:
        token (str): Token extracted from a free-form name string.

    Returns:
        str: Uppercase ASCII initial. Defaults to ``"X"`` when the token lacks
            any ASCII alphabetic characters after normalisation.

    """
    if not token:
        return "X"

    base_initial = token[0]
    normalised = unicodedata.normalize("NFKD", base_initial)
    stripped = "".join(
        character for character in normalised if unicodedata.category(character) != "Mn"
    )
    ascii_letters = [
        character
        for character in stripped
        if character.isalpha() and character.isascii()
    ]
    if ascii_letters:
        return ascii_letters[0].upper()

    fallback = "".join(
        character
        for character in unicodedata.normalize("NFKD", token)
        if character.isalpha() and character.isascii()
    )
    if fallback:
        return fallback[0].upper()

    return "X"


def _initials_from_name(name: str) -> str:
    """Generate uppercase ASCII initials extracted from a free-form name string.

    Args:
        name (str): Free-form name value.

    Returns:
        str: Uppercase ASCII initials derived solely from the provided name.

    """
    if not name:
        return ""

    tokens = re.findall(r"[^\W\d_]+", name, flags=re.UNICODE)
    return "".join(_extract_ascii_initial(token) for token in tokens if token)


def _generate_combo(length: int = 5) -> str:
    """Generate a random alphanumeric string used in RCA identifiers.

    Args:
        length (int, optional): Length of the combo. Defaults to ``5``.

    Returns:
        str: Random alphanumeric string.

    """
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _extract_relation_entities(value: str) -> list[str]:
    """Extract individual relationship entity names from a bracketed string.

    Args:
        value (str): String potentially containing a JSON-style list of entities.

    Returns:
        list[str]: Extracted entity names.

    """
    matches = [
        match.strip() for match in re.findall(r'\["([^\"]+)"\]', value) if match.strip()
    ]
    if matches:
        return matches

    trimmed = value.strip()
    if trimmed.startswith("[") and trimmed.endswith("]"):
        trimmed = trimmed[1:-1].strip()
    trimmed = trimmed.strip('"').strip()
    return [trimmed] if trimmed else []


def _collect_parent_entities(subset: pd.DataFrame) -> list[tuple[str, str]]:
    """Collect pairs of parent identifiers and cleaned entity names.

    Args:
        subset (pd.DataFrame): Subset containing ``ID`` and relationship values.

    Returns:
        list[tuple[str, str]]: List of ``(parent_identifier, entity_name)`` pairs.

    """
    pairs: list[tuple[str, str]] = []
    for pep_id, relation_value in subset.itertuples(index=False):
        if pd.isna(pep_id):
            continue
        parent_identifier = str(pep_id)
        entities = _extract_relation_entities(str(relation_value)) or [
            str(relation_value)
        ]
        for raw_entity in entities:
            clean_entity = raw_entity.strip()
            if clean_entity:
                pairs.append((parent_identifier, clean_entity))
    return pairs


def _replace_alias_inner_quotes(value: str) -> tuple[str, bool]:
    """Convert internal double quotes to single quotes within an alias entry.

    Args:
        value (str): Alias text that may contain double quotation marks.

    Returns:
        tuple[str, bool]: Pair containing the normalised alias text and a flag
        indicating whether any replacements were applied.

    """
    normalised = value
    replacements_applied = False
    if '""' in normalised:
        normalised = normalised.replace('""', "'")
        replacements_applied = True
    if '"' in normalised:
        normalised = normalised.replace('"', "'")
        replacements_applied = True
    return normalised, replacements_applied


def _extract_alias_entries(raw_value: object) -> list[tuple[str, bool]]:
    """Extract alias entries while tracking quote replacements.

    Args:
        raw_value (object): Cell value sourced from an alias column.

    Returns:
        list[tuple[str, bool]]: Ordered alias entries paired with a boolean
        indicating whether double quotes were encountered and converted.

    """
    if not isinstance(raw_value, str):
        return []

    trimmed = raw_value.strip()
    if not trimmed or trimmed.lower() == "none":
        return []

    bracketed = re.findall(r'\["(.*?)"\]', trimmed)
    if bracketed:
        raw_entries = bracketed
    else:
        parts = re.split(r"[;,]", trimmed)
        cleaned_parts = [part.strip(' []"') for part in parts if part.strip(' []"')]
        if cleaned_parts:
            raw_entries = cleaned_parts
        else:
            stripped = trimmed.strip('[]"')
            raw_entries = [stripped] if stripped else []

    entries: list[tuple[str, bool]] = []
    for entry in raw_entries:
        cleaned = entry.strip()
        if not cleaned:
            continue
        normalised_entry, replacements_applied = _replace_alias_inner_quotes(cleaned)
        entries.append((normalised_entry, replacements_applied))

    return entries


def _normalise_alias_display_value(value: str) -> str:
    """Normalise alias text by removing special characters.

    Args:
        value (str): Raw alias value sourced from the workbook.

    Returns:
        str: Alias value with hyphens and apostrophes replaced by spaces while
        preserving non-ASCII letters and collapsing other punctuation.

    Raises:
        None.

    """
    stripped = value.strip()
    if not stripped:
        return ""

    substituted = stripped.replace("-", " ").replace("'", " ")
    normalised_chars = [
        character if (character.isalnum() or character.isspace()) else " "
        for character in substituted
    ]
    cleaned = "".join(normalised_chars)
    return " ".join(cleaned.split())


def _register_alias_entry(
    entries: list[str],
    types: list[str],
    alias_value: str,
    alias_type: str,
) -> None:
    """Append a cleaned alias value while avoiding duplicates.

    Args:
        entries (list[str]): Current alias values in order.
        types (list[str]): Alias types aligned with ``entries``.
        alias_value (str): Alias value to register.
        alias_type (str): Alias type associated with ``alias_value``.

    Returns:
        None.

    Raises:
        None.

    """
    cleaned_alias = _normalise_alias_display_value(alias_value)
    if not cleaned_alias:
        return

    if cleaned_alias in entries:
        existing_index = entries.index(cleaned_alias)
        if (
            types[existing_index] != "Original Script Name"
            and alias_type == "Original Script Name"
        ):
            types[existing_index] = "Original Script Name"
        return

    entries.append(cleaned_alias)
    types.append(alias_type)


def _character_is_latin(letter: str) -> bool:
    """Return ``True`` when the provided character belongs to the Latin script.

    Args:
        letter (str): Single-character string to classify.

    Returns:
        bool: ``True`` if the character is Latin; ``False`` otherwise.

    """
    if not letter:
        return False
    if letter.isascii():
        return letter.isalpha()
    try:
        return "LATIN" in unicodedata.name(letter)
    except ValueError:
        return False


def _has_non_latin_letters(value: str) -> bool:
    """Return ``True`` when the supplied text contains non-Latin characters.

    Args:
        value (str): Text to evaluate for script classification.

    Returns:
        bool: ``True`` if any alphabetic character is non-Latin; ``False`` otherwise.

    """
    if not value:
        return False
    for character in value:
        if not character.isalpha():
            continue
        if not _character_is_latin(character):
            return True
    return False


def _is_original_script_alias(value: str) -> bool:
    """Determine whether an alias should be classified as original script.

    Args:
        value (str): Alias text subject to classification.

    Returns:
        bool: ``True`` if the alias contains non-Latin or accented characters.

    """
    stripped = value.strip()
    if not stripped:
        return False
    if _has_non_latin_letters(stripped):
        return True
    return _contains_special_characters(stripped)


def _collect_alias_names(pep_alias: pd.DataFrame) -> dict[str, list[tuple[str, str]]]:
    """Aggregate allowed alias entries and their types per ID from the alias sheet.

    Args:
        pep_alias (pd.DataFrame): Alias sheet containing additional name columns.

    Returns:
        dict[str, list[tuple[str, str]]]: Mapping from IDs to ordered pairs of
        ``(alias_value, alias_type)`` derived from the permitted columns.

    """
    if pep_alias.empty or "ID" not in pep_alias.columns:
        return {}

    alias_columns = [column for column in pep_alias.columns if column != "ID"]
    if not alias_columns:
        return {}

    allowed_columns = {
        column: ALIAS_COLUMN_TYPE_MAP[column.lower()]
        for column in alias_columns
        if column.lower() in ALIAS_COLUMN_TYPE_MAP
    }
    if not allowed_columns:
        return {}

    alias_values_map: dict[str, list[str]] = {}
    alias_types_map: dict[str, list[str]] = {}
    for _, row in pep_alias.iterrows():
        raw_identifier = row.get("ID")
        if pd.isna(raw_identifier):
            continue
        identifier = str(raw_identifier)

        collected_values = alias_values_map.setdefault(identifier, [])
        collected_types = alias_types_map.setdefault(identifier, [])
        for column, default_alias_type in allowed_columns.items():
            alias_entries = _extract_alias_entries(row.get(column))
            for alias_value, had_double_quotes in alias_entries:
                if not alias_value:
                    continue
                alias_type = (
                    "Also Known As" if had_double_quotes else default_alias_type
                )
                if alias_type != "Original Script Name" and _is_original_script_alias(
                    alias_value
                ):
                    alias_type = "Original Script Name"
                _register_alias_entry(
                    collected_values, collected_types, alias_value, alias_type
                )

    return {
        identifier: list(zip(values, alias_types_map[identifier], strict=True))
        for identifier, values in alias_values_map.items()
    }


def _build_alias_columns(
    ireland_df: pd.DataFrame,
    alias_lists: dict[str, list[tuple[str, str]]],
) -> tuple[list[str | None], list[str | None]]:
    """Construct formatted alias and alias type column values.

    Args:
        ireland_df (pd.DataFrame): Ireland dataframe containing the ``ID`` column
            and optionally ``Original Script Name``.
        alias_lists (dict[str, list[tuple[str, str]]]): Mapping from IDs to
            ordered ``(alias_value, alias_type)`` pairs sourced from the
            alias sheet.

    Returns:
        tuple[list[str | None], list[str | None]]: A tuple containing:
            - A list of bracketed alias strings (or ``None`` when empty).
            - A list of bracketed alias type strings aligned with the alias
              entries (or ``None`` when empty).

    """
    if "Original Script Name" in ireland_df.columns:
        original_script_series = ireland_df["Original Script Name"]
    else:
        original_script_series = pd.Series(
            [None] * len(ireland_df), index=ireland_df.index
        )

    alias_values: list[str | None] = []
    alias_type_values: list[str | None] = []

    for row_index, identifier in enumerate(ireland_df["ID"]):
        alias_entries: list[str] = []
        alias_types: list[str] = []

        if not pd.isna(identifier):
            base_aliases = alias_lists.get(str(identifier), [])
            for alias_value, alias_type in base_aliases:
                _register_alias_entry(
                    alias_entries, alias_types, alias_value, alias_type
                )

        original_script_entries = _normalise_relation_entries(
            original_script_series.iloc[row_index]
        )
        for entry in original_script_entries:
            _register_alias_entry(
                alias_entries, alias_types, entry, "Original Script Name"
            )

        alias_values.append(_format_bracketed_entries(alias_entries))
        alias_type_values.append(_format_bracketed_entries(alias_types))

    return alias_values, alias_type_values


def _remove_orphaned_end_dates(frame: pd.DataFrame) -> pd.DataFrame:
    """Drop ``End Date`` values when no corresponding ``Start Date`` exists.

    Args:
        frame (pd.DataFrame): Dataframe potentially containing ``Start Date`` and
            ``End Date`` columns.

    Returns:
        pd.DataFrame: Copy of ``frame`` with orphaned end-date entries cleared.

    Raises:
        None.

    """
    if "Start Date" not in frame.columns or "End Date" not in frame.columns:
        return frame

    updated = frame.copy()
    removal_indices: list[int] = []

    for row_index, (start_value, end_value) in enumerate(
        zip(updated["Start Date"], updated["End Date"], strict=True),
    ):
        start_entries = _normalise_relation_entries(start_value)
        end_entries = _normalise_relation_entries(end_value)
        if end_entries and not start_entries:
            removal_indices.append(row_index)

    if removal_indices:
        updated.loc[removal_indices, "End Date"] = None

    return updated


def _format_role_date_value(raw_value: object) -> str | None:
    """Normalise role dates to ``YYYY-MM-DD`` with bracketed entries.

    Args:
        raw_value (object): Original ``Start Date`` or ``End Date`` cell value.

    Returns:
        str | None: Bracketed ISO date string or ``None`` when empty.

    Raises:
        None.

    """
    if _value_is_missing(raw_value):
        return None

    entries = _normalise_relation_entries(raw_value)
    if not entries:
        text_value = (
            raw_value.strip() if isinstance(raw_value, str) else str(raw_value).strip()
        )
        entries = [text_value] if text_value else []

    formatted_entries: list[str] = []
    for entry in entries:
        trimmed_entry = entry.strip()
        if not trimmed_entry:
            continue

        parsed = pd.to_datetime(trimmed_entry, errors="coerce")  # type: ignore[arg-type]
        if isinstance(parsed, pd.Series):
            parsed = parsed.squeeze()
        if isinstance(parsed, pd.Timestamp) and not pd.isna(parsed):
            timestamp = parsed.tz_convert(None) if parsed.tzinfo is not None else parsed
            formatted_entries.append(timestamp.date().isoformat())
            continue

        formatted_entries.append(trimmed_entry)

    if not formatted_entries:
        return None

    return _format_bracketed_entries(formatted_entries)


def _create_rca_record(
    entity_name: str,
    rca_identifier: str,
    ireland_cols: pd.Index,
) -> dict[str, str | int | None]:
    """Create an RCA record with cleaned name and optional original-script alias.

    Args:
        entity_name (str): Original relationship entity name extracted from the RCA sheet.
        rca_identifier (str): Generated identifier assigned to the RCA row.
        ireland_cols (pd.Index): Column ordering required by the Ireland template.

    Returns:
        dict[str, str | int | None]: RCA record initialised with default values.

    """
    record: dict[str, str | int | None] = dict.fromkeys(ireland_cols, None)
    record["ID"] = rca_identifier
    record["Name"] = _format_name_value(entity_name)
    record["List Category"] = "Relative Close Associate"
    record["Deceased Dissolved Status"] = 0
    if _contains_special_characters(entity_name):
        record["Alias"] = _format_bracketed_entries([entity_name])
        record["Alias Type"] = _format_bracketed_entries(["Original Script Name"])

    return record


def _rca_lookup_path(output_path: Path) -> Path:
    """Return the expected RCA lookup workbook path for an Ireland export.

    Args:
        output_path (Path): Path to the generated Ireland 44 workbook.

    Returns:
        Path: Location where the RCA lookup workbook should reside.

    """
    return output_path.with_name(f"{output_path.stem}_rca_lookup{output_path.suffix}")


def _normalise_lookup_name(value: object) -> str:
    """Normalise RCA names for matching against existing lookup entries.

    Args:
        value (object): Name value sourced from either the RCA sheet or lookup.

    Returns:
        str: Lowercased, whitespace-collapsed representation suitable for keys.

    """
    if value is None:
        return ""
    text_value = value if isinstance(value, str) else str(value)
    flattened = _flatten_bracketed_value(text_value)
    candidate = flattened if flattened is not None else text_value
    collapsed = " ".join(candidate.strip().split())
    return collapsed.casefold()


def _normalise_lookup_identifier(raw_identifier: object) -> str | None:
    """Convert a raw identifier into a cleaned string suitable for lookup use.

    Args:
        raw_identifier (object): Identifier value extracted from a dataframe.

    Returns:
        str | None: Stripped identifier string or ``None`` when missing.

    """
    if _value_is_missing(raw_identifier):
        return None
    identifier = str(raw_identifier).strip()
    return identifier if identifier else None


def _extract_existing_lookup_entry(
    raw_name: object,
    raw_identifier: object,
) -> tuple[str, str, str] | None:
    """Prepare a lookup entry sourced from a prior lookup workbook.

    Args:
        raw_name (object): Display name column value.
        raw_identifier (object): Identifier column value.

    Returns:
        tuple[str, str, str] | None: Tuple containing normalised name key, identifier,
            and display name. Returns ``None`` when data is unusable.

    """
    identifier = _normalise_lookup_identifier(raw_identifier)
    if identifier is None:
        return None

    display_name = "" if _value_is_missing(raw_name) else str(raw_name).strip()
    normalised_name = _normalise_lookup_name(display_name)
    if not normalised_name:
        return None

    return normalised_name, identifier, display_name


def _extract_new_lookup_entry(
    raw_name: object,
    raw_identifier: object,
) -> tuple[str, str, str] | None:
    """Prepare a lookup entry derived from the freshly generated RCA rows.

    Args:
        raw_name (object): Formatted name value from the RCA dataframe.
        raw_identifier (object): Identifier allocated to the new RCA row.

    Returns:
        tuple[str, str, str] | None: Tuple containing normalised name key, identifier,
            and display name. Returns ``None`` when data is unusable.

    """
    identifier = _normalise_lookup_identifier(raw_identifier)
    if identifier is None:
        return None

    flattened_name = _flatten_bracketed_value(raw_name) or ""
    normalised_name = _normalise_lookup_name(flattened_name)
    if not normalised_name:
        return None

    return normalised_name, identifier, flattened_name


def _load_existing_rca_lookup(
    output_path: Path,
) -> tuple[dict[str, str], pd.DataFrame | None]:
    """Load an existing RCA lookup workbook when present on disk.

    Args:
        output_path (Path): Path where the Ireland workbook will be stored.

    Returns:
        tuple[dict[str, str], pd.DataFrame | None]:
            - Mapping from normalised RCA names to existing IDs.
            - Dataframe containing the existing lookup rows, or ``None`` when
              no prior workbook exists.

    """
    lookup_path = _rca_lookup_path(output_path)
    if not lookup_path.exists():
        return {}, None

    try:
        lookup_df = pd.read_excel(lookup_path)
    except Exception:  # noqa: BLE001 # External files may not be parseable
        logger.warning("Unable to read existing RCA lookup at %s", lookup_path)
        return {}, None

    if lookup_df.empty:
        return {}, pd.DataFrame(columns=["RCA Name", "RCA ID"])

    normalised_columns = {
        str(column).strip().casefold(): str(column) for column in lookup_df.columns
    }
    name_column = normalised_columns.get("rca name") or normalised_columns.get("name")
    id_column = normalised_columns.get("rca id") or normalised_columns.get("id")

    if not name_column or not id_column:
        logger.warning(
            "RCA lookup at %s is missing required columns",
            lookup_path,
        )
        return {}, pd.DataFrame(columns=["RCA Name", "RCA ID"])

    existing_map: dict[str, str] = {}
    for raw_name, raw_id in zip(
        lookup_df[name_column],
        lookup_df[id_column],
        strict=False,
    ):
        if raw_id is None or (isinstance(raw_id, float) and pd.isna(raw_id)):
            continue
        identifier = str(raw_id).strip()
        if not identifier:
            continue
        key = _normalise_lookup_name(raw_name)
        if not key:
            continue
        existing_map[key] = identifier

    existing_lookup_df = lookup_df.rename(
        columns={name_column: "RCA Name", id_column: "RCA ID"},
    )[["RCA Name", "RCA ID"]]

    return existing_map, existing_lookup_df


def _get_or_create_rca_identifier(
    entity_name: str,
    tracked_lookup: dict[str, str],
    used_combos: set[str],
    sequence_tracker: dict[tuple[str, str], int],
) -> str:
    """Return an RCA identifier for an entity, creating one when absent.

    Args:
        entity_name (str): Relationship entity name requiring an identifier.
        tracked_lookup (dict[str, str]): Mapping of normalised names to identifiers.
        used_combos (set[str]): Previously generated random combos to avoid clashes.
        sequence_tracker (dict[tuple[str, str], int]): Counter keyed by initials and
            combo segments to maintain sequential suffixes.

    Returns:
        str: Existing or newly generated RCA identifier for the entity.

    """
    formatted_name = _format_name_value(entity_name)
    flattened_name = (
        _flatten_bracketed_value(formatted_name) if formatted_name else None
    )
    lookup_source = flattened_name if flattened_name else entity_name
    lookup_key = _normalise_lookup_name(lookup_source)
    if not lookup_key:
        lookup_key = _normalise_lookup_name(entity_name)
    existing_identifier = tracked_lookup.get(lookup_key)
    if existing_identifier:
        return existing_identifier

    initials_source = flattened_name if flattened_name else entity_name
    initials = _initials_from_name(initials_source)
    combo = _generate_combo()
    while combo in used_combos:
        combo = _generate_combo()
    used_combos.add(combo)

    tracker_key = (initials, combo)
    sequence_tracker[tracker_key] = sequence_tracker.get(tracker_key, 0) + 1

    identifier = f"IE-GEN-{initials}-{combo}-RCA-" f"{sequence_tracker[tracker_key]}"
    tracked_lookup[lookup_key] = identifier
    return identifier


def _fill_missing_structured_entries(ireland_df: pd.DataFrame) -> pd.DataFrame:
    """Populate structured columns with explicit empty placeholders.

    Args:
        ireland_df (pd.DataFrame): Ireland dataframe containing structured columns.

    Returns:
        pd.DataFrame: Dataframe where bracketed or JSON-formatted columns use
            ``[]`` or ``{}`` to represent empty values.

    """
    if ireland_df.empty:
        return ireland_df

    updated = ireland_df.copy()

    def _detect_placeholder(sample_value: str) -> str | None:
        trimmed = sample_value.strip()
        if trimmed.startswith(("[]", '["')):
            return "[]"
        if trimmed.startswith("{"):
            return "{}"
        return None

    def _needs_placeholder(value: object) -> bool:
        return _value_is_missing(value) or (
            isinstance(value, str) and not value.strip()
        )

    for column in updated.columns:
        sample_value = next(
            (
                str(value).strip()
                for value in updated[column]
                if isinstance(value, str) and value.strip()
            ),
            None,
        )
        placeholder = (
            _detect_placeholder(sample_value) if sample_value is not None else None
        )
        placeholder = placeholder or STRUCTURED_COLUMN_DEFAULT_PLACEHOLDERS.get(column)
        if placeholder is None:
            continue

        updated[column] = updated[column].apply(
            lambda value, placeholder=placeholder: (
                placeholder if _needs_placeholder(value) else value
            ),
        )

    return updated


def _build_rca_rows(
    pep_rca: pd.DataFrame,
    ireland_cols: pd.Index,
    id_mapping: dict[str, str],
    existing_lookup: dict[str, str] | None = None,
) -> tuple[pd.DataFrame, dict[str, list[tuple[str, str]]]]:
    """Create RCA rows and track generated identifiers per source ID.

    Args:
        pep_rca (pd.DataFrame): RCA sheet with relationship columns.
        ireland_cols (pd.Index): Column ordering from the Ireland template.
        id_mapping (dict[str, str]): Mapping from original IDs to their sequentially
            prefixed values.
        existing_lookup (dict[str, str] | None): Mapping of normalised RCA names
            to previously generated identifiers from an external lookup file.

    Returns:
        tuple[pd.DataFrame, dict[str, list[tuple[str, str]]]]:
            - A dataframe of RCA rows aligned to ``ireland_cols``.
            - A mapping of prefixed source IDs to pairs of
              ``(relationship_type, rca_identifier)`` describing the newly
              created RCA rows.

    """
    if pep_rca.empty or "ID" not in pep_rca.columns:
        return pd.DataFrame(columns=ireland_cols), {}

    normalised = pep_rca.copy()
    normalised["ID"] = normalised["ID"].astype(str)
    relation_columns = [column for column in normalised.columns if column != "ID"]

    tracked_lookup = existing_lookup.copy() if existing_lookup is not None else {}
    rca_records: list[dict[str, str | int | None]] = []
    sequence_tracker: dict[tuple[str, str], int] = {}
    used_combos: set[str] = set()
    created_ids: set[str] = set()
    source_to_rca_links: dict[str, list[tuple[str, str]]] = {}

    for column in relation_columns:
        if column.lower() in EXCLUDED_RELATIONSHIP_COLUMNS:
            continue
        subset = normalised[["ID", column]].dropna(subset=[column])
        if subset.empty:
            continue

        subset[column] = subset[column].astype(str).str.strip()
        subset = subset[subset[column] != ""]
        if subset.empty:
            continue

        for parent_identifier, entity_name in _collect_parent_entities(subset):
            rca_identifier = _get_or_create_rca_identifier(
                entity_name,
                tracked_lookup,
                used_combos,
                sequence_tracker,
            )

            if rca_identifier not in created_ids:
                record = _create_rca_record(entity_name, rca_identifier, ireland_cols)
                rca_records.append(record)
                created_ids.add(rca_identifier)

            prefixed_parent_identifier = id_mapping.get(parent_identifier)
            if prefixed_parent_identifier:
                source_to_rca_links.setdefault(prefixed_parent_identifier, []).append(
                    (column, rca_identifier),
                )

    if not rca_records:
        empty = pd.DataFrame(columns=ireland_cols)
        return _apply_relationship_type_mapping(empty), source_to_rca_links

    rca_df = pd.DataFrame.from_records(rca_records, columns=ireland_cols)
    rca_df = _apply_relationship_type_mapping(rca_df)
    return rca_df, source_to_rca_links


def _resolve_output_path(pep_path: Path, output_hint: Path | None) -> Path:
    """Determine the final output path using the PEP filename and optional hint path.

    Args:
        pep_path (Path): Path to the input PEP workbook.
        output_hint (Path | None): Desired output path or directory. When ``None``,
            the input workbook directory is used.

    Returns:
        Path: Fully-qualified output path for the generated workbook.

    """
    output_directory = pep_path.parent

    if output_hint is None:
        output_directory = pep_path.parent
    elif output_hint.exists():
        output_directory = output_hint if output_hint.is_dir() else output_hint.parent
    elif output_hint.suffix:
        output_directory = (
            output_hint.parent if output_hint.parent != Path() else pep_path.parent
        )
    elif output_hint.name:
        output_directory = output_hint

    if output_directory == Path():
        output_directory = pep_path.parent

    output_suffix = pep_path.suffix or ".xlsx"
    output_filename = f"{pep_path.stem}_complete{output_suffix}"
    return output_directory / output_filename


def _merge_main_sheet(ireland_df: pd.DataFrame, pep_main: pd.DataFrame) -> pd.DataFrame:
    """Merge identifying columns from the Main sheet into the Ireland dataframe.

    Args:
        ireland_df (pd.DataFrame): Dataframe shaped to the Ireland template.
        pep_main (pd.DataFrame): Main sheet containing identifying fields.

    Returns:
        pd.DataFrame: Ireland dataframe enriched with selected main-sheet columns.

    """
    main_columns = [
        "ID",
        "personLabel",
        "fatherLabel",
        "genderLabel",
        "birthPlaceLabel",
        "academicDegreeLabel",
        "image",
    ]
    if pep_main.empty:
        return ireland_df
    existing_main_columns = [
        column for column in main_columns if column in pep_main.columns
    ]
    if "ID" not in existing_main_columns:
        return ireland_df

    merged = ireland_df.merge(
        pep_main[existing_main_columns],
        on="ID",
        how="left",
    )
    rename_map = {
        "personLabel": "Name",
        "fatherLabel": "Father Name",
        "genderLabel": "Gender",
        "birthPlaceLabel": "Place of Birth",
        "image": "Image Tag",
    }
    available_renames = {
        old: new for old, new in rename_map.items() if old in merged.columns
    }
    renamed = merged.rename(columns=available_renames)
    renamed = _apply_name_and_script_columns(renamed, merged)
    renamed = _apply_parent_and_image_columns(renamed)
    return _normalise_place_of_birth_column(renamed)


def _apply_column_mappings(
    ireland_df: pd.DataFrame,
    pep_dob: pd.DataFrame,
    pep_nat: pd.DataFrame,
    pep_alias: pd.DataFrame,
    pep_address: pd.DataFrame,
    pep_case: pd.DataFrame,
    pep_role: pd.DataFrame,
) -> pd.DataFrame:
    """Populate Ireland columns using the supporting PEP sheets.

    Args:
        ireland_df (pd.DataFrame): Dataframe shaped to the Ireland template.
        pep_dob (pd.DataFrame): Date-of-birth sheet.
        pep_nat (pd.DataFrame): Nationality sheet.
        pep_alias (pd.DataFrame): Alias sheet.
        pep_address (pd.DataFrame): Address sheet.
        pep_case (pd.DataFrame): Case details sheet.
        pep_role (pd.DataFrame): Role type sheet.

    Returns:
        pd.DataFrame: Ireland dataframe with populated supporting columns.

    """
    column_mappings = {
        "Date of Birth": _map_single_value(
            pep_dob,
            "ID",
            "birthDate",
            _normalise_birth_date_value,
        ),
        "Nationality": _map_single_value(pep_nat, "ID", "nationalityLabel"),
        "Primary Address": _map_single_value(
            pep_address,
            "ID",
            "residenceLabel",
            lambda value: _format_value_as_bracketed_list(value),
        ),
        "Designation": _map_grouped_values(pep_role, "ID", "positionLabel"),
        "Start Date": _map_grouped_values(pep_role, "ID", "startTime"),
        "End Date": _map_grouped_values(pep_role, "ID", "endTime"),
        "Description": _map_single_value(pep_role, "ID", "personDescription"),
    }

    for column_name, mapping in column_mappings.items():
        if mapping:
            ireland_df[column_name] = ireland_df["ID"].map(mapping)

    ireland_df = _remove_orphaned_end_dates(ireland_df)
    for column_name in ("Start Date", "End Date"):
        if column_name in ireland_df.columns:
            ireland_df[column_name] = ireland_df[column_name].apply(
                _format_role_date_value
            )

    alias_lists = _collect_alias_names(pep_alias)
    alias_values, alias_type_values = _build_alias_columns(ireland_df, alias_lists)
    ireland_df["Alias"] = alias_values
    ireland_df["Alias Type"] = alias_type_values

    if "Primary Occupation" not in ireland_df.columns:
        ireland_df["Primary Occupation"] = None
    primary_occupation_map = _map_grouped_values(pep_role, "ID", "occupationLabel")
    if primary_occupation_map:
        ireland_df["Primary Occupation"] = ireland_df["Primary Occupation"].fillna(
            ireland_df["ID"].map(primary_occupation_map),
        )

    if "Deceased Dissolved Status" not in ireland_df.columns:
        ireland_df["Deceased Dissolved Status"] = 0
    else:
        ireland_df["Deceased Dissolved Status"] = 0

    ireland_df = _apply_updated_country_list_nationalities(ireland_df)
    ireland_df = _apply_political_party_designations(ireland_df, pep_role)
    if "Designation" in ireland_df.columns:
        ireland_df["Designation"] = ireland_df["Designation"].apply(
            _normalise_designation_value,
        )
    ireland_df = _apply_case_details_column(ireland_df, pep_case)

    if "Primary Occupation" in ireland_df.columns:
        ireland_df["Primary Occupation"] = ireland_df["Primary Occupation"].map(
            lambda value: _capitalise_primary_occupation(value),
        )

    return ireland_df


def _capitalise_primary_occupation(value: object) -> object:
    """Capitalise the first character of a primary occupation entry.

    Args:
        value (object): Original primary occupation value.

    Returns:
        object: Value with capitalisation applied when text is present.

    """
    if _value_is_missing(value):
        return value
    if isinstance(value, str):
        entries = _normalise_relation_entries(value)
        if entries:
            capitalised_entries = [
                _capitalise_first_character(entry) for entry in entries if entry
            ]
            formatted = _format_bracketed_entries(capitalised_entries)
            return formatted if formatted is not None else value

        stripped = value.strip()
        if not stripped:
            return value
        return _capitalise_first_character(stripped)
    return value


def _ensure_relationship_columns(ireland_df: pd.DataFrame) -> pd.DataFrame:
    """Guarantee the presence of relationship columns required by the template.

    Args:
        ireland_df (pd.DataFrame): Ireland template dataframe.

    Returns:
        pd.DataFrame: Dataframe with relationship columns ensured.

    """
    if "Relationship Type" not in ireland_df.columns:
        ireland_df["Relationship Type"] = None
    if "Relation With" not in ireland_df.columns:
        ireland_df["Relation With"] = None
    return ireland_df


def _build_id_to_name_map(ireland_df: pd.DataFrame) -> dict[str, str | None]:
    """Build a mapping from original IDs to their associated display names.

    Args:
        ireland_df (pd.DataFrame): Ireland template dataframe.

    Returns:
        dict[str, str | None]: Mapping from source IDs to display names.

    """
    mapping: dict[str, str | None] = {}
    if "ID" not in ireland_df.columns:
        return mapping
    name_series: pd.Series
    if "Name" in ireland_df.columns:
        name_series = ireland_df["Name"]
    else:
        name_series = pd.Series([None] * len(ireland_df), index=ireland_df.index)

    for identifier, name_value in zip(ireland_df["ID"], name_series, strict=True):
        if pd.isna(identifier):
            continue
        mapping[str(identifier)] = None if pd.isna(name_value) else str(name_value)
    return mapping


def _prefix_identifier_column(
    ireland_df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Assign sequential IE-GEN -I-x identifiers to primary rows.

    Args:
        ireland_df (pd.DataFrame): Ireland template dataframe.

    Returns:
        tuple[pd.DataFrame, dict[str, str]]: Updated dataframe with prefixed IDs and a
        mapping from original identifier strings to their new sequential values.

    """
    updated = ireland_df.copy()
    next_index = 1
    prefixed_ids: list[str | float] = []
    id_mapping: dict[str, str] = {}
    for identifier in updated["ID"]:
        if pd.isna(identifier):
            prefixed_ids.append(identifier)
            continue
        source_id = str(identifier)
        prefixed_value = f"IE-GEN-I-{next_index}"
        prefixed_ids.append(prefixed_value)
        id_mapping[source_id] = prefixed_value
        next_index += 1
    updated["ID"] = prefixed_ids
    return updated, id_mapping


def _truncate_after_comma(value: str) -> str:
    """Remove the first comma and any characters that follow from a string.

    Args:
        value (str): Input string that may contain a comma.

    Returns:
        str: String truncated at the first comma, with surrounding whitespace removed.

    """
    trimmed = value.strip()
    if trimmed.startswith('["') and trimmed.endswith('"]'):
        trimmed = trimmed[2:-2].strip()

    comma_index = trimmed.find(",")
    if comma_index == -1:
        return trimmed
    return trimmed[:comma_index].strip()


def _replace_name_hyphens(value: str) -> str:
    """Replace hyphen characters with spaces while collapsing extra whitespace.

    Args:
        value (str): Input string that may contain hyphens.

    Returns:
        str: String with hyphens replaced by single spaces.

    """
    replaced = value.replace("-", " ")
    return " ".join(replaced.split())


def _replace_ampersand(value: str) -> str:
    """Replace ampersand characters with the word ``and``.

    Args:
        value (str): Input string that may contain ``&`` symbols.

    Returns:
        str: String with ampersands replaced by ``and`` and normalised spacing.

    """
    replaced = value.replace("&", " and ")
    return " ".join(replaced.split())


def _replace_apostrophes(value: str) -> str:
    """Replace apostrophes with spaces while collapsing whitespace.

    Args:
        value (str): Input string that may contain apostrophes.

    Returns:
        str: String with apostrophes replaced by spaces and normalised spacing.

    """
    replaced = value.replace("'", " ")
    return " ".join(replaced.split())


def _remove_non_alphanumeric(value: str) -> str:
    """Remove non-alphanumeric characters by replacing them with spaces.

    Args:
        value (str): Input string potentially containing special characters.

    Returns:
        str: String containing only alphanumeric characters and single spaces.

    """
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", value)
    return " ".join(cleaned.split())


def _normalise_name_tokens(value: str) -> str:
    """Normalise a name string by removing accents and symbols.

    Args:
        value (str): Raw name string potentially containing accents, hyphens,
            or ``&`` characters.

    Returns:
        str: ASCII string with hyphens replaced by spaces and ampersands mapped
        to ``and``.

    """
    stripped = _strip_accents(value)
    without_ampersand = _replace_ampersand(stripped)
    without_hyphen = _replace_name_hyphens(without_ampersand)
    without_apostrophe = _replace_apostrophes(without_hyphen)
    return _remove_non_alphanumeric(without_apostrophe)


def _normalise_image_tag_value(raw_value: object) -> str | None:
    """Return a plain URL string for an ``Image Tag`` cell value.

    Args:
        raw_value (object): Original value that may represent a URL.

    Returns:
        str | None: Raw URL string or ``None`` when the value is missing.

    """
    if raw_value is None:
        return None

    if isinstance(raw_value, str):
        trimmed = raw_value.strip()
        if not trimmed:
            return None

        hyperlink_match = re.match(
            r'=HYPERLINK\("([^"]+)"', trimmed, flags=re.IGNORECASE
        )
        if hyperlink_match:
            url_candidate = hyperlink_match.group(1).strip()
            return url_candidate or None

        return trimmed

    try:
        is_missing = bool(pd.isna(raw_value))  # type: ignore[arg-type]
    except TypeError:
        is_missing = False

    if is_missing:
        return None

    coerced = str(raw_value).strip()
    return coerced or None


def _split_place_of_birth_entries(value: object) -> list[str]:
    """Split a place of birth cell into individual entries.

    Args:
        value (object): Original value from the ``Place of Birth`` column.

    Returns:
        list[str]: Cleaned list of place-of-birth entries.

    """
    entries = _normalise_relation_entries(value)
    if entries:
        return entries

    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            return []
        if ";" in trimmed:
            return [item.strip() for item in trimmed.split(";") if item.strip()]
        return [trimmed]

    return []


def _normalise_place_of_birth_column(frame: pd.DataFrame) -> pd.DataFrame:
    """Ensure only one entry remains in ``Place of Birth`` and spill extras.

    Args:
        frame (pd.DataFrame): Dataframe potentially containing ``Place of Birth``
            and ``Extra Information`` columns.

    Returns:
        pd.DataFrame: Dataframe with ``Place of Birth`` containing at most one
        entry and additional locations appended to ``Extra Information`` with an
        ``Extra POB:`` prefix.

    """
    if "Place of Birth" not in frame.columns:
        return frame

    if "Extra Information" not in frame.columns:
        frame["Extra Information"] = None

    place_values = frame["Place of Birth"].tolist()
    extra_values = frame["Extra Information"].tolist()

    updated_place_of_birth: list[str | None] = []
    updated_extra_info: list[str | None] = []

    for pob_value, extra_value in zip(place_values, extra_values, strict=True):
        entries = _split_place_of_birth_entries(pob_value)
        primary_entry = entries[0] if entries else None
        formatted_primary = (
            _format_bracketed_entries([primary_entry]) if primary_entry else None
        )

        extra_entries = entries[1:]
        merged_extra = extra_value
        if extra_entries:
            prefixed_extra = [f"Extra POB: {entry}" for entry in extra_entries]
            merged_extra = _merge_relation_entries(merged_extra, prefixed_extra)

        updated_place_of_birth.append(formatted_primary)
        updated_extra_info.append(merged_extra)

    frame["Place of Birth"] = updated_place_of_birth
    frame["Extra Information"] = updated_extra_info
    return frame


def _apply_name_and_script_columns(
    renamed: pd.DataFrame,
    merged: pd.DataFrame,
) -> pd.DataFrame:
    """Populate name-related columns including original script values.

    Args:
        renamed (pd.DataFrame): Dataframe with renamed columns.
        merged (pd.DataFrame): Original merged dataframe including raw values.

    Returns:
        pd.DataFrame: Dataframe with formatted ``Name`` and ``Original Script Name``.

    """
    if "Name" not in renamed.columns:
        return renamed

    raw_names = (
        merged["personLabel"].astype(str)
        if "personLabel" in merged.columns
        else pd.Series(["" for _ in range(len(renamed))], index=renamed.index)
    )

    if "Original Script Name" not in renamed.columns:
        renamed["Original Script Name"] = None

    special_mask = raw_names.apply(_contains_special_characters)

    def _merge_original_script(existing: object, alias_value: str) -> str | None:
        if not alias_value:
            return existing if isinstance(existing, str) else None
        entries = _normalise_relation_entries(existing)
        if alias_value not in entries:
            entries.append(alias_value)
        return _format_bracketed_entries(entries)

    if special_mask.any():
        alias_values = raw_names.loc[special_mask].apply(_truncate_after_comma)
        renamed.loc[special_mask, "Original Script Name"] = [
            _merge_original_script(existing, alias_value)
            for existing, alias_value in zip(
                renamed.loc[special_mask, "Original Script Name"],
                alias_values,
                strict=True,
            )
        ]

    renamed["Name"] = renamed["Name"].apply(_format_name_value)
    return renamed


def _apply_parent_and_image_columns(renamed: pd.DataFrame) -> pd.DataFrame:
    """Format secondary identifying columns such as parent and image data.

    Args:
        renamed (pd.DataFrame): Dataframe that may contain parent or image columns.

    Returns:
        pd.DataFrame: Dataframe with formatted ``Father Name`` and ``Image Tag``.

    """
    if "Father Name" in renamed.columns:
        renamed["Father Name"] = renamed["Father Name"].apply(_format_name_value)

    if "Image Tag" in renamed.columns:
        renamed["Image Tag"] = renamed["Image Tag"].apply(_normalise_image_tag_value)

    return renamed


@lru_cache(maxsize=1)
def _load_updated_country_list() -> pd.DataFrame | None:
    """Load the Updated CountryList workbook.

    Args:
        None.

    Returns:
        pd.DataFrame | None: Contents of ``Updated CountryList.xlsx`` or ``None`` when
        the workbook is unavailable.

    Raises:
        None.

    """
    module_path = Path(__file__).resolve()
    search_roots = list(module_path.parents[:4])
    search_roots.append(Path.cwd())

    seen_paths: set[Path] = set()
    for root in search_roots:
        candidate = root / COUNTRY_LIST_FILENAME
        if candidate in seen_paths:
            continue
        seen_paths.add(candidate)
        if candidate.exists():
            try:
                return pd.read_excel(candidate)
            except (FileNotFoundError, ValueError, OSError) as exc:
                logger.warning(
                    "Unable to read Updated CountryList workbook at %s: %s",
                    candidate,
                    exc,
                )
                return None

    logger.warning(
        "Updated CountryList workbook not found. Nationality values will remain unchanged.",
    )
    return None


def _value_is_missing(value: object) -> bool:
    """Return ``True`` when a value should be treated as missing.

    Args:
        value (object): Value to evaluate.

    Returns:
        bool: ``True`` when the value represents a missing entry.

    Raises:
        None.

    """
    if value is None:
        return True
    try:
        return bool(pd.isna(value))  # type: ignore[arg-type]
    except TypeError:
        return False


def _normalise_country_list_value(value: object) -> str | None:
    """Normalise a value sourced from the Updated CountryList workbook.

    Args:
        value (object): Raw workbook cell value.

    Returns:
        str | None: Trimmed string representation or ``None`` when empty.

    Raises:
        None.

    """
    if _value_is_missing(value):
        return None
    text = value.strip() if isinstance(value, str) else str(value).strip()
    capitalised_text = _capitalise_first_character(text) if text else ""
    return capitalised_text or None


def _register_country_title_mapping(
    mapping: dict[str, str],
    title_text: str,
    canonical_title: str,
) -> None:
    """Insert a country-title mapping using direct and accent-stripped keys.

    Args:
        mapping (dict[str, str]): Destination mapping to update.
        title_text (str): Country title sourced from the workbook.
        canonical_title (str): Canonical country title (``Country Title 1``) to
            associate with ``title_text``.

    Returns:
        None

    Raises:
        None.

    """
    lowered_key = title_text.lower()
    mapping[lowered_key] = canonical_title

    accent_key = _strip_accents(title_text).lower()
    mapping.setdefault(accent_key, canonical_title)


@lru_cache(maxsize=1)
def _country_title_to_nationality_map() -> dict[str, str]:
    """Build a mapping from country titles to nationalities.

    Args:
        None.

    Returns:
        dict[str, str]: Mapping where keys are normalised country titles and values
        are nationality descriptors.

    Raises:
        None.

    """
    country_frame = pd.read_excel(os.path.join(BASE_DIR, COUNTRY_LIST_FILENAME))
    if country_frame is None:
        return {}

    available_title_columns = [
        column
        for column in COUNTRY_LIST_TITLE_COLUMNS
        if column in country_frame.columns
    ]
    if not available_title_columns:
        logger.warning(
            "Updated CountryList workbook does not contain the expected country title columns.",
        )
        return {}

    mapping: dict[str, str] = {}
    for _, row in country_frame.iterrows():
        canonical_title: str | None = None
        for priority_column in COUNTRY_LIST_TITLE_COLUMNS:
            if priority_column not in country_frame.columns:
                continue
            canonical_title = _normalise_country_list_value(row.get(priority_column))
            if canonical_title:
                break
        if not canonical_title:
            continue

        for column in available_title_columns:
            title_text = _normalise_country_list_value(row.get(column))
            if not title_text:
                continue

            _register_country_title_mapping(mapping, title_text, canonical_title)

    return mapping


def _lookup_nationality_replacement(entry: str, mapping: dict[str, str]) -> str | None:
    """Return the normalised nationality for a country entry when available.

    Args:
        entry (str): Country entry requiring normalisation.
        mapping (dict[str, str]): Country-to-nationality mapping.

    Returns:
        str | None: Replacement nationality or ``None`` when no match exists.

    Raises:
        None.

    """
    lowered_key = entry.lower()
    if lowered_key in mapping:
        return mapping[lowered_key]
    accent_key = _strip_accents(entry).lower()
    return mapping.get(accent_key)


def _format_standardised_entries(
    original_value: object,
    entries: list[str],
) -> str | None:
    """Format mapped nationality entries to mirror the original representation.

    Args:
        original_value (object): Original cell value used to infer formatting.
        entries (list[str]): Nationality entries after mapping.

    Returns:
        str | None: Formatted nationality string or ``None`` when no entries remain.

    Raises:
        None.

    """
    if not entries:
        return None

    if isinstance(original_value, str):
        trimmed = original_value.strip()
        if trimmed.startswith('["') and trimmed.endswith('"]'):
            return _format_bracketed_entries(entries)

    capitalised_entries = [_capitalise_first_character(entry) for entry in entries]

    if len(capitalised_entries) == 1:
        return capitalised_entries[0]

    return "; ".join(capitalised_entries)


def _standardise_nationality_value(
    value: object,
    mapping: dict[str, str],
) -> str | None:
    """Standardise a nationality entry using the Updated CountryList mapping.

    Args:
        value (object): Raw nationality value sourced from the Ireland dataframe.
        mapping (dict[str, str]): Country-to-nationality lookup mapping.

    Returns:
        str | None: Standardised nationality string or ``None`` when the input is empty.

    Raises:
        None.

    """
    if _value_is_missing(value):
        return None

    entries = _normalise_relation_entries(value)
    if not entries:
        single_entry = _normalise_country_list_value(value)
        if single_entry is None:
            return None

        replacement = _lookup_nationality_replacement(single_entry, mapping)
        return replacement or single_entry

    replaced_entries = [
        _lookup_nationality_replacement(entry.strip(), mapping) or entry.strip()
        for entry in entries
        if entry.strip()
    ]

    return _format_standardised_entries(value, replaced_entries)


def _apply_updated_country_list_nationalities(ireland_df: pd.DataFrame) -> pd.DataFrame:
    """Apply the Updated CountryList mapping to the ``Nationality`` column.

    Args:
        ireland_df (pd.DataFrame): Ireland dataframe possibly containing a ``Nationality`` column.

    Returns:
        pd.DataFrame: Dataframe with standardised nationality entries.

    Raises:
        None.

    """
    if ireland_df.empty or "Nationality" not in ireland_df.columns:
        return ireland_df

    mapping = _country_title_to_nationality_map()
    if not mapping:
        return ireland_df

    updated = ireland_df.copy()
    updated["Nationality"] = updated["Nationality"].apply(
        lambda value: _standardise_nationality_value(value, mapping),
    )
    return updated


def _resolve_extra_info_column(
    available_columns: dict[str, str],
    candidates: list[str],
) -> str | None:
    """Resolve the actual column name matching the provided candidates.

    Args:
        available_columns (dict[str, str]): Mapping of lowercase column names to
            their original casing.
        candidates (list[str]): Candidate column names in lowercase to search
            for within ``available_columns``.

    Returns:
        str | None: Matching column name from ``available_columns`` or ``None``
        when no candidate is present.

    """
    for candidate in candidates:
        actual_column = available_columns.get(candidate)
        if actual_column:
            return actual_column
    return None


def _normalise_extra_info_value(raw_value: object) -> list[str]:
    """Normalise extra information cell values into a list of entries.

    Args:
        raw_value (object): Original cell value from a supporting sheet.

    Returns:
        list[str]: Cleaned list of entries, or an empty list when no data is
        available.

    """
    entries = _normalise_relation_entries(raw_value)
    if entries:
        return entries

    if isinstance(raw_value, str):
        trimmed = raw_value.strip()
        if not trimmed:
            return []
        semicolon_split = [item.strip() for item in trimmed.split(";") if item.strip()]
        return semicolon_split if semicolon_split else [trimmed]

    if raw_value is None:
        return []

    try:
        is_missing = bool(pd.isna(raw_value))  # type: ignore[arg-type]
    except TypeError:
        is_missing = False

    if is_missing:
        return []

    text_value = str(raw_value).strip()
    return [text_value] if text_value else []


def _compose_prefixed_value(prefix: str, entry: str) -> str | None:
    """Compose a prefixed entry while trimming extraneous whitespace.

    Args:
        prefix (str): Prefix label that should precede the entry.
        entry (str): Normalised entry value.

    Returns:
        str | None: Prefixed entry string or ``None`` when the entry is empty.

    """
    clean_entry = entry.strip()
    if not clean_entry:
        return None
    capitalised_entry = _capitalise_first_character(clean_entry)
    return f"{prefix} {capitalised_entry}".strip()


def _collect_prefixed_entries_for_frame(
    frame: pd.DataFrame,
    prefix_config: list[tuple[str, list[str]]],
) -> dict[str, dict[str, list[str]]]:
    """Collect prefixed entry values from a single supporting frame.

    Args:
        frame (pd.DataFrame): Source dataframe potentially containing the target
            columns.
        prefix_config (list[tuple[str, list[str]]]): Prefix to column candidate
            mapping.

    Returns:
        dict[str, dict[str, list[str]]]: Nested mapping of identifier -> prefix ->
        ordered entry list.

    """
    collected: dict[str, dict[str, list[str]]] = {}
    if frame.empty or "ID" not in frame.columns:
        return collected

    available_columns = {column.lower(): column for column in frame.columns}
    identifiers = frame["ID"].astype(str)

    for prefix, candidates in prefix_config:
        actual_column = _resolve_extra_info_column(available_columns, candidates)
        if actual_column is None:
            continue

        for identifier, raw_value in zip(
            identifiers, frame[actual_column], strict=True
        ):
            if pd.isna(raw_value):
                continue

            entries = _normalise_extra_info_value(raw_value)
            if not entries:
                continue

            prefix_map = collected.setdefault(identifier, {})
            entry_list = prefix_map.setdefault(prefix, [])
            for entry in entries:
                clean_entry = entry.strip()
                if clean_entry and clean_entry not in entry_list:
                    entry_list.append(clean_entry)

    return collected


def _merge_prefixed_entry_maps(
    target: dict[str, dict[str, list[str]]],
    source: dict[str, dict[str, list[str]]],
) -> None:
    """Merge prefixed entry maps while preserving insertion order.

    Args:
        target (dict[str, dict[str, list[str]]]): Destination mapping to update.
        source (dict[str, dict[str, list[str]]]): Source mapping to merge into
            ``target``.

    Returns:
        None

    """
    for identifier, prefix_map in source.items():
        target_prefix_map = target.setdefault(identifier, {})
        for prefix, values in prefix_map.items():
            target_values = target_prefix_map.setdefault(prefix, [])
            for value in values:
                if value not in target_values:
                    target_values.append(value)


def _apply_static_column_values(
    frame: pd.DataFrame,
    static_values: dict[str, str | int | float] = STATIC_COLUMN_VALUES,
) -> pd.DataFrame:
    """Populate static string values across designated columns.

    Args:
        frame (pd.DataFrame): Dataframe to populate.
        static_values (dict[str, str], optional): Mapping of column names to
            constant values. Defaults to ``STATIC_COLUMN_VALUES``.

    Returns:
        pd.DataFrame: Dataframe with the specified columns filled with the
        provided static values.

    """
    if not static_values:
        return frame

    updated = frame.copy()
    for column, value in static_values.items():
        if column in updated.columns:
            updated[column] = updated[column].fillna(value)
        else:
            updated[column] = value
    return updated


def _collect_prefixed_extra_information(
    frames: list[pd.DataFrame],
    prefix_config: list[tuple[str, list[str]]],
) -> dict[str, list[str]]:
    """Collect prefixed extra information entries across multiple sheets.

    Args:
        frames (list[pd.DataFrame]): Dataframes that may contain extra
            information columns keyed by ``ID``.
        prefix_config (list[tuple[str, list[str]]]): Mapping of prefix labels to
            candidate column names (in lowercase) to source values from.

    Returns:
        dict[str, list[str]]: Mapping from identifier strings to ordered lists of
        prefixed extra information entries.

    """
    aggregated: dict[str, dict[str, list[str]]] = {}
    for frame in frames:
        frame_entries = _collect_prefixed_entries_for_frame(frame, prefix_config)
        if frame_entries:
            _merge_prefixed_entry_maps(aggregated, frame_entries)

    result: dict[str, list[str]] = {}
    for identifier, prefix_map in aggregated.items():
        combined_entries: list[str] = []
        for prefix, values in prefix_map.items():
            combined_value = "; ".join(values)
            prefixed = _compose_prefixed_value(prefix, combined_value)
            if prefixed and prefixed not in combined_entries:
                combined_entries.append(prefixed)
        result[identifier] = combined_entries

    return result


def _append_prefixed_extra_information(
    ireland_df: pd.DataFrame,
    frames: list[pd.DataFrame],
    prefix_config: list[tuple[str, list[str]]] = EXTRA_INFORMATION_PREFIX_CONFIG,
) -> pd.DataFrame:
    """Append prefixed extra information entries to the Ireland dataframe.

    Args:
        ireland_df (pd.DataFrame): Ireland dataframe containing the ``ID`` and
            ``Extra Information`` columns.
        frames (list[pd.DataFrame]): Source dataframes used to populate extra
            information.
        prefix_config (list[tuple[str, list[str]]], optional): Prefix
            configuration describing which columns to read. Defaults to
            ``EXTRA_INFORMATION_PREFIX_CONFIG``.

    Returns:
        pd.DataFrame: Dataframe with ``Extra Information`` updated to include
        newly prefixed entries.

    """
    if ireland_df.empty or "ID" not in ireland_df.columns:
        return ireland_df

    entries_by_identifier = _collect_prefixed_extra_information(frames, prefix_config)
    if not entries_by_identifier:
        return ireland_df

    updated = ireland_df.copy()
    if "Extra Information" not in updated.columns:
        updated["Extra Information"] = None

    for row_index, identifier in enumerate(updated["ID"]):
        if pd.isna(identifier):
            continue
        entry_list = entries_by_identifier.get(str(identifier))
        if not entry_list:
            continue
        updated.loc[row_index, "Extra Information"] = _merge_relation_entries(
            updated.loc[row_index, "Extra Information"],
            entry_list,
        )

    return updated


def _strip_accents(value: str) -> str:
    """Remove diacritic marks from a string while preserving base characters.

    Args:
        value (str): Input string potentially containing accented characters.

    Returns:
        str: String with accents removed.

    """
    normalized = unicodedata.normalize("NFKD", value)
    ascii_bytes = normalized.encode("ascii", "ignore")
    return ascii_bytes.decode("ascii")


def _contains_special_characters(value: str) -> bool:
    """Determine whether a string contains accented or non-ASCII characters.

    Args:
        value (str): Input string to evaluate.

    Returns:
        bool: ``True`` when accents or non-ASCII characters are present.

    """
    if not value:
        return False
    stripped = _strip_accents(value)
    if stripped != value:
        return True
    return not stripped.isascii()


def _format_name_value(raw_value: object) -> str | None:
    """Format a name cell value using the bracketed convention.

    Args:
        raw_value (object): Original value from the ``Name`` column.

    Returns:
        str | None: Value formatted as ``["value"]`` or ``None`` when empty.

    Raises:
        None.

    """
    formatted_value: str | None

    if isinstance(raw_value, str):
        base = _truncate_after_comma(raw_value.strip())
        cleaned = _normalise_name_tokens(base)
        formatted_value = cleaned if cleaned else None
    elif raw_value is None:
        formatted_value = None
    else:
        try:
            is_missing = bool(pd.isna(raw_value))  # type: ignore[arg-type] # Accept arbitrary scalar inputs such as numpy types
        except TypeError:
            is_missing = False

        if is_missing:
            formatted_value = None
        else:
            base = _truncate_after_comma(str(raw_value).strip())
            cleaned = _normalise_name_tokens(base)
            formatted_value = cleaned if cleaned else None

    if formatted_value is None:
        return None

    if formatted_value.startswith('["') and formatted_value.endswith('"]'):
        return formatted_value

    return _format_bracketed_entries([formatted_value])


def _normalise_relation_entries(raw_value: object) -> list[str]:
    """Convert a relation cell value into a list of cleaned entries.

    Args:
        raw_value (object): Original value from the ``Relation With`` column.

    Returns:
        list[str]: Cleaned list of relation entries.

    """
    entries: list[str] = []
    if isinstance(raw_value, str):
        trimmed = raw_value.strip()
        if trimmed:
            quoted_matches = [
                match.strip()
                for match in re.findall(r'"([^\"]+)"', trimmed)
                if match.strip()
            ]
            entries = (
                quoted_matches
                if quoted_matches
                else [item.strip() for item in trimmed.split(",") if item.strip()]
            )
        return entries

    if raw_value is None:
        return entries

    try:
        is_missing = bool(pd.isna(raw_value))  # type: ignore[arg-type]
    except TypeError:
        is_missing = False

    if is_missing:
        return entries

    text = str(raw_value).strip()
    if text and text.lower() not in {"nan", "none", "<na>", "pandas.na"}:
        entries = [text]
    return entries


def _merge_relation_entries(
    existing_value: object,
    new_entries: list[str],
    *,
    allow_duplicates: bool = False,
) -> str | None:
    """Merge semicolon-separated entries with optional de-duplication.

    Args:
        existing_value (object): Current cell value (e.g., relation or type).
        new_entries (list[str]): Values to append to ``existing_value``.
        allow_duplicates (bool, optional): When ``True`` duplicates in ``new_entries``
            are preserved. Defaults to ``False``.

    Returns:
        str | None: Updated relation string including ``new_entries``, or ``None``
        when no entries remain.

    """
    entries = _normalise_relation_entries(existing_value)

    def _normalise_candidate(candidate: object) -> str:
        return (
            candidate.strip() if isinstance(candidate, str) else str(candidate).strip()
        )

    if allow_duplicates:
        for candidate in new_entries:
            candidate_text = _normalise_candidate(candidate)
            if candidate_text:
                entries.append(candidate_text)
        return _format_bracketed_entries(entries)

    tracked_values = set(entries)
    for candidate in new_entries:
        candidate_text = _normalise_candidate(candidate)
        if not candidate_text:
            continue
        if candidate_text not in tracked_values:
            entries.append(candidate_text)
            tracked_values.add(candidate_text)

    return _format_bracketed_entries(entries)


def _flatten_bracketed_value(value: object) -> str | None:
    """Convert a bracketed relation value into a plain string.

    Args:
        value (object): Original cell value that may use bracketed notation.

    Returns:
        str | None: Semicolon-separated string without brackets, or ``None`` when empty.

    """
    entries = _normalise_relation_entries(value)
    if entries:
        capitalised_entries = [_capitalise_first_character(entry) for entry in entries]
        return "; ".join(capitalised_entries)

    if value is None:
        return None

    try:
        is_missing = bool(pd.isna(value))  # type: ignore[arg-type] # Pandas handles scalar missing values
    except TypeError:
        is_missing = False

    if is_missing:
        return None

    text_value = str(value).strip()
    capitalised_text = _capitalise_first_character(text_value) if text_value else ""
    return capitalised_text or None


def _format_value_as_bracketed_list(value: object) -> str:
    """Normalise a raw value into a bracketed list string.

    Args:
        value (object): Raw value possibly representing multiple entries.

    Returns:
        str: Bracketed list representation, defaulting to ``[]`` when empty.

    """
    if _value_is_missing(value):
        return "[]"

    entries: list[str] = []
    if isinstance(value, (list, tuple, set)):
        entries = [
            str(item).strip()
            for item in value
            if not _value_is_missing(item) and str(item).strip()
        ]
    else:
        normalised_entries = _normalise_relation_entries(value)
        if normalised_entries:
            entries = normalised_entries
        else:
            text_value = str(value).strip()
            if text_value and text_value not in {"[]", "{}"}:
                entries = [text_value]

    formatted = _format_bracketed_entries(entries)
    return formatted if formatted is not None else "[]"


def _format_address_list_columns(ireland_df: pd.DataFrame) -> pd.DataFrame:
    """Ensure address and identity columns use bracketed list notation.

    Args:
        ireland_df (pd.DataFrame): Ireland dataframe containing the target columns.

    Returns:
        pd.DataFrame: Dataframe with address-related columns formatted as
            bracketed list strings.

    """
    if ireland_df.empty:
        return ireland_df

    updated = ireland_df.copy()
    for column in ADDRESS_LIST_COLUMNS:
        if column not in updated.columns:
            continue
        updated[column] = updated[column].apply(_format_value_as_bracketed_list)

    return updated


def _convert_bracketed_value_to_list(value: object) -> list[str]:
    """Convert a bracketed string into a list of serialised entries.

    Args:
        value (object): Value potentially containing a bracketed string.

    Returns:
        list[str]: Normalised list representation. Returns an empty list when the
            input is missing or empty.

    """
    if _value_is_missing(value):
        return []

    normalised: list[str]

    if isinstance(value, list):
        normalised = [item if isinstance(item, str) else str(item) for item in value]
    elif isinstance(value, (tuple, set)):
        normalised = [
            item if isinstance(item, str) else str(item)
            for item in value
            if not _value_is_missing(item)
        ]
    elif isinstance(value, str):
        trimmed = value.strip()
        if not trimmed or trimmed.lower() == "none" or trimmed in {"[]", "{}"}:
            normalised = []
        elif trimmed.startswith("[") and trimmed.endswith("]"):
            try:
                parsed = json.loads(trimmed)
            except json.JSONDecodeError:
                normalised = [trimmed]
            else:
                if isinstance(parsed, list):
                    normalised = [
                        item if isinstance(item, str) else str(item)
                        for item in parsed
                        if not _value_is_missing(item)
                    ]
                else:
                    serialised = parsed if isinstance(parsed, str) else str(parsed)
                    normalised = [serialised]
        else:
            normalised = [trimmed]
    else:
        normalised = [value if isinstance(value, str) else str(value)]

    return normalised


def _convert_bracketed_columns_to_lists(
    ireland_df: pd.DataFrame,
    columns: tuple[str, ...] = LIST_OUTPUT_COLUMNS,
) -> pd.DataFrame:
    """Convert bracketed string columns to list instances.

    Args:
        ireland_df (pd.DataFrame): Ireland dataframe requiring normalisation.
        columns (tuple[str, ...], optional): Columns to convert. Defaults to
            ``LIST_OUTPUT_COLUMNS``.

    Returns:
        pd.DataFrame: Dataframe with targeted columns stored as lists.

    """
    if ireland_df.empty:
        return ireland_df

    updated = ireland_df.copy()
    for column in columns:
        if column not in updated.columns:
            continue
        updated[column] = updated[column].apply(_convert_bracketed_value_to_list)

    return updated


def _extra_information_to_json(value: object) -> str | None:
    """Convert extra information entries into a single JSON object string.

    Args:
        value (object): Original extra information cell value.

    Returns:
        str | None: JSON object string mapping prefixes to values, or ``None``
        when empty.

    """
    entries = _normalise_relation_entries(value)
    if not entries:
        return None

    aggregated: dict[str, list[str]] = {}
    for entry in entries:
        key: str
        val: str
        if ":" in entry:
            key_part, value_part = entry.split(":", 1)
            key = key_part.strip()
            val = value_part.strip()
        else:
            key = "value"
            val = entry.strip()
        if not val:
            continue
        capitalised_val = _capitalise_first_character(val)
        normalised_key = key or "value"
        bucket = aggregated.setdefault(normalised_key, [])
        if capitalised_val not in bucket:
            bucket.append(capitalised_val)

    if not aggregated:
        return None

    serialisable: dict[str, str | list[str]] = {}
    for key, values in aggregated.items():
        if not values:
            continue
        serialisable[key] = values[0] if len(values) == 1 else values

    if not serialisable:
        return None

    return json.dumps(serialisable, ensure_ascii=False, separators=(",", ":"))


def _remap_relationship_type_value(value: object) -> str | None:
    """Remap relationship type entries to human-friendly categories.

    Args:
        value (object): Original ``Relationship Type`` cell value.

    Returns:
        str | None: Remapped value with aliases applied, or ``None`` if empty.

    """
    entries = _normalise_relation_entries(value)
    if not entries:
        return None

    remapped = [RELATIONSHIP_TYPE_MAP.get(entry, entry) for entry in entries]
    return _format_bracketed_entries(remapped)


def _apply_relationship_type_mapping(ireland_df: pd.DataFrame) -> pd.DataFrame:
    """Apply relationship type remapping across the dataframe column.

    Args:
        ireland_df (pd.DataFrame): Ireland dataframe containing ``Relationship Type``.

    Returns:
        pd.DataFrame: Copy of dataframe with remapped relationship categories.

    """
    if "Relationship Type" not in ireland_df.columns:
        return ireland_df

    updated = ireland_df.copy()
    updated["Relationship Type"] = updated["Relationship Type"].apply(
        _remap_relationship_type_value,
    )
    return updated


def _append_rca_ids_to_sources(
    ireland_df: pd.DataFrame,
    source_to_rca_links: dict[str, list[tuple[str, str]]],
) -> pd.DataFrame:
    """Append generated RCA identifiers to parent rows in relationship columns.

    Args:
        ireland_df (pd.DataFrame): Ireland dataframe with prefixed identifiers.
        source_to_rca_links (dict[str, list[tuple[str, str]]]): Mapping from source IDs
            to pairs of ``(relationship_type, rca_identifier)``.

    Returns:
        pd.DataFrame: Dataframe with updated ``Relation With`` and
        ``Relationship Type`` values.

    """
    if not source_to_rca_links:
        return ireland_df

    updated = ireland_df.copy()

    for source_id, rca_entries in source_to_rca_links.items():
        filtered_entries = [
            entry
            for entry in rca_entries
            if isinstance(entry[0], str)
            and entry[0].lower() not in EXCLUDED_RELATIONSHIP_COLUMNS
        ]
        if not filtered_entries:
            continue
        relationship_types = [entry[0] for entry in filtered_entries]
        rca_ids = [entry[1] for entry in filtered_entries]
        mask = updated["ID"] == source_id
        if not mask.any():
            continue
        updated.loc[mask, "Relation With"] = updated.loc[mask, "Relation With"].apply(
            lambda value, ids=rca_ids: _merge_relation_entries(value, ids),
        )
        updated.loc[mask, "Relationship Type"] = updated.loc[
            mask, "Relationship Type"
        ].apply(
            lambda value, types=relationship_types: _merge_relation_entries(
                value,
                types,
                allow_duplicates=True,
            ),
        )

    return _apply_relationship_type_mapping(updated)


def _append_rca_rows(
    ireland_df: pd.DataFrame,
    pep_rca: pd.DataFrame,
    ireland_cols: pd.Index,
    existing_lookup: dict[str, str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Ensure relationship columns exist, prefix IDs, and append RCA rows.

    Args:
        ireland_df (pd.DataFrame): Ireland dataframe populated from primary sheets.
        pep_rca (pd.DataFrame): RCA sheet containing relationship information.
        ireland_cols (pd.Index): Column ordering from the Ireland template.
        existing_lookup (dict[str, str] | None): Optional mapping of normalised
            RCA names to identifiers sourced from a prior lookup workbook.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]:
            - Combined dataframe containing the original rows plus appended RCAs.
            - Dataframe of RCA rows only (may be empty when no RCA data exists).

    """
    prepared = _ensure_relationship_columns(ireland_df.copy())
    prefixed, id_mapping = _prefix_identifier_column(prepared)

    rca_rows, source_to_rca_links = _build_rca_rows(
        pep_rca,
        ireland_cols,
        id_mapping,
        existing_lookup=existing_lookup,
    )
    prefixed = _append_rca_ids_to_sources(prefixed, source_to_rca_links)

    combined = prefixed
    if not rca_rows.empty:
        combined = pd.concat([prefixed, rca_rows], ignore_index=True)

    return combined, rca_rows


def _ensure_all_columns(
    ireland_df: pd.DataFrame, ireland_cols: pd.Index
) -> pd.DataFrame:
    """Add any missing Ireland template columns to the dataframe.

    Args:
        ireland_df (pd.DataFrame): Dataframe possibly missing columns.
        ireland_cols (pd.Index): Required Ireland template columns.

    Returns:
        pd.DataFrame: Dataframe with all required columns present.

    """
    for column in ireland_cols:
        if column not in ireland_df.columns:
            ireland_df[column] = None
    return ireland_df


def _write_rca_lookup_file(
    rca_rows: pd.DataFrame,
    output_path: Path,
    *,
    existing_lookup_df: pd.DataFrame | None = None,
) -> Path:
    """Create an RCA lookup workbook pairing names with generated identifiers.

    Args:
        rca_rows (pd.DataFrame): Dataframe containing RCA records.
        output_path (Path): Path to the primary Ireland 44 workbook.
        existing_lookup_df (pd.DataFrame | None, optional): Previously stored
            lookup dataframe used to preserve identifiers. Defaults to ``None``.

    Returns:
        Path: File path of the generated RCA lookup workbook.

    """
    lookup_path = os.path.join(CLEANED_DIR, "pep_ireland_living_relevant_rca_lookup.xlsx")

    ordered_lookup: dict[str, tuple[str, str]] = {}

    if existing_lookup_df is not None and not existing_lookup_df.empty:
        for raw_name, raw_id in zip(
            existing_lookup_df["RCA Name"],
            existing_lookup_df["RCA ID"],
            strict=False,
        ):
            entry = _extract_existing_lookup_entry(raw_name, raw_id)
            if entry is None:
                continue
            normalised_name, identifier, display_name = entry
            if normalised_name not in ordered_lookup:
                ordered_lookup[normalised_name] = (identifier, display_name)

    if not rca_rows.empty:
        for raw_name, identifier in zip(
            rca_rows["Name"],
            rca_rows["ID"],
            strict=True,
        ):
            entry = _extract_new_lookup_entry(raw_name, identifier)
            if entry is None:
                continue
            normalised_name, identifier_str, display_name = entry
            if normalised_name in ordered_lookup:
                existing_identifier, _ = ordered_lookup[normalised_name]
                identifier_str = existing_identifier or identifier_str
            ordered_lookup[normalised_name] = (identifier_str, display_name)

    lookup_df = pd.DataFrame(
        {
            "RCA ID": [entry[0] for entry in ordered_lookup.values()],
            "RCA Name": [entry[1] for entry in ordered_lookup.values()],
        },
    )

    if lookup_df.empty:
        lookup_df = pd.DataFrame(columns=["RCA ID", "RCA Name"])

    lookup_df = lookup_df[["RCA Name", "RCA ID"]]

    lookup_df.to_excel(lookup_path, index=False, sheet_name="RCA Lookup")
    logger.info("RCA lookup workbook generated at: %s", lookup_path)
    return lookup_path


def pep_to_ireland44(
    pep_file: str | Path = "pep_ireland_living_relevant_20251110_135822.xlsx",
    ireland_template_file: str | Path = None,
    output_file: str | Path | None = None,
) -> None:
    """Convert the multi-sheet PEP workbook into the single-sheet Ireland 44 format.

    Args:
        pep_file (str | Path): Path to the PEP workbook produced by the scraper.
        ireland_template_file (str | Path): Path to an Ireland 44 template workbook
            whose first sheet provides the required column ordering.
        output_file (str | Path | None): Destination path or directory. When ``None``,
            the generated workbook is saved alongside ``pep_file`` using the same name
            with an ``_complete`` suffix.

    Returns:
        None: The resulting workbook is written to ``output_file``.

    Raises:
        FileNotFoundError: If any of the provided paths cannot be read or written.

    """
    pep_path = Path(pep_file)
    if ireland_template_file:
        template_path = Path(ireland_template_file)
    output_hint = Path(output_file) if output_file is not None else None
    output_path = _resolve_output_path(pep_path, output_hint)
    existing_lookup_map, existing_lookup_df = _load_existing_rca_lookup(output_path)

    pep_sheets = pd.read_excel(pep_path, sheet_name=None)
    pep_main = _normalise_id_column(_safe_sheet(pep_sheets, "Main"))
    pep_dob = _normalise_id_column(_safe_sheet(pep_sheets, "DOB"))
    pep_nat = _normalise_id_column(_safe_sheet(pep_sheets, "Nationality"))
    pep_alias = _normalise_id_column(_safe_sheet(pep_sheets, "Alias"))
    pep_address = _normalise_id_column(_safe_sheet(pep_sheets, "Address"))
    pep_case = _normalise_id_column(_safe_sheet(pep_sheets, "Case Details"))
    pep_role = _normalise_id_column(_safe_sheet(pep_sheets, "Role Type"))
    pep_rca = _normalise_id_column(_safe_sheet(pep_sheets, "RCA"))

    ireland_cols = [
        "ID",
        "Name",
        "Father Name",
        "Gender",
        "Description",
        "Place of Birth",
        "Deceased Dissolved Status",
        "Deceased Dissolved Date",
        "Registration Date",
        "Date of Inclusion",
        "Date of Exclusion",
        "Head Bounty",
        "Extra Information",
        "Source List",
        "Category",
        "List Category",
        "List Type",
        "Image Tag",
        "Scraper Tag",
        "Updated On",
        "Added On",
        "Status",
        "Charges",
        "Case Details",
        "Notification Reference",
        "ID Type",
        "ID Number",
        "Date of Birth",
        "Nationality",
        "Alias Type",
        "Alias",
        "Primary Address",
        "Street",
        "City",
        "State",
        "Country of Residence",
        "ZIP",
        "Other Details",
        "Primary Occupation",
        "Designation",
        "Start Date",
        "End Date",
        "Relationship Type",
        "Relation With",
    ]

    unique_ids = _collect_unique_ids(
        [
            pep_main,
            pep_dob,
            pep_nat,
            pep_alias,
            pep_address,
            pep_case,
            pep_role,
            pep_rca,
        ],
    )

    ireland_df = pd.DataFrame({"ID": unique_ids})
    ireland_df = _merge_main_sheet(ireland_df, pep_main)
    ireland_df = _apply_column_mappings(
        ireland_df,
        pep_dob,
        pep_nat,
        pep_alias,
        pep_address,
        pep_case,
        pep_role,
    )
    ireland_df = _append_prefixed_extra_information(
        ireland_df,
        [pep_main, pep_role],
    )
    ireland_df, rca_rows = _append_rca_rows(
        ireland_df,
        pep_rca,
        ireland_cols,
        existing_lookup=existing_lookup_map,
    )
    ireland_df = _apply_static_column_values(ireland_df)
    ireland_df = _ensure_all_columns(ireland_df, ireland_cols)

    ireland_df = ireland_df.loc[:, ireland_cols]

    columns_to_flatten = [
        "Name",
        "Father Name",
        "Gender",
        "Description",
        "Place of Birth",
        "Case Details",
    ]
    for column in columns_to_flatten:
        if column in ireland_df.columns:
            ireland_df[column] = ireland_df[column].apply(_flatten_bracketed_value)

    if "Extra Information" in ireland_df.columns:
        ireland_df["Extra Information"] = ireland_df["Extra Information"].apply(
            _extra_information_to_json,
        )

    ireland_df = _format_address_list_columns(ireland_df)
    ireland_df = _fill_missing_structured_entries(ireland_df)
    ireland_df = _convert_bracketed_columns_to_lists(ireland_df)

    logger.info(
        "All PEP sheets collated into a single tab with 44 column formatting. Saved to: %s",
        output_path,
    )
    _write_rca_lookup_file(rca_rows, output_path, existing_lookup_df=existing_lookup_df)
    return ireland_df

def common_cleaning(df):
    columns_to_strip = [
        "ID",
        "Name",
        "Father Name",
        "Gender",
        "Description",
        "Place of Birth",
        "Deceased Dissolved Status",
        "Head Bounty",
        "Source List",
        "Category",
        "List Category",
        "List Type",
        "Image Tag",
        "Scraper Tag",
        "Status",
        "Charges",
        "Case Details",
        "Notification Reference",
    ]
    df[columns_to_strip] = df[columns_to_strip].apply(
        lambda col: col.apply(lambda x: x.strip() if isinstance(x, str) else x)
    )
    columns_with_lists = [
        "ID Type",
        "ID Number",
        "Nationality",
        "Alias Type",
        "Alias",
        "Primary Address",
        "Street",
        "City",
        "State",
        "Country of Residence",
        "ZIP",
        "Other Details",
        "Primary Occupation",
        "Designation",
        "Relationship Type",
        "Relation With",
    ]
    for col in columns_with_lists:
        df[col] = df[col].apply(
            lambda x: ([element.strip() for element in x] if isinstance(x, list) else x)
        )

    df = df[
        [
            "Name",
            "Father Name",
            "Gender",
            "Description",
            "Head Bounty",
            "Category",
            "Source List",
            "List Category",
            "List Type",
            "Updated On",
            "Added On",
            "Image Tag",
            "Scraper Tag",
            "ID",
            "Date of Exclusion",
            "Date of Inclusion",
            "Deceased Dissolved Status",
            "Deceased Dissolved Date",
            "Registration Date",
            "Extra Information",
            "Status",
            "Place of Birth",
            "ID Type",
            "ID Number",
            "Date of Birth",
            "Nationality",
            "Alias Type",
            "Alias",
            "Primary Address",
            "Street",
            "City",
            "State",
            "Country of Residence",
            "ZIP",
            "Other Details",
            "Charges",
            "Case Details",
            "Notification Reference",
            "Primary Occupation",
            "Designation",
            "Start Date",
            "End Date",
            "Relationship Type",
            "Relation With",
        ]
    ]

    df.fillna("", inplace=True)
   
    def _sanitise_date_list(value):
        if not isinstance(value, list):
            return value
        cleaned = []
        for item in value:
            if item is None:
                cleaned.append(None)
            elif isinstance(item, str) and item.strip().lower() in (
                "none", "null", "nan", "nat", ""
            ):
                cleaned.append(None)
            else:
                cleaned.append(item)
        return cleaned

    for date_col in ["Start Date", "End Date"]:
        if date_col in df.columns:
            df[date_col] = df[date_col].apply(_sanitise_date_list)
    df.drop(index=df[df["Name"] == ""].index, inplace=True)
    return df

def replacements_for_delta(df):
    df.replace('', 'NULL', inplace=True)
    replacement_values = {'Deceased Dissolved Date': {'NULL': '1890-01-01'},
                        'Registration Date': {'NULL': '1890-01-01'},
                        'Date of Inclusion': {'NULL': '1890-01-01'},
                        'Date of Exclusion': {'NULL': '1890-01-01'},
                        'Updated On': {'NULL': '1890-01-01'},
                        'Added On': {'NULL': '2025-11-11'}}
    df.replace(replacement_values, inplace=True)
    return df


def ireland_pep_scrapper(raw_file_path: str = None) -> pd.DataFrame: 
    global RAW_FILE_PATH                    # the variable declared at top of file 
    if raw_file_path is not None: 
        RAW_FILE_PATH = raw_file_path       # override with the path passed in 
    try: 
        logger.info('Starting ireland PEP scraper...') 
        clean_df = pep_to_ireland44(RAW_FILE_PATH)
        clean_df = common_cleaning(clean_df)
        clean_df = replacements_for_delta(clean_df)
        clean_df.to_excel(CLEAN_XLSX, index=False)
        logger.info("ireland PEP scraper completed successfully.")
        return clean_df
    except Exception as e:
        logger.error(
            get_standard_logger_message(
                "ireland_pep_scrapper()", e, "Error in ireland PEP scraper"
            )
        )
        raise
