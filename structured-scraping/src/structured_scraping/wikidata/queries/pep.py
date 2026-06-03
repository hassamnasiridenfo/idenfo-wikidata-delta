"""SPARQL queries for Politically Exposed Persons (PEPs).

This module contains SPARQL queries for finding entities that are both humans
and politicians, which can be useful for PEP (Politically Exposed Person)
screening and compliance purposes.
"""

# Basic query for entities that are both humans (Q5) and politicians (Q82955)
BASIC_POLITICIANS_QUERY = """
SELECT ?person ?personLabel ?personDescription WHERE {{
  ?person wdt:P31 wd:Q5 .        # Instance of human
  ?person wdt:P106 wd:Q82955 .   # Occupation: politician
  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en,en-gb,en-ca,fr,de,es,it,pt,ga,ro,pl,uk,arz,mul".
  }}
}}
"""


# Extended query with additional information for PEP screening
EXTENDED_POLITICIANS_QUERY = """
SELECT ?person ?personLabel ?personDescription
       ?birthDate ?deathDate ?nationality ?nationalityLabel
       ?gender ?genderLabel ?residence ?residenceLabel ?birthPlace ?birthPlaceLabel
       ?position ?positionLabel ?startTime ?endTime ?politicalParty
       ?candidacyElection WHERE {{
  ?person wdt:P31 wd:Q5 .        # Instance of human
  ?person wdt:P106 wd:Q82955 .   # Occupation: politician
  
  OPTIONAL {{ ?person wdt:P569 ?birthDate . }}      # Date of birth
  OPTIONAL {{ ?person wdt:P570 ?deathDate . }}      # Date of death
  OPTIONAL {{ ?person wdt:P27 ?nationality . }}     # Country of citizenship
  OPTIONAL {{ ?person wdt:P21 ?gender . }}          # Gender
  OPTIONAL {{ ?person wdt:P551 ?residence . }}      # Residence
  OPTIONAL {{ ?person wdt:P19 ?birthPlace . }}      # Place of birth
  
  # Political positions held
  OPTIONAL {{
    ?person p:P39 ?positionStatement .
    ?positionStatement ps:P39 ?position .
    OPTIONAL {{ ?positionStatement pq:P580 ?startTime . }}  # Start time
    OPTIONAL {{ ?positionStatement pq:P582 ?endTime . }}    # End time
  }}
  
  # Member of political party (P102)
  OPTIONAL {{ ?person wdt:P102 ?politicalParty . }}
  
  # Candidacy in election (P3602)
  OPTIONAL {{ ?person wdt:P3602 ?candidacyElection . }}
  
  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en,en-gb,en-ca,fr,de,es,it,pt,ga,ro,pl,uk,arz,mul".
  }}
}}
"""

# Extended query filtered by specific nationality for country-specific PEP screening
EXTENDED_POLITICIANS_BY_NATIONALITY_QUERY = """
SELECT ?person ?personLabel ?personDescription
       ?birthDate ?deathDate ?nationality ?nationalityLabel
       ?gender ?genderLabel ?residence ?residenceLabel ?birthPlace ?birthPlaceLabel
       ?position ?positionLabel ?startTime ?endTime ?politicalParty
       ?candidacyElection WHERE {{
  ?person wdt:P31 wd:Q5 .        # Instance of human
  ?person wdt:P106 wd:Q82955 .   # Occupation: politician
  ?person wdt:P27 wd:{nationality_qid} .  # Country of citizenship (specific nationality)
  
  OPTIONAL {{ ?person wdt:P569 ?birthDate . }}      # Date of birth
  OPTIONAL {{ ?person wdt:P570 ?deathDate . }}      # Date of death
  OPTIONAL {{ ?person wdt:P27 ?nationality . }}     # Country of citizenship
  OPTIONAL {{ ?person wdt:P21 ?gender . }}          # Gender
  OPTIONAL {{ ?person wdt:P551 ?residence . }}      # Residence
  OPTIONAL {{ ?person wdt:P19 ?birthPlace . }}      # Place of birth
  
  # Political positions held
  OPTIONAL {{
    ?person p:P39 ?positionStatement .
    ?positionStatement ps:P39 ?position .
    OPTIONAL {{ ?positionStatement pq:P580 ?startTime . }}  # Start time
    OPTIONAL {{ ?positionStatement pq:P582 ?endTime . }}    # End time
  }}
  
  # Member of political party (P102)
  OPTIONAL {{ ?person wdt:P102 ?politicalParty . }}
  
  # Candidacy in election (P3602)
  OPTIONAL {{ ?person wdt:P3602 ?candidacyElection . }}
  
  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en,en-gb,en-ca,fr,de,es,it,pt,ga,ro,pl,uk,arz,mul".
  }}
}}
"""

# Living politicians query filtered by nationality - optimized for batch processing
MAIN_QUERY = """
SELECT DISTINCT
  (STRAFTER(STR(?person), "http://www.wikidata.org/entity/") AS ?ID)
  (COALESCE(?personLabelEn, STRAFTER(STR(?person), "http://www.wikidata.org/entity/")) AS ?personLabel)
  ?image
WHERE {
  ?person wdt:P31 wd:Q5 .        # Instance of human
  ?person wdt:P569 ?birthDate . date_filter
  ?person wdt:P106 ?occupation .
  {
    VALUES ?occupation {
      wd:Q82955   # Politician
      wd:Q43845   # Businessperson
      wd:Q484876  # Chief executive officer
      wd:Q911554  # Business magnate
      wd:Q189290  # Military officer
      wd:Q16533   # Judge
    }
  }
  UNION
  {
    ?occupation wdt:P425 wd:Q1551985 .  # Field of bureaucracy
  }
  ?person wdt:P27 wd:nationality_qid .  # Country of citizenship (specific nationality)

  # Filter out deceased politicians (no death date) - this must come early
  FILTER NOT EXISTS { ?person wdt:P570 ?deathDate . }
  
  OPTIONAL { ?person wdt:P18 ?image. }  # main image (if available)

  OPTIONAL {
    ?person rdfs:label ?personLabelEn .
    FILTER (LANG(?personLabelEn) = "en")
  }
}
"""

DOB_POLITICIANS_QUERY = """
SELECT DISTINCT
  (STRAFTER(STR(?person), "http://www.wikidata.org/entity/") AS ?ID)
  ?personLabel
  ?birthDate
WHERE {
  BIND(wd:person_qid AS ?person)
  OPTIONAL { ?person wdt:P569 ?birthDate . }
  OPTIONAL { ?person rdfs:label ?personLabel . FILTER (LANG(?personLabel) = "en") }
}
"""
NATIONALITY_POLITICIANS_QUERY = """
SELECT DISTINCT
  (STRAFTER(STR(?person), "http://www.wikidata.org/entity/") AS ?ID)
  ?nationalityLabel
WHERE {
  BIND(wd:person_qid AS ?person)
  OPTIONAL {
    ?person wdt:P27 ?nationality .
    OPTIONAL {
      ?nationality rdfs:label ?nationalityLabel .
      FILTER (LANG(?nationalityLabel) = "en")
    }
  }
}
"""

ALIAS_POLITICIANS_QUERY = """
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX schema: <http://schema.org/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX bd: <http://www.bigdata.com/rdf#>

SELECT DISTINCT (STRAFTER(STR(?person), "http://www.wikidata.org/entity/") AS ?ID)
       ?AKA
WHERE {
  BIND(wd:person_qid AS ?person)

  ?person skos:altLabel ?AKA .
}
"""
RESIDENCE_POLITICIANS_QUERY = """
SELECT DISTINCT ?ID ?residenceLabel WHERE {
  BIND(wd:person_qid AS ?person)

  ?person wdt:P551 ?residence .

  OPTIONAL { ?residence rdfs:label ?residenceLabel . FILTER (LANG(?residenceLabel) = "en") }

  BIND(STRAFTER(STR(?person), "http://www.wikidata.org/entity/") AS ?ID)
}
"""
CRIMINAL_POLITICIANS_QUERY = """
SELECT DISTINCT
  (STRAFTER(STR(?person), "http://www.wikidata.org/entity/") AS ?ID)
  ?convictedOfLabel
  ?placeOfDetentionLabel
WHERE {
  BIND(wd:person_qid AS ?person)

  OPTIONAL {
    ?person wdt:P1399 ?convictedOf .  # Convicted of
    OPTIONAL {
      ?convictedOf rdfs:label ?convictedOfLabel .
      FILTER (LANG(?convictedOfLabel) = "en")
    }
  }
  OPTIONAL {
    ?person wdt:P2632 ?placeOfDetention .  # Place of detention
    OPTIONAL {
      ?placeOfDetention rdfs:label ?placeOfDetentionLabel .
      FILTER (LANG(?placeOfDetentionLabel) = "en")
    }
  }

  FILTER(
    BOUND(?convictedOf) || BOUND(?placeOfDetention)
    )
}
  """

ROLE_POLITICIANS_QUERY = """
SELECT DISTINCT
  (STRAFTER(STR(?person), "http://www.wikidata.org/entity/") AS ?ID)
  ?positionLabel ?startTime ?endTime ?politicalPartyLabel ?personDescription ?occupationLabel
WHERE {
  BIND(wd:person_qid AS ?person)
  ?person wdt:P106 ?occupation .

  OPTIONAL {
    ?person p:P39 ?positionStatement .
    ?positionStatement ps:P39 ?position .
    OPTIONAL { ?positionStatement pq:P580 ?startTime . }
    OPTIONAL { ?positionStatement pq:P582 ?endTime . }
    OPTIONAL {
      ?position rdfs:label ?positionLabel .
      FILTER (LANG(?positionLabel) = "en")
    }
  }
  OPTIONAL {
    ?person wdt:P102 ?politicalParty .
    OPTIONAL {
      ?politicalParty rdfs:label ?politicalPartyLabel .
      FILTER (LANG(?politicalPartyLabel) = "en")
    }
  }

  OPTIONAL { ?occupation rdfs:label ?occupationLabel . FILTER (LANG(?occupationLabel) = "en") }
  OPTIONAL { ?person schema:description ?personDescription . FILTER (LANG(?personDescription) = "en") }
}

  """

RCA_POLITICIANS_QUERY = """
SELECT DISTINCT
  ((STRAFTER(STR(?person), "http://www.wikidata.org/entity/")) AS ?ID)
  ?fatherLabel ?motherLabel ?siblingLabel
  ?spouseLabel ?childLabel ?relativeLabel
WHERE {
  BIND(wd:person_qid AS ?person)

  {
    ?person wdt:P22 ?father.
    OPTIONAL { ?father rdfs:label ?fatherLabel . FILTER (LANG(?fatherLabel) = "en") }
  }
  UNION
  {
    ?person wdt:P25 ?mother.
    OPTIONAL { ?mother rdfs:label ?motherLabel . FILTER (LANG(?motherLabel) = "en") }
  }
  UNION
  {
    ?person wdt:P3373 ?sibling.
    OPTIONAL { ?sibling rdfs:label ?siblingLabel . FILTER (LANG(?siblingLabel) = "en") }
  }
  UNION
  {
    ?person wdt:P26 ?spouse.
    OPTIONAL { ?spouse rdfs:label ?spouseLabel . FILTER (LANG(?spouseLabel) = "en") }
  }
  UNION
  {
    ?person wdt:P40 ?child.
    OPTIONAL { ?child rdfs:label ?childLabel . FILTER (LANG(?childLabel) = "en") }
  }
  UNION
  {
    ?person wdt:P1038 ?relative.
    OPTIONAL { ?relative rdfs:label ?relativeLabel . FILTER (LANG(?relativeLabel) = "en") }
  }

}
"""

# Living politicians query filtered by nationality - optimized for batch processing
EXTENDED_LIVING_POLITICIANS_BY_NATIONALITY_QUERY = """
SELECT ?person ?personLabel ?personDescription
       ?birthDate ?nationality ?nationalityLabel
       ?gender ?genderLabel ?residence ?residenceLabel ?birthPlace ?birthPlaceLabel
       ?position ?positionLabel ?startTime ?endTime ?politicalParty ?politicalPartyLabel
       ?candidacyElection ?candidacyElectionLabel WHERE {{
  ?person wdt:P31 wd:Q5 .        # Instance of human
  ?person wdt:P106 wd:Q82955 .   # Occupation: politician
  ?person wdt:P27 wd:{nationality_qid} .  # Country of citizenship (specific nationality)
  
  # Filter out deceased politicians (no death date) - this must come early
  FILTER NOT EXISTS {{ ?person wdt:P570 ?deathDate . }}
  
  OPTIONAL {{ ?person wdt:P569 ?birthDate . }}      # Date of birth
  OPTIONAL {{ ?person wdt:P27 ?nationality . }}     # Country of citizenship
  OPTIONAL {{ ?person wdt:P21 ?gender . }}          # Gender
  OPTIONAL {{ ?person wdt:P551 ?residence . }}      # Residence
  OPTIONAL {{ ?person wdt:P19 ?birthPlace . }}      # Place of birth
  
  # Political positions held
  OPTIONAL {{
    ?person p:P39 ?positionStatement .
    ?positionStatement ps:P39 ?position .
    OPTIONAL {{ ?positionStatement pq:P580 ?startTime . }}  # Start time
    OPTIONAL {{ ?positionStatement pq:P582 ?endTime . }}    # End time
  }}
  
  # Member of political party (P102)
  OPTIONAL {{ ?person wdt:P102 ?politicalParty . }}
  
  # Candidacy in election (P3602)
  OPTIONAL {{ ?person wdt:P3602 ?candidacyElection . }}
  
  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en,en-gb,en-ca,fr,de,es,it,pt,ga,ro,pl,uk,arz,mul".
  }}
}}
"""

SUPER_EXTENDED_LIVING_POLITICIANS_BY_NATIONALITY_QUERY = """
SELECT ?person ?personLabel ?personDescription
       ?birthDate ?nationality ?nationalityLabel
       ?gender ?genderLabel ?residence ?residenceLabel ?birthPlace ?birthPlaceLabel
       ?position ?positionLabel ?startTime ?endTime ?politicalParty ?politicalPartyLabel
       ?candidacyElection ?candidacyElectionLabel
       ?nameInNativeLanguage ?birthName ?givenName ?givenNameLabel ?familyName ?familyNameLabel ?pseudonym
       ?father ?fatherLabel ?mother ?motherLabel ?sibling ?siblingLabel
       ?spouse ?spouseLabel ?child ?childLabel ?relative ?relativeLabel ?family ?familyLabel
       ?convictedOf ?convictedOfLabel ?placeOfDetection ?placeOfDetectionLabel
       ?occupation ?occupationLabel ?positionHeld ?positionHeldLabel ?employer ?employerLabel
       ?fieldOfWork ?fieldOfWorkLabel ?workLocation ?workLocationLabel ?ownerOf ?ownerOfLabel
       ?educatedAt ?educatedAtLabel ?academicDegree ?academicDegreeLabel ?affiliationString WHERE {
  BIND(wd:person_qid AS ?person)
  
  # Filter out deceased politicians (no death date)
  FILTER NOT EXISTS { ?person wdt:P570 ?deathDate . }
  
  # Optional name-related properties
  OPTIONAL { ?person wdt:P1559 ?nameInNativeLanguage . }  # Name in native language
  OPTIONAL { ?person wdt:P1477 ?birthName . }             # Birth name (present if different)
  OPTIONAL { ?person wdt:P735 ?givenName . }              # Given name
  OPTIONAL { ?person wdt:P734 ?familyName . }             # Family name
  OPTIONAL { ?person wdt:P742 ?pseudonym . }              # Pseudonym

  # Optional personal properties
  OPTIONAL { ?person wdt:P21 ?gender . }                  # Gender
  OPTIONAL { ?person wdt:P569 ?birthDate . }              # Date of birth
  OPTIONAL { ?person wdt:P19 ?birthPlace . }             # Place of birth
  OPTIONAL { ?person wdt:P27 ?nationality . }             # Country of citizenship
  OPTIONAL { ?person wdt:P551 ?residence . }              # Residence
  
  # Optional family-related properties
  OPTIONAL { ?person wdt:P22 ?father . }                  # Father
  OPTIONAL { ?person wdt:P25 ?mother . }                  # Mother
  OPTIONAL { ?person wdt:P3375 ?sibling . }               # Sibling
  OPTIONAL { ?person wdt:P26 ?spouse . }                  # Spouse
  OPTIONAL { ?person wdt:P40 ?child . }                   # Child
  OPTIONAL { ?person wdt:P1038 ?relative . }              # Relative
  OPTIONAL { ?person wdt:P53 ?family . }                  # Family
  
  # Optional crime-related properties
  OPTIONAL { ?person wdt:P1399 ?convictedOf . }           # Conviected of
  OPTIONAL { ?person wdt:P2632 ?placeOfDetection . }      # Place of detention
  
  # Optional employment- and education-related properties
  OPTIONAL { ?person wdt:P106 ?occupation . }             # Occupation
  OPTIONAL { ?person wdt:P39 ?positionHeld . }            # Position held
  OPTIONAL { ?person wdt:P108 ?employer . }               # Employer
  OPTIONAL { ?person wdt:P101 ?fieldOfWork . }            # Field of work
  OPTIONAL { ?person wdt:P937 ?workLocation . }           # Work location
  OPTIONAL { ?person wdt:P1830 ?ownerOf . }               # Owner of
  OPTIONAL { ?person wdt:P69 ?educatedAt . }              # Educated at
  OPTIONAL { ?person wdt:P512 ?academicDegree . }         # Academic degree
  OPTIONAL { ?person wdt:P6426 ?affiliationString . }     # Affiliation string
  
  # Optional politics-related properties
  OPTIONAL { ?person wdt:P102 ?politicalParty . }         # Member of political party
  OPTIONAL { ?person wdt:P3602 ?candidacyElection . }     # Candidacy in election
  OPTIONAL {
    ?person p:P39 ?positionStatement .
    ?positionStatement ps:P39 ?position .
    OPTIONAL { ?positionStatement pq:P580 ?startTime . }  # Start time
    OPTIONAL { ?positionStatement pq:P582 ?endTime . }    # End time
  }
  
  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en,en-gb,en-ca,fr,de,es,it,pt,ga,ro,pl,uk,arz,mul".
  }
}

LIMIT 100
"""
