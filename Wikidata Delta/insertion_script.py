import itertools
import logging
import os
import time

import mysql.connector

# InnoDB throws these when a transaction is chosen as the deadlock victim
# (1213) or waits too long for a lock (1205). A deadlock rolls back the WHOLE
# transaction, so the whole record must be retried — not a single statement.
DEADLOCK_ERRNOS = (1213, 1205)
MAX_DEADLOCK_RETRIES = 3


def _insert_single_record(row, cursor, logger):
    """
    Insert one delta record (main + all child tables) within the caller's
    transaction. Returns the new main_id.

    Every table block still logs WHICH table failed, but then RE-RAISES so the
    caller can decide retry (on deadlock) vs skip (on any other error). No
    rollback/commit happens here — that is the caller's job.
    """
    # main
    try:
        query_main = "INSERT INTO main (name, father_name, gender, `desc`, pob, deceased_dissolved_status, deceased_dissolved_date, reg_date, head_bounty, extra_info, category, source_list, list_category, list_type, updated_on, added_on, status, img_tag, scraper_tag, customer_id, date_exclusion, date_inclusion, is_delta_list) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        values_main = (row['Name'], row['Father Name'], row['Gender'], row['Description'], row['Place of Birth'], row['Deceased Dissolved Status'], row['Deceased Dissolved Date'], row['Registration Date'], row['Head Bounty'], row['Extra Information'], row['Category'], row['Source List'], row['List Category'], row['List Type'], row['Updated On'], row['Added On'], row['Status'], row['Image Tag'], row['Scraper Tag'], row['ID'], row['Date of Exclusion'], row['Date of Inclusion'], 1)
        cursor.execute(query_main, values_main)
        main_id = cursor.lastrowid
    except Exception as err:
        logger.error(f'Error inserting data into / main table: {err}')
        raise

    # alias
    try:
        aliases = row['Alias']
        alias_types = row['Alias Type']
        if isinstance(aliases, list) and isinstance(alias_types, list):
            for alias, alias_type in zip(aliases, alias_types):
                if alias != None or alias_type != None:
                    query_alias = "INSERT INTO alias (alias_type, alias, main_id) VALUES (%s, %s, %s)"
                    values_alias = (alias_type, alias, main_id)
                    cursor.execute(query_alias, values_alias)
        else:
            logger.info(f'{main_id} does not contain aliases as list')
    except Exception as err:
        logger.error(f'Error inserting data into {main_id}/ alias table: {err}')
        raise

    # identity
    try:
        idts = row['ID Type']
        idns = row['ID Number']
        if isinstance(idts, list) and isinstance(idns, list):
            for idt, idn in zip(idts, idns):
                if idt != None or idn != None:
                    query_identity = "INSERT INTO identity (id_type, id_number, main_id) VALUES (%s, %s, %s)"
                    values_identity = (idt, idn, main_id)
                    cursor.execute(query_identity, values_identity)
        else:
            logger.info(f'{main_id} does not contain identities as list')
    except Exception as err:
        logger.error(f'Error inserting data into{main_id}/ identity table: {err}')
        raise

    # nationality
    try:
        nationalities = row['Nationality']
        if isinstance(nationalities, list):
            for nationality in nationalities:
                if nationality != None:
                    query_nationality = "INSERT INTO nationality (nationality, main_id) VALUES (%s, %s)"
                    values_nationality = (nationality, main_id)
                    cursor.execute(query_nationality, values_nationality)
        else:
            logger.info(f'{main_id} does not contain nationalities as list')
    except Exception as err:
        logger.error(f'Error inserting data into {main_id}/ nationality table: {err}')
        raise

    # date of birth
    try:
        dobs = row['Date of Birth']
        if isinstance(dobs, list):
            for dob in dobs:
                if dob != None:
                    query_dob = "INSERT INTO dob (dob, main_id) VALUES (%s, %s)"
                    values_dob = (dob, main_id)
                    cursor.execute(query_dob, values_dob)
        else:
            logger.info(f'{main_id} does not contain dobs as list')
    except Exception as err:
        logger.error(f'Error inserting data into {main_id}/ date of birth table: {err}')
        raise

    # rca
    try:
        relation_types = row['Relationship Type']
        relation_withs = row['Relation With']
        if isinstance(relation_types, list) and isinstance(relation_withs, list):
            for relation_type, relation_with in zip(relation_types, relation_withs):
                if relation_type != None or relation_with != None:
                    query_rtype = "INSERT INTO rca (relationship_type, relation_with, main_id) VALUES (%s, %s, %s)"
                    values_rwith = (relation_type, relation_with, main_id)
                    cursor.execute(query_rtype, values_rwith)
        else:
            logger.info(f'{main_id} does not contain rca as list')
    except Exception as err:
        logger.error(f'Error inserting data into {main_id}/ rca table: {err}')
        raise

    # address
    try:
        ch = row['Primary Address']
        stt = row['Street']
        cty = row['City']
        sta = row['State']
        cor = row['Country of Residence']
        zp = row['ZIP']
        od = row['Other Details']

        if isinstance(ch, list) and isinstance(stt, list) and isinstance(cty, list) and isinstance(sta, list) and isinstance(cor, list) and isinstance(zp, list) and isinstance(od, list):
            for a, b, c, d, e, f, g in itertools.zip_longest(ch, stt, cty, sta, cor, zp, od, fillvalue=None):
                if a != None or b != None or c != None or d != None or e != None or f != None or g != None:
                    query_address = "INSERT INTO address (primary_address, street, city, state, country_of_residence, zip, other_details, main_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
                    values_address = (a, b, c, d, e, f, g, main_id)
                    cursor.execute(query_address, values_address)
        else:
            logger.info(f'{main_id} does not contain address as list')
    except Exception as err:
        logger.error(f'Error inserting data into {main_id}/ address table: {err}')
        raise

    # role_type
    try:
        po = row['Primary Occupation']
        dsg = row['Designation']
        sd = row['Start Date']
        ed = row['End Date']

        if isinstance(po, list) and isinstance(dsg, list) and isinstance(sd, list) and isinstance(ed, list):
            for a, b, c, d in itertools.zip_longest(po, dsg, sd, ed, fillvalue=None):
                if a != None or b != None or c != None or d != None:
                    query_role_type = "INSERT INTO role_type (primary_occupation, designation, start_date, end_date, main_id) VALUES (%s, %s, %s, %s, %s)"
                    values_role_type = (a, b, c, d, main_id)
                    cursor.execute(query_role_type, values_role_type)
        else:
            logger.info(f'{main_id} does not contain role_type as list')
    except Exception as err:
        logger.error(f'Error inserting data into {main_id}/ role type table: {err}')
        raise

    # case_details
    try:
        if row['Charges'] != None or row['Case Details'] != None or row['Notification Reference'] != None:
            query_case_details = "INSERT INTO case_details (charges, case_details, notification_ref, main_id) VALUES (%s, %s, %s, %s)"
            values_case_details = (row['Charges'], row['Case Details'], row['Notification Reference'], main_id)
            cursor.execute(query_case_details, values_case_details)
    except Exception as err:
        logger.error(f'Error inserting data into {main_id}/ case details table: {err}')
        raise

    return main_id


def insertion_code(new_df, cursor, cnx, log_file):
    # Configure logger for the insertion code
    list_type_value = new_df['Scraper Tag'].iloc[0]
    logger = logging.getLogger(f'{list_type_value}_Insertion logs')
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s-%(levelname)s-%(name)s-%(message)s')
    # Absolute path so the existing 'Insertion Logs' folder is found no matter
    # the CWD (delta can be auto-triggered from structured-scraping, where the
    # old relative path resolved to a non-existent dir → FileNotFoundError).
    _ins_log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Insertion Logs')
    file_handler = logging.FileHandler(os.path.join(_ins_log_dir, f'{log_file}.log'))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    for index, row in new_df.iterrows():
        row = row.fillna('')
        row = row.replace('', None)

        # ── Per-record transaction with deadlock-retry ───────────────────
        # Each record is its own transaction (commit below). On an InnoDB
        # deadlock / lock-wait-timeout (another service touching the DB at the
        # same time) the whole record is rolled back and retried; on any other
        # error it is rolled back and skipped (previous behaviour).
        for attempt in range(1, MAX_DEADLOCK_RETRIES + 1):
            try:
                main_id = _insert_single_record(row, cursor, logger)
                cnx.commit()
                logger.info(f'Successfully inserted data into {main_id}')
                break
            except mysql.connector.Error as err:
                cnx.rollback()
                if getattr(err, 'errno', None) in DEADLOCK_ERRNOS and attempt < MAX_DEADLOCK_RETRIES:
                    logger.warning(
                        f'[{index}] deadlock/lock-timeout (errno {getattr(err, "errno", None)}) '
                        f'— retry {attempt}/{MAX_DEADLOCK_RETRIES}'
                    )
                    time.sleep(0.3 * attempt)
                    continue
                logger.error(f'[{index}] record insert failed permanently: {err}')
                break
            except Exception as err:
                cnx.rollback()
                logger.error(f'[{index}] record insert failed (non-DB error): {err}')
                break

    # ── Post-insert placeholder cleanup ('NULL' string -> real NULL) ─────
    # SCOPED to this scraper_tag so the UPDATE only touches THIS list's rows
    # and never locks other services' rows (was a table-wide UPDATE before).
    disable_safe_updates_query = "SET SQL_SAFE_UPDATES = 0;"
    cursor.execute(disable_safe_updates_query)
    cnx.commit()
    query_status_change = """UPDATE `main` SET `name` = NULLIF(`name`, 'NULL'), `father_name` = NULLIF(`father_name`, 'NULL'), `gender` = NULLIF(`gender`, 'NULL'), `desc` = NULLIF(`desc`, 'NULL'), `head_bounty` = NULLIF(`head_bounty`, 'NULL'), `category` = NULLIF(`category`, 'NULL'), `source_list` = NULLIF(`source_list`, 'NULL'), `list_category` = NULLIF(`list_category`, 'NULL'), `list_type` = NULLIF(`list_type`, 'NULL'), `updated_on` = NULLIF(`updated_on`, '1890-01-01'), `added_on` = NULLIF(`added_on`, '1890-01-01'), `img_tag` = NULLIF(`img_tag`, 'NULL'), `scraper_tag` = NULLIF(`scraper_tag`, 'NULL'), `customer_id` = NULLIF(`customer_id`, 'NULL'), `date_exclusion` = NULLIF(`date_exclusion`, '1890-01-01'), `date_inclusion` = NULLIF(`date_inclusion`, '1890-01-01'), `deceased_dissolved_date` = NULLIF(`deceased_dissolved_date`, '1890-01-01'), `reg_date` = NULLIF(`reg_date`, '1890-01-01'), `extra_info` = NULLIF(`extra_info`, 'NULL'), `pob` = NULLIF(`pob`, 'NULL') WHERE `scraper_tag` = %s AND (`name` = 'NULL' OR `father_name` = 'NULL' OR `gender` = 'NULL' OR `desc` = 'NULL' OR `head_bounty` = 'NULL' OR `category` = 'NULL' OR `source_list` = 'NULL' OR `list_category` = 'NULL' OR `list_type` = 'NULL' OR `updated_on` = '1890-01-01' OR `added_on` = '1890-01-01' OR `img_tag` = 'NULL' OR `scraper_tag` = 'NULL' OR `customer_id` = 'NULL' OR `date_exclusion` = '1890-01-01' OR `date_inclusion` = '1890-01-01' OR `deceased_dissolved_date` = '1890-01-01' OR `reg_date` = '1890-01-01' OR `extra_info` = 'NULL' OR `pob` = 'NULL');"""
    cursor.execute(query_status_change, (list_type_value,))
    cnx.commit()
    query_status_change = """UPDATE `case_details` c JOIN `main` m ON c.`main_id` = m.`main_id` SET c.`charges` = NULLIF(c.`charges`, 'NULL'), c.`case_details` = NULLIF(c.`case_details`, 'NULL'), c.`notification_ref` = NULLIF(c.`notification_ref`, 'NULL') WHERE m.`scraper_tag` = %s AND (c.`charges` = 'NULL' OR c.`case_details` = 'NULL' OR c.`notification_ref` = 'NULL');"""
    cursor.execute(query_status_change, (list_type_value,))
    cnx.commit()
