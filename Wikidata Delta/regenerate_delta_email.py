"""
Regenerate the delta report Excel + send the delta email for a scraper_tag
WITHOUT re-running the full delta pipeline.

Use when insertion already completed (records are in `main` with today's updated_on)
but the run died before the delta-file/email step (e.g. terminal closed).

Usage (Wikidata Delta folder se, isi din jab records insert huए):
    python regenerate_delta_email.py kg_nl_gen
    python regenerate_delta_email.py np_gen

NOTE:
 - delta_records_excel `updated_on = AAJ ki date` query karta hai -> isi din chalao
   jis din records insert huए (kal chalaoge to woh records nahi milenge).
 - Yeh email POORI team (email_to + email_cc) ko jayega.
 - delta_records_excel me S3 image-deletion agar ON hai to status=0 records ki
   images S3 se delete hongi (prod behaviour).
"""
import os
import sys

from dotenv import load_dotenv

from mysql_connection_dictionary import create_mysql_connection_dictionary
from delta_records_excel import delta_excel_df_creator
from sending_delta_excel_email import send_emails

load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

HOST = os.getenv("host")
USER = os.getenv("user")
PWD = os.getenv("password")
DB = os.getenv("database")
PORT = os.getenv("db_port")

EMAIL_FROM = os.getenv("email_from")
EMAIL_NAME = os.getenv("email_name")
EMAIL_TO = os.getenv("email_to").split(",")
EMAIL_CC = os.getenv("email_cc").split(",")
SMTP_SERVER = os.getenv("smtp_server")
SMTP_PORT = os.getenv("smtp_port")
SMTP_USER = os.getenv("smtp_user")
SMTP_PASSWORD = os.getenv("smtp_pswd")
EMAIL_SUBJECT = os.getenv("email_subject")

folder_names = os.getenv("file_paths").split(",")
FILE_PATHS = [
    os.path.join(BASE_DIR, folder.strip()).replace("\\", "/") for folder in folder_names
]


def main():
    if len(sys.argv) < 2:
        print("Usage: python regenerate_delta_email.py <scraper_tag>   e.g. kg_nl_gen")
        sys.exit(1)
    scraper_tag = sys.argv[1].strip()

    # 1) DB se delta report Excel regenerate (today's updated_on records)
    cnx_dict, cursor_dict = create_mysql_connection_dictionary(HOST, USER, PWD, DB, PORT)
    delta_excel_df_creator(scraper_tag, cursor_dict, cnx_dict)
    print(f"[OK] Delta file regenerated for {scraper_tag}")

    # 2) Delta report email (delta files attach) — POORI team ko jata hai
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
    print("[OK] Delta report email sent")


if __name__ == "__main__":
    main()
