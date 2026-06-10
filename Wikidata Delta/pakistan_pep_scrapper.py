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


BASE_DIR = Path(__file__).parent.parent.parent
# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CLEANED_DIR = os.path.join(BASE_DIR, "Cleaned")
os.makedirs(CLEANED_DIR, exist_ok=True)
RAW_DIR = os.path.join(BASE_DIR, "Raw")
os.makedirs(RAW_DIR, exist_ok=True)
# CLEANED_DIR = BASE_DIR
# RAW_DIR = BASE_DIR
CLEAN_FILE_PATH = os.path.join(CLEANED_DIR, "pep_pakistan_living_relevant_cleaned.xlsx")
RAW_FILE_PATH = os.path.join(RAW_DIR, "pep_pakistan_living_relevant_raw.xlsx")
RCA_FILE_PATH = os.path.join(
    CLEANED_DIR, "pep_pakistan_living_relevant_rca_lookup.xlsx"
)

logger = logging.getLogger("PakistanPEPScrapper")
if not logger.hasHandlers():
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(os.path.join(BASE_DIR, "pakistan_pep.log"))
    formatter = logging.Formatter(
        "\n%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%d-%m-%Y %I:%M:%S %p",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

translator = GoogleTranslator(source="auto", target="en")


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


def normalize_list_strings(
    list_str: str, return_type: str | None = None, splitter: str | None = None
) -> str | list[str]:
    """Normalize list strings by splitting, cleaning, and returning as list or string.

    For example '['Pakistan'],['uk']' -> 'Pakistan, UK' or ['Pakistan', 'UK'] BASED ON return_type

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
    """Format name as bracketed JSON list - matches pakistan_pep_scrapper.py"""
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
        cleaned = translator.translate(base)
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
            "Category": ["General Pakistan"] * num_rows,
            "List Category": [""] * num_rows,
            "List Type": ["Individual"] * num_rows,
            "Image Tag": [""] * num_rows,
            "Scraper Tag": ["pk_gen"] * num_rows,
            "Updated On": [""] * num_rows,
            "Added On": ["2025-12-17"] * num_rows,
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
    if raw_file_path is None:
        raw_file_path = os.path.join(RAW_DIR, "pep_pakistan_living_relevant_raw.xlsx")
    return pd.read_excel(raw_file_path, sheet_name=sheet, engine="openpyxl")


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
            os.path.join(BASE_DIR, "Updated CountryList.xlsx"), sheet_name="Sheet3"
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

    return "Other" if genders[0] == "trans woman" else genders[0].title()


def get_place_of_birth(birthPlaceLabel: str, extra_info: dict) -> str:
    if pd.isna(birthPlaceLabel) or not birthPlaceLabel:
        return ""
    if birthPlaceLabel.count("]") == 1 and birthPlaceLabel.count("[") == 1:
        place = normalize_list_strings(birthPlaceLabel)
        return place
    else:
        places = normalize_list_strings(
            birthPlaceLabel, return_type="list", splitter=","
        )
        if len(places) == 0:
            return ""
        if len(places) > 1:
            extra_info["Extra POB"] = ", ".join(places[1:])
    return places[0]


def get_formatted_date(dateStr: str) -> list[str]:
    # Check for None, empty, or "none" string
    if not dateStr or pd.isna(dateStr) or str(dateStr).strip().lower() in ["none", ""]:
        return []

    # Convert to string if not already
    dateStr = str(dateStr).strip()

    # Parse dates directly without normalizing
    # Extract dates from bracketed format
    date_pattern = r'"([^"]+)"'
    dates = re.findall(date_pattern, dateStr)

    if not dates:
        dates = [dateStr]

    result = []
    for date in dates:
        if not date or not date.strip():
            continue

        if date.lower() == "none":
            result.append(None)
            continue

        # Remove the timestamp part (T00:00:00Z)
        date_only = date.split("T")[0] if "T" in date else date
        date_only = date_only.strip()

        # Skip if empty after cleanup
        if not date_only or date_only.lower() == "none":
            continue

        try:
            parsed_date = datetime.strptime(date_only, "%Y-%m-%d")
            result.append(parsed_date.strftime("%Y-%m-%d"))
        except ValueError:
            # Skip invalid dates silently since they're already filtered
            continue

    return result


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
        return result
    else:
        nat = nationalities[0].lower()
        if nat not in country_lookup:
            missing_countries.add(nat)
            return [nat]
        else:
            return [country_lookup[nat]]


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
    return "; ".join(details)


def get_role_details(
    positionLabel: str, politicalPartyLabel: str, startTime: str, endTime: str
) -> tuple[list[str], list[str], list[str]]:
    designations = []
    start_dates = []
    end_dates = []

    if pd.notna(positionLabel) and positionLabel:
        positions = normalize_list_strings(
            positionLabel, return_type="list", splitter=","
        )
        designations.extend([p.title() for p in positions])
    if pd.notna(politicalPartyLabel) and politicalPartyLabel:
        parties = normalize_list_strings(
            politicalPartyLabel, return_type="list", splitter=","
        )
        designations.extend(
            [
                (
                    f"Member of {party}"
                    if "independent politician" not in party.lower()
                    else party.title()
                )
                for party in parties
            ]
        )

    if pd.notna(startTime) and startTime:
        start_dates = get_formatted_date(startTime)
        if len(start_dates) > 0:
            if pd.notna(endTime) and endTime:
                end_dates = get_formatted_date(endTime)

    return (start_dates, end_dates, designations)


def clean_alias(alias: str) -> str:
    alias = alias.strip()
    alias = alias.replace("-", " ").replace("&", " and ").strip()
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
    alias = re.sub(r"[^\w\s]", "", alias)
    return alias.strip().title()


def clean_name(name_data: dict) -> dict:
    name = name_data.get("name", "")
    if pd.isna(name) or not name:
        return ""
    name_str = normalize_list_strings(name)

    # check if name is wikidata ID
    matches = re.match(r"^Q\d+$", name_str)
    if matches:
        name_data["name"] = ""
        return name_data

    strs_to_rem = [
        "(Khyber Pakhtunkhwa politician)",
        "Ms",
        "Ms.",
        "Brig. (R)",
        "Maulana",
        "Lt. General (R)",
        "Dr.",
        "Dr",
        "Engr.",
        "Lt. Col.",
        "Col. (r)",
        "Advocate",
        "Engineer",
        "(Advocate)",
        "(judge, born 1924)",
        "Crown Prince of Bahawalpur",
    ]

    strs_to_rem.sort(key=len, reverse=True)

    for s in strs_to_rem:
        if s in name_str:
            name_data["aliases"].append(clean_alias(name_str))
            name_data["alias_types"].append(get_alias_type(name_str))
            name_str = name_str.replace(s, "").strip()

    paren_pattern = r"\((.*?)\)"
    name = re.sub(paren_pattern, "", name_str).strip()
    name = name.replace("-", " ").replace("&", " and ").replace("-", " ").strip()

    tmp_name = (
        name.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    )
    if not tmp_name.isascii():
        name_data["aliases"].append(clean_alias(name))
        name_data["alias_types"].append(get_alias_type(name))
        name = unidecode(name)

    name = re.sub(r"[^\w\s]", "", name)

    name_data["name"] = name.strip().title()
    return name_data


def get_father_name(fatherLabel: str) -> str:
    if pd.isna(fatherLabel) or not fatherLabel:
        return ""
    father_name = normalize_list_strings(fatherLabel)
    matches = re.match(r"^Q\d+$", father_name)
    if not father_name or matches:
        return ""

    return clean_alias(father_name).strip().title()


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
    aka_list = normalize_list_strings(aka, return_type="list", splitter=",")
    birthName_list = normalize_list_strings(birthName, return_type="list", splitter=",")
    nativeName_list = normalize_list_strings(
        nativeName, return_type="list", splitter=","
    )
    nonEngLabel_list = []
    paren_pattern = r"\((.*?)\)"
    # ── OLD nonEngLabel parsing (commented out — was only extracting index [0],
    #    discarding all Arabic/Urdu/Bengali aliases after the first English entry)
    # if nonEngLabel and not pd.isna(nonEngLabel):
    #     if nonEngLabel.startswith('["') and nonEngLabel.endswith('"]'):
    #         nonEngLabel = literal_eval(nonEngLabel)
    #         if isinstance(nonEngLabel, list):
    #             nonEngLabel = nonEngLabel[0]
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
    alias_types = []
    for alias in complete_aliases:
        alias_types.append(get_alias_type(alias))

    return list(complete_aliases), alias_types


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
        df = pd.read_excel(
            os.path.join(CLEANED_DIR, "pep_pakistan_living_relevant_rca_lookup.xlsx")
        )
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
    rca_df: pd.DataFrame, existing_lookup: dict[str, str], country_code: str = "PK"
) -> tuple[list[dict], dict[str, list[tuple[str, str]]]]:
    """
    Build RCA rows and track parent-child relationships.
    CORRECTED to match pakistan_pep_scrapper.py logic exactly.
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
    """Save RCA lookup workbook - matches pakistan_pep_scrapper.py"""
    lookup_path = os.path.join(
        CLEANED_DIR, "pep_pakistan_living_relevant_rca_lookup.xlsx"
    )

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
    loopkup = create_country_lookup_map()
    missing_countries = set()

    # Track ID mapping for relationships
    id_mapping = {}  # {original_wikidata_id: new_clean_df_id}

    # Process main records
    for i, row in raw_df.iterrows():
        try:
            name_data = {
                "name": row.get("personLabel", ""),
                "aliases": [],
                "alias_types": [],
                "extra_info": {},
            }

            # Assign ID and track mapping
            original_id = str(row.get("ID", ""))
            prefixed_id = f"PK-GEN-I-{i+1}"
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
            clean_df.loc[i, "Image Tag"] = row.get("image", "")
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
                )
            )
            continue

    # Handle empty names
    empty_name_rows = clean_df[clean_df["Name"] == ""]
    for idx, empty_row in empty_name_rows.iterrows():
        if empty_row["Alias"]:
            aliases = empty_row["Alias"]
            alias_types = empty_row["Alias Type"]
            for j, alias in enumerate(aliases):
                if alias.isascii():
                    clean_df.at[idx, "Name"] = alias
                    break

            if clean_df.at[idx, "Name"] == "":
                first_alias = aliases[0]
                translated_name = translator.translate(first_alias)
                clean_df.at[idx, "Name"] = translated_name

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
                    rca_df_clean[col] = "General Pakistan"
                elif col in ["List Type"]:
                    rca_df_clean[col] = "Individual"
                elif col in ["Scraper Tag"]:
                    rca_df_clean[col] = "pk_gen"
                else:
                    rca_df_clean[col] = ""

        # Reorder columns to match clean_df
        rca_df_clean = rca_df_clean[clean_df.columns]

        # Append RCA rows
        clean_df = pd.concat([clean_df, rca_df_clean], ignore_index=True)
        logger.info(f"Total records exported: {len(clean_df)}")
        clean_df.to_excel(
            os.path.join(CLEANED_DIR, "pep_pakistan_living_relevant_cleaned.xlsx"),
            index=False,
        )

        # Save RCA lookup
        save_rca_lookup(rca_records, existing_lookup_df)
        logger.info(f"Total RCA records exported: {len(rca_df_clean)}")
        return clean_df

    logger.info(f"Missing countries: {missing_countries}")
    logger.info(
        f"Total records: {len(clean_df)} (Main: {len(raw_df)}, RCA: {len(rca_records)})"
    )

    return clean_df


def pakistan_pep_scrapper() -> pd.DataFrame:
    try:
        logger.info("Starting Pakistan PEP scraper...")
        clean_df = get_clean_df()
        logger.info("Pakistan PEP scraper completed successfully.")
        return clean_df
    except Exception as e:
        logger.error(
            get_standard_logger_message(
                "pakistan_pep_scrapper()", e, "Error in Pakistan PEP scraper"
            )
        )
        raise
