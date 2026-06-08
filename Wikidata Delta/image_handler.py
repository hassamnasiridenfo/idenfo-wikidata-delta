import io
import logging
import os
import time
import boto3
import requests
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

S3_BUCKET = os.getenv('aws_s3_bucket_name', 'namescreening-images')
s3_client = boto3.client(
    's3',
    region_name           = os.getenv('region', 'ap-southeast-1'),
    aws_access_key_id     = os.getenv('aws_access_key_id'),
    aws_secret_access_key = os.getenv('aws_secret_access_key'),
)

TARGET_PX    = 500   # resize longest side to this many pixels
TOTAL_DELAY  = 3.0   # starting delay between requests (seconds)
MIN_DELAY    = 0.5   # floor — never go below this
DELAY_STEP   = 0.5   # reduce delay by this much after each success

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


# ── Download + resize ───────────────────────────────────────────────────────────

def _download_and_resize(url: str, save_path: str, delay: float) -> None:
    time.sleep(delay)
    resp = requests.get(
        url,
        timeout=30,
        headers={'User-Agent': 'Mozilla/5.0 (compatible; WikidataDelta/1.0)'},
    )

    if resp.status_code == 429:
        retry_after = float(resp.headers.get('Retry-After', 10))
        raise TooManyRequestsError(retry_after)

    resp.raise_for_status()

    img = Image.open(io.BytesIO(resp.content))
    img.thumbnail((TARGET_PX, TARGET_PX), Image.LANCZOS)

    # JPEG does not support alpha — convert if needed
    if img.mode in ('RGBA', 'P', 'LA'):
        img = img.convert('RGB')

    img.save(save_path, 'JPEG')  # default quality (75)


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
    _download_and_resize(url, local_path, delay)
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

    # Success → reduce delay by DELAY_STEP (floor = MIN_DELAY)
    return max(MIN_DELAY, delay - DELAY_STEP)


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

    Failed downloads are retried once at the end.
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

    uploaded    = 0
    skipped     = 0
    copied      = 0
    failed      = 0
    retry_queue = []   # [(idx, url, record_id), ...]

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

        # ── Case 4: URL → download → upload ──────────────────────────
        key = _s3_key(scraper_tag, record_id)
        if _s3_exists(key):
            img_log.info(f'SKIP | already on S3 | {key}')
            new_df.at[idx, 'Image Tag'] = record_id
            skipped += 1
            continue

        try:
            delay = _do_download_upload(img_tag, record_id, scraper_tag,
                                        local_dir, delay, img_log, log)
            new_df.at[idx, 'Image Tag'] = record_id
            uploaded += 1

        except TooManyRequestsError as e:
            # Server told us to wait — increase delay, queue for retry
            new_delay = e.retry_after + 1
            img_log.warning(
                f'429 | {record_id} | server Retry-After={e.retry_after}s '
                f'→ delay {delay:.1f}s → {new_delay:.1f}s | queued for retry'
            )
            log.warning(f'[IMAGE] 429 for {record_id}, delay raised to {new_delay:.1f}s')
            delay = new_delay
            retry_queue.append((idx, img_tag, record_id))

        except Exception as exc:
            img_log.error(f'FAILED | {record_id} | {img_tag} | {exc}')
            log.warning(f'[IMAGE] Failed for {record_id}: {exc}')
            retry_queue.append((idx, img_tag, record_id))

    # ── Retry pass ────────────────────────────────────────────────────
    if retry_queue:
        img_log.info(f'RETRY START | {len(retry_queue)} image(s) to retry')
        delay = max(delay, TOTAL_DELAY)   # reset to safe delay before retrying

        for idx, url, record_id in retry_queue:
            key = _s3_key(scraper_tag, record_id)
            if _s3_exists(key):
                img_log.info(f'RETRY SKIP | already on S3 | {key}')
                new_df.at[idx, 'Image Tag'] = record_id
                skipped += 1
                continue
            try:
                delay = _do_download_upload(url, record_id, scraper_tag,
                                            local_dir, delay, img_log, log)
                new_df.at[idx, 'Image Tag'] = record_id
                uploaded += 1
                img_log.info(f'RETRY OK | {record_id}')

            except TooManyRequestsError as e:
                new_delay = e.retry_after + 1
                img_log.warning(f'RETRY 429 | {record_id} | delay → {new_delay:.1f}s')
                delay = new_delay
                failed += 1

            except Exception as exc:
                img_log.error(f'RETRY FAILED | {record_id} | {exc}')
                failed += 1

        img_log.info(f'RETRY END | retried={len(retry_queue)}')

    img_log.info(
        f'DONE process_new_images | '
        f'uploaded={uploaded} copied={copied} skipped={skipped} '
        f'failed={failed} final_delay={delay:.1f}s'
    )
    img_log.info('='*60)
    return new_df


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
