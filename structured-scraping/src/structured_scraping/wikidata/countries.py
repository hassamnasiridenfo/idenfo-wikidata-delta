"""Country code mappings and utilities for Wikidata queries.

This module provides centralized country code mappings and utility functions
for working with country-specific queries.
"""

# Country name to Wikidata ID mapping
COUNTRY_NAMES: dict[str, str] = {
    # Major English-speaking countries
    "united kingdom": "Q145",
    "united states": "Q30",
    "canada": "Q16",
    "australia": "Q408",
    "new zealand": "Q664",
    "ireland": "Q27",
    
    # Major European countries
    "germany": "Q183",
    "france": "Q142",
    "italy": "Q38",
    "spain": "Q29",
    "portugal": "Q45",
    "netherlands": "Q55",
    "kingdom-of-the-netherlands": "Q29999",
    "belgium": "Q31",
    "switzerland": "Q39",
    "austria": "Q40",
    "sweden": "Q34",
    "norway": "Q20",
    "denmark": "Q35",
    "finland": "Q33",
    "iceland": "Q189",
    "poland": "Q36",
    "czech republic": "Q213",
    "slovakia": "Q214",
    "hungary": "Q28",
    "romania": "Q218",
    "bulgaria": "Q219",
    "croatia": "Q224",
    "slovenia": "Q215",
    "estonia": "Q191",
    "latvia": "Q211",
    "lithuania": "Q37",
    "greece": "Q41",
    "cyprus": "Q229",
    "malta": "Q233",
    
    # Major Asian countries
    "japan": "Q17",
    "china": "Q148",
    "south korea": "Q884",
    "india": "Q668",
    "indonesia": "Q252",
    "malaysia": "Q833",
    "singapore": "Q334",
    "thailand": "Q869",
    "philippines": "Q928",
    "vietnam": "Q881",
    "bangladesh": "Q902",
    "pakistan": "Q843",
    "sri lanka": "Q854",
    "myanmar": "Q836",
    "cambodia": "Q424",
    "laos": "Q819",
    "nepal": "Q837",
    "bhutan": "Q917",
    "maldives": "Q826",
    "brunei": "Q921",
    "mongolia": "Q711",
    "kazakhstan": "Q232",
    "uzbekistan": "Q265",
    "kyrgyzstan": "Q813",
    "tajikistan": "Q863",
    "turkmenistan": "Q874",
    "afghanistan": "Q889",
    "taiwan": "Q865",
    "hong kong": "Q8646",
    "macau": "Q14773",
    
    # Middle East & Gulf countries
    "turkey": "Q43",
    "iran": "Q794",
    "iraq": "Q796",
    "syria": "Q858",
    "lebanon": "Q822",
    "jordan": "Q810",
    "israel": "Q801",
    "palestine": "Q219060",
    "saudi arabia": "Q851",
    "united arab emirates": "Q878",
    "kuwait": "Q817",
    "bahrain": "Q398",
    "qatar": "Q846",  # Add Qatar support!
    "oman": "Q842",
    "yemen": "Q805",
    "georgia": "Q230",
    "armenia": "Q399",
    "azerbaijan": "Q227",
    
    # African countries
    "south africa": "Q258",
    "egypt": "Q79",
    "nigeria": "Q1033",
    "kenya": "Q114",
    "ghana": "Q117",
    "morocco": "Q1028",
    "tunisia": "Q948",
    "algeria": "Q262",
    "libya": "Q1016",
    "sudan": "Q1049",
    "ethiopia": "Q115",
    "uganda": "Q1036",
    "tanzania": "Q924",
    "rwanda": "Q1037",
    "botswana": "Q963",
    "namibia": "Q1030",
    "zambia": "Q953",
    "zimbabwe": "Q954",
    "mozambique": "Q1029",
    "madagascar": "Q1019",
    "mauritius": "Q1027",
    "seychelles": "Q1042",
    "ivory coast": "Q1008",
    "mali": "Q912",
    "niger": "Q1032",
    "chad": "Q657",
    "cameroon": "Q1009",
    "central african republic": "Q929",
    "democratic republic of the congo": "Q974",
    "republic of the congo": "Q971",
    "gabon": "Q1000",
    "equatorial guinea": "Q983",
    "sao tome and principe": "Q1039",
    "cape verde": "Q1011",
    "guinea-bissau": "Q1007",
    "guinea": "Q1006",
    "sierra leone": "Q1044",
    "liberia": "Q1014",
    "senegal": "Q1041",
    "gambia": "Q1005",
    "mauritania": "Q1025",
    "benin": "Q962",
    "togo": "Q945",
    "somalia": "Q1045",
    "djibouti": "Q977",
    "eritrea": "Q986",
    "comoros": "Q970",
    "lesotho": "Q1013",
    "eswatini": "Q1050",
    "malawi": "Q1020",
    "angola": "Q916",
    
    # Latin American countries
    "brazil": "Q155",
    "argentina": "Q414",
    "chile": "Q298",
    "colombia": "Q739",
    "peru": "Q419",
    "venezuela": "Q717",
    "ecuador": "Q736",
    "bolivia": "Q750",
    "paraguay": "Q733",
    "uruguay": "Q77",
    "guyana": "Q734",
    "suriname": "Q730",
    "french guiana": "Q3769",
    "mexico": "Q96",
    "guatemala": "Q774",
    "belize": "Q242",
    "honduras": "Q783",
    "el salvador": "Q792",
    "nicaragua": "Q811",
    "costa rica": "Q800",
    "panama": "Q804",
    "cuba": "Q241",
    "jamaica": "Q766",
    "haiti": "Q790",
    "dominican republic": "Q786",
    "puerto rico": "Q1183",
    "trinidad and tobago": "Q754",
    "barbados": "Q244",
    "saint lucia": "Q760",
    "grenada": "Q769",
    "saint vincent and the grenadines": "Q757",
    "antigua and barbuda": "Q781",
    "dominica": "Q784",
    "saint kitts and nevis": "Q763",
    "bahamas": "Q778",
    
    # Oceania
    "fiji": "Q712",
    "papua new guinea": "Q691",
    "solomon islands": "Q685",
    "vanuatu": "Q686",
    "samoa": "Q683",
    "tonga": "Q678",
    "kiribati": "Q710",
    "tuvalu": "Q672",
    "nauru": "Q697",
    "palau": "Q695",
    "marshall islands": "Q709",
    "micronesia": "Q702",
}

# Reverse mapping: Wikidata ID to country name
WIKIDATA_TO_NAME: dict[str, str] = {v: k for k, v in COUNTRY_NAMES.items()}

# Comprehensive country code to Wikidata ID mapping
COUNTRY_CODES: dict[str, str] = {
    # Major English-speaking countries
    "uk": "Q145",    # United Kingdom
    "us": "Q30",     # United States
    "ca": "Q16",     # Canada
    "au": "Q408",    # Australia
    "nz": "Q664",    # New Zealand
    "ie": "Q27",     # Ireland
    
    # Major European countries
    "de": "Q183",    # Germany
    "fr": "Q142",    # France
    "it": "Q38",     # Italy
    "es": "Q29",     # Spain
    "pt": "Q45",     # Portugal
    "nl": "Q55",     # Netherlands
    "knl": "Q29999", # Kingdom of the Netherlands
    "be": "Q31",     # Belgium
    "ch": "Q39",     # Switzerland
    "at": "Q40",     # Austria
    "se": "Q34",     # Sweden
    "no": "Q20",     # Norway
    "dk": "Q35",     # Denmark
    "fi": "Q33",     # Finland
    "is": "Q189",    # Iceland
    "pl": "Q36",     # Poland
    "cz": "Q213",    # Czech Republic
    "sk": "Q214",    # Slovakia
    "hu": "Q28",     # Hungary
    "ro": "Q218",    # Romania
    "bg": "Q219",    # Bulgaria
    "hr": "Q224",    # Croatia
    "si": "Q215",    # Slovenia
    "ee": "Q191",    # Estonia
    "lv": "Q211",    # Latvia
    "lt": "Q37",     # Lithuania
    "gr": "Q41",     # Greece
    "cy": "Q229",    # Cyprus
    "mt": "Q233",    # Malta
    
    # Major Asian countries
    "jp": "Q17",     # Japan
    "cn": "Q148",    # China
    "kr": "Q884",    # South Korea
    "kp": "Q423",    # North Korea
    "in": "Q668",    # India
    "pk": "Q843",    # Pakistan
    "bd": "Q902",    # Bangladesh
    "lk": "Q854",    # Sri Lanka
    "th": "Q869",    # Thailand
    "vn": "Q881",    # Vietnam
    "ph": "Q928",    # Philippines
    "id": "Q252",    # Indonesia
    "my": "Q833",    # Malaysia
    "sg": "Q334",    # Singapore
    "mm": "Q836",    # Myanmar
    "kh": "Q424",    # Cambodia
    "la": "Q819",    # Laos
    "bn": "Q921",    # Brunei
    "tl": "Q574",    # East Timor
    "mn": "Q711",    # Mongolia
    "kz": "Q232",    # Kazakhstan
    "uz": "Q265",    # Uzbekistan
    "kg": "Q813",    # Kyrgyzstan
    "tj": "Q863",    # Tajikistan
    "tm": "Q874",    # Turkmenistan
    "af": "Q889",    # Afghanistan
    
    # Middle East - Gulf Cooperation Council (GCC) states
    "sa": "Q851",    # Saudi Arabia
    "ae": "Q878",    # United Arab Emirates
    "qa": "Q846",    # Qatar
    "bh": "Q398",    # Bahrain
    "kw": "Q817",    # Kuwait
    "om": "Q842",    # Oman
    
    # Middle East - Other countries
    "ir": "Q794",    # Iran
    "iq": "Q796",    # Iraq
    "sy": "Q858",    # Syria
    "lb": "Q822",    # Lebanon
    "jo": "Q810",    # Jordan
    "il": "Q801",    # Israel
    "ps": "Q219060", # Palestine
    "ye": "Q805",    # Yemen
    
    # Transcontinental (Europe Asia)
    "tr": "Q43",     # Turkey
    "ru": "Q159",    # Russia
    
    # Caucasus
    "am": "Q399",    # Armenia
    "az": "Q227",    # Azerbaijan
    "ge": "Q230",    # Georgia
    
    # Eastern Europe
    "ua": "Q212",    # Ukraine
    "by": "Q184",    # Belarus
    "md": "Q217",    # Moldova
    
    # Balkans
    "rs": "Q403",    # Serbia
    "me": "Q236",    # Montenegro
    "ba": "Q225",    # Bosnia and Herzegovina
    "mk": "Q221",    # North Macedonia
    "al": "Q222",    # Albania
    "xk": "Q1246",   # Kosovo
    
    # Americas
    "br": "Q155",    # Brazil
    "ar": "Q414",    # Argentina
    "mx": "Q96",     # Mexico
    "co": "Q739",    # Colombia
    "pe": "Q419",    # Peru
    "ve": "Q717",    # Venezuela
    "cl": "Q298",    # Chile
    "ec": "Q736",    # Ecuador
    "uy": "Q77",     # Uruguay
    "py": "Q733",    # Paraguay
    "bo": "Q750",    # Bolivia
    "sr": "Q730",    # Suriname
    "gy": "Q734",    # Guyana
    
    # Africa
    "za": "Q258",    # South Africa
    "eg": "Q79",     # Egypt
    "ng": "Q1033",   # Nigeria
    "ke": "Q114",    # Kenya
    "et": "Q115",    # Ethiopia
    "gh": "Q117",    # Ghana
    "ma": "Q1028",   # Morocco
    "tn": "Q948",    # Tunisia
    "dz": "Q262",    # Algeria
    "ly": "Q1016",   # Libya
    "sd": "Q1049",   # Sudan
    "ss": "Q958",    # South Sudan
    "ug": "Q1036",   # Uganda
    "tz": "Q924",    # Tanzania
    "rw": "Q1037",   # Rwanda
    "bi": "Q967",    # Burundi
    "mw": "Q1020",   # Malawi
    "zm": "Q953",    # Zambia
    "zw": "Q954",    # Zimbabwe
    "bw": "Q963",    # Botswana
    "na": "Q1030",   # Namibia
    "sz": "Q1050",   # Eswatini
    "ls": "Q1013",   # Lesotho
    "mz": "Q1029",   # Mozambique
    "mg": "Q1019",   # Madagascar
    "mu": "Q1027",   # Mauritius
    "sc": "Q1042",   # Seychelles
    "km": "Q970",    # Comoros
    
    # Oceania
    "fj": "Q712",    # Fiji
    "pg": "Q691",    # Papua New Guinea
    "sb": "Q685",    # Solomon Islands
    "vu": "Q686",    # Vanuatu
    "ws": "Q683",    # Samoa
    "to": "Q678",    # Tonga
    "tv": "Q672",    # Tuvalu
    "ki": "Q710",    # Kiribati
    "nr": "Q697",    # Nauru
    "pw": "Q695",    # Palau
    "fm": "Q702",    # Micronesia
    "mh": "Q709",    # Marshall Islands
}


def get_country_id(country_input: str) -> str:
    """Get Wikidata ID for a country.
    
    Args:
        country_input (str): Country code (e.g., 'uk', 'us'),
                            country name (e.g., 'Qatar', 'Denmark'),
                            or Wikidata ID (e.g., 'Q145')
        
    Returns:
        str: Wikidata ID for the country
        
    Raises:
        ValueError: If country is not recognized
        
    """
    # If it's already a Wikidata ID, validate and return
    if country_input.startswith("Q") and country_input[1:].isdigit():
        return country_input
    
    # Look up country code (case-insensitive)
    country_lower = country_input.lower()
    if country_lower in COUNTRY_CODES:
        return COUNTRY_CODES[country_lower]
    
    # Look up country name (case-insensitive)
    country_name_lower = country_input.lower()
    if country_name_lower in COUNTRY_NAMES:
        return COUNTRY_NAMES[country_name_lower]
    
    # If not found, provide helpful error message
    available_codes = ", ".join(sorted(COUNTRY_CODES.keys()))
    available_names = ", ".join(sorted(list(COUNTRY_NAMES.keys())[:10]))  # Show first 10
    raise ValueError(
        f"Unknown country: {country_input}. "
        f"Available codes: {available_codes[:100]}... (and more) "
        f"Available names: {available_names}... (and more) "
        f"or use Wikidata ID (e.g., Q145)",
    )


def get_country_name(country_input: str) -> str:
    """Get a display name for a country.
    
    Args:
        country_input (str): Country code, country name, or Wikidata ID
        
    Returns:
        str: Display name for the country
        
    Raises:
        ValueError: If country is not recognized
        
    """
    # If it's already a Wikidata ID, look it up
    if country_input.startswith("Q"):
        if country_input in WIKIDATA_TO_NAME:
            return WIKIDATA_TO_NAME[country_input].title()
        # Fall back to checking country codes
        for code, wikidata_id in COUNTRY_CODES.items():
            if wikidata_id == country_input:
                return code.upper()
        raise ValueError(f"Unknown country ID: {country_input}")
    
    # Look up by country name (return as title case)
    country_lower = country_input.lower()
    if country_lower in COUNTRY_NAMES:
        return country_lower.title()
    
    # Look up by country code
    if country_lower in COUNTRY_CODES:
        wikidata_id = COUNTRY_CODES[country_lower]
        if wikidata_id in WIKIDATA_TO_NAME:
            return WIKIDATA_TO_NAME[wikidata_id].title()
        return country_lower.upper()
    
    raise ValueError(f"Unknown country: {country_input}")


def list_supported_countries() -> list[dict[str, str]]:
    """Get a list of all supported countries with their codes, names, and Wikidata IDs.
    
    Returns:
        list[dict[str, str]]: List of dictionaries containing country information
        
    """
    countries: list[dict[str, str]] = []
    
    # Add all country codes
    for code, wikidata_id in COUNTRY_CODES.items():
        name = WIKIDATA_TO_NAME.get(wikidata_id, code.upper())
        countries.append({
            "code": code,
            "name": name.title(),
            "wikidata_id": wikidata_id,
        })
    
    # Add any names that don't have corresponding codes
    for name, wikidata_id in COUNTRY_NAMES.items():
        # Check if this wikidata_id is already in our list
        if not any(c["wikidata_id"] == wikidata_id for c in countries):
            countries.append({
                "code": "",
                "name": name.title(),
                "wikidata_id": wikidata_id,
            })
    
    return sorted(countries, key=lambda x: x["name"])


def search_countries(query: str) -> dict[str, str]:
    """Search for countries by partial code match.
    
    Args:
        query (str): Partial country code to search for
        
    Returns:
        dict[str, str]: Dictionary of matching country codes and IDs
        
    """
    query_lower = query.lower()
    return {
        code: wikidata_id
        for code, wikidata_id in COUNTRY_CODES.items()
        if query_lower in code.lower()
    }
