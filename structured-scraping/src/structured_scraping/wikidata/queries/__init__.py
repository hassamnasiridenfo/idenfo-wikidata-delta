"""Sample SPARQL queries for Wikidata.

This module contains commonly used SPARQL query templates for Wikidata.
These can be used directly or as starting points for more complex queries.

For Politically Exposed Persons (PEP) queries, see the pep.py module.
"""

# Query to get instances of cats (Q146)
CATS_QUERY = """
SELECT ?item ?itemLabel WHERE {
  ?item wdt:P31 wd:Q146 .      # Instances of 'cat'
  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "en".
  }
}
LIMIT 10
"""

# Query to get all Nobel Prize winners
NOBEL_WINNERS_QUERY = """
SELECT ?person ?personLabel ?prize ?prizeLabel ?year WHERE {
  ?person wdt:P166 ?prize .
  ?prize wdt:P31/wdt:P279* wd:Q7191 .  # Nobel Prize or subclass
  ?person wdt:P166 ?prize .
  OPTIONAL { ?person p:P166/pq:P585 ?year . }
  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "en".
  }
}
ORDER BY ?year
LIMIT 50
"""

# Query to get all countries and their capitals
COUNTRIES_CAPITALS_QUERY = """
SELECT ?country ?countryLabel ?capital ?capitalLabel WHERE {
  ?country wdt:P31 wd:Q6256 .          # Instance of country
  ?country wdt:P36 ?capital .          # Has capital
  SERVICE wikibase:label {
    bd:serviceParam wikibase:language "en".
  }
}
ORDER BY ?countryLabel
"""

# Query to get information about a specific entity (template)
ENTITY_INFO_TEMPLATE = """
SELECT ?item ?itemLabel ?itemDescription ?property ?propertyLabel ?value ?valueLabel WHERE {{
  VALUES ?item {{ wd:{entity_id} }}
  ?item ?p ?statement .
  ?statement ?ps ?value .
  ?property wikibase:claim ?p .
  ?property wikibase:statementProperty ?ps .
  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "{language}".
  }}
}}
LIMIT 50
"""

# Query to search for entities by label (template)
SEARCH_BY_LABEL_TEMPLATE = """
SELECT ?item ?itemLabel ?itemDescription WHERE {{
  ?item rdfs:label ?itemLabel .
  FILTER(LANG(?itemLabel) = "{language}")
  FILTER(CONTAINS(LCASE(?itemLabel), LCASE("{search_term}")))
  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "{language}".
  }}
}}
LIMIT {limit}
"""

# Query to get all properties of an entity (template)
ENTITY_PROPERTIES_TEMPLATE = """
SELECT ?property ?propertyLabel ?value ?valueLabel WHERE {{
  wd:{entity_id} ?p ?statement .
  ?statement ?ps ?value .
  ?property wikibase:claim ?p .
  ?property wikibase:statementProperty ?ps .
  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "{language}".
  }}
}}
"""

# Query to get count of instances for a class
COUNT_INSTANCES_TEMPLATE = """
SELECT (COUNT(?item) AS ?count) WHERE {{
  ?item wdt:P31 wd:{class_id} .
}}
"""
