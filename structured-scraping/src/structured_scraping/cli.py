"""CLI interface for structured scraping."""
import json
import logging
import os
import sys
import traceback
from pathlib import Path
from dotenv import load_dotenv  # ← ADD
load_dotenv()     
import click

from .sentinel import write_sentinel, remove_sentinel, sentinel_path
from .wikidata.countries import get_country_id, get_country_name, list_supported_countries
from .wikidata.scrapers import (
    PEPScraperConfig,
    count_country_politicians,
    scrape_country_politicians_by_decade,
)

# Constants
MAX_TABLE_ROWS = 20
MAX_DISPLAY_COUNTRIES = 20

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# LOGGING HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def configure_debug_logging() -> None:
    """Configure debug logging for the entire structured_scraping package."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    package_logger = logging.getLogger("structured_scraping")
    package_logger.setLevel(logging.DEBUG)

    for handler in root_logger.handlers:
        handler.setLevel(logging.DEBUG)

    logger.debug("Debug logging enabled for structured_scraping package")


def _setup_logging(ctx: click.Context) -> None:
    """Set up debug logging if requested."""
    debug_enabled = ctx.obj.get("debug", False) if ctx.obj else False
    if debug_enabled:
        configure_debug_logging()
        logger.debug("Debug logging enabled")


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT PATH BUILDER  (NEW)
# ─────────────────────────────────────────────────────────────────────────────

def _build_output_path(
    country_name: str,
    living: bool,
    relevant: bool,
    explicit_output: Path | None,
) -> Path:
    """
    Decide where the raw extraction file will be saved.

    Priority:
      1. --output flag passed by user  →  use it exactly
      2. DELTA_RAW_DATA_PATH set in .env  →  raw_data/<country>/<filename>
      3. Fallback  →  current working directory
    """
    import datetime as dt

    timestamp    = dt.datetime.now(tz=dt.UTC).strftime("%Y%m%d_%H%M%S")
    living_tag   = "living"   if living   else "all"
    relevant_tag = "relevant" if relevant else "all"

    # "United Kingdom" -> "united_kingdom"
    folder_name = country_name.lower().replace(" ", "_")
    filename    = f"pep_{folder_name}_{living_tag}_{relevant_tag}_{timestamp}.xlsx"

    if explicit_output is not None:
        return explicit_output                        # respect --output flag

    raw_base = os.getenv("DELTA_RAW_DATA_PATH")
    if raw_base:
        country_folder = Path(raw_base) / folder_name
        country_folder.mkdir(parents=True, exist_ok=True)
        return country_folder / filename              # e.g. raw_data/oman/pep_oman_...xlsx

    return Path(filename)                             # fallback: current directory


# ─────────────────────────────────────────────────────────────────────────────
# DELTA TRIGGER  (NEW)
# ─────────────────────────────────────────────────────────────────────────────

def _trigger_delta_pipeline(
    country_name: str,
    raw_file_path: Path,
    ctx: click.Context,
) -> None:
    """
    Call orchestrator.run_delta_for_country() after a successful extraction.
    This replaces having to run 'python3 main.py' manually.

    Reads DELTA_PROJECT_PATH from .env to locate orchestrator.py.
    Skips gracefully if the env var is not set.
    """
    delta_project_path = os.getenv("DELTA_PROJECT_PATH")

    if not delta_project_path:
        click.echo(
            "ℹ️  DELTA_PROJECT_PATH not set in .env — skipping delta pipeline automatically."
        )
        return

    click.echo(f"🔗 Triggering delta pipeline for: {country_name}")

    try:
        # Add delta project to path so orchestrator.py can be imported
        if delta_project_path not in sys.path:
            sys.path.insert(0, delta_project_path)

        from orchestrator import run_delta_for_country  # type: ignore[import]

        run_delta_for_country(
            country=country_name,
            raw_file_path=str(raw_file_path),
        )

    except ImportError:
        click.echo(
            f"❌ Could not import orchestrator.py from: {delta_project_path}\n"
            "   Make sure orchestrator.py exists in that folder.",
            err=True,
        )
    except Exception as e:  # noqa: BLE001
        click.echo(f"❌ Delta pipeline failed: {e}", err=True)
        debug_enabled = ctx.obj.get("debug", False) if ctx.obj else False
        if debug_enabled:
            click.echo(traceback.format_exc(), err=True)


# ─────────────────────────────────────────────────────────────────────────────
# COUNT HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _count_politicians(
    country_id: str,
    living: bool,
    config: PEPScraperConfig,
    ctx: click.Context,
) -> int:
    """Count politicians for the given country."""
    click.echo("📊 Counting politicians...")
    try:
        count = count_country_politicians(
            country=country_id,
            living_only=living,
            config=config,
        )
    except Exception as e:
        click.echo(f"❌ Error counting politicians: {e}", err=True)
        debug_enabled = ctx.obj.get("debug", False) if ctx.obj else False
        if debug_enabled:
            logger.exception("Count failed")
            click.echo("\n🔍 Full traceback (debug mode):", err=True)
            click.echo(traceback.format_exc(), err=True)
        sys.exit(1)
    else:
        living_text = "living " if living else ""
        click.echo(f"✅ Found {count:,} {living_text}politicians")
        return count


# ─────────────────────────────────────────────────────────────────────────────
# ERROR CLASSIFIER
# ─────────────────────────────────────────────────────────────────────────────

def _classify_error_type(error_msg: str) -> str | None:
    """Classify the error type based on error message patterns."""
    error_msg_lower = error_msg.lower()

    if "resilient processing failed after json corruption" in error_msg_lower:
        return "backend_timeout"

    if any(pattern in error_msg_lower for pattern in [
        "backend timeout",
        "query too complex for server",
        "query complexity exceeds server processing capacity",
        "timed out",
        "timeout",
        "the read operation timed out",
    ]):
        return "backend_timeout"

    if any(pattern in error_msg_lower for pattern in [
        "json corruption",
        "falling back to resilient processing",
        "invalid control character",
    ]):
        return "json_corruption"

    if any(pattern in error_msg_lower for pattern in [
        "rate limit",
        "too many requests",
        "server overload",
    ]):
        return "rate_limiting"

    if any(pattern in error_msg_lower for pattern in [
        "network connectivity issue",
        "connection",
        "network",
    ]):
        return "network_error"

    return None


# ─────────────────────────────────────────────────────────────────────────────
# SCRAPE AND SAVE  (UPDATED — sentinel + output path integrated)
# ─────────────────────────────────────────────────────────────────────────────

def _scrape_and_save(  # noqa: C901
    country_id: str,
    country_name: str,          # NEW parameter
    output: Path | None,
    living: bool,
    relevant: bool,
    batching: bool,
    config: PEPScraperConfig,
    ctx: click.Context,
) -> Path | None:
    """
    Execute scraping with sentinel safety and save results.

    Returns the output Path on success, or None on failure.
    The sentinel file is written BEFORE extraction starts and removed ONLY
    after full success — so a crash leaves it on disk and the orchestrator
    will refuse to process the incomplete file.
    """
    # ── Build the output path (routes into raw_data/<country>/ folder) ──
    output_path = _build_output_path(country_name, living, relevant, output)

    execution_mode = "batched" if batching else "simple"
    click.echo(f"🔄 Scraping politician data ({execution_mode} execution)...")
    click.echo(f"📂 Output will be saved to: {output_path}")

    # ── Write sentinel BEFORE extraction starts ──────────────────────────
    write_sentinel(output_path)
    click.echo("🔒 Sentinel written — extraction in progress")

    try:
        if batching:
            click.echo("⏳ Processing batches...")

        scraped_count, output_file = scrape_country_politicians_by_decade(
            country=country_id,
            output_file=output_path,        # always use the path we built
            living_only=living,
            apply_relevance_filter=relevant,
            config=config,
        )

        # ── Remove sentinel ONLY on full success ─────────────────────────
        remove_sentinel(output_path)
        click.echo("🔓 Sentinel removed — extraction complete")

        click.echo(f"✅ Scraped {scraped_count:,} records")
        click.echo(f"📁 Saved to: {output_file}")

        file_path = Path(output_file)
        if file_path.exists():
            file_size = file_path.stat().st_size
            click.echo(f"📈 File size: {file_size:,} bytes")

        return output_path                  # ← success: return the path

    except Exception as e:  # noqa: BLE001
        # ── IMPORTANT: sentinel is NOT removed here ───────────────────────
        # It stays on disk so the orchestrator refuses to process a partial
        # or corrupted file. Delete it manually if you want to retry with
        # the same filename (normally just re-run the command for a fresh file).
        click.echo(
            f"⚠️  Sentinel left in place: {sentinel_path(output_path).name}",
            err=True,
        )
        click.echo(
            "   Delete it manually after verifying the file, or just re-run the command.",
            err=True,
        )

        error_msg = str(e)
        debug_enabled = ctx.obj.get("debug", False) if ctx.obj else False

        if debug_enabled:
            logger.debug("CLI received error: %r", error_msg)

        error_type = _classify_error_type(error_msg)

        if debug_enabled:
            logger.debug("CLI classified error type as: %r", error_type)

        if error_type == "backend_timeout":
            click.echo(
                "❌ Error: Query too complex or too large for Wikidata backend (timeout). "
                "Try enabling batching, reducing batch size, or limiting the number of fields.",
                err=True,
            )
        elif error_type == "json_corruption":
            click.echo(
                "❌ Error: JSON corruption detected. This may be due to a backend bug or incomplete response.",
                err=True,
            )
        elif error_type == "rate_limiting":
            click.echo(
                "❌ Error: Rate limiting or server overload. Please try again later.",
                err=True,
            )
        elif error_type == "network_error":
            click.echo(
                "❌ Error: Network connectivity issue. Please check your connection and try again.",
                err=True,
            )
        else:
            click.echo(f"❌ Error scraping data: {e}", err=True)

        if debug_enabled:
            click.echo("\n🔍 Full traceback (debug mode):", err=True)
            click.echo(traceback.format_exc(), err=True)

        return None                         # ← failure: return None


# ─────────────────────────────────────────────────────────────────────────────
# CLI GROUP
# ─────────────────────────────────────────────────────────────────────────────

@click.group()
@click.version_option()
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug logging for all operations.",
)
@click.pass_context
def main(ctx: click.Context, debug: bool) -> None:
    """Structured Scraping CLI - Extract politician data from Wikidata."""
    ctx.ensure_object(dict)
    ctx.obj["debug"] = debug

    if debug:
        configure_debug_logging()


# ─────────────────────────────────────────────────────────────────────────────
# SCRAPE COMMAND
# ─────────────────────────────────────────────────────────────────────────────

@main.command()
@click.argument("country")
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    help="Output file path. If not provided, auto-generates timestamped filename.",
)
@click.option("--living",      is_flag=True, help="Only scrape living politicians (exclude deceased).")
@click.option("--relevant",    is_flag=True, help="Apply relevance filtering (exclude pre-1925 births etc).")
@click.option("--batching",    is_flag=True, help="Enable batched query execution for large datasets.")
@click.option("--decades",     is_flag=True, help="Enable decade-based filtering for results.")
@click.option("--batch-size",  type=click.IntRange(min=1, max=10000), default=3000,  help="Results per batch (only with --batching).")
@click.option("--pause",       type=click.FloatRange(min=0.0),        default=2.0,   help="Pause between batches in seconds.")
@click.option("--timeout",     type=click.IntRange(min=1),            default=60,    help="Query timeout in seconds.")
@click.option("--max-retries", type=click.IntRange(min=0),            default=5,     help="Maximum retry attempts for rate limiting.")
@click.option("--count-only",  is_flag=True, help="Only count politicians, don't scrape data.")
@click.pass_context
def scrape(
    ctx: click.Context,
    country: str,
    output: Path | None,
    living: bool,
    relevant: bool,
    batching: bool,
    decades: bool,
    batch_size: int,
    pause: float,
    timeout: int,
    max_retries: int,
    count_only: bool,
) -> None:
    """Scrape politicians from a specific country.

    COUNTRY can be a country code (qa, us, uk), country name (Qatar, United States),
    or Wikidata ID (Q846 for Qatar).

    Examples:\n
        idenfo-struct-scrape scrape qa\n
        idenfo-struct-scrape scrape qa --batching\n
        idenfo-struct-scrape scrape "United States" --living\n
        idenfo-struct-scrape scrape qa --living --relevant\n
        idenfo-struct-scrape scrape uk --count-only\n
        idenfo-struct-scrape scrape qa --batching --batch-size 1000 --output qatar_peps.csv
    """
    _setup_logging(ctx)

    try:
        # ── Resolve country ───────────────────────────────────────────────
        country_id   = get_country_id(country)
        country_name = get_country_name(country)

        click.echo(f"🌍 Target: {country_name} ({country_id})")

        # ── Build config ──────────────────────────────────────────────────
        config = PEPScraperConfig(
            batch_size=batch_size,
            pause_s=pause,
            timeout=timeout,
            max_retries=max_retries,
            use_batching=batching,
            use_decades=decades,
        )

        # ── Count first ───────────────────────────────────────────────────
        count = _count_politicians(country_id, living, config, ctx)

        if count_only:
            return

        if count == 0:
            click.echo("⚠️  No politicians found. Nothing to scrape.")
            return

        # ── Scrape and save ───────────────────────────────────────────────
        result_path = _scrape_and_save(
            country_id=country_id,
            country_name=country_name,      # passed so output path can be built
            output=output,
            living=living,
            relevant=relevant,
            batching=batching,
            config=config,
            ctx=ctx,
        )

        # ── Trigger delta pipeline automatically ──────────────────────────
        # This replaces running 'python3 main.py' manually.
        # Only fires if extraction fully succeeded (result_path is not None).
        if result_path is not None:
            _trigger_delta_pipeline(
                country_name=country_name,
                raw_file_path=result_path,
                ctx=ctx,
            )

    except ValueError as e:
        click.echo(f"❌ Invalid country: {e}", err=True)
        click.echo("\nUse 'idenfo-struct-scrape countries' to see supported countries.", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        debug_enabled = ctx.obj.get("debug", False) if ctx.obj else False
        if debug_enabled:
            logger.exception("Unexpected error")
            click.echo("\n🔍 Full traceback (debug mode):", err=True)
            click.echo(traceback.format_exc(), err=True)
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# COUNTRIES COMMAND  (unchanged from original)
# ─────────────────────────────────────────────────────────────────────────────

@main.command()
@click.option(
    "--format", "output_format",
    type=click.Choice(["table", "csv", "json"]),
    default="table",
    help="Output format for country list.",
)
@click.option("--search", help="Search for countries containing this text.")
@click.pass_context
def countries(ctx: click.Context, output_format: str, search: str | None) -> None:  # noqa: C901
    """List all supported countries.

    Examples:\n
        idenfo-struct-scrape countries\n
        idenfo-struct-scrape countries --search "gulf"\n
        idenfo-struct-scrape countries --format csv
    """
    try:
        all_countries = list_supported_countries()

        if search:
            search_lower = search.lower()
            filtered_countries = [
                c for c in all_countries
                if (search_lower in c["name"].lower() or
                    search_lower in c["code"].lower() or
                    search_lower in c["wikidata_id"].lower())
            ]
            click.echo(f"🔍 Found {len(filtered_countries)} countries matching '{search}':")
        else:
            filtered_countries = all_countries
            click.echo(f"🌍 {len(filtered_countries)} supported countries:")

        if not filtered_countries:
            click.echo("No countries found matching your search.")
            return

        if output_format == "table":
            click.echo(f"{'Code':<6} {'Name':<30} {'Wikidata ID':<12}")
            click.echo("-" * 50)
            for c in filtered_countries[:MAX_TABLE_ROWS]:
                code = c["code"] or "N/A"
                click.echo(f"{code:<6} {c['name']:<30} {c['wikidata_id']:<12}")
            if len(filtered_countries) > MAX_TABLE_ROWS:
                click.echo(f"... and {len(filtered_countries) - MAX_TABLE_ROWS} more countries")
                click.echo("Use --format csv or --format json to see all countries")

        elif output_format == "csv":
            click.echo("code,name,wikidata_id")
            for c in filtered_countries:
                code = c["code"] or ""
                click.echo(f'"{code}","{c["name"]}","{c["wikidata_id"]}"')

        elif output_format == "json":
            click.echo(json.dumps(filtered_countries, indent=2))

    except (KeyError, ValueError) as e:
        click.echo(f"❌ Error listing countries: {e}", err=True)
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        click.echo(f"❌ Unexpected error listing countries: {e}", err=True)
        debug_enabled = ctx.obj.get("debug", False) if ctx.obj else False
        if debug_enabled:
            click.echo("\n🔍 Full traceback (debug mode):", err=True)
            click.echo(traceback.format_exc(), err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()