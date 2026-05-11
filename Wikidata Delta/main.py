import schedule
import time
from datetime import datetime
import os

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

# Get folder names from .env
folder_names = os.getenv("file_paths").split(",")
delta_file_path = os.getenv("delta_log_file_path")
# Join base directory with each folder name
FILE_PATHS = [
    os.path.join(BASE_DIR, folder.strip()).replace("\\", "/") for folder in folder_names
]
DELTA_LOG_FILE_PATH = os.path.join(BASE_DIR, delta_file_path.strip()).replace("\\", "/")



import logging
from sending_delta_excel_email import send_emails
from sending_delta_log_file import send_main_delta_logs
from mysql_connection import create_mysql_connection
from mysql_connection_dictionary import create_mysql_connection_dictionary
from delta_records_excel import delta_excel_df_creator
from delta_script import delta_code
from new_df_cleaner import new_df_cleaner
from insertion_script import insertion_code
from cities_extractor import cities_extractor
from qatar_pep_scrapper import qatar_pep_scrapper
from oman_pep_scrapper import oman_pep_scrapper
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(BASE_DIR, "Logs")
INSERTION_LOGS_DIR = os.path.join(BASE_DIR, "Insertion Logs")


def master_function():
    
    logger = logging.getLogger("<country> Pep General Delta")
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("\n%(asctime)s-%(levelname)s-%(name)s-%(message)s")
    file_handler = logging.FileHandler(
        os.path.join(
            LOGS_DIR, f'Delta_main_file{datetime.now().date().strftime("%Y-%m-%d")}.log'
        )
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    # print("Start of master function")
    print(
        f'Start of master function at {datetime.now().strftime("%I:%M:%S%p").lower()} on {datetime.today().strftime("%Y-%m-%d")}'
    )
    delta_process_start_time = time.time()
    logger.info(
        f"Delta of {datetime.today().strftime('%Y-%m-%d')} beginning at {datetime.now().strftime('%I:%M:%S %p')}."
    )

    #Pakistan pep General Delta Function
    # logger.info(f"============================================================================================")
    # logger.info(f"Pakistan Pep General (Scraper Tag: pk_gen")
    # log_file = "pk_gen"
    # try:
    #     df =  pakistan_pep_scrapper()
    #     # log_file = df['Scraper Tag'].iloc[0]
    #     if not df.empty:
    #         df = cities_extractor(df)
    #         cnx, cursor = create_mysql_connection(
    #             HOST_NAME, USER, PASSWORD, DATABASE, DB_PORT
    #         )
    #         delta_start_time = time.time()
    #         new_df = delta_code(df, cursor, cnx)
    #         delta_end_time = time.time()
    #         delta_execution_time = delta_end_time - delta_start_time
    #         logger.info(
    #             f"Delta completed for file {log_file}. {len(new_df)} delta records. Time taken: {delta_execution_time:.2f} seconds."
    #         )
    #         if not new_df.empty:
    #             cleaned_df = new_df_cleaner(new_df, cursor, cnx)
    #             insertion_code(cleaned_df, cursor, cnx, log_file)
    #             cnx_dict, cursor_dict = create_mysql_connection_dictionary(
    #                 HOST_NAME, USER, PASSWORD, DATABASE, DB_PORT
    #             )
    #             delta_excel_df_creator(log_file, cursor_dict, cnx_dict)
    #         else:
    #             logger.info(f"No Delta Today in {log_file}")
    #     else:
    #         logger.info(f"Error in Scraping {log_file}")
    # except Exception as e:
    #     logger.error(f"{log_file} scraper failed to run today: {e}")
    # logger.info(f"============================================================================================")
  

#united kingdom Pep General Delta Function
    # logger.info(f"============================================================================================")
    # logger.info(f"United Kingdom Pep General (Scraper Tag: uk_gen")
    # log_file = "uk_gen"
    # try:
    #     df =  uk_pep_scrapper()
    #     # log_file = df['Scraper Tag'].iloc[0]
    #     if not df.empty:
    #         df = cities_extractor(df)
    #         cnx, cursor = create_mysql_connection(
    #             HOST_NAME, USER, PASSWORD, DATABASE, DB_PORT
    #         )
    #         delta_start_time = time.time()
    #         new_df = delta_code(df, cursor, cnx)
    #         delta_end_time = time.time()
    #         delta_execution_time = delta_end_time - delta_start_time
    #         logger.info(
    #             f"Delta completed for file {log_file}. {len(new_df)} delta records. Time taken: {delta_execution_time:.2f} seconds."
    #         )
    #         if not new_df.empty:
    #             cleaned_df = new_df_cleaner(new_df, cursor, cnx)
    #             insertion_code(cleaned_df, cursor, cnx, log_file)
    #             cnx_dict, cursor_dict = create_mysql_connection_dictionary(
    #                 HOST_NAME, USER, PASSWORD, DATABASE, DB_PORT
    #             )
    #             delta_excel_df_creator(log_file, cursor_dict, cnx_dict)
    #         else:
    #             logger.info(f"No Delta Today in {log_file}")
    #     else:
    #         logger.info(f"Error in Scraping {log_file}")
    # except Exception as e:
    #     logger.error(f"{log_file} scraper failed to run today: {e}")
    # logger.info(f"============================================================================================")
  


#lithuania Pep General Delta Function
   # logger.info(f"============================================================================================")
    # logger.info(f"lithuania Pep General (Scraper Tag: lt_gen")
    # log_file = "lt_gen"
    # try:
    #     df =  lithuania_pep_scrapper()
    #     # log_file = df['Scraper Tag'].iloc[0]
    #     if not df.empty:
    #         df = cities_extractor(df)
    #         cnx, cursor = create_mysql_connection(
    #             HOST_NAME, USER, PASSWORD, DATABASE, DB_PORT
    #         )
    #         delta_start_time = time.time()
    #         new_df = delta_code(df, cursor, cnx)
    #         delta_end_time = time.time()
    #         delta_execution_time = delta_end_time - delta_start_time
    #         logger.info(
    #             f"Delta completed for file {log_file}. {len(new_df)} delta records. Time taken: {delta_execution_time:.2f} seconds."
    #         )
    #         if not new_df.empty:
    #             cleaned_df = new_df_cleaner(new_df, cursor, cnx)
    #             insertion_code(cleaned_df, cursor, cnx, log_file)
    #             cnx_dict, cursor_dict = create_mysql_connection_dictionary(
    #                 HOST_NAME, USER, PASSWORD, DATABASE, DB_PORT
    #             )
    #             delta_excel_df_creator(log_file, cursor_dict, cnx_dict)
    #         else:
    #             logger.info(f"No Delta Today in {log_file}")
    #     else:
    #         logger.info(f"Error in Scraping {log_file}")
    # except Exception as e:
    #     logger.error(f"{log_file} scraper failed to run today: {e}")
    # logger.info(f"============================================================================================")
  

#Oman PEP Scrapper Delta Function---
    logger.info(f"============================================================================================")
    logger.info(f"Oman PEP General  (Scraper Tag: om_gen")
    log_file = "om_gen"
    try:
        df =  oman_pep_scrapper()
        # log_file = df['Scraper Tag'].iloc[0]
        if not df.empty:
            df = cities_extractor(df)
            cnx, cursor = create_mysql_connection(
                HOST_NAME, USER, PASSWORD, DATABASE, DB_PORT
            )
            delta_start_time = time.time()
            new_df = delta_code(df, cursor, cnx)
            delta_end_time = time.time()
            delta_execution_time = delta_end_time - delta_start_time
            logger.info(
                f"Delta completed for file {log_file}. {len(new_df)} delta records. Time taken: {delta_execution_time:.2f} seconds."
            )
            if not new_df.empty:
                cleaned_df = new_df_cleaner(new_df, cursor, cnx)
                insertion_code(cleaned_df, cursor, cnx, log_file)
                cnx_dict, cursor_dict = create_mysql_connection_dictionary(
                    HOST_NAME, USER, PASSWORD, DATABASE, DB_PORT
                )
                delta_excel_df_creator(log_file, cursor_dict, cnx_dict)
            else:
                logger.info(f"No Delta Today in {log_file}")
        else:
            logger.info(f"Error in Scraping {log_file}")
    except Exception as e:
        logger.error(f"{log_file} scraper failed to run today: {e}",exc_info=True)
    logger.info(f"============================================================================================")


  #Qatar General List Delta Function---
    logger.info(f"============================================================================================")
    logger.info(f"Qatar General List (Scraper Tag: qa_gen")
    log_file = "qa_gen"
    try:
        df =  qatar_pep_scrapper()
        # log_file = df['Scraper Tag'].iloc[0]
        if not df.empty:
            df = cities_extractor(df)
            cnx, cursor = create_mysql_connection(
                HOST_NAME, USER, PASSWORD, DATABASE, DB_PORT
            )
            delta_start_time = time.time()
            new_df = delta_code(df, cursor, cnx)
            delta_end_time = time.time()
            delta_execution_time = delta_end_time - delta_start_time
            logger.info(
                f"Delta completed for file {log_file}. {len(new_df)} delta records. Time taken: {delta_execution_time:.2f} seconds."
            )
            if not new_df.empty:
                cleaned_df = new_df_cleaner(new_df, cursor, cnx)
                insertion_code(cleaned_df, cursor, cnx, log_file)
                cnx_dict, cursor_dict = create_mysql_connection_dictionary(
                    HOST_NAME, USER, PASSWORD, DATABASE, DB_PORT
                )
                delta_excel_df_creator(log_file, cursor_dict, cnx_dict)
            else:
                logger.info(f"No Delta Today in {log_file}")
        else:
            logger.info(f"Error in Scraping {log_file}")
    except Exception as e:
        logger.error(f"{log_file} scraper failed to run today: {e}")
    logger.info(f"============================================================================================")

# #Most Wanted Netherland Delta Function---
#     logger.info(f"============================================================================================")
#     logger.info(f"Most Wanted Netherland  (Scraper Tag: nl_np_np")
#     log_file = "nl_np_np"
#     try:
#         df =  most_wanted_list_politie_nl_scrapper()
#         # log_file = df['Scraper Tag'].iloc[0]
#         if not df.empty:
#             df = cities_extractor(df)
#             cnx, cursor = create_mysql_connection(
#                 HOST_NAME, USER, PASSWORD, DATABASE, DB_PORT
#             )
#             delta_start_time = time.time()
#             new_df = delta_code(df, cursor, cnx)
#             delta_end_time = time.time()
#             delta_execution_time = delta_end_time - delta_start_time
#             logger.info(
#                 f"Delta completed for file {log_file}. {len(new_df)} delta records. Time taken: {delta_execution_time:.2f} seconds."
#             )
#             if not new_df.empty:
#                 cleaned_df = new_df_cleaner(new_df, cursor, cnx)
#                 insertion_code(cleaned_df, cursor, cnx, log_file)
#                 cnx_dict, cursor_dict = create_mysql_connection_dictionary(
#                     HOST_NAME, USER, PASSWORD, DATABASE, DB_PORT
#                 )
#                 delta_excel_df_creator(log_file, cursor_dict, cnx_dict)
#             else:
#                 logger.info(f"No Delta Today in {log_file}")
#         else:
#             logger.info(f"Error in Scraping {log_file}")
#     except Exception as e:
#         logger.error(f"{log_file} scraper failed to run today: {e}",exc_info=True)
#     logger.info(f"============================================================================================")


#Nacta Qatar Delta Function---
    # logger.info(f"============================================================================================")
    # logger.info(f"Nacta Qatar Delta Function (Scraper Tag: qa_nctc")
    # log_file = "qa_nctc"
    # try:
    #     df =  nacta_qatar_scraper()
    #     # log_file = df['Scraper Tag'].iloc[0]
    #     if not df.empty:
    #         df = cities_extractor(df)
    #         cnx, cursor = create_mysql_connection(
    #             HOST_NAME, USER, PASSWORD, DATABASE, DB_PORT
    #         )
    #         delta_start_time = time.time()
    #         new_df = delta_code(df, cursor, cnx)
    #         delta_end_time = time.time()
    #         delta_execution_time = delta_end_time - delta_start_time
    #         logger.info(
    #             f"Delta completed for file {log_file}. {len(new_df)} delta records. Time taken: {delta_execution_time:.2f} seconds."
    #         )
    #         if not new_df.empty:
    #             cleaned_df = new_df_cleaner(new_df, cursor, cnx)
    #             insertion_code(cleaned_df, cursor, cnx, log_file)
    #             cnx_dict, cursor_dict = create_mysql_connection_dictionary(
    #                 HOST_NAME, USER, PASSWORD, DATABASE, DB_PORT
    #             )
    #             delta_excel_df_creator(log_file, cursor_dict, cnx_dict)
    #         else:
    #             logger.info(f"No Delta Today in {log_file}")
    #     else:
    #         logger.info(f"Error in Scraping {log_file}")
    # except Exception as e:
    #     logger.error(f"{log_file} scraper failed to run today: {e}",exc_info=True)
    # logger.info(f"============================================================================================")


    delta_process_end_time = time.time()
    delta_process_execution_time = delta_process_end_time - delta_process_start_time
    logger.info(
        f"Delta of {datetime.today().strftime('%Y-%m-%d')} ending at {datetime.now().strftime('%I:%M:%S %p')}. Total duration: {delta_process_execution_time:.2f} seconds."
    )

    print(
        f'End of master function at {datetime.now().strftime("%I:%M:%S%p").lower()} on {datetime.today().strftime("%Y-%m-%d")}'
    )
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
        DELTA_LOG_FILE_PATH,
    )
   

if __name__ == "__main__":

    master_function()