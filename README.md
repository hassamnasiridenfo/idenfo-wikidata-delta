# Idenfo Wikidata Delta — PEP Data Pipeline

End-to-end pipeline that **extracts** Politically Exposed Persons (PEP) data from
Wikidata, **cleans** it into Idenfo's standard schema, runs a **delta comparison**
against the production MySQL database, **inserts** only the new/changed records,
manages **profile images on S3**, generates a **delta Excel report**, and **emails**
the results to the NameScreening team.

> **⚠️ Proprietary & confidential — Idenfo internal use only.**
> Do not distribute, publish, or upload to any public repository.
> Never commit real credentials, customer data, or PII. Use the `.env` file
> (git-ignored) for all secrets.

---

## Table of Contents

- [Repository Layout](#repository-layout)
- [The Two Sub-Projects](#the-two-sub-projects)
- [High-Level Flow](#high-level-flow)
- [Stage 1 — Extraction (`structured-scraping`)](#stage-1--extraction-structured-scraping)
- [Stage 2 — Delta Pipeline (`Wikidata Delta`)](#stage-2--delta-pipeline-wikidata-delta)
  - [Pipeline steps in detail](#pipeline-steps-in-detail)
  - [Delta comparison logic](#delta-comparison-logic)
  - [Image handling logic](#image-handling-logic)
  - [Email logic](#email-logic)
- [Database Schema (overview)](#database-schema-overview)
- [Configuration (`.env`)](#configuration-env)
- [How to Run](#how-to-run)
- [Logs & Outputs](#logs--outputs)
- [Scraper Tags & Country Registry](#scraper-tags--country-registry)
- [Troubleshooting](#troubleshooting)

---

## Repository Layout

```text
idenfo-wikidata-delta/
├── .env                      # all secrets & paths (git-ignored — never commit)
├── environment.yml           # conda environment for the delta project
├── README.md                 # this file
│
├── structured-scraping/      # Stage 1: Wikidata SPARQL extractor (installable CLI)
│   ├── src/structured_scraping/
│   │   ├── cli.py            # `idenfo-struct-scrape` CLI entry point
│   │   ├── sentinel.py       # crash-safe `.inprogress` file gate
│   │   └── ...               # sparql_utils/, wikidata/ (queries, scrapers, filters)
│   ├── extraction_logs/     # per-country extraction logs (replaced each run)
│   └── README.md            # detailed CLI / SPARQL documentation
│
└── Wikidata Delta/           # Stage 2: clean → delta → insert → image → excel → email
    ├── orchestrator.py       # main entry — routes one country through the pipeline
    ├── main.py               # legacy scheduled runner (calls scrapers directly)
    ├── <country>_pep_scrapper.py   # 18 country cleaning scripts (oman, qatar, uk, ...)
    ├── cities_extractor.py   # enriches the City column from address text
    ├── delta_script.py       # delta comparison engine (new vs changed vs same)
    ├── new_df_cleaner.py     # assigns final customer IDs to new records
    ├── insertion_script.py   # inserts new/changed records into MySQL
    ├── image_handler.py      # download → resize → S3 upload / copy / delete
    ├── delta_records_excel.py# rebuilds the delta Excel from the DB
    ├── sending_delta_excel_email.py  # emails the delta report (or "No Delta Found")
    ├── sending_delta_log_file.py     # emails the run log files
    ├── mysql_connection.py            # tuple-cursor connection
    ├── mysql_connection_dictionary.py # dict-cursor connection
    ├── raw_data/<country>/   # extractor output lands here (input to the pipeline)
    ├── <tag>_excels/         # per-tag working folder + generated DELTA xlsx
    ├── Logs/                 # Delta_main_file_<date>.log
    ├── Insertion Logs/       # <tag>.log  (per-tag insertion detail)
    ├── images-Logs/          # <tag>-<date>.log  (image download/upload detail)
    └── Delta Record/         # archived copies of emailed delta files, by date
```

---

## The Two Sub-Projects

| | `structured-scraping` | `Wikidata Delta` |
|---|---|---|
| **Role** | Extract raw PEP data from Wikidata | Clean, compare, insert, report |
| **Interface** | `idenfo-struct-scrape` CLI | `python orchestrator.py <country>` |
| **Output** | `raw_data/<country>/*.xlsx` | DB rows + DELTA Excel + emails |
| **Install** | conda env `idenfo-struct-scrape` | conda env (see `environment.yml`) |

The two are connected: after a successful extraction the CLI **automatically
triggers** the delta pipeline (see [handoff](#the-handoff-extractor--delta)).

---

## High-Level Flow

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 1 — structured-scraping (idenfo-struct-scrape scrape <country>)     │
│                                                                           │
│  Wikidata SPARQL  →  write .inprogress sentinel  →  extract politicians   │
│                   →  save raw_data/<country>/pep_<country>_...xlsx         │
│                   →  remove sentinel ONLY on full success                 │
└───────────────────────────────┬───────────────────────────────────────────┘
                                 │  auto-trigger (DELTA_PROJECT_PATH)
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ STAGE 2 — Wikidata Delta (orchestrator.run_delta_for_country)             │
│                                                                           │
│  0. Sentinel safety gate (refuse partial files)                          │
│  1. Clean   → <country>_pep_scrapper.py  (raw → standard schema df)       │
│  2. Cities  → cities_extractor.py        (fill City from address text)    │
│  3. Connect → MySQL (tuple cursor)                                        │
│  4. Delta   → delta_script.py            (new_df = new + changed)         │
│        └─ if new_df empty → email "No Delta Found" + logs → STOP          │
│  4.5 ID     → new_df_cleaner.py          (assign final customer IDs)      │
│  4.5 Image  → image_handler.process_new_images (download/copy → S3)       │
│  5. Insert  → insertion_script.py        (write new/changed to MySQL)     │
│  4.6 Pending→ image_handler.process_pending_db_images (retry stuck URLs)  │
│  6. Excel   → delta_records_excel.py     (rebuild DELTA xlsx from DB,     │
│                                           delete S3 images of status=0)   │
│  7. Email   → send_emails + send_main_delta_logs                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Stage 1 — Extraction (`structured-scraping`)

A standalone, installable Python package exposing the `idenfo-struct-scrape` CLI.
Full CLI/SPARQL documentation lives in
[`structured-scraping/README.md`](structured-scraping/README.md). Key points:

- **Commands:** `countries` (list/search supported countries) and
  `scrape <country>` (extract politician data).
- **Country input:** code (`om`, `qa`), name (`"United Kingdom"`), or Wikidata ID (`Q145`).
- **Filters:** `--living` (exclude deceased), `--relevant` (exclude pre-1925 births).
- **Batching:** `--batching --batch-size --pause --timeout --max-retries` for large
  datasets, with automatic 429 rate-limit retry.

### The sentinel (crash safety)

[`sentinel.py`](structured-scraping/src/structured_scraping/sentinel.py) writes a
`<output>.inprogress` marker **before** extraction and removes it **only on full
success**. If extraction crashes, the marker stays — and the delta orchestrator
**refuses to process** that partial file. This guarantees the pipeline never
ingests a half-written extract.

### Extraction logs

Each `scrape` run writes a fresh log to `structured-scraping/extraction_logs/<country>.log`
(previous logs are cleared each run, so the folder only ever holds the latest).

### The handoff (extractor → delta)

On successful extraction, `cli.py::_trigger_delta_pipeline()` imports
`orchestrator.run_delta_for_country()` (located via `DELTA_PROJECT_PATH` in `.env`)
and runs Stage 2 automatically — no manual step needed. If `DELTA_PROJECT_PATH`
is unset, it skips gracefully.

---

## Stage 2 — Delta Pipeline (`Wikidata Delta`)

Entry point: **[`orchestrator.py`](Wikidata%20Delta/orchestrator.py)**

```bash
# Run for one country (auto-resolves latest safe raw file)
python orchestrator.py oman

# Or point at a specific extract file
python orchestrator.py oman /path/to/pep_oman_..._.xlsx
```

`run_delta_for_country(country, raw_file_path=None)` looks the country up in
`COUNTRY_REGISTRY`, resolves the raw file, runs the safety gate, then executes
the pipeline. Returns `True` on success/no-op, `False` on failure.

### Pipeline steps in detail

| Step | Module / Function | What it does |
|------|-------------------|--------------|
| **0. Safety gate** | `_check_sentinel()` | Refuses to run if a `.inprogress` sentinel exists for the raw file. |
| **1. Clean** | `<country>_pep_scrapper.py` | Parses the raw extract into the canonical column schema (Name, Alias, RCA, addresses, etc.). Each country has its own quirks (e.g. alias parsing). |
| **2. Cities** | `cities_extractor.py` | Scans address text against a world-cities list and fills in the `City` column. |
| **3. DB connect** | `mysql_connection.py` | Opens a tuple-cursor connection. (`mysql_connection_dictionary.py` opens a dict-cursor used later for the Excel rebuild.) |
| **4. Delta** | `delta_script.py::delta_code()` | Compares each scraped record against the DB. Produces `new_df` = brand-new **+** changed records. Records that are unchanged are flagged for retention; records no longer present get `status = 0`. |
| **→ empty short-circuit** | `orchestrator.py` | If `new_df` is empty, it sends the **"No Delta Found"** email + log email and returns. (Fixed so 0-delta runs still notify.) |
| **4.5 Assign IDs** | `new_df_cleaner.py` | Computes the next `customer_id` per scraper tag (e.g. `OM-GEN-I-78`) and assigns it to each new record's `ID`. |
| **4.5 Images** | `image_handler.process_new_images()` | For each new record: copy existing S3 image to the new ID, or download the Wikidata image URL, resize to 500px, and upload to S3. |
| **5. Insert** | `insertion_script.py::insertion_code()` | Inserts new/changed records into `main` and all child tables (alias, identity, dob, nationality, rca, address, role_type, case_details). |
| **4.6 Pending images** | `image_handler.process_pending_db_images()` | Retries any DB record whose `img_tag` is still a URL (failed earlier or in a prior weekly run) so images are eventually consistent. |
| **6. Delta Excel** | `delta_records_excel.py::delta_excel_df_creator()` | Rebuilds the DELTA report **from the DB** (single big LEFT-JOIN query filtered by `scraper_tag` + today's `updated_on`). Also deletes S3 images for `status = 0` records. |
| **7. Email** | `sending_delta_excel_email.py`, `sending_delta_log_file.py` | Emails the DELTA Excel (with a per-tag summary table) and the run logs. |

### Delta comparison logic

`delta_code()` is the heart of the pipeline. For each scraped row:

1. **Normalize NULLs** — temporarily converts DB `NULL`s to the string `'NULL'`
   (and missing dates to `'1890-01-01'`) so equality comparisons are reliable,
   then reverts at the end.
2. **Exact match query (AND)** — looks for a `main` row matching on all core
   scalar fields (name, father_name, gender, category, desc, source_list,
   list_category, list_type, scraper_tag, dates, status, pob).
   - **Match found** → compare every **child table** (alias, identity,
     nationality, dob, rca, address, role_type, case_details) using
     `Counter`-based set differences (`to_remove` / `to_add`).
     - All child tables equal → **SAME** → kept (added to `is_del_list_1`).
     - Any difference → **CHANGED** → added to `new_df` (logged with the exact
       failing check, e.g. `['alias', 'rca']`).
   - **No exact match** → diagnostic log shows which field(s) differ from the
     closest name+scraper_tag record, then it's treated as a **truly new** record
     and added to `new_df`.
3. **Retire stale records** — any active (`status = 1`) record for this scraper
   tag that wasn't matched this run is set to `status = 0` (no longer in source).

> The result `new_df` therefore contains **both** brand-new records **and**
> changed records that need re-insertion under a new `customer_id`.

### Image handling logic

[`image_handler.py`](Wikidata%20Delta/image_handler.py) handles four per-record cases:

1. **No image** → skip.
2. **Old ID in `Image Tag`** (≠ new ID) → S3 **copy** old key → new key.
3. **`Image Tag` already = the new ID** → skip (already correct).
4. **`Image Tag` is a URL** → **download → resize (500px) → upload** to S3, then set
   `Image Tag` to the record ID.

**Wikimedia handling & adaptive delay:**

- Tries the **thumbnail URL** first (`.../thumb/.../500px-<file>`), falling back to
  the original only on HTTP 400.
- On HTTP **429** (rate limit): waits the server's `Retry-After`, retries the same
  URL up to `DOWNLOAD_RETRIES` times; if still limited, the image is **queued and
  skipped** so the run moves on instead of hammering one URL.
- **Adaptive delay:** delay is set to the server's `Retry-After` value (capped at
  `MAX_DELAY = 10s`); after successful downloads it **reduces by 0.5s** back toward
  `MIN_DELAY`. Tunable via `image_*` env vars.
- Queued (429-exhausted) images are retried at the **end** of the run; anything
  still stuck stays as a URL in the DB and is retried by
  `process_pending_db_images()` (this run) and future weekly runs.

### Email logic

- **`send_emails()`** ([sending_delta_excel_email.py](Wikidata%20Delta/sending_delta_excel_email.py))
  collects today's `*_DELTA_<date>.xlsx` files, builds an HTML summary table
  (scraper tags, list name, source lists, category, record counts), attaches the
  files, and sends. If **no** delta file exists for today, it sends a
  **"No Delta Found for &lt;date&gt;."** notice instead.
- **`send_main_delta_logs()`** ([sending_delta_log_file.py](Wikidata%20Delta/sending_delta_log_file.py))
  emails the run's main log + any error log.
- Both are now called on the **0-delta path** too, so a no-change run still
  produces a notification email.

---

## Database Schema (overview)

The pipeline writes to a MySQL database with a parent `main` table and several
one-to-many child tables keyed on `main_id`:

| Table | Holds |
|-------|-------|
| `main` | Core record: name, father_name, gender, `desc`, category, source_list, list_type, status, `img_tag`, `scraper_tag`, `customer_id`, dates, pob, … |
| `alias` | Aliases / alternate-language name forms (`alias_type`, `alias`) |
| `identity` | ID documents (`id_type`, `id_number`) |
| `nationality` | Nationalities |
| `dob` | Dates of birth |
| `rca` | Related/connected associates (`relationship_type`, `relation_with`) |
| `address` | Address components (primary_address, street, city, state, country, zip, other) |
| `role_type` | Positions held (primary_occupation, designation, start/end date) |
| `case_details` | Charges, case details, notification reference |

Key columns used throughout: `customer_id` (the public record ID, e.g.
`OM-GEN-I-78`), `scraper_tag` (country/source tag, e.g. `om_gen`), `img_tag`
(S3 image ID or a pending URL), `status` (1 = active, 0 = retired).

---

## Configuration (`.env`)

All configuration lives in the git-ignored `.env` at the repo root. **Keys only**
(never commit values):

| Key | Purpose |
|-----|---------|
| `host`, `user`, `password`, `database`, `db_port` | MySQL connection |
| `aws_access_key_id`, `aws_secret_access_key`, `region` / `aws_region` | S3 image storage |
| `smtp_server`, `smtp_port`, `smtp_user`, `smtp_pswd` | Email transport |
| `email_from`, `email_name`, `email_to`, `email_cc` | Delta report recipients |
| `delta_log_email_cc` | Log email CC list |
| `email_subject`, `log_email_subject`, `error_log_email_subject` | Email subjects |
| `file_paths` | Comma-separated folders scanned for `*_DELTA_<date>.xlsx` to attach |
| `DELTA_RAW_DATA_PATH` | Base folder of `raw_data/<country>/` extracts |
| `DELTA_PROJECT_PATH` | Path to `Wikidata Delta/` (lets the CLI import `orchestrator.py`) |
| `STRUCT_SCRAPING_PATH` | Path to `structured-scraping` src (lets orchestrator import the sentinel) |

Optional image tuning (with defaults): `image_total_delay` (0.0),
`image_min_delay` (0.5), `image_delay_step` (0.5), `image_max_delay` (10.0),
`image_max_rate_limit_wait` (10), `image_recovery_floor_429` (8.5),
`image_download_retries` (2), `image_max_429_retry_rounds` (10),
`image_pending_start_delay`.

> **S3 / AWS credentials and DB passwords must never appear in code, logs, commits,
> or chat.** They belong only in `.env`.

---

## How to Run

### Full automated run (extract → delta → email)

```bash
conda activate idenfo-struct-scrape
idenfo-struct-scrape scrape oman --living --relevant --batching
# → extracts, saves to raw_data/oman/, then auto-triggers the delta pipeline
```

### Delta pipeline only (raw file already exists)

```bash
cd "Wikidata Delta"
conda activate <delta-env>        # see environment.yml
python orchestrator.py oman       # newest safe file in raw_data/oman/
python orchestrator.py oman /abs/path/to/extract.xlsx   # explicit file
```

### Legacy scheduled runner

`main.py` is the older entry point that calls the country scrapers directly
(Oman + Qatar currently active; others commented out) and emails at the end.
`orchestrator.py` is the preferred, per-country path.

---

## Logs & Outputs

| Path | Contents |
|------|----------|
| `Wikidata Delta/Logs/Delta_main_file_<date>.log` | Main pipeline log (delta decisions per record) |
| `Wikidata Delta/Insertion Logs/<tag>.log` | Per-tag insertion detail |
| `Wikidata Delta/images-Logs/<tag>-<date>.log` | Image download/upload/copy/delete detail |
| `structured-scraping/extraction_logs/<country>.log` | Latest extraction log (replaced each run) |
| `Wikidata Delta/<tag>_excels/<tag>_DELTA_<date>.xlsx` | Generated delta report |
| `Wikidata Delta/Delta Record/Delta of <date>/` | Archived copies of emailed delta files |

---

## Scraper Tags & Country Registry

Each country maps to a `scraper_tag` and a cleaning module in
`orchestrator.py::COUNTRY_REGISTRY`. Currently registered:

| Country | Key(s) | Tag | Cleaner module |
|---------|--------|-----|----------------|
| Oman | `oman`, `om` | `om_gen` | `oman_pep_scrapper` |
| Qatar | `qatar`, `qa` | `qa_gen` | `qatar_pep_scrapper` |
| Pakistan | `pakistan`, `pk` | `pk_gen` | `pakistan_pep_scrapper` |
| United Kingdom | `uk` | `uk_gen` | `uk_pep_scrapper` |
| Lithuania | `lithuania`, `lt` | `lt_gen` | `lithuania_pep_scrapper` |
| Bahrain | `bahrain`, `bh` | `bh_gen` | `bahrain_pep_scrapper` |
| Belgium | `belgium`, `be` | `be_gen` | `belgium_pep_scrapper` |
| France | `france`, `fr` | `fr_gen` | `france_pep_scrapper` |
| Greece | `greece`, `gr` | `gr_gen` | `greece_pep_scrapper` |
| India | `india`, `in` | `in_gen` | `indian_pep_scrapper` |
| Ireland | `ireland`, `ie` | `ie_gen` | `ireland_pep_scrapper` |
| Kazakhstan | `kazakhstan`, `kz` | `kz_gen` | `kazakhstan_pep_scrapper` |
| Nepal | `nepal`, `np` | `np_gen` | `nepal_pep_scrapper` |
| Netherlands | `netherlands`, `nl` | `kg_nl_gen` | `netherlands_pep_scrapper` |
| Nigeria | `nigeria`, `ng` | `ng_gen` | `nigeria_pep_scrapper` |
| Switzerland | `switzerland`, `ch` | `ch_gen` | `switzerland_pep_scrapper` |
| UAE | `united arab emirates`, `ae` | `ae_gen` | `uae_pep_scrapper` |
| Uzbekistan | `uzbekistan`, `uz` | `uz_gen` | `uzbekistan_pep_scrapper` |

To add a country: write `<country>_pep_scrapper.py` returning the standard schema
DataFrame, then add a row to `COUNTRY_REGISTRY`.

---

## Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| "BLOCKED: sentinel found" | Extraction crashed → a `.inprogress` file remains. Re-run the extraction; the orchestrator won't process a partial file. |
| No email on a 0-delta run | Fixed — the empty-`new_df` branch now sends the "No Delta Found" + log emails. Check SMTP env vars if still missing. |
| Images exhaust at start / very slow | Wikimedia is rate-limiting the IP. Delay is capped at `image_max_delay` (10s); stuck images are left as URLs and retried by `process_pending_db_images` / next weekly run. |
| `No config for country` | The country key isn't in `COUNTRY_REGISTRY` — add it. |
| `DELTA_PROJECT_PATH not set` | The CLI can't find the delta project to auto-trigger — set it in `.env`. |
| Delta Excel missing columns | The rebuild query reads from the DB; ensure insertion succeeded (check `Insertion Logs/<tag>.log`). |

---

*Generated as project documentation. Keep secrets in `.env`; all compliance/regulatory
outputs must be reviewed by a qualified compliance officer before use.*
