""" 

Orchestrator — routes extraction output to the correct country 

cleaning script, then runs the full delta pipeline automatically. 

  

Called by cli.py after successful extraction. Can also be run manually: 

    python orchestrator.py oman 

    python orchestrator.py oman /path/to/specific/file.xlsx 

""" 
import importlib 
import inspect 
import logging 
import os 
import sys 
import time 
from pathlib import Path 
from datetime import datetime
from sending_delta_excel_email import send_emails
from sending_delta_log_file import send_main_delta_logs
from dotenv import load_dotenv

load_dotenv()
HOST_NAME = os.getenv("host")
USER = os.getenv("user")
PASSWORD = os.getenv("password")
DATABASE = os.getenv("database")
DB_PORT = os.getenv("db_port")
SMTP_PORT = os.getenv("smtp_port")
SMTP_SERVER = os.getenv("smtp_server")
SMTP_USER = os.getenv("smtp_user")
SMTP_PASSWORD = os.getenv("smtp_pswd")
EMAIL_FROM = os.getenv("email_from")
EMAIL_NAME = os.getenv("email_name")
EMAIL_TO = os.getenv("email_to").split(",")
EMAIL_CC = os.getenv("email_cc").split(",")
EMAIL_SUBJECT = os.getenv("email_subject")
ERROR_LOG_EMAIL_SUBJECT = os.getenv("error_log_email_subject")
LOG_EMAIL_SUBJECT = os.getenv("log_email_subject")
DELTA_LOG_EMAIL_CC = os.getenv("delta_log_email_cc").split(",")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(BASE_DIR, "Logs")

# Get folder names from .env
folder_names = os.getenv("file_paths").split(",")
delta_file_path = os.getenv("delta_log_file_path")
# Join base directory with each folder name
FILE_PATHS = [
    os.path.join(BASE_DIR, folder.strip()).replace("\\", "/") for folder in folder_names
]

DELTA_LOG_FILE_PATH = LOGS_DIR


logging.basicConfig(level=logging.INFO, 

                    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s') 

logger = logging.getLogger('orchestrator')

# Add FileHandler to log to Logs folder

os.makedirs(LOGS_DIR, exist_ok=True)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
file_handler = logging.FileHandler(
    os.path.join(
        LOGS_DIR, f'Delta_main_file_{datetime.now().date().strftime("%Y-%m-%d")}.log'
    )
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler) 

  

  

# ───────────────────────────────────────────────────────────────── 

# COUNTRY REGISTRY 

# Format: 'key' : ('folder_name', 'scraper_tag', 'module', 'function') 

# Add one row per country. Multiple keys can point to the same entry. 

# ───────────────────────────────────────────────────────────────── 

COUNTRY_REGISTRY = { 

    'oman':           ('oman',     'om_gen',   'oman_pep_scrapper',  'oman_pep_scrapper'), 

    'om':             ('oman',     'om_gen',   'oman_pep_scrapper',  'oman_pep_scrapper'), 

    'qatar':          ('qatar',    'qa_gen',  'qatar_pep_scrapper',   'qatar_pep_scrapper'), 

    'qa':             ('qatar',    'qa_gen',  'qatar_pep_scrapper',   'qatar_pep_scrapper'), 

    'pakistan':       ('pakistan', 'pk_gen',   'pakistan_pep_scrapper', 'pakistan_pep_scrapper'), 

    'pk':             ('pakistan', 'pk_gen',   'pakistan_pep_scrapper', 'pakistan_pep_scrapper'), 

    'united kingdom': ('uk',       'uk_gen',   'uk_pep_scrapper',    'uk_pep_scrapper'), 

    'uk':             ('uk',       'uk_gen',   'uk_pep_scrapper',    'uk_pep_scrapper'), 
    
    'lithuania':      ('lithuania', 'lt_gen',  'lithuania_pep_scrapper','lithuania_pep_scrapper'), 
    
    'lt':             ('lithuania', 'lt_gen',  'lithuania_pep_scrapper', 'lithuania_pep_scrapper'), 

    'bahrain':        ('bahrain',   'bh_gen',   'bahrain_pep_scrapper',    'bahrain_pep_scrapper'), 

    'bh':             ('bahrain',   'bh_gen',   'bahrain_pep_scrapper',    'bahrain_pep_scrapper'), 

    'belgium':        ('belgium',   'be_gen',   'belgium_pep_scrapper',    'belgium_pep_scrapper'), 

    'be':             ('belgium',   'be_gen',   'belgium_pep_scrapper',    'belgium_pep_scrapper'), 

    'france':         ('france',    'fr_gen',   'france_pep_scrapper',    'france_pep_scrapper'), 

    'fr':             ('france',    'fr_gen',   'france_pep_scrapper',    'france_pep_scrapper'), 

    'greece':         ('greece',    'gr_gen',   'greece_pep_scrapper',    'greece_pep_scrapper'), 

    'gr':             ('greece',    'gr_gen',   'greece_pep_scrapper',    'greece_pep_scrapper'), 

    'india':          ('india',     'in_gen',   'indian_pep_scrapper',    'indian_pep_scrapper'), 

    'in':             ('india',     'in_gen',   'indian_pep_scrapper',    'indian_pep_scrapper'), 

    'ireland':        ('ireland',   'ie_gen',   'ireland_pep_scrapper',    'ireland_pep_scrapper'), 

    'ie':             ('ireland',   'ie_gen',   'ireland_pep_scrapper',    'ireland_pep_scrapper'), 

    'kazakhstan':     ('kazakhstan','kz_gen',   'kazakhstan_pep_scrapper',  'kazakhstan_pep_scrapper'), 

    'kz':             ('kazakhstan','kz_gen',   'kazakhstan_pep_scrapper',   'kazakhstan_pep_scrapper'), 

    'nepal':          ('nepal',      'np_gen',   'nepal_pep_scrapper',    'nepal_pep_scrapper'), 

    'np':             ('nepal',      'np_gen',   'nepal_pep_scrapper',    'nepal_pep_scrapper'), 

    'netherlands':     ('netherlands', 'kg_nl_gen',   'netherlands_pep_scrapper',  'netherlands_pep_scrapper'), 

    'nl':              ('netherlands', 'kg_nl_gen',   'netherlands_pep_scrapper', 'netherlands_pep_scrapper'), 

    'nigeria':        ('nigeria',    'ng_gen',   'nigeria_pep_scrapper',    'nigeria_pep_scrapper'), 

    'ng':             ('nigeria',    'ng_gen',   'nigeria_pep_scrapper',    'nigeria_pep_scrapper'), 

    'switzerland':    ('switzerland','ch_gen',   'switzerland_pep_scrapper',    'switzerland_pep_scrapper'), 

    'ch':             ('switzerland','ch_gen',   'switzerland_pep_scrapper',    'switzerland_pep_scrapper'), 

    'united arab emirates': ('uae',  'ae_gen',   'uae_pep_scrapper',    'uae_pep_scrapper'), 

    'ae': ('uae',       'ae_gen',   'uae_pep_scrapper',    'uae_pep_scrapper'), 

    'uzbekistan': ('uzbekistan',       'uz_gen',   'uzbekistan_pep_scrapper',    'uzbekistan_pep_scrapper'), 

    'uz': ('uzbekistan',       'uz_gen',   'uzbekistan_pep_scrapper',    'uzbekistan_pep_scrapper'), 


} 

def _check_sentinel(raw_file_path: Path) -> bool: 

    """Safety gate: refuse if sentinel (.inprogress) file is present.""" 

    struct_path = os.getenv('STRUCT_SCRAPING_PATH') 

    if struct_path: 

        sys.path.insert(0, struct_path) 

    try: 

        from structured_scraping.sentinel import is_safe_to_process 

        return is_safe_to_process(raw_file_path) 

    except ImportError: 

        # Fallback: manual sentinel check without importing sentinel.py 

        sentinel = Path(str(raw_file_path) + '.inprogress') 

        if sentinel.exists(): 

            logger.error('BLOCKED: sentinel found at %s', sentinel) 

            return False 

        return raw_file_path.exists() 

def _get_latest_safe_file(folder: Path) -> Path | None: 

    """Find newest file in folder that has no sentinel. Fallback only.""" 

    import glob 

    files = sorted(glob.glob(str(folder / '*.xlsx')), 

                   key=os.path.getmtime, reverse=True) 

    for f in files: 

        p = Path(f) 

        if not Path(str(p) + '.inprogress').exists(): 

            return p 

    return None 

def run_delta_for_country( 

    country: str, 

    raw_file_path: str | None = None, 

) -> bool: 

    """ 

    Main entry point. Called by cli.py after extraction, or manually. 

    Returns True on success, False on any failure. 

    """ 

    key = country.lower().strip().replace('_', ' ') 

    if key not in COUNTRY_REGISTRY: 

        logger.error('No config for country: %s — add it to COUNTRY_REGISTRY', country) 

        return False 

  

    folder_name, scraper_tag, module_name, function_name = COUNTRY_REGISTRY[key] 

  

    # ── Resolve raw file path ────────────────────────────────────── 

    if raw_file_path is None: 

        raw_base = os.getenv('DELTA_RAW_DATA_PATH') 

        if not raw_base: 

            logger.error('raw_file_path not given and DELTA_RAW_DATA_PATH not set') 

            return False 

        raw_file_path = _get_latest_safe_file(Path(raw_base) / folder_name) 

        if raw_file_path is None: 

            logger.error('No safe file found in raw_data/%s/', folder_name) 

            return False 

  

    raw_file_path = Path(raw_file_path) 

  

    # ── Safety gate ──────────────────────────────────────────────── 

    if not _check_sentinel(raw_file_path): 

        return False 

    logger.info('='*60) 
    logger.info('country=%s | tag=%s | file=%s', country, scraper_tag, raw_file_path.name) 
    logger.info('='*60) 

  

    # ── Step 1: Run cleaning script ──────────────────────────────── 

    try: 

        module = importlib.import_module(module_name) 

        cleaner = getattr(module, function_name) 

        sig = inspect.signature(cleaner) 

        if 'raw_file_path' in sig.parameters: 

            df = cleaner(raw_file_path=str(raw_file_path)) 

        else: 

            # Older scripts: set RAW_FILE_PATH on the module directly 

            if hasattr(module, 'RAW_FILE_PATH'): 

                module.RAW_FILE_PATH = str(raw_file_path) 

            df = cleaner() 

    except Exception as e: 

        logger.error('Cleaning failed for %s: %s', scraper_tag, e, exc_info=True) 

        return False 

  

    if df is None or df.empty: 
        logger.warning('Cleaning returned empty df for %s', scraper_tag) 
        return False 

  

    # ── Step 2: City extraction ──────────────────────────────────── 

    try: 
        from cities_extractor import cities_extractor 
        df = cities_extractor(df) 

    except Exception as e: 
        logger.error('cities_extractor failed: %s', e, exc_info=True) 
        return False 

  

    # ── Step 3: DB connection ────────────────────────────────────── 

    try: 

        from mysql_connection import create_mysql_connection 
        from mysql_connection_dictionary import create_mysql_connection_dictionary 
        HOST = os.getenv('host'); USER = os.getenv('user') 
        PWD  = os.getenv('password'); DB = os.getenv('database') 
        PORT = os.getenv('db_port') 
        cnx, cursor = create_mysql_connection(HOST, USER, PWD, DB, PORT) 

    except Exception as e: 

        logger.error('DB connection failed: %s', e, exc_info=True) 

        return False 

  

    # ── Step 4: Delta ────────────────────────────────────────────── 

    try: 

        from delta_script import delta_code 

        t = time.time() 

        new_df = delta_code(df, cursor, cnx, logger)

        logger.info('Delta: %d new records in %.1fs', len(new_df), time.time()-t) 

    except Exception as e: 

        logger.error('delta_code failed: %s', e, exc_info=True) 

        return False 

  

    if new_df.empty: 

        logger.info('No new records for %s — DB is up to date', scraper_tag) 

        return True 

  

    # ── Step 5: Insertion ────────────────────────────────────────── 

    try: 

        from new_df_cleaner import new_df_cleaner 

        from insertion_script import insertion_code 

        from delta_records_excel import delta_excel_df_creator 

        cleaned_df = new_df_cleaner(new_df, cursor, cnx) 

        insertion_code(cleaned_df, cursor, cnx, scraper_tag) 

        cnx_dict, cursor_dict = create_mysql_connection_dictionary(HOST, USER, PWD, DB, PORT) 

        delta_excel_df_creator(scraper_tag, cursor_dict, cnx_dict) 

        logger.info('Inserted %d records for %s', len(cleaned_df), scraper_tag) 

        send_emails(
        EMAIL_FROM,
        EMAIL_NAME,
        EMAIL_TO,
        EMAIL_CC,
        SMTP_SERVER,
        SMTP_PORT,
        SMTP_USER,
        SMTP_PASSWORD,
        EMAIL_SUBJECT,
        FILE_PATHS,
    )
        send_main_delta_logs(
        EMAIL_FROM,
        EMAIL_NAME,
        EMAIL_TO,
        DELTA_LOG_EMAIL_CC,
        SMTP_SERVER,
        SMTP_PORT,
        SMTP_USER,
        SMTP_PASSWORD,
        LOG_EMAIL_SUBJECT,
        ERROR_LOG_EMAIL_SUBJECT,
        LOGS_DIR,
    )

        return True 

    except Exception as e: 

        logger.error('Insertion failed for %s: %s', scraper_tag, e, exc_info=True) 

        return False 

  
    
  

# ── Manual entry point ──────────────────────────────────────────── 

if __name__ == '__main__': 

    if len(sys.argv) < 2: 

        print('Usage: python orchestrator.py <country> [raw_file_path]') 

        sys.exit(1) 

    success = run_delta_for_country( 

        country=sys.argv[1], 

        raw_file_path=sys.argv[2] if len(sys.argv) > 2 else None, 
        
        


    ) 


