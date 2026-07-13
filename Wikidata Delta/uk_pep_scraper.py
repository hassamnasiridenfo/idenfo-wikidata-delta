import json
import logging
import os
import re
import secrets
import string
import unicodedata
from unidecode import unidecode
from pathlib import Path
from deep_translator import GoogleTranslator
import pandas as pd
from datetime import datetime
from ast import literal_eval


METADATA = {
    "Name": "General UK",
    "Publisher": "Idenfo",
    "Description": "A detailed database of United Kingdom's political figures and leadership profiles, offering reliable information for compliance, due diligence, and risk management. Designed for financial institutions, corporates, and professionals who require accurate insights into United Kingdom's political landscape.",
    "Country": "UK",
    "Weblink": "Idenfo Research",
    "Tag": "uk_gen",
    "Status": 1,
}


SCRAPER_DIR = Path(__file__).parent
SCRAPER_NAME = SCRAPER_DIR.name
# BASE_DIR = SCRAPER_DIR.parent.parent
# RAW_DIR = BASE_DIR / "Raw"
# CLEANED_DIR = BASE_DIR / "Cleaned"
# UTILS_DIR = BASE_DIR / "Util_excels"

# Changed By Hassam Nasir — raw/cleaned apne uk_gen_excels folder mein; UTILS main folder mein (Updated CountryList.xlsx wahan hai)
# RAW_DIR = SCRAPER_DIR
# CLEANED_DIR = SCRAPER_DIR
RAW_DIR = SCRAPER_DIR / "uk_gen_excels"
CLEANED_DIR = SCRAPER_DIR / "uk_gen_excels"
UTILS_DIR = SCRAPER_DIR


# Ensure directories exist
RAW_DIR.mkdir(parents=True, exist_ok=True)
CLEANED_DIR.mkdir(parents=True, exist_ok=True)

# ============================================
# LOGGING SETUP (Scraper-specific log file)
# ============================================
# Changed By Hassam Nasir — log apne uk_gen_excels folder ke andar save ho
# LOG_FILE = SCRAPER_DIR / f"{METADATA['Tag']}.log"
LOG_FILE = CLEANED_DIR / f"{METADATA['Tag']}.log"
translator = GoogleTranslator(source="auto", target="en")

# Changed By Hassam Nasir
# Translation cache: same source naam -> hamesha same English (deterministic) -> churn khatam.
# Naya record aaye jiska translation cache me nahi -> ek baar translate karke cache me save ->
# agli run me wahi cache se. unidecode: translate ke baad bhi non-English reh jaye to
# English-alphabet me likho -> naam har run same -> re-insert (churn) na ho.
TRANSLATION_CACHE_PATH = os.path.join(CLEANED_DIR, "pep_uk_translation_cache.xlsx")


def _load_translation_cache() -> dict:
    if os.path.exists(TRANSLATION_CACHE_PATH):
        try:
            _df = pd.read_excel(TRANSLATION_CACHE_PATH)
            return {
                str(s): str(t)
                for s, t in zip(_df["Source"], _df["Translation"])
                if pd.notna(s) and pd.notna(t)
            }
        except Exception as _e:
            logger.warning(f"Translation cache read failed: {_e}")
    return {}


_TRANSLATION_CACHE = _load_translation_cache()


def cached_translate(text: str) -> str:
    """Translate via cache first; on miss, call Google once and store it (ASCII-normalized)."""
    key = str(text).strip()
    if not key:
        return text
    if key in _TRANSLATION_CACHE:
        result = _TRANSLATION_CACHE[key]
    else:
        result = translator.translate(key)
    if result and not str(result).isascii():
        result = unidecode(result)
    if result:
        _TRANSLATION_CACHE[key] = result
    return result


def _save_translation_cache() -> None:
    try:
        pd.DataFrame(
            {
                "Source": list(_TRANSLATION_CACHE.keys()),
                "Translation": list(_TRANSLATION_CACHE.values()),
            }
        ).to_excel(TRANSLATION_CACHE_PATH, index=False)
    except Exception as _e:
        logger.warning(f"Translation cache save failed: {_e}")

logger = logging.getLogger(METADATA["Tag"])
if not logger.handlers:
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    # Prevent propagation to root logger (main log)
    logger.propagate = False


# ============================================
# REQUIRED FUNCTION: get_metadata()
# ============================================
def get_metadata():
    """
    Returns metadata dict for DB insertion
    This function is REQUIRED and called by main.py
    """
    return METADATA


CLEAN_FILE_PATH = os.path.join(
    CLEANED_DIR, "pep_united_kingdom_living_relevant_cleaned.xlsx"
)
RAW_FILE_PATH = os.path.join(RAW_DIR, "pep_united_kingdom_living_relevant_raw.xlsx")
RCA_FILE_PATH = os.path.join(
    CLEANED_DIR, "pep_united_kingdom_living_relevant_rca_lookup.xlsx"
)


# RCA Configuration
RELATIONSHIP_TYPE_MAP = {
    "FatherLabel": "Father",
    "MotherLabel": "Mother",
    "SiblingLabel": "Sibling",
    "SpouseLabel": "Partner",
    "ChildLabel": "Child",
    "RelativeLabel": "Relative",
    "SignificantPersonLabel": "Associate",
    # Also keep lowercase versions for compatibility
    "fatherLabel": "Father",
    "motherLabel": "Mother",
    "siblingLabel": "Sibling",
    "spouseLabel": "Partner",
    "childLabel": "Child",
    "relativeLabel": "Relative",
    "significantPersonLabel": "Associate",
}

EXCLUDED_RELATIONSHIP_COLUMNS = {"fatherlabel", "father", "FatherLabel", "Father"}


def get_standard_logger_message(func_name, err, message):
    return f"""{func_name}| Error: {err} Message: {message}"""


def check_if_date(date_str: str) -> bool:
    # check if the string is a date in any common format
    date_formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%B %d, %Y",
        "%d %B %Y",
        "%b %d, %Y",
        "%d %b %Y",
    ]
    for fmt in date_formats:
        try:
            datetime.strptime(date_str, fmt)
            return True
        except ValueError:
            continue
    return False


def normalize_list_strings(
    list_str: str, return_type: str | None = None, splitter: str | None = None
) -> str | list[str]:
    """Normalize list strings by splitting, cleaning, and returning as list or string.

    For example '['United kingdom'],['uk']' -> 'United kingdom, UK' or ['United kingdom', 'UK'] BASED ON return_type

    """

    if not list_str or pd.isna(list_str):
        return [] if return_type == "list" else ""

    items = (
        [item.strip() for item in list_str.split(splitter)]
        if splitter
        else [list_str.strip()]
    )
    normalized_items = []
    for item in items:
        item = unicodedata.normalize("NFKC", item)
        item = re.sub(r"\s+", " ", item)
        item = item.replace("[", "").replace("]", "").replace('"', "").replace("'", "")
        normalized_items.append(item.strip())

    if return_type == "list":
        return normalized_items
    else:
        return ", ".join(normalized_items)


def capitalize_first_char(text: str) -> str:
    """Capitalize the first alphabetical character."""
    if not text:
        return text
    stripped = text.lstrip()
    if not stripped:
        return text.strip()
    return text[: len(text) - len(stripped)] + stripped[0].upper() + stripped[1:]


def flatten_list_value(value: object) -> str | None:
    """Convert bracketed list to semicolon-separated string."""
    entries = parse_list_entries(value)
    if not entries:
        return None
    capitalized = [capitalize_first_char(e) for e in entries]
    return "; ".join(capitalized)


def parse_list_entries(value: object) -> list[str]:
    """Parse value into list of entries"""
    if is_missing_value(value):
        return []

    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower() in {"none", "null", "[]", "{}"}:
            return []

        # Try JSON parsing
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if x]
            except json.JSONDecodeError:
                pass

        # Try quoted matches
        quoted = [m.strip() for m in re.findall(r'"([^\"]+)"', text) if m.strip()]
        if quoted:
            return quoted

        # Try comma split
        if "," in text:
            return [x.strip() for x in text.split(",") if x.strip()]

        return [text]

    return [str(value).strip()] if str(value).strip() else []


def strip_accents(text: str) -> str:
    """Remove diacritic marks from text."""
    normalized = unicodedata.normalize("NFKD", text)
    return normalized.encode("ascii", "ignore").decode("ascii")


def contains_special_chars(text: str) -> bool:
    """Check if text contains accents or non-ASCII characters."""
    if not text:
        return False
    return strip_accents(text) != text or not strip_accents(text).isascii()


def normalize_name_tokens(text: str) -> str:
    """Clean name by removing accents, hyphens, and special chars."""
    text = strip_accents(text)
    text = text.replace("&", " and ").replace("-", " ").replace("'", " ")
    text = re.sub(r"[^A-Za-z0-9 ]+", " ", text)
    return " ".join(text.split())


def truncate_after_comma(text: str) -> str:
    """Remove everything after the first comma."""
    text = text.strip()
    if text.startswith('["') and text.endswith('"]'):
        text = text[2:-2].strip()
    comma_idx = text.find(",")
    return text[:comma_idx].strip() if comma_idx != -1 else text


def format_name_value(value: object) -> str | None:
    """Format name as bracketed JSON list - matches united_kingdom_pep_scrapper.py"""
    if is_missing_value(value):
        return None

    text = str(value).strip() if not isinstance(value, str) else value.strip()
    if not text:
        return None

    # Remove Q-codes
    base = truncate_after_comma(text)

    # If primary value is Q-code, return None
    if base.startswith("Q") and base[1:].isdigit():
        return None

    if contains_special_chars(base):
        cleaned = cached_translate(base)
        cleaned = normalize_name_tokens(cleaned)
    else:
        cleaned = normalize_name_tokens(base)

    if not cleaned:
        return None

    return cleaned


def get_alias_type(alias: str) -> str:
    if alias:
        if alias.isascii():
            return "Also Known As"
        return "Original Script Name"


def is_missing_value(value: object) -> bool:
    """Check if value represents missing data."""
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except TypeError:
        return False


def initalize_clean_df(raw_df_len: pd.DataFrame) -> pd.DataFrame:
    try:
        num_rows: int = raw_df_len
        data: dict = {
            "ID": [""] * num_rows,
            "Name": [""] * num_rows,
            "Father Name": [""] * num_rows,
            "Gender": [""] * num_rows,
            "Description": [""] * num_rows,
            "Place of Birth": [""] * num_rows,
            "Deceased Dissolved Status": [0] * num_rows,
            "Deceased Dissolved Date": [""] * num_rows,
            "Registration Date": [""] * num_rows,
            "Date of Inclusion": [""] * num_rows,
            "Date of Exclusion": [""] * num_rows,
            "Head Bounty": [""] * num_rows,
            "Extra Information": [{}] * num_rows,
            "Source List": ["Idenfo"] * num_rows,
            "Category": ["General United kingdom"] * num_rows,
            "List Category": [""] * num_rows,
            "List Type": ["Individual"] * num_rows,
            "Image Tag": [""] * num_rows,
            "Scraper Tag": ["uk_gen"] * num_rows,
            "Updated On": [""] * num_rows,
            "Added On": ["2026-01-27"] * num_rows,
            "Status": [1] * num_rows,
            "Charges": [""] * num_rows,
            "Case Details": [""] * num_rows,
            "Notification Reference": [""] * num_rows,
            # List columns - keep as actual lists, not strings
            "ID Type": [[] for _ in range(num_rows)],
            "ID Number": [[] for _ in range(num_rows)],
            "Date of Birth": [[] for _ in range(num_rows)],
            "Nationality": [[] for _ in range(num_rows)],
            "Alias Type": [[] for _ in range(num_rows)],
            "Alias": [[] for _ in range(num_rows)],
            "Primary Address": [[] for _ in range(num_rows)],
            "Street": [[] for _ in range(num_rows)],
            "City": [[] for _ in range(num_rows)],
            "State": [[] for _ in range(num_rows)],
            "Country of Residence": [[] for _ in range(num_rows)],
            "ZIP": [[] for _ in range(num_rows)],
            "Other Details": [[] for _ in range(num_rows)],
            "Primary Occupation": [[] for _ in range(num_rows)],
            "Designation": [[] for _ in range(num_rows)],
            "Start Date": [[] for _ in range(num_rows)],
            "End Date": [[] for _ in range(num_rows)],
            "Relationship Type": [[] for _ in range(num_rows)],
            "Relation With": [[] for _ in range(num_rows)],
        }
        clean_df = pd.DataFrame(data)
        return clean_df
    except Exception as e:
        logger.error(
            get_standard_logger_message(
                "initalize_clean_df()", e, "Error initializing clean dataframe"
            )
        )
        raise


def get_sheet_df(sheet: str, raw_file_path: str | None = None) -> pd.DataFrame:
    try:
        return pd.read_excel(RAW_FILE_PATH, sheet_name=sheet, engine="openpyxl")
    except Exception as e:
        logger.error(
            get_standard_logger_message(
                "get_sheet_df()", e, f"Error loading sheet: {sheet}"
            )
        )
        return pd.DataFrame()


def clean_siblings(siblingLabel: str) -> str | None:
    if siblingLabel is None or pd.isna(siblingLabel):
        return None

    sibling_str = normalize_list_strings(siblingLabel)
    url_pattern = r"https?:\/\/"
    if re.match(url_pattern, sibling_str):
        return "[]"
    if sibling_str in ["spouse", "zero"]:
        return "[]"

    return siblingLabel


def get_raw_df(
    sheet: str = None, raw_file_path: str | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load raw data, returning main df and separate RCA df"""
    main_df = get_sheet_df(sheet="Main")
    dob_df = get_sheet_df(sheet="DOB")
    nat_df = get_sheet_df(sheet="Nationality")
    alias_df = get_sheet_df(sheet="Alias")
    address_df = get_sheet_df(sheet="Address")
    case_df = get_sheet_df(sheet="Case Details")
    role_df = get_sheet_df(sheet="Role Type")
    rca_df = get_sheet_df(sheet="RCA")  # Keep separate
    logger.info("Raw data loaded successfully.")
    # remove familyLabel column from rca_df if exists
    if "familyLabel" in rca_df.columns:
        rca_df = rca_df.drop(columns=["familyLabel"])

    if "childLabel" in rca_df.columns:
        rca_df["childLabel"] = rca_df["childLabel"].apply(
            lambda x: x if x != '["7"]' else None
        )
    if "siblingLabel" in rca_df.columns:
        rca_df["siblingLabel"] = rca_df["siblingLabel"].apply(clean_siblings)

    combined_raw_df = main_df
    sheets = [dob_df, nat_df, alias_df, address_df, case_df, role_df]

    # Merging all sheets EXCEPT RCA on 'ID' column
    for sheet in sheets:
        if not sheet.empty:
            combined_raw_df = combined_raw_df.merge(
                sheet, on="ID", how="left", suffixes=("", "_dup")
            )
            # Drop duplicate columns if any
            dup_cols = [col for col in combined_raw_df.columns if col.endswith("_dup")]
            combined_raw_df.drop(columns=dup_cols, inplace=True)

    return combined_raw_df, rca_df


def create_country_lookup_map():
    """
    Creates a dictionary mapping all known country aliases to their standard name.
    """
    try:
        logger.info("Creating country lookup map...")
        country_df = pd.read_excel(
            os.path.join(UTILS_DIR, "Updated CountryList.xlsx"), sheet_name="Sheet3"
        )
        country_lookup = {}

        for _, row in country_df.iterrows():
            standard_name = row["Country Title 1"]
            if not standard_name or pd.isna(standard_name):
                continue

            aliases = [
                row["Country Title 1"],
                row["Country Title 2"],
                row["Country Title 3"],
                row["Country Title 4"],
                row["Country Code"],
                row["Country Code 3"],
                row["Nationality"],
            ]

            for alias in aliases:
                if alias and pd.notna(alias):
                    key = str(alias).strip().lower()
                    country_lookup[key] = standard_name.title()

        return country_lookup

    except FileNotFoundError as e:
        logger.error(
            get_standard_logger_message(
                "create_country_lookup_map()", e, "Country list file not found"
            )
        )
        return {}
    except Exception as e:
        logger.error(
            get_standard_logger_message(
                "create_country_lookup_map()", e, "Error creating country lookup map"
            )
        )
        return {}


def get_gender(genderLabel: str) -> str:
    if pd.isna(genderLabel) or not genderLabel:
        return ""
    genders = normalize_list_strings(genderLabel, return_type="list", splitter=",")
    if len(genders) == 0:
        return ""

    if genders[0].lower() in [
        "trans woman",
        "cisgender woman",
        "cisgender man",
        "non-binary",
        "genderqueer",
        "hijra",
        "transfeminine",
        "agender",
        "trans man",
        "genderfluid",
    ]:
        return "Other"

    return genders[0].title()


def get_place_of_birth(birthPlaceLabel: str, extra_info: dict) -> str:
    if pd.isna(birthPlaceLabel) or not birthPlaceLabel:
        return ""
    if birthPlaceLabel.count("]") == 1 and birthPlaceLabel.count("[") == 1:
        place = normalize_list_strings(birthPlaceLabel)
        if (
            check_if_date(place)
            or re.match(r"^Q\d+$", place)
            or re.match(r"https?:\/\/", place)
        ):
            return ""
        if not place.isascii():
            extra_info["POB In Other Language"] = cached_translate(place)
        return unidecode(place)
    else:
        # Use parse_list_entries to properly handle bracketed items with commas
        places = parse_list_entries(birthPlaceLabel)
        # Filter out dates without modifying list during iteration
        places = [
            p
            for p in places
            if not check_if_date(p)
            and not re.match(r"^Q\d+$", p)
            and not re.match(r"https?:\/\/", p)
        ]
        if len(places) == 0:
            return ""
        extra_info["Extra POB"] = ""
        extra_info["POB In Other Language"] = ""
        for place in places[1:]:
            if not place.isascii():
                extra_info["Extra POB"] += cached_translate(place) + ", "
                extra_info["POB In Other Language"] += place + ", "
            else:
                extra_info["Extra POB"] += place + ", "
    if "POB In Other Language" in extra_info:
        if not extra_info["POB In Other Language"]:
            del extra_info["POB In Other Language"]
    return unidecode(places[0])


def get_formatted_date(dateStr: str) -> list[str]:
    if not dateStr or pd.isna(dateStr):
        return []

    date_list = normalize_list_strings(dateStr, return_type="list", splitter="],")
    formatted_dates = []

    for date in date_list:
        date = date.strip()

        # Check if it's a URL - if so, append None instead of skipping
        if date.startswith("http://") or date.startswith("https://"):
            formatted_dates.append(None)
            continue

        # Extract date from timestamp format
        match = re.search(r"(\d{4}-\d{2}-\d{2})", date)
        if match:
            formatted_dates.append(match.group(1))
        else:
            formatted_dates.append(None)

    return formatted_dates


def get_nationality(
    nationalityLabel: str, country_lookup: dict, missing_countries: set
) -> list[str]:
    if pd.isna(nationalityLabel) or not nationalityLabel or country_lookup is None:
        return []

    nationalities = normalize_list_strings(
        nationalityLabel, return_type="list", splitter=","
    )
    if len(nationalities) == 0:
        return []
    if len(nationalities) > 1:
        result = []
        for nat in nationalities:
            nat = nat.lower()
            if nat not in country_lookup:
                missing_countries.add(nat)
                result.append(nat)
            else:
                result.append(country_lookup[nat])
        return [r.title() for r in result]
    else:
        nat = nationalities[0].lower()
        if nat not in country_lookup:
            missing_countries.add(nat)
            return [nat]
        else:
            return [country_lookup[nat].title()]


def get_extra_info(
    extra_info: dict,
    educatedAtLabel: str,
    workLocationLabel: str,
    academicDegLabel: str,
    affiliationStrLabel: str,
    Id: str,
) -> dict:
    info = extra_info.copy()
    if pd.notna(educatedAtLabel) and educatedAtLabel:
        educations = normalize_list_strings(
            educatedAtLabel, return_type="list", splitter=","
        )
        if educations:
            info["Educated At"] = ", ".join(educations)
    if pd.notna(workLocationLabel) and workLocationLabel:
        work_locations = normalize_list_strings(
            workLocationLabel, return_type="list", splitter=","
        )
        if work_locations:
            info["Work Location"] = ", ".join(work_locations)
    if pd.notna(academicDegLabel) and academicDegLabel:
        degrees = normalize_list_strings(
            academicDegLabel, return_type="list", splitter=","
        )
        if degrees:
            info["Academic Degree"] = ", ".join(degrees)
    if pd.notna(affiliationStrLabel) and affiliationStrLabel:
        affiliations = normalize_list_strings(
            affiliationStrLabel, return_type="list", splitter=","
        )
        if affiliations:
            info["Affiliation"] = ", ".join(affiliations)
    info["Reference ID"] = Id

    return info


def get_case_details(convictedOfLabel: str, placeOfDetentionLabel: str) -> str:
    details = []
    if pd.notna(convictedOfLabel) and convictedOfLabel:
        convictedLabels = normalize_list_strings(
            convictedOfLabel, return_type="list", splitter=","
        )
        if convictedLabels:
            if len(convictedLabels) == 1:
                details.append(f"Convicted Of: {convictedLabels[0]}")
            else:
                details.append(f"Convicted Of: {', '.join(convictedLabels)}")

    if pd.notna(placeOfDetentionLabel) and placeOfDetentionLabel:
        detentionPlaces = normalize_list_strings(
            placeOfDetentionLabel, return_type="list", splitter=","
        )
        if detentionPlaces:
            if len(detentionPlaces) == 1:
                details.append(f"Place of Detention: {detentionPlaces[0]}")
            else:
                details.append(f"Place of Detention: {', '.join(detentionPlaces)}")
    return ", ".join(details)


def get_role_details(
    positionLabel: str, politicalPartyLabel: str, startTime: str, endTime: str
) -> tuple[list[str], list[str], list[str]]:
    designations = []
    start_dates = []
    end_dates = []

    # Parse start and end times first
    parsed_start_dates = []
    parsed_end_dates = []

    if pd.notna(startTime) and startTime:
        parsed_start_dates = get_formatted_date(startTime)
    if pd.notna(endTime) and endTime:
        parsed_end_dates = get_formatted_date(endTime)

    # Process positions and filter out Q-codes along with their dates
    if pd.notna(positionLabel) and positionLabel:
        # Parse as list literal instead of splitting by comma
        positions = parse_list_entries(positionLabel)

        for i, p in enumerate(positions):
            # Skip Q-codes
            if re.match(r"^Q\d+$", p):
                continue

            # Add the designation
            formatted_position = p.replace(
                "Litvánia miniszterelnökeinek listája",
                "Prime Minister of United kingdom",
            ).title()
            designations.append(formatted_position)

            # Add corresponding dates if they exist
            if i < len(parsed_start_dates):
                start_dates.append(parsed_start_dates[i])
            else:
                start_dates.append(None)

            if i < len(parsed_end_dates):
                end_dates.append(parsed_end_dates[i])
            else:
                end_dates.append(None)

    # Add political party (no corresponding dates, so append None)
    if pd.notna(politicalPartyLabel) and politicalPartyLabel:
        parties = parse_list_entries(politicalPartyLabel)
        for party in parties:
            if re.match(r"^Q\d+$", party):
                continue

            formatted_party = (
                f"Member of {party}"
                if "independent politician" not in party.lower()
                else party.title()
            )
            designations.append(formatted_party)

    # Validate: if start date is None, end date should also be None
    for i in range(len(end_dates)):
        if i < len(start_dates) and start_dates[i] is None and end_dates[i] is not None:
            end_dates[i] = None

    # If there are no valid start dates at all, clear both date lists
    if len(start_dates) == 0 or all(d is None for d in start_dates):
        start_dates = []
        end_dates = []

    return (start_dates, end_dates, designations)


def clean_alias(alias: str) -> str:
    alias = alias.strip()
    alias = alias.replace("-", " ").replace("&", " and ").replace("'", "").strip()
    # if name is non ascii then just remove the punctuations else remove all special characters
    if not alias.isascii():
        alias = (
            alias.replace("“", '"')
            .replace("”", '"')
            .replace("‘", "'")
            .replace("’", "'")
            .replace("(", "")
            .replace(")", "")
            .replace(".", "")
            .replace(",", "")
            .strip()
        )
        return alias.strip()
    alias = re.sub(r"[^\w\s]", " ", alias)
    alias = alias.replace("_", " ")
    alias = re.sub(r"\s+", " ", alias)
    return alias.strip().title()


def clean_name(name_data: dict) -> dict:
    name = name_data.get("name", "")
    if pd.isna(name) or not name:
        name_data["name"] = ""
        return name_data
    name_str = normalize_list_strings(name)

    # check if name is wikidata ID
    matches = re.match(r"^Q\d+$", name_str)
    if matches:
        name_data["name"] = ""
        return name_data

    strs_to_rem = [
        "HON. MR. Justice",
        "HON. MR. JUSTICE",
        "Justice",
        "Honourable",
        "Professor",
        "Prof Dr",
        "Prof.",
        "His Excellency",
        "Dr ",
        "Dr.",
        "HON. MR.",
        "Dr. ",
        "Colonel",
        "Engr.",
        "Chief",
        "Mrs",
        "Mr.",
        "Ms.",
        "Mr",
        "Barr.",
        "HON.",
        "Brigadier General",
        "Barrister",
    ]

    strs_to_rem.sort(key=len, reverse=True)

    for s in strs_to_rem:
        # Use regex with word boundary to match only at the start of the name
        pattern = r"^" + re.escape(s) + r"\s*"
        if re.search(pattern, name_str, re.IGNORECASE):
            name_data["aliases"].append(clean_alias(name_str))
            name_data["alias_types"].append(get_alias_type(name_str))
            name_str = re.sub(pattern, "", name_str, flags=re.IGNORECASE).strip()
            name_str = name_str[0].upper() + name_str[1:] if name_str else ""

    paren_pattern = r"\((.*?)\)"
    if re.search(paren_pattern, name_str):
        name_data["aliases"].append(clean_alias(name_str))
        name_data["alias_types"].append(get_alias_type(name_str))
        name_str = re.sub(paren_pattern, "", name_str).strip()
        name_str = (
            name_str.replace("-", " ").replace("&", " and ").replace("-", " ").strip()
        )

    tmp_name = (
        name_str.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    )
    if not tmp_name.isascii():
        name_data["aliases"].append(clean_alias(name_str))
        name_data["alias_types"].append(get_alias_type(name_str))
        name_str = unidecode(name_str)

    name_str = (
        name_str.replace("-", " ")
        .replace("&", " and ")
        .replace("-", " ")
        .replace("'", "")
        .strip()
    )
    name_str = re.sub(r"[^\w\s]", "", name_str)
    name_str = re.sub(r"\s+", " ", name_str)

    name_data["name"] = name_str.strip().title()
    return name_data


def get_father_name(fatherLabel: str) -> str:
    if pd.isna(fatherLabel) or not fatherLabel:
        return ""
    father_name = normalize_list_strings(fatherLabel)
    matches = re.match(r"^Q\d+$", father_name)
    url_matches = re.match(r"https?:\/\/", father_name)
    if not father_name or matches or url_matches:
        return ""

    if not father_name.isascii():
        father_name = cached_translate(father_name)

    return unidecode(clean_alias(father_name).strip().title())


def clean_rca_name(name: str) -> str:
    if pd.isna(name) or not name:
        return ""
    name = normalize_list_strings(name)

    # check if name is wikidata ID
    matches = re.match(r"^Q\d+$", name)
    if matches:
        return ""

    tmp_name = (
        name.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    )
    if not tmp_name.isascii():
        name = unidecode(name)
    return name.strip()


def get_aliases(
    aka: str, nativeName: str, birthName: str, nonEngLabel: str
) -> tuple[list[str], list[str]]:
    aka_list = parse_list_entries(aka)
    birthName_list = parse_list_entries(birthName)
    nativeName_list = parse_list_entries(nativeName)
    nonEngLabel_list = []
    paren_pattern = r"\((.*?)\)"
    # ── OLD nonEngLabel parsing (commented out — was only extracting index [0],
    #    discarding all Arabic/Urdu/Bengali aliases after the first English entry)
    # if nonEngLabel and not pd.isna(nonEngLabel):
    #     # Convert to string if not already
    #     if not isinstance(nonEngLabel, str):
    #         nonEngLabel = str(nonEngLabel)
    #     if nonEngLabel.startswith('["') and nonEngLabel.endswith('"]'):
    #         try:
    #             nonEngLabel = literal_eval(nonEngLabel)
    #             if isinstance(nonEngLabel, (list, tuple)):
    #                 nonEngLabel = nonEngLabel[0]
    #         except (SyntaxError, ValueError):
    #             # If literal_eval fails, strip the brackets and quotes manually
    #             nonEngLabel = nonEngLabel[2:-2]  # Remove [" and "]
    #     # Ensure it's a string before regex operations
    #     if not isinstance(nonEngLabel, str):
    #         nonEngLabel = str(nonEngLabel)
    #     nonEngLabel = re.sub(paren_pattern, "", nonEngLabel).strip()
    #     if ";" in nonEngLabel:
    #         parts = [part.strip() for part in nonEngLabel.split(";") if part.strip()]
    #         nonEngLabel_list.extend(parts)
    #     else:
    #         nonEngLabel_list.append(nonEngLabel)

    # ── NEW nonEngLabel parsing ───────────────────────────────────────────────
    # raw format: '["alias1"], ["Arabic alias"], ["Urdu alias"], ...'
    # re.findall extracts EVERY entry individually — no Arabic/non-English loss
    if nonEngLabel and not pd.isna(nonEngLabel):
        extracted = re.findall(r'\["([^"]+?)"\]', str(nonEngLabel))
        nonEngLabel_list.extend([e.strip() for e in extracted if e.strip()])

    aka_list = [re.sub(paren_pattern, "", alias).strip() for alias in aka_list]
    complete_aliases = set()
    for alias in aka_list + birthName_list + nativeName_list + nonEngLabel_list:
        clean_alias_str = clean_alias(alias)
        if clean_alias_str:
            complete_aliases.add(clean_alias_str)
    # Changed By Hassam Nasir — set() ka order har run par badalta tha (hash randomization)
    # -> alias sequence / empty-name fallback change -> churn. sorted() se order fixed.
    sorted_aliases = sorted(complete_aliases)
    alias_types = [get_alias_type(alias) for alias in sorted_aliases]

    return sorted_aliases, alias_types


def normalize_rca_lookup_name(value: object) -> str:
    """Normalize RCA name for lookup matching."""
    if is_missing_value(value):
        return ""

    text = str(value)
    flat = flatten_list_value(text) or text
    return " ".join(flat.strip().split()).casefold()


def load_rca_lookup() -> tuple[dict[str, str], pd.DataFrame | None]:
    """Load existing RCA lookup workbook."""

    try:
        df = pd.read_excel(RCA_FILE_PATH)
        logger.info(f"RCA lookup loaded from {RCA_FILE_PATH}")
    except Exception:
        logger.warning(f"Unable to read RCA lookup at {CLEANED_DIR}")
        return {}, None

    if df.empty:
        return {}, pd.DataFrame(columns=["RCA Name", "RCA ID"])

    # Find name and ID columns
    cols_lower = {str(c).strip().casefold(): str(c) for c in df.columns}
    name_col = cols_lower.get("rca name") or cols_lower.get("name")
    id_col = cols_lower.get("rca id") or cols_lower.get("id")

    if not name_col or not id_col:
        return {}, pd.DataFrame(columns=["RCA Name", "RCA ID"])

    mapping = {}
    for name, rca_id in zip(df[name_col], df[id_col], strict=False):
        if is_missing_value(rca_id):
            continue

        id_str = str(rca_id).strip()
        if not id_str:
            continue

        key = normalize_rca_lookup_name(name)
        if key:
            mapping[key] = id_str

    lookup_df = df.rename(columns={name_col: "RCA Name", id_col: "RCA ID"})[
        ["RCA Name", "RCA ID"]
    ]
    return mapping, lookup_df


def generate_initials(name: str) -> str:
    """Generate ASCII initials from name."""
    if not name:
        return "X"

    tokens = re.findall(r"[^\W\d_]+", name, flags=re.UNICODE)
    initials = []

    for token in tokens:
        if not token:
            initials.append("X")
            continue

        first_char = token[0]
        normalized = unicodedata.normalize("NFKD", first_char)
        stripped = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
        ascii_chars = [c for c in stripped if c.isalpha() and c.isascii()]

        if ascii_chars:
            initials.append(ascii_chars[0].upper())
        else:
            fallback = "".join(
                c
                for c in unicodedata.normalize("NFKD", token)
                if c.isalpha() and c.isascii()
            )
            initials.append(fallback[0].upper() if fallback else "X")

    return "".join(initials) or "X"


def generate_random_combo(length: int = 5) -> str:
    """Generate random alphanumeric string."""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def get_or_create_rca_id(
    entity_name: str,
    lookup: dict[str, str],
    used_combos: set[str],
    sequence: dict[tuple[str, str], int],
    country_code: str,
) -> str:
    """Get existing or create new RCA identifier."""
    formatted = format_name_value(entity_name)
    flat = flatten_list_value(formatted) if formatted else None
    lookup_key = normalize_rca_lookup_name(flat or entity_name)

    if lookup_key in lookup:
        return lookup[lookup_key]

    initials = generate_initials(flat or entity_name)
    combo = generate_random_combo()
    while combo in used_combos:
        combo = generate_random_combo()
    used_combos.add(combo)

    key = (initials, combo)
    sequence[key] = sequence.get(key, 0) + 1

    rca_id = f"{country_code}-GEN-{initials}-{combo}-RCA-{sequence[key]}"
    lookup[lookup_key] = rca_id
    return rca_id


def is_valid_rca_name(name: str, category: str) -> bool:
    """Check if RCA name should be included."""
    if not name or not isinstance(name, str):
        return False

    name_lower = name.lower().strip()
    if not name_lower:
        return False

    # Exclude Q-codes
    stripped = name.strip()
    if stripped.startswith("Q") and stripped[1:].isdigit():
        return False

    # Exclude problematic patterns
    has_digits = any(c.isdigit() for c in name)
    has_http = "http" in name_lower
    has_zero = "zero" in name_lower
    has_category = category.lower() in name_lower

    return not (has_digits or has_http or has_zero or has_category)


def build_rca_rows(
    rca_df: pd.DataFrame, existing_lookup: dict[str, str], country_code: str = "UK"
) -> tuple[list[dict], dict[str, list[tuple[str, str]]]]:
    """
    Build RCA rows and track parent-child relationships.
    CORRECTED to match united_kingdom_pep_scrapper.py logic exactly.
    Returns: (rca_records, parent_links)
    """
    if rca_df.empty or "ID" not in rca_df.columns:
        return [], {}

    lookup = existing_lookup.copy()
    used_combos = set()
    sequence = {}
    created_ids = set()  # Track which RCA IDs we've already created
    rca_records = []
    parent_links = {}  # {parent_id: [(relationship_type, rca_id), ...]}

    for col in rca_df.columns:
        if col == "ID" or col.lower() in EXCLUDED_RELATIONSHIP_COLUMNS:
            continue

        subset = rca_df[["ID", col]].dropna(subset=[col])
        if subset.empty:
            continue

        category = col.lower().replace("label", "").strip()

        for parent_id, value in zip(subset["ID"], subset[col], strict=True):
            if is_missing_value(parent_id) or is_missing_value(value):
                continue

            # Parse RCA names using proper list parsing
            entries = parse_list_entries(value)
            if not entries:
                entries = [str(value).strip()]

            for entity_name in entries:
                # Validate RCA name
                if not is_valid_rca_name(entity_name, category):
                    continue

                # Get or create RCA ID
                rca_id = get_or_create_rca_id(
                    entity_name, lookup, used_combos, sequence, country_code
                )

                # Only create record if we haven't already
                if rca_id not in created_ids:
                    # Format the name properly
                    formatted_name = format_name_value(entity_name)
                    if not formatted_name:
                        continue

                    # Create RCA record
                    rca_record = {
                        "ID": rca_id,
                        "Name": formatted_name,
                        "List Category": "Relative Close Associate",
                        "Deceased Dissolved Status": 0,
                        "Alias": [],
                        "Alias Type": [],
                    }

                    # Handle special characters - add as alias with proper type
                    if contains_special_chars(entity_name):
                        # Store original non-ASCII name as alias
                        alias_val = truncate_after_comma(entity_name)
                        rca_record["Alias"] = [alias_val]
                        rca_record["Alias Type"] = ["Original Script Name"]

                    rca_records.append(rca_record)
                    created_ids.add(rca_id)

                # Track parent link using original parent ID (will be mapped later)
                parent_id_str = str(parent_id)
                if parent_id_str not in parent_links:
                    parent_links[parent_id_str] = []
                parent_links[parent_id_str].append((col, rca_id))

    return rca_records, parent_links


def save_rca_lookup(rca_records: list[dict], existing_df: pd.DataFrame | None) -> None:
    """Save RCA lookup workbook - matches united_kingdom_pep_scrapper.py"""
    lookup_path = os.path.join(RCA_FILE_PATH)

    ordered = {}

    # Add existing entries
    if existing_df is not None and not existing_df.empty:
        for name, rca_id in zip(
            existing_df["RCA Name"], existing_df["RCA ID"], strict=False
        ):
            if not is_missing_value(name) and not is_missing_value(rca_id):
                id_str = str(rca_id).strip()
                key = normalize_rca_lookup_name(name)
                if key and key not in ordered:
                    display = str(name).strip()
                    ordered[key] = (id_str, display)

    # Add new entries from RCA records
    for record in rca_records:
        name = record.get("Name", "")
        rca_id = record.get("ID", "")
        if name and rca_id:
            key = normalize_rca_lookup_name(name)
            if key and key not in ordered:
                ordered[key] = (str(rca_id).strip(), str(name).strip())

    lookup_df = pd.DataFrame(
        {
            "RCA Name": [v[1] for v in ordered.values()],
            "RCA ID": [v[0] for v in ordered.values()],
        }
    )

    if lookup_df.empty:
        lookup_df = pd.DataFrame(columns=["RCA Name", "RCA ID"])

    lookup_df.to_excel(lookup_path, index=False, sheet_name="RCA Lookup")
    logger.info(f"RCA lookup saved: {lookup_path}")


def get_clean_df() -> pd.DataFrame:
    # Load data
    raw_df, rca_df = get_raw_df()
    existing_lookup, existing_lookup_df = load_rca_lookup()

    # Initialize clean df for main records only
    clean_df = initalize_clean_df(len(raw_df))
    logger.info("Initialized clean dataframe.")
    loopkup = create_country_lookup_map()
    missing_countries = set()

    # Track ID mapping for relationships
    id_mapping = {}  # {original_wikidata_id: new_clean_df_id}

    # Process main records
    logger.info("Processing main records...")
    for i, row in raw_df.iterrows():
        if i % 100 == 0 and i > 0:
            logger.info(f"Processed {i}/{len(raw_df)} records...")
        try:
            name_data = {
                "name": row.get("personLabel", ""),
                "aliases": [],
                "alias_types": [],
                "extra_info": {},
            }

            # Assign ID and track mapping
            original_id = str(row.get("ID", ""))
            prefixed_id = f"UK-GEN-I-{i+1}"
            id_mapping[original_id] = prefixed_id

            clean_df.loc[i, "ID"] = prefixed_id

            name_data = clean_name(name_data)
            clean_df.loc[i, "Name"] = name_data.get("name", "")
            clean_df.loc[i, "Father Name"] = get_father_name(row.get("fatherLabel", ""))
            clean_df.loc[i, "Gender"] = get_gender(row.get("genderLabel"))
            clean_df.loc[i, "Description"] = normalize_list_strings(
                row.get("personDescription", "")
            ).title()
            clean_df.loc[i, "Place of Birth"] = get_place_of_birth(
                row.get("birthPlaceLabel", ""), name_data["extra_info"]
            )
            clean_df.loc[i, "List Category"] = "Politically Exposed Person"

            if row.get("image", "") and len(str(row.get("image", "")).strip()) < 256:
                clean_df.loc[i, "Image Tag"] = row.get("image", "")
            else:
                clean_df.loc[i, "Image Tag"] = ""
                logger.warning(
                    f"Image URL too long or missing for ID {original_id}, setting to empty."
                )
            clean_df.at[i, "Primary Address"] = normalize_list_strings(
                row.get("residenceLabel", ""), return_type="list", splitter=","
            )
            clean_df.at[i, "Date of Birth"] = get_formatted_date(row.get("birthDate"))
            clean_df.at[i, "Nationality"] = get_nationality(
                row.get("nationalityLabel", ""), loopkup, missing_countries
            )
            clean_df.loc[i, "Case Details"] = get_case_details(
                row.get("convictedOfLabel", ""), row.get("placeOfDetentionLabel", "")
            )
            clean_df.at[i, "Primary Occupation"] = [
                po.title()
                for po in normalize_list_strings(
                    row.get("occupationLabel", ""), return_type="list", splitter=","
                )
                if not re.search(r"^Q\d+$", po)
            ]
            (
                clean_df.at[i, "Start Date"],
                clean_df.at[i, "End Date"],
                clean_df.at[i, "Designation"],
            ) = get_role_details(
                row.get("positionLabel", ""),
                row.get("politicalPartyLabel", ""),
                row.get("startTime", ""),
                row.get("endTime", ""),
            )

            aliases, alias_types = get_aliases(
                row.get("AKA", ""),
                row.get("nativeName", ""),
                row.get("birthName", ""),
                row.get("nonEnglishLabel", ""),
            )

            aliases.extend(name_data["aliases"])
            alias_types.extend(name_data["alias_types"])

            unique_aliases = []
            unique_alias_types = []
            for a, at in zip(aliases, alias_types):
                if a not in unique_aliases:
                    unique_aliases.append(a)
                    unique_alias_types.append(at)

            clean_df.at[i, "Alias"] = unique_aliases
            clean_df.at[i, "Alias Type"] = unique_alias_types

            extra_info = get_extra_info(
                name_data["extra_info"],
                row.get("educatedAtLabel", ""),
                row.get("workLocationLabel", ""),
                row.get("academicDegreeLabel", ""),
                row.get("affiliationStringLabel", ""),
                original_id,
            )
            clean_df.at[i, "Extra Information"] = json.dumps(extra_info)

        except Exception as e:
            logger.error(
                get_standard_logger_message(
                    "get_clean_df()", e, f"Error processing row index {i}"
                ),
                exc_info=True,
            )
            continue

    logger.info("Main records processing completed.")
    # Handle empty names
    empty_name_rows = clean_df[clean_df["Name"] == ""]
    for idx, empty_row in empty_name_rows.iterrows():
        if empty_row["Alias"]:
            aliases = empty_row["Alias"]
            alias_types = empty_row["Alias Type"]
            for j, alias in enumerate(aliases):
                if alias.isascii():
                    clean_df.at[idx, "Name"] = clean_alias(alias)
                    break

            if clean_df.at[idx, "Name"] == "":
                first_alias = aliases[0]
                translated_name = cached_translate(first_alias)
                clean_df.at[idx, "Name"] = clean_alias(translated_name)

    logger.info("Processing RCA records...")
    # Build RCA rows using corrected function
    rca_records, parent_links = build_rca_rows(rca_df, existing_lookup)

    # Add relationships to parent rows
    for original_parent_id, links in parent_links.items():
        # Map original ID to prefixed ID
        prefixed_parent_id = id_mapping.get(original_parent_id)
        if not prefixed_parent_id:
            continue

        # Find parent row
        parent_idx = clean_df[clean_df["ID"] == prefixed_parent_id].index
        if len(parent_idx) == 0:
            continue

        parent_idx = parent_idx[0]

        # Process each relationship link
        for relationship_col, rca_id in links:
            # Skip excluded columns
            if relationship_col.lower() in EXCLUDED_RELATIONSHIP_COLUMNS:
                continue

            # Map relationship type - try both cases
            relationship_type = RELATIONSHIP_TYPE_MAP.get(
                relationship_col,
                RELATIONSHIP_TYPE_MAP.get(relationship_col.lower(), relationship_col),
            )

            # Add to Relation With
            current_relations = clean_df.at[parent_idx, "Relation With"]
            if not isinstance(current_relations, list):
                current_relations = []
            if rca_id not in current_relations:
                current_relations.append(rca_id)
            clean_df.at[parent_idx, "Relation With"] = current_relations

            # Add to Relationship Type (allow duplicates to match counts)
            current_types = clean_df.at[parent_idx, "Relationship Type"]
            if not isinstance(current_types, list):
                current_types = []
            # Always append to maintain 1-to-1 correspondence with Relation With
            current_types.append(relationship_type)
            clean_df.at[parent_idx, "Relationship Type"] = current_types

    # Convert RCA records to DataFrame and append
    if rca_records:
        rca_df_clean = pd.DataFrame(rca_records)

        # Define all list-type columns
        list_columns = [
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

        # Ensure all columns exist in RCA df
        for col in clean_df.columns:
            if col not in rca_df_clean.columns:
                if col in list_columns:
                    rca_df_clean[col] = [[] for _ in range(len(rca_df_clean))]
                elif col == "Extra Information":
                    rca_df_clean[col] = [
                        json.dumps({}) for _ in range(len(rca_df_clean))
                    ]
                elif col in ["Deceased Dissolved Status", "Status"]:
                    rca_df_clean[col] = 0 if col == "Deceased Dissolved Status" else 1
                elif col in ["Source List"]:
                    rca_df_clean[col] = "Idenfo"
                elif col in ["Category"]:
                    rca_df_clean[col] = "General United kingdom"
                elif col in ["List Type"]:
                    rca_df_clean[col] = "Individual"
                elif col in ["Scraper Tag"]:
                    rca_df_clean[col] = "uk_gen"
                elif col in ["Added On"]:
                    rca_df_clean[col] = "2026-01-27"
                else:
                    rca_df_clean[col] = ""

        # Reorder columns to match clean_df
        rca_df_clean = rca_df_clean[clean_df.columns]

        # Append RCA rows
        clean_df = pd.concat([clean_df, rca_df_clean], ignore_index=True)
        logger.info(f"Total records exported: {len(clean_df)}")
        # Save RCA lookup
        save_rca_lookup(rca_records, existing_lookup_df)
        logger.info(f"Total RCA records exported: {len(rca_df_clean)}")

    clean_df.to_excel(
        os.path.join(CLEANED_DIR, "pep_united_kingdom_living_relevant_cleaned.xlsx"),
        index=False,
    )
    logger.info(f"Missing countries: {missing_countries}")
    logger.info(
        f"Total records: {len(clean_df)} (Main: {len(raw_df)}, RCA: {len(rca_records)})"
    )

    return clean_df


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
    df.drop(index=df[df["Name"] == ""].index, inplace=True)
    return df

def replacements_for_delta(df):
    df.replace('', 'NULL', inplace=True)
    replacement_values = {'Deceased Dissolved Date': {'NULL': '1890-01-01'},
                        'Registration Date': {'NULL': '1890-01-01'},
                        'Date of Inclusion': {'NULL': '1890-01-01'},
                        'Date of Exclusion': {'NULL': '1890-01-01'},
                        'Updated On': {'NULL': '1890-01-01'}}
    df.replace(replacement_values, inplace=True)
    return df



def united_kingdom_pep_scrapper(raw_file_path: str = None) -> pd.DataFrame: 

    global RAW_FILE_PATH                    # the variable declared at top of file 
    if raw_file_path is not None: 
        RAW_FILE_PATH = raw_file_path 
    try:
        logger.info("Starting united_kingdom PEP scraper...")
        clean_df = get_clean_df()
        clean_df = common_cleaning(clean_df)
        clean_df = replacements_for_delta(clean_df)
        # Changed By Hassam Nasir — run ke aakhir me naye translations disk par save,
        # taake agli run cache se deterministic rahe (naam churn na ho).
        _save_translation_cache()
        logger.info("united_kingdom  PEP scraper completed successfully.")
        return clean_df
    except Exception as e:
        logger.error(
            get_standard_logger_message(
                "united_kingdom_pep_scrapper()", e, "Error in united_kingdom PEP scraper"
            )
        )
        raise