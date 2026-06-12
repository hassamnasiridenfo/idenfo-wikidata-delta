import io
import logging
import os
import time
import boto3
import requests
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from PIL import Image
from urllib.parse import quote, unquote, urlparse, urlunparse

load_dotenv()

S3_BUCKET = os.getenv('aws_s3_bucket_name', 'namescreening-images')
s3_client = boto3.client(
    's3',
    region_name           = os.getenv('region', 'ap-southeast-1'),
    aws_access_key_id     = os.getenv('aws_access_key_id'),
    aws_secret_access_key = os.getenv('aws_secret_access_key'),
)

TARGET_PX           = 500   # resize longest side to this many pixels
TOTAL_DELAY         = float(os.getenv('image_total_delay', '0.0'))
MIN_DELAY           = float(os.getenv('image_min_delay', '0.5'))
DELAY_STEP          = float(os.getenv('image_delay_step', '0.5'))
# Changed By Hassam Nasir
# MAX_DELAY         = float(os.getenv('image_max_delay', '10.0'))  # old: 10s cap too low — IP kept getting 429
MAX_DELAY           = float(os.getenv('image_max_delay', '20.0'))  # allow pacing up to 30s to clear throttle
# MAX_RATE_LIMIT_WAIT = float(os.getenv('image_max_rate_limit_wait', '10'))  # old: retried after only 10s → re-429
MAX_RATE_LIMIT_WAIT = float(os.getenv('image_max_rate_limit_wait', '20'))    # honor server Retry-After up to 30s
RATE_LIMIT_BACKOFF_BASE = float(os.getenv('image_rate_limit_backoff_base', '10'))  # escalate 10→20→30 across retries
RECOVERY_FLOOR_429  = float(os.getenv('image_recovery_floor_429', '8.5'))
DOWNLOAD_RETRIES    = int(os.getenv('image_download_retries', '2'))
MAX_429_RETRY_ROUNDS = int(os.getenv('image_max_429_retry_rounds', '10'))
PENDING_START_DELAY = float(os.getenv('image_pending_start_delay', str(RECOVERY_FLOOR_429)))

# Changed By Hassam Nasir
# Wikimedia's User-Agent policy aggressively rate-limits (429) generic/browser User-Agents
# hitting upload.wikimedia.org in bulk. A descriptive UA that identifies the client and a
# contact address is the primary fix for the 429 storm. Configurable via env if needed.
USER_AGENT = os.getenv(
    'image_user_agent',
    'IdenfoPEPImageBot/1.0 (NameScreening compliance pipeline; contact: support@idenfo.com)'
)
# Shared session → connection reuse + consistent headers on every request.
_session = requests.Session()
_session.headers.update({
    'User-Agent': USER_AGENT,
    'Accept': 'image/avif,image/webp,image/png,image/jpeg,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
})

_log = logging.getLogger('image_handler')

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
IMAGES_LOG_DIR = os.path.join(BASE_DIR, 'images-Logs')


def _setup_image_logger(scraper_tag: str) -> logging.Logger:
    """
    Return a logger that writes to:
        images-Logs/<scraper_tag>-<image_upload_logs><YYYY-MM-DD>.log

    The folder is created if it does not exist.
    Calling this multiple times with the same scraper_tag is safe —
    handlers are only added once.
    """
    import datetime
    os.makedirs(IMAGES_LOG_DIR, exist_ok=True)

    date_str  = datetime.datetime.now().strftime('%Y-%m-%d')
    log_name  = f'image_handler.{scraper_tag}'
    log_file  = os.path.join(IMAGES_LOG_DIR, f'{scraper_tag}-{date_str}.log')

    logger = logging.getLogger(log_name)
    logger.setLevel(logging.INFO)

    # Avoid adding duplicate handlers on repeated calls
    if not any(
        isinstance(h, logging.FileHandler) and h.baseFilename == os.path.abspath(log_file)
        for h in logger.handlers
    ):
        handler = logging.FileHandler(log_file, encoding='utf-8')
        handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        )
        logger.addHandler(handler)

    return logger


# ── S3 helpers ──────────────────────────────────────────────────────────────────

def _s3_key(scraper_tag: str, record_id: str) -> str:
    return f"{scraper_tag}/{record_id}.jpg"


def _s3_exists(key: str) -> bool:
    try:
        s3_client.head_object(Bucket=S3_BUCKET, Key=key)
        return True
    except ClientError:
        return False


def _upload(local_path: str, key: str) -> None:
    with open(local_path, 'rb') as fh:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=fh.read(),
            ContentType='image/jpeg',
        )


def _delete_from_s3(key: str, logger) -> None:
    try:
        s3_client.delete_object(Bucket=S3_BUCKET, Key=key)
        logger.info(f'[IMAGE] Deleted from S3: {key}')
    except ClientError as exc:
        logger.warning(f'[IMAGE] S3 delete failed for {key}: {exc}')


def _ensure_s3_folder(scraper_tag: str, logger) -> None:
    """
    Check if the <scraper_tag>/ folder exists in S3.
    If not, create it as a zero-byte folder-marker object so it appears
    as a proper folder in the S3 console and for any country run.
    """
    folder_key = f"{scraper_tag}/"
    try:
        resp = s3_client.list_objects_v2(
            Bucket=S3_BUCKET,
            Prefix=folder_key,
            MaxKeys=1,
        )
        if resp.get('KeyCount', 0) == 0:
            # Folder does not exist — create folder marker
            s3_client.put_object(Bucket=S3_BUCKET, Key=folder_key, Body=b'')
            logger.info(f'[IMAGE] Created S3 folder: {S3_BUCKET}/{folder_key}')
        else:
            logger.info(f'[IMAGE] S3 folder already exists: {S3_BUCKET}/{folder_key}')
    except ClientError as exc:
        logger.warning(f'[IMAGE] Could not ensure S3 folder {folder_key}: {exc}')


# ── Custom exception for 429 ────────────────────────────────────────────────────

class TooManyRequestsError(Exception):
    """Raised when server responds with HTTP 429. Carries the Retry-After value."""
    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(f'429 Too Many Requests — retry after {retry_after}s')


def _parse_retry_after(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return MAX_RATE_LIMIT_WAIT


def _delay_after_429(current_delay: float, retry_after: float) -> float:
    # Changed By Hassam Nasir
    # Steady-state spacing climbs by DELAY_STEP on each 429 (and is never below the
    # server's Retry-After), capped at MAX_DELAY (30s). Clean downloads reduce it again
    # in the caller, so the delay self-tunes to the lowest spacing that avoids 429.
    wait_seconds = min(float(retry_after or RATE_LIMIT_BACKOFF_BASE), MAX_RATE_LIMIT_WAIT)
    return min(max(current_delay + DELAY_STEP, wait_seconds), MAX_DELAY)


# ── Wikimedia thumbnail URL helpers ────────────────────────────────────────────

def _normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    path  = quote(unquote(parsed.path),  safe="/:%")
    query = quote(unquote(parsed.query), safe="=&?/:+,%")
    return urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, query, parsed.fragment))


def _wikimedia_thumbnail_url(url: str, width: int = TARGET_PX) -> str:
    """Convert a Wikimedia Commons full-size URL to its 500px thumbnail equivalent."""
    parsed     = urlparse(url.strip())
    path_parts = parsed.path.split("/")
    if parsed.netloc.lower() != "upload.wikimedia.org":
        return url
    if len(path_parts) < 6:
        return url
    if path_parts[1:3] != ["wikipedia", "commons"]:
        return url
    if path_parts[3] == "thumb":
        return url     # already a thumbnail
    filename           = path_parts[-1]
    thumb_filename     = f"{width}px-{filename}"
    if filename.lower().endswith(".svg"):
        thumb_filename += ".png"
    thumb_path = "/".join(path_parts[:3] + ["thumb"] + path_parts[3:] + [thumb_filename])
    return urlunparse((parsed.scheme, parsed.netloc, thumb_path, parsed.params, parsed.query, parsed.fragment))


def _download_url_candidates(url: str) -> list:
    """Return [thumbnail_url, original_url] for Wikimedia, or [original_url] for others."""
    original  = _normalize_url(url)
    thumbnail = _normalize_url(_wikimedia_thumbnail_url(url, TARGET_PX))
    if thumbnail != original:
        return [thumbnail, original]
    return [original]


# ── Download + resize ───────────────────────────────────────────────────────────

def _download_and_resize(url: str, save_path: str, delay: float, img_log=None) -> float:
    """
    Try Wikimedia thumbnail URL first, then original URL (on 400 only).
    On 429: sleeps Retry-After and retries the same candidate up to
            DOWNLOAD_RETRIES times; if all retries exhausted → raises
            TooManyRequestsError immediately (does NOT fall through to
            original URL — same IP rate limit applies to both).
    On 400 for a thumbnail URL: skips to the original URL.
    Other errors: raised immediately (no retry).

    Returns max_retry_after (float):
      0.0  → clean download, no 429 encountered at all
      >0.0 → 429 was hit but eventually recovered; value = max Retry-After seen
    Raises TooManyRequestsError when all candidates + all retries exhausted on 429.
    """
    time.sleep(delay)

    candidates        = _download_url_candidates(url)
    original_url      = _normalize_url(url)
    max_retry_after   = 0.0

    logger = img_log or _log   # write to image log file when available

    for candidate_url in candidates:
        is_thumbnail = candidate_url != original_url
        if is_thumbnail:
            logger.info('THUMBNAIL | Using Wikimedia thumbnail URL: %s', candidate_url)

        for attempt in range(DOWNLOAD_RETRIES + 1):
            # Changed By Hassam Nasir
            # Use the shared session (compliant Wikimedia User-Agent + connection reuse).
            resp = _session.get(candidate_url, timeout=30)

            if resp.status_code == 429:
                retry_after  = _parse_retry_after(resp.headers.get('Retry-After'))
                # Changed By Hassam Nasir
                # Escalating backoff: wait at least the server's Retry-After, but grow each
                # attempt (10s → 20s → 30s) so a later retry actually clears the throttle
                # window instead of re-failing on a too-short wait. Capped at MAX_RATE_LIMIT_WAIT.
                escalated    = max(retry_after, RATE_LIMIT_BACKOFF_BASE * (attempt + 1))
                wait_seconds = min(escalated, MAX_RATE_LIMIT_WAIT)
                max_retry_after = max(max_retry_after, wait_seconds)
                if attempt < DOWNLOAD_RETRIES:
                    logger.warning('Rate limited. Waiting %.0fs before retrying (attempt %d/%d).',
                                   wait_seconds, attempt + 1, DOWNLOAD_RETRIES)
                    time.sleep(wait_seconds)
                    continue                 # retry same candidate
                # 429 exhausted on this candidate → raise (same IP throttle applies to original too)
                raise TooManyRequestsError(max_retry_after or MAX_RATE_LIMIT_WAIT)

            if resp.status_code == 400 and is_thumbnail:
                break                       # thumbnail rejected → try original URL (400 only)

            resp.raise_for_status()         # other 4xx/5xx: raise immediately

            # ── Success: decode and save ─────────────────────────────────────
            img = Image.open(io.BytesIO(resp.content))
            img.thumbnail((TARGET_PX, TARGET_PX), Image.LANCZOS)
            if img.mode in ('RGBA', 'P', 'LA'):
                img = img.convert('RGB')
            img.save(save_path, 'JPEG')
            return max_retry_after          # 0.0 = clean, >0.0 = 429 but recovered

    # All candidates exhausted on 429
    raise TooManyRequestsError(max_retry_after or MAX_RATE_LIMIT_WAIT)


# ── Public API ──────────────────────────────────────────────────────────────────

def _local_images_dir(scraper_tag: str) -> str:
    """
    Returns (and creates if needed) the local folder where images are saved
    before S3 upload:
        <BASE_DIR>/<scraper_tag>_excels/<scraper_tag>/
    e.g.  Wikidata Delta/om_gen_excels/om_gen/
    This is the same folder where the cleaned Excel and RCA lookup are saved.
    """
    folder = os.path.join(BASE_DIR, f'{scraper_tag}_excels', scraper_tag)
    os.makedirs(folder, exist_ok=True)
    return folder


def _do_download_upload(url: str, record_id: str, scraper_tag: str,
                        local_dir: str, delay: float, img_log, log):
    """
    Download + resize + upload one image.
    Returns updated delay on success.
    Raises TooManyRequestsError or other Exception on failure.
    """
    key        = _s3_key(scraper_tag, record_id)
    local_path = os.path.join(local_dir, f'{record_id}.jpg')

    img_log.info(f'DOWNLOAD | {record_id} | {url}')
    t0 = time.time()
    max_retry_after = _download_and_resize(url, local_path, delay, img_log=img_log)
    download_time = time.time() - t0 - delay
    img_log.info(f'DOWNLOAD OK | {record_id} | took {download_time:.2f}s (delay={delay:.2f}s)')

    img_log.info(f'UPLOAD   | {key}')
    _upload(local_path, key)

    # Delete local file immediately after successful upload
    try:
        os.remove(local_path)
    except OSError:
        pass

    img_log.info(f'UPLOAD OK | {key}')
    log.info(f'[IMAGE] Uploaded: {key}')
    return max_retry_after   # pass back to caller for adaptive delay adjustment


# Writes the URL→ID images Excel for manual S3 upload
def _write_image_url_excel(scraper_tag: str, rows: list, img_log) -> str:
    """
    Create <scraper_tag>_excels/<scraper_tag>_images_url_<YYYY-MM-DD>.xlsx with two
    columns — URL and ID — one row per new image that must be uploaded manually to S3.
    Any previous images_url file for this tag is removed first so only the latest remains.
    Returns the written file path.
    """
    import datetime
    import pandas as pd

    date_str = datetime.datetime.now().strftime('%Y-%m-%d')
    out_dir  = os.path.join(BASE_DIR, f'{scraper_tag}_excels')
    os.makedirs(out_dir, exist_ok=True)

    # Remove previous images_url file(s) for this tag
    for fname in os.listdir(out_dir):
        if fname.startswith(f'{scraper_tag}_images_url_') and fname.endswith('.xlsx'):
            try:
                os.remove(os.path.join(out_dir, fname))
            except OSError:
                pass

    out_path = os.path.join(out_dir, f'{scraper_tag}_images_url_{date_str}.xlsx')
    pd.DataFrame(rows, columns=['URL', 'ID']).to_excel(out_path, index=False)
    img_log.info(f'IMAGE URL EXCEL | wrote {len(rows)} row(s) → {out_path}')
    return out_path


def process_new_images(new_df, scraper_tag: str, logger=None):
    """
    Called from orchestrator AFTER delta_code(), BEFORE insertion_code().

    Handles four cases per row:
      1. No image (empty/NaN)           → skip
      2. Image Tag = old ID ≠ record_id → copy S3 old→new, update Image Tag
      3. Image Tag = record_id already  → skip (already correct)
      4. Image Tag = URL                → download → upload → update Image Tag

    Adaptive delay:
      - On 429: new_delay = server's Retry-After + 1s
      - On success: new_delay = max(MIN_DELAY, current - DELAY_STEP)

    429 downloads are retried in adaptive rounds at the end.
    Images saved locally to <scraper_tag>_excels/<scraper_tag>/ (deleted after upload).
    Returns modified new_df.
    """
    log       = logger or _log
    img_log   = _setup_image_logger(scraper_tag)
    local_dir = _local_images_dir(scraper_tag)
    delay     = TOTAL_DELAY

    img_log.info('='*60)
    img_log.info(f'START process_new_images | scraper_tag={scraper_tag} | rows={len(new_df)}')
    img_log.info(f'Local image folder: {local_dir}')

    _ensure_s3_folder(scraper_tag, img_log)

    uploaded       = 0
    skipped        = 0
    copied         = 0
    failed         = 0
    retry_queue    = []            # [(idx, url, record_id), ...] — 429 only
    # Changed By Hassam nasir — manual-upload mode: collect (URL, ID) for the images Excel
    image_url_rows    = []         # [{'URL': <wikidata url>, 'ID': <record id>}, ...]
    queued_for_manual = 0
    # Changed By Hassam Nasir
    # recovery_floor = TOTAL_DELAY   # old: bumped to 8.5s after any 429, blocking recovery
    recovery_floor = MIN_DELAY       # delay reduces by 0.5 down to MIN_DELAY after each success
    clean_streak   = 0

    for idx, row in new_df.iterrows():
        img_tag   = str(row.get('Image Tag', '')).strip()
        record_id = str(row.get('ID',        '')).strip()

        # ── Case 1: no image ─────────────────────────────────────────
        if not img_tag or img_tag.lower() in ('nan', 'none', 'null'):
            continue

        # ── Case 2: old ID in Image Tag → S3 copy ────────────────────
        if not img_tag.startswith('http') and img_tag != record_id:
            old_key = _s3_key(scraper_tag, img_tag)
            new_key = _s3_key(scraper_tag, record_id)
            try:
                if _s3_exists(new_key):
                    img_log.info(f'COPY SKIP | new key already on S3 | {new_key}')
                elif _s3_exists(old_key):
                    s3_client.copy_object(
                        Bucket=S3_BUCKET,
                        CopySource={'Bucket': S3_BUCKET, 'Key': old_key},
                        Key=new_key,
                    )
                    img_log.info(f'COPY OK  | {old_key} → {new_key}')
                    log.info(f'[IMAGE] Copied {old_key} → {new_key}')
                    copied += 1
                else:
                    img_log.warning(f'COPY FAIL | old key not on S3 | {old_key}')
            except Exception as exc:
                img_log.error(f'COPY ERROR | {old_key} → {new_key} | {exc}')
            new_df.at[idx, 'Image Tag'] = record_id
            continue

        # ── Case 3: Image Tag already correct ID ─────────────────────
        if not img_tag.startswith('http'):
            continue

        # ── Case 4: URL → record for MANUAL upload (no download) ─────
        # Changed By Hassam nasir
        # Wikidata/Wikimedia soft-throttling (429) made bulk image downloads far too slow
        # (and will be worse for big countries). So we NO LONGER download/upload here.
        # Instead: set img_tag = record ID in the DB (as if uploaded), and collect the
        # (URL, ID) pair into an Excel that is emailed for MANUAL S3 upload later.
        image_url_rows.append({'URL': img_tag, 'ID': record_id})
        new_df.at[idx, 'Image Tag'] = record_id
        queued_for_manual += 1
        img_log.info(f'QUEUED FOR MANUAL UPLOAD | {record_id} | {img_tag}')
        continue

        # ── OLD download/upload + adaptive-delay + 429-retry logic (disabled) ──
        # Changed By Hassam nasir — kept for reference, no longer executed.
        # key = _s3_key(scraper_tag, record_id)
        # if _s3_exists(key):
        #     img_log.info(f'SKIP | already on S3 | {key}')
        #     new_df.at[idx, 'Image Tag'] = record_id
        #     skipped += 1
        #     continue
        #
        # try:
        #     max_retry_after = _do_download_upload(img_tag, record_id, scraper_tag,
        #                                            local_dir, delay, img_log, log)
        #     new_df.at[idx, 'Image Tag'] = record_id
        #     uploaded += 1
        #
        #     if max_retry_after > 0:
        #         delay = _delay_after_429(delay, max_retry_after)
        #         clean_streak = 0
        #         img_log.info(f'DELAY SET | {delay:.1f}s (429 during download, Retry-After={max_retry_after}s)')
        #     else:
        #         clean_streak += 1
        #         if clean_streak >= 3 and delay > recovery_floor:
        #             delay = max(delay - DELAY_STEP, recovery_floor)
        #             img_log.info(f'DELAY REDUCED | {delay:.1f}s after {clean_streak} clean downloads')
        #
        # except TooManyRequestsError as e:
        #     delay = _delay_after_429(delay, e.retry_after)
        #     clean_streak = 0
        #     img_log.warning(f'429 | {record_id} | all retries exhausted → delay={delay:.1f}s | queued for retry')
        #     log.warning(f'[IMAGE] 429 for {record_id}, delay set to {delay:.1f}s')
        #     retry_queue.append((idx, img_tag, record_id))
        #
        # except Exception as exc:
        #     img_log.error(f'FAILED | {record_id} | {img_tag} | {exc}')
        #     log.warning(f'[IMAGE] Failed for {record_id}: {exc}')
        #     delay = min(delay + 2.0, MAX_DELAY)
        #     clean_streak = 0
        #     failed += 1

    # ── Retry pass (429-only) ─────────────────────────────────────────
    # Changed By Hassam nasir — in manual-upload mode no downloads happen, so retry_queue
    # is always empty and this block never runs (kept for reference / future re-enable).
    if retry_queue:
        img_log.info(
            f'RETRY START | {len(retry_queue)} image(s) to retry | '
            f'max_rounds={MAX_429_RETRY_ROUNDS}'
        )
        # Changed By Hassam Nasir
        # delay = max(delay, RECOVERY_FLOOR_429)   # old: forced retry pass to start at 8.5s
        delay = min(delay, MAX_DELAY)              # carry current delay, capped at 10s
        clean_streak = 0
        retry_round = 0

        while retry_queue and retry_round < MAX_429_RETRY_ROUNDS:
            retry_round += 1
            current_retry_queue = retry_queue
            retry_queue = []
            img_log.info(
                f'RETRY ROUND {retry_round}/{MAX_429_RETRY_ROUNDS} | '
                f'images={len(current_retry_queue)} | delay={delay:.1f}s'
            )

            for idx, url, record_id in current_retry_queue:
                key = _s3_key(scraper_tag, record_id)
                if _s3_exists(key):
                    img_log.info(f'RETRY SKIP | already on S3 | {key}')
                    new_df.at[idx, 'Image Tag'] = record_id
                    skipped += 1
                    continue
                try:
                    max_retry_after = _do_download_upload(url, record_id, scraper_tag,
                                                           local_dir, delay, img_log, log)
                    new_df.at[idx, 'Image Tag'] = record_id
                    uploaded += 1
                    img_log.info(f'RETRY OK | {record_id}')

                    if max_retry_after > 0:
                        delay = _delay_after_429(delay, max_retry_after)
                        # Changed By Hassam Nasir
                        # recovery_floor = max(recovery_floor, RECOVERY_FLOOR_429)  # old: locked floor at 8.5s
                        clean_streak = 0
                    else:
                        clean_streak += 1
                        if clean_streak >= 3 and delay > recovery_floor:
                            delay = max(delay - DELAY_STEP, recovery_floor)

                except TooManyRequestsError as e:
                    delay = _delay_after_429(delay, e.retry_after)
                    # Changed By Hassam Nasir
                    # recovery_floor = max(recovery_floor, RECOVERY_FLOOR_429)  # old: locked floor at 8.5s
                    clean_streak = 0
                    retry_queue.append((idx, url, record_id))
                    img_log.warning(
                        f'RETRY 429 | {record_id} | delay={delay:.1f}s | '
                        f'requeued for same run'
                    )

                except Exception as exc:
                    img_log.error(f'RETRY FAILED | {record_id} | {exc}')
                    delay = min(delay + 2.0, MAX_DELAY)
                    clean_streak = 0
                    failed += 1

        if retry_queue:
            failed += len(retry_queue)
            img_log.warning(
                f'RETRY GIVEUP | {len(retry_queue)} image(s) still rate-limited '
                f'after {MAX_429_RETRY_ROUNDS} round(s); left as URL for DB pending retry'
            )

        img_log.info(f'RETRY END | rounds={retry_round}')

    # Changed By Hassam nasir — write the URL→ID images Excel for manual S3 upload
    if image_url_rows:
        _write_image_url_excel(scraper_tag, image_url_rows, img_log)
    else:
        img_log.info('IMAGE URL EXCEL | no new image URLs to write')

    img_log.info(
        f'DONE process_new_images | '
        f'queued_for_manual={queued_for_manual} copied={copied} skipped={skipped} '
        f'uploaded={uploaded} failed={failed}'
    )
    img_log.info('='*60)
    return new_df


def process_pending_db_images(scraper_tag: str, cursor, cnx, logger=None) -> None:
    """
    Called from orchestrator AFTER insertion_code().

    Queries the DB for ANY active record of this scraper_tag where img_tag
    still contains a URL (i.e. image download failed in process_new_images,
    or failed in a previous weekly run and was never retried).

    For each such record:
      - Downloads, resizes, uploads to S3
      - On success: UPDATE main SET img_tag = <record_id> WHERE customer_id = <record_id>

    This retries failed images inside the same pipeline run with adaptive delay.
    If the remote server keeps returning 429 after the configured retry rounds,
    the URL is left in img_tag so the next run can still detect it.
    """
    log     = logger or _log
    img_log = _setup_image_logger(scraper_tag)

    img_log.info('='*60)
    img_log.info(f'START process_pending_db_images | scraper_tag={scraper_tag}')

    try:
        cursor.execute(
            "SELECT customer_id, img_tag FROM main "
            "WHERE scraper_tag = %s AND img_tag LIKE 'http%%' AND status = 1",
            (scraper_tag,)
        )
        rows = cursor.fetchall()
    except Exception as exc:
        img_log.error(f'DB query failed: {exc}')
        log.error('[IMAGE] process_pending_db_images DB query failed: %s', exc)
        img_log.info('='*60)
        return

    if not rows:
        img_log.info('No pending image URLs found in DB — nothing to retry')
        img_log.info('='*60)
        return

    img_log.info(f'Found {len(rows)} record(s) with pending image URLs in DB')

    local_dir      = _local_images_dir(scraper_tag)
    _ensure_s3_folder(scraper_tag, img_log)

    # Changed By Hassam Nasir
    # delay          = max(TOTAL_DELAY, PENDING_START_DELAY)   # old: forced start at 8.5s
    # recovery_floor = max(TOTAL_DELAY, RECOVERY_FLOOR_429)    # old: locked floor at 8.5s
    delay          = TOTAL_DELAY
    recovery_floor = MIN_DELAY        # delay reduces by 0.5 down to MIN_DELAY after each success
    clean_streak   = 0
    updated        = 0
    failed         = 0
    pending_queue = [
        (str(row['customer_id']).strip(), str(row['img_tag']).strip())
        for row in rows
    ]
    pending_round = 0

    while pending_queue and pending_round < MAX_429_RETRY_ROUNDS:
        pending_round += 1
        current_pending_queue = pending_queue
        pending_queue = []
        img_log.info(
            f'PENDING ROUND {pending_round}/{MAX_429_RETRY_ROUNDS} | '
            f'images={len(current_pending_queue)} | delay={delay:.1f}s'
        )

        for record_id, img_url in current_pending_queue:
            # If already on S3 (uploaded by a parallel process), just fix the DB column
            key = _s3_key(scraper_tag, record_id)
            if _s3_exists(key):
                img_log.info(f'PENDING SKIP | already on S3 | updating DB | {key}')
                try:
                    cursor.execute(
                        "UPDATE main SET img_tag = %s WHERE customer_id = %s",
                        (record_id, record_id)
                    )
                    cnx.commit()
                    updated += 1
                except Exception as exc:
                    img_log.error(f'PENDING DB UPDATE failed for {record_id}: {exc}')
                continue

            img_log.info(f'PENDING | {record_id} | {img_url}')
            try:
                max_retry_after = _do_download_upload(img_url, record_id, scraper_tag,
                                                       local_dir, delay, img_log, log)
                cursor.execute(
                    "UPDATE main SET img_tag = %s WHERE customer_id = %s",
                    (record_id, record_id)
                )
                cnx.commit()
                updated += 1
                img_log.info(f'PENDING OK | {record_id} | DB updated')
                log.info(f'[IMAGE] Pending image resolved: {record_id}')

                if max_retry_after > 0:
                    delay = _delay_after_429(delay, max_retry_after)
                    # Changed By Hassam Nasir
                    # recovery_floor = max(recovery_floor, RECOVERY_FLOOR_429)  # old: locked floor at 8.5s
                    clean_streak = 0
                    img_log.info(f'DELAY SET | {delay:.1f}s')
                else:
                    clean_streak += 1
                    if clean_streak >= 3 and delay > recovery_floor:
                        delay = max(delay - DELAY_STEP, recovery_floor)
                        img_log.info(f'DELAY REDUCED | {delay:.1f}s after {clean_streak} clean downloads')

            except TooManyRequestsError as e:
                delay = _delay_after_429(delay, e.retry_after)
                # Changed By Hassam Nasir
                # recovery_floor = max(recovery_floor, RECOVERY_FLOOR_429)  # old: locked floor at 8.5s
                clean_streak = 0
                pending_queue.append((record_id, img_url))
                img_log.warning(
                    f'PENDING 429 | {record_id} | delay={delay:.1f}s | '
                    f'requeued for same run'
                )
                log.warning(f'[IMAGE] Pending 429 for {record_id}, requeued')

            except Exception as exc:
                img_log.error(f'PENDING FAILED | {record_id} | {exc}')
                delay = min(delay + 2.0, MAX_DELAY)
                clean_streak = 0
                failed += 1

    if pending_queue:
        failed += len(pending_queue)
        img_log.warning(
            f'PENDING GIVEUP | {len(pending_queue)} image(s) still rate-limited '
            f'after {MAX_429_RETRY_ROUNDS} round(s); DB img_tag remains URL'
        )

    img_log.info(
        f'DONE process_pending_db_images | updated={updated} failed={failed} '
        f'rounds={pending_round} final_delay={delay:.1f}s'
    )
    img_log.info('='*60)


def delete_inactive_images(df2, scraper_tag: str, logger=None) -> None:
    """
    Called from delta_records_excel BEFORE df2.to_excel().

    For every status=0 row that has an Image Tag value:
      - Delete <scraper_tag>/<ID>.jpg from S3 if it exists.
    """
    log     = logger or _log
    img_log = _setup_image_logger(scraper_tag)

    img_log.info('='*60)
    img_log.info(f'START delete_inactive_images | scraper_tag={scraper_tag}')

    deleted = 0
    missing = 0

    for _, row in df2.iterrows():
        try:
            status    = int(row.get('Status', 1))
            record_id = str(row.get('ID', '')).strip()
            img_tag   = str(row.get('Image Tag', '')).strip()
        except (TypeError, ValueError):
            continue

        if status != 0:
            continue
        if not record_id or img_tag.lower() in ('', 'nan', 'none', 'null'):
            continue

        key = _s3_key(scraper_tag, record_id)
        if _s3_exists(key):
            img_log.info(f'DELETE   | status=0 | {key}')
            _delete_from_s3(key, log)
            img_log.info(f'DELETE OK | {key}')
            deleted += 1
        else:
            img_log.info(f'DELETE SKIP | no image on S3 for status=0 | {key}')
            log.info(f'[IMAGE] Status=0 but no image found on S3: {key}')
            missing += 1

    img_log.info(f'DONE delete_inactive_images | deleted={deleted} not_found={missing}')
    img_log.info('='*60)