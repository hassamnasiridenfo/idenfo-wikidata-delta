# Structured Scraping

A Python package for scraping structured data from RDF sources such as Wikidata using SPARQL queries. This package provides both generic SPARQL utilities and specialized Wikidata query functions, with comprehensive support for large-scale data extraction and Politically Exposed Persons (PEP) screening.

## Table of Contents

- [Structured Scraping](#structured-scraping)
  - [Table of Contents](#table-of-contents)
  - [Installation](#installation)
    - [Using conda (recommended)](#using-conda-recommended)
  - [Command Line Interface](#command-line-interface)
    - [Global Options](#global-options)
    - [Main Commands](#main-commands)
      - [1. `countries` - List and Search Countries](#1-countries---list-and-search-countries)
      - [2. `scrape` - Extract Politician Data](#2-scrape---extract-politician-data)
    - [Command Examples](#command-examples)
      - [Basic Scraping](#basic-scraping)
      - [Filtering Options](#filtering-options)
      - [Count-Only Mode](#count-only-mode)
      - [Batched Execution for Large Datasets](#batched-execution-for-large-datasets)
      - [Advanced Combinations](#advanced-combinations)
    - [Automated File Naming](#automated-file-naming)
    - [Error Handling](#error-handling)
    - [Integration with Python API](#integration-with-python-api)
    - [Quick Reference](#quick-reference)
  - [Python API](#python-api)
    - [Core Modules](#core-modules)
      - [1. Generic SPARQL Utilities (`sparql_utils`)](#1-generic-sparql-utilities-sparql_utils)
      - [2. Wikidata Module (`wikidata`)](#2-wikidata-module-wikidata)
        - [PEP Queries (`wikidata/queries/pep`)](#pep-queries-wikidataqueriespep)
  - [Development](#development)
    - [Setting up development environment](#setting-up-development-environment)
    - [Running tests](#running-tests)
  - [Architecture](#architecture)
  - [Use Cases](#use-cases)
    - [1. Compliance Screening](#1-compliance-screening)
    - [2. Research \& Analytics](#2-research--analytics)
    - [3. Data Integration](#3-data-integration)
  - [Contributing](#contributing)
  - [Important Notice](#important-notice)

## Installation

### Using conda (recommended)

1. Clone the repository:

   ```bash
   git clone https://github.com/Idenfo/structured-scraping
   cd structured-scraping
   ```

2. Create and activate the conda environment:

   ```bash
   conda env create -f environment.yml
   conda activate idenfo-struct-scrape
   ```

3. The package is automatically installed in development mode via the conda environment.

## Command Line Interface

The `idenfo-struct-scrape` CLI provides comprehensive functionality for extracting Politically Exposed Person (PEP) data from Wikidata. It offers two main commands with extensive configuration options.

### Global Options

```bash
# Show version information
idenfo-struct-scrape --version

# Enable debug logging for all operations
idenfo-struct-scrape --debug [COMMAND]

# Show help for any command
idenfo-struct-scrape --help
idenfo-struct-scrape [COMMAND] --help
```

### Main Commands

#### 1. `countries` - List and Search Countries

Lists all supported countries for politician scraping with flexible output formats.

**Basic Usage:**

```bash
idenfo-struct-scrape countries [OPTIONS]
```

**Options:**

- `--format [table|csv|json]` - Output format (default: table)
- `--search TEXT` - Search for countries containing specific text
- `--help` - Show command help

**Examples:**

```bash
# List all countries in table format (shows first 20 for readability)
idenfo-struct-scrape countries

# Search for specific countries or regions
idenfo-struct-scrape countries --search "united"
idenfo-struct-scrape countries --search "Q145"  # Search by Wikidata ID

# Export complete country list to CSV
idenfo-struct-scrape countries --format csv > countries.csv

# Export to JSON for programmatic use
idenfo-struct-scrape countries --format json > countries.json

# Combine search with different formats
idenfo-struct-scrape countries --search "europe" --format csv
```

**Output Formats:**

- **Table**: Human-readable format with columns (Code, Name, Wikidata ID)
- **CSV**: Comma-separated values with headers
- **JSON**: Structured JSON array for programmatic processing

#### 2. `scrape` - Extract Politician Data

Scrapes politician data from Wikidata for a specific country with comprehensive filtering and batching options.

**Basic Usage:**

```bash
idenfo-struct-scrape scrape [OPTIONS] COUNTRY
```

**Country Input Formats:**

- **Country code**: `uk`, `us`, `de`, `qa`
- **Country name**: `"United Kingdom"`, `"United States"`, `"Germany"`
- **Wikidata ID**: `Q145`, `Q30`, `Q183`, `Q846`

**Core Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `-o, --output PATH` | Path | Auto-generated | Output CSV file path |
| `--living` | Flag | False | Only scrape living politicians (exclude deceased) |
| `--relevant` | Flag | False | Apply relevance filtering (exclude pre-1925 births) |
| `--count-only` | Flag | False | Only count politicians without scraping data |

**Batching Options:**

| Option | Type | Default | Range | Description |
|--------|------|---------|-------|-------------|
| `--batching` | Flag | False | - | Enable batched query execution |
| `--batch-size` | Integer | 3000 | 1-10000 | Results per batch |
| `--pause` | Float | 2.0 | ≥0.0 | Pause between batches (seconds) |
| `--timeout` | Integer | 60 | ≥1 | Query timeout (seconds) |
| `--max-retries` | Integer | 5 | ≥0 | Max retry attempts for rate limiting |

### Command Examples

#### Basic Scraping

```bash
# Scrape all politicians from Qatar (simple query)
idenfo-struct-scrape scrape qa

# Scrape using country name with quotes if it contains spaces
idenfo-struct-scrape scrape "United States"

# Scrape using Wikidata ID
idenfo-struct-scrape scrape Q846  # Qatar

# Save to specific output file
idenfo-struct-scrape scrape uk --output uk_politicians.csv
```

#### Filtering Options

```bash
# Only living politicians (exclude deceased)
idenfo-struct-scrape scrape us --living

# Apply relevance filtering (exclude people born before 1925, etc.)
idenfo-struct-scrape scrape de --relevant

# Combine both filters
idenfo-struct-scrape scrape fr --living --relevant
```

#### Count-Only Mode

```bash
# Count politicians without scraping (fast overview)
idenfo-struct-scrape scrape uk --count-only
idenfo-struct-scrape scrape "United States" --count-only --living
```

#### Batched Execution for Large Datasets

Batched execution allows you to process large datasets in manageable chunks, providing better control over memory usage and enabling recovery from interruptions. However, it's important to understand the performance implications when deciding whether to use batching.

**Key Considerations:**

- **Backend Processing**: The scrape batch size does not affect the speed of backend processing. Backend processing is entirely dependent on the size of the query and the amount of data returned.
- **Query Sorting**: To scrape an entire query's results in batches, an `ORDER BY` clause is required in the SPARQL query. This ensures that the results are returned in a consistent order, allowing for proper pagination and batch processing.
- **Performance Trade-off**: Each batch needs to process the entire query at the backend, meaning that while batching helps with frontend concerns (memory usage, user control), it doesn't improve overall query performance.

**Pros of Batching:**

- **Memory Management**: Prevents memory overflow when dealing with very large datasets
- **Progress Tracking**: Allows you to see incremental progress and stop/resume operations
- **Error Recovery**: If a batch fails, you don't lose all progress
- **Rate Limiting**: Built-in pauses help respect server limits and avoid being blocked
- **User Control**: You can process data incrementally based on your needs

**Cons of Batching:**

- **No Performance Gain**: Backend still processes the full query for each batch due to required `ORDER BY` sorting
- **Increased Complexity**: More parameters to configure and potential points of failure
- **Higher Total Load**: Multiple requests with sorting can put more total load on the server
- **Longer Total Time**: The overhead of multiple requests and pauses increases total execution time

**When to Use Batching:**

- Very large queries where frontend memory usage is a concern
- When you need to process data incrementally or want progress visibility
- When dealing with unreliable network connections

**When to Avoid Batching:**

- Complex queries, where the backend processing time is already high
- Small to medium datasets where a single query is sufficient

```bash
# Enable batching with default settings
idenfo-struct-scrape scrape us --batching

# Custom batch configuration for very large datasets
idenfo-struct-scrape scrape us --batching \
  --batch-size 1000 \
  --pause 5.0 \
  --max-retries 10 \
  --timeout 120

# Conservative settings for respectful scraping
idenfo-struct-scrape scrape de --batching \
  --batch-size 500 \
  --pause 10.0 \
  --output german_politicians_conservative.csv
```

#### Advanced Combinations

```bash
# Complete PEP scraping workflow
idenfo-struct-scrape scrape qa --living --relevant --batching \
  --batch-size 2000 --pause 3.0 --output qatar_living_peps.csv

# Debug mode for detailed troubleshooting
idenfo-struct-scrape --debug scrape uk --count-only

# Debug mode with batching for large datasets
idenfo-struct-scrape --debug scrape us --batching
```

### Automated File Naming

When no `--output` file is specified, the CLI automatically generates timestamped filenames:

**Format:** `{country_name}_{relevant/all}_{living/all}_politicians_{timestamp}.csv`

**Examples:**

- `qatar_all_all_politicians_20250805_143022.csv`
- `united_states_relevant_living_politicians_20250805_143022.csv`
- `germany_all_living_politicians_20250805_143022.csv`

### Error Handling

The CLI provides comprehensive error handling and user feedback:

```bash
# Invalid country codes show suggestions
$ idenfo-struct-scrape scrape xyz
❌ Country 'xyz' not found. Did you mean: ...

# Rate limiting is handled automatically with retry logic
$ idenfo-struct-scrape scrape us --batching
⏳ Processing batches...
⚠️  Rate limited (429). Waiting 30 seconds before retry...
✅ Scraped 15,247 records

# Debug output shows detailed progress
$ idenfo-struct-scrape --debug scrape uk --batching
🔍 Resolved country: UK -> United Kingdom (Q145)
🔄 Scraping politician data (batched execution)...
INFO - Starting batched query with batch_size=3000, pause=2.0s
INFO - Executing batch 1 (offset 0-2999)
INFO - Retrieved 3000 results in batch 1
✅ Scraped 8,421 records
📁 Saved to: united_kingdom_all_all_politicians_20250805_143022.csv
```

### Integration with Python API

The CLI commands correspond to Python functions for programmatic use:

```python
# CLI: idenfo-struct-scrape countries
from structured_scraping import list_supported_countries
countries = list_supported_countries()

# CLI: idenfo-struct-scrape scrape uk --count-only
from structured_scraping import count_country_politicians
count = count_country_politicians("uk")

# CLI: idenfo-struct-scrape scrape uk --batching --living
from structured_scraping import scrape_living_politicians
from structured_scraping.wikidata.scrapers import PEPScraperConfig

config = PEPScraperConfig(batch_size=3000, pause_s=2.0)
count, filename = scrape_living_politicians("uk", config=config)
```

### Quick Reference

**Most Common Commands:**

```bash
# List countries
idenfo-struct-scrape countries

# Quick count
idenfo-struct-scrape scrape [COUNTRY] --count-only

# Basic scrape
idenfo-struct-scrape scrape [COUNTRY]

# Large dataset scrape
idenfo-struct-scrape scrape [COUNTRY] --batching

# Living politicians only
idenfo-struct-scrape scrape [COUNTRY] --living --batching
```

**Country Input Examples:**

- Code: `uk`, `us`, `de`, `qa`, `fr`
- Name: `"United Kingdom"`, `"United States"`, `"Qatar"`  
- ID: `Q145`, `Q30`, `Q183`, `Q846`, `Q142`

**Default Values:**

- Batch size: 3000
- Pause: 2.0 seconds
- Timeout: 60 seconds  
- Max retries: 5
- Output: Auto-generated filename

## Python API

### Core Modules

#### 1. Generic SPARQL Utilities (`sparql_utils`)

Generic functions for querying any SPARQL endpoint. This is organized as a module with separate files for different functionality:

- `core.py` - Core SPARQL query functions
- `batching.py` - Batching functionality for large queries  
- `retry.py` - Retry logic and rate limiting
- `io.py` - File I/O operations
- `queries.py` - Query templates

```python
from structured_scraping.sparql_utils import (
    query_sparql_endpoint_with_retry, 
    extract_bindings,
    batched_sparql_query,
    batched_sparql_query_to_csv
)

# Query any SPARQL endpoint with automatic retry logic
results = query_sparql_endpoint_with_retry(
    endpoint_url="https://example.org/sparql",
    query="SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10",
    return_format="json",
    timeout=30
)

# Extract simplified results
bindings = extract_bindings(results)

# Large-scale batched querying
all_results = batched_sparql_query(
    endpoint_url="https://example.org/sparql",
    base_query="SELECT ?s ?p ?o WHERE { ?s ?p ?o }",
    batch_size=5000,
    pause_s=2.0
)

# Memory-efficient CSV export
total_count = batched_sparql_query_to_csv(
    endpoint_url="https://example.org/sparql", 
    base_query="SELECT ?s ?p ?o WHERE { ?s ?p ?o }",
    file_path="results.csv",
    batch_size=5000
)
```

**Available functions:**

- `query_sparql_endpoint_with_retry()` - Execute queries with automatic retry logic (recommended)
- `query_sparql_endpoint()` - Execute queries against any SPARQL endpoint (basic version)
- `extract_bindings()` - Extract simplified results from SPARQL JSON
- `count_results()` - Count result bindings  
- `batched_sparql_query()` - Execute large queries in batches (returns all results)
- `batched_sparql_query_to_csv()` - Execute large queries and save directly to CSV
- `SPARQLError` - Custom exception for query failures

#### 2. Wikidata Module (`wikidata`)

Specialized functions for Wikidata queries:

```python
from structured_scraping.wikidata import (
    query_wdqs,                  # Full JSON results
    query_wdqs_simple,           # Simplified results
    get_entity_info,             # Entity information
    search_entities_by_label,    # Search by label
    get_instances_of             # Get class instances
)

# Get entity information
cat_info = get_entity_info("Q146")  # Information about cats

# Search entities
python_entities = search_entities_by_label("python", limit=5)

# Get class instances
languages = get_instances_of("Q9143", limit=10)  # Programming languages
```

##### PEP Queries (`wikidata/queries/pep`)

Specialized queries for Politically Exposed Persons screening using Wikidata:

```python
from structured_scraping.wikidata.queries.pep import (
    BASIC_POLITICIANS_QUERY,                        # Basic politician search
    EXTENDED_POLITICIANS_QUERY,                     # Detailed politician info
    EXTENDED_POLITICIANS_BY_NATIONALITY_QUERY,      # Politicians by nationality
    build_living_politicians_by_nationality_query   # Function to build living politicians query
)
```

**Available PEP Query Types:**

1. **`BASIC_POLITICIANS_QUERY`** - Simple politician identification
   - Returns: Person ID, label, and description
   - Filters: Human entities with politician occupation
   - Use case: Basic PEP screening, quick counts, initial identification

2. **`EXTENDED_POLITICIANS_QUERY`** - Comprehensive politician data
   - Returns: Full biographical and political information including birth/death dates, nationality, gender, residence, positions held, political parties, and election candidacies
   - Filters: Human entities with politician occupation
   - Use case: Detailed compliance screening, risk assessment, complete PEP profiles

3. **`EXTENDED_POLITICIANS_BY_NATIONALITY_QUERY`** - Country-specific detailed search
   - Returns: Same comprehensive data as extended query
   - Filters: Politicians from a specific country (requires `nationality_qid` parameter)
   - Use case: Jurisdiction-specific compliance, country-focused PEP screening

4. **`build_living_politicians_by_nationality_query(country_id)`** - Living politicians only
   - Returns: Comprehensive data excluding death date (optimized for batching)
   - Filters: Living politicians from a specific country (excludes deceased)
   - Special feature: Query optimized to avoid SPARQL conflicts in batched execution
   - Use case: Current PEP identification, active politician monitoring, compliance for living persons

## Development

### Setting up development environment

1. Follow the installation steps above
2. The conda environment includes all development dependencies

### Running tests

```bash
# Activate the conda environment first
conda activate idenfo-struct-scrape

# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=structured_scraping --cov-report=html -v
```

Use the provided VS Code tasks for testing:

- `Test: Run all tests` - Run the full test suite
- `Test: Run with coverage` - Run tests with coverage reporting

## Architecture

```text
src/structured_scraping/
├── __init__.py                 # Main package exports
├── cli.py                      # Command line interface
├── sparql_utils/              # Generic SPARQL utilities module
│   ├── __init__.py            # Module exports
│   ├── core.py                # Core SPARQL functions
│   ├── batching.py            # Batching functionality
│   ├── retry.py               # Retry logic and rate limiting
│   ├── io.py                  # File I/O operations
│   ├── queries.py             # Query templates
│   └── errors.py              # Custom exceptions and error handling
└── wikidata/                  # Wikidata-specific module
    ├── __init__.py            # Wikidata query functions
    ├── countries.py           # Country identification utilities
    ├── filters.py             # Data filtering utilities
    ├── scrapers.py            # High-level scraping functions
    └── queries/               # Query templates
        ├── __init__.py        # General query templates
        └── pep.py             # PEP-specific queries
```

## Use Cases

### 1. Compliance Screening

- PEP (Politically Exposed Persons) identification
- Risk assessment for financial institutions
- Due diligence processes

### 2. Research & Analytics

- Political data analysis
- Entity relationship mapping
- Knowledge graph exploration

### 3. Data Integration

- Enriching datasets with Wikidata information
- Cross-referencing entity information
- Building knowledge bases

## Contributing

1. Create a feature branch and make your changes
2. Ensure all existing code quality checks and functionality tests are passing
3. Add tests for new functionality
4. Run the test suite
5. Submit a pull request

## Important Notice

**This software is proprietary and confidential.**

- This code is for Idenfo's internal use only
- Do not distribute, share, or upload to any public repositories
- Do not publish or make publicly available in any form
- All rights reserved
