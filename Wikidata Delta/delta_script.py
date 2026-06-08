import datetime
import pandas as pd
from collections import Counter
from itertools import zip_longest

def delta_code(df, cursor, cnx,logger):
    new_df = pd.DataFrame(columns=df.columns)
    is_del_list_1 = []

    disable_safe_updates_query = "SET SQL_SAFE_UPDATES = 0;"
    cursor.execute(disable_safe_updates_query)
    cnx.commit()

    try:
        query_status_change = """UPDATE `main` SET `name` = IFNULL(`name`, 'NULL'),`father_name` = IFNULL(`father_name`, 'NULL'),`gender` = IFNULL(`gender`, 'NULL'),`desc` = IFNULL(`desc`, 'NULL'),`head_bounty` = IFNULL(`head_bounty`, 'NULL'),`category` = IFNULL(`category`, 'NULL'),`source_list` = IFNULL(`source_list`, 'NULL'),`list_category` = IFNULL(`list_category`, 'NULL'),`list_type` = IFNULL(`list_type`, 'NULL'),`updated_on` = IFNULL(`updated_on`, '1890-01-01'),`added_on` = IFNULL(`added_on`, '1890-01-01'),`img_tag` = IFNULL(`img_tag`, 'NULL'),`scraper_tag` = IFNULL(`scraper_tag`, 'NULL'),`customer_id` = IFNULL(`customer_id`, 'NULL'),`date_exclusion` = IFNULL(`date_exclusion`, '1890-01-01'),`date_inclusion` = IFNULL(`date_inclusion`, '1890-01-01'),`deceased_dissolved_date` = IFNULL(`deceased_dissolved_date`, '1890-01-01'),`reg_date` = IFNULL(`reg_date`, '1890-01-01'),`extra_info` = IFNULL(`extra_info`, 'NULL'),`pob` = IFNULL(`pob`, 'NULL') WHERE `name` IS NULL OR `father_name` IS NULL OR `gender` IS NULL OR `desc` IS NULL OR `head_bounty` IS NULL OR `category` IS NULL OR `source_list` IS NULL OR `list_category` IS NULL OR `list_type` IS NULL OR `updated_on` IS NULL OR `added_on` IS NULL OR `img_tag` IS NULL OR `scraper_tag` IS NULL OR `customer_id` IS NULL OR `date_exclusion` IS NULL OR `date_inclusion` IS NULL OR`deceased_dissolved_date` IS NULL OR `reg_date` IS NULL OR `extra_info` IS NULL OR  `pob` IS NULL;"""
        cursor.execute(query_status_change)
        cnx.commit()
    except Exception as e:
        logger.error(
            f"❌❌ Error occurred while updating datatype null to string null in main table: {e}"
        )

    try:
        query_status_change = """UPDATE `case_details` SET `charges` = IFNULL(`charges`, 'NULL'),`case_details` = IFNULL(`case_details`, 'NULL'),`notification_ref` = IFNULL(`notification_ref`, 'NULL') WHERE `charges` IS NULL OR `case_details` IS NULL OR `notification_ref` IS NULL;"""
        cursor.execute(query_status_change)
        cnx.commit()
    except Exception as e:
        logger.error(
            f"❌❌ Error occurred while updating datatype null to string null in case_details table: {e}"
        )

    enable_safe_updates_query = "SET SQL_SAFE_UPDATES = 1;"
    cursor.execute(enable_safe_updates_query)
    cnx.commit()

    checkkk = []

    for index, row in df.iterrows():
        name = row["Name"]
        logger.info(f"[DELTA] Processing record #{index}: '{name}'")

        query_check = "SELECT main_id FROM main WHERE (name = %s) AND (father_name = %s) AND (gender = %s) AND (category = %s) AND (`desc` = %s) AND (source_list = %s) AND (list_category = %s) AND (list_type = %s)  AND (scraper_tag = %s) AND (date_exclusion = %s) AND (date_inclusion = %s) AND (deceased_dissolved_status = %s) AND (deceased_dissolved_date = %s) AND (reg_date = %s) AND (status = %s) AND (pob = %s)"

        # query_check = "SELECT main_id FROM main WHERE (name = %s) AND (father_name = %s) AND (gender = %s) AND (category = %s) AND (`desc` = %s) AND (source_list = %s) AND (list_category = %s) AND (list_type = %s) AND (img_tag = %s) AND (scraper_tag = %s) AND (date_exclusion = %s) AND (date_inclusion = %s) AND (deceased_dissolved_status = %s) AND (deceased_dissolved_date = %s) AND (reg_date = %s) AND (status = %s) AND (pob = %s)"
        values_check = (
            row["Name"],
            row["Father Name"],
            row["Gender"],
            row["Category"],
            row["Description"],
            row["Source List"],
            row["List Category"],
            row["List Type"],
            # row["Image Tag"],
            row["Scraper Tag"],
            row["Date of Exclusion"],
            row["Date of Inclusion"],
            row["Deceased Dissolved Status"],
            row["Deceased Dissolved Date"],
            row["Registration Date"],
            row["Status"],
            row["Place of Birth"],
        )
        cursor.execute(query_check, values_check)
        main_existss = cursor.fetchall()

        if not main_existss:
            # Log why the AND-query found no match by checking each field individually
            field_map = {
                "name":                    row["Name"],
                "father_name":             row["Father Name"],
                "gender":                  row["Gender"],
                "category":                row["Category"],
                "desc":                    row["Description"],
                "source_list":             row["Source List"],
                "list_category":           row["List Category"],
                "list_type":               row["List Type"],
                # "img_tag":                 row["Image Tag"],
                "scraper_tag":             row["Scraper Tag"],
                "date_exclusion":          row["Date of Exclusion"],
                "date_inclusion":          row["Date of Inclusion"],
                "deceased_dissolved_status": row["Deceased Dissolved Status"],
                "deceased_dissolved_date": row["Deceased Dissolved Date"],
                "reg_date":                row["Registration Date"],
                "status":                  row["Status"],
                "pob":                     row["Place of Birth"],
            }
            cursor.execute(
                "SELECT main_id FROM main WHERE name = %s AND scraper_tag = %s AND status = 1",
                (row["Name"], row["Scraper Tag"]),
            )
            possible_matches = cursor.fetchall()
            if possible_matches:
                logger.info(
                    f"[DELTA]   AND-query missed — found {len(possible_matches)} record(s) by name+scraper_tag. "
                    f"Checking which main-table field(s) differ for main_id={possible_matches[0][0]}:"
                )
                cursor.execute(
                    "SELECT father_name, gender, category, `desc`, source_list, list_category, list_type, "
                    "img_tag, DATE_FORMAT(date_exclusion,'%Y-%m-%d'), DATE_FORMAT(date_inclusion,'%Y-%m-%d'), "
                    "deceased_dissolved_status, DATE_FORMAT(deceased_dissolved_date,'%Y-%m-%d'), "
                    "DATE_FORMAT(reg_date,'%Y-%m-%d'), status, pob "
                    "FROM main WHERE main_id = %s",
                    (possible_matches[0][0],),
                )
                db_row = cursor.fetchone()
                if db_row:
                    db_fields = {
                        "father_name":             db_row[0],
                        "gender":                  db_row[1],
                        "category":                db_row[2],
                        "desc":                    db_row[3],
                        "source_list":             db_row[4],
                        "list_category":           db_row[5],
                        "list_type":               db_row[6],
                        # "img_tag":                 db_row[7],
                        "date_exclusion":          db_row[8],
                        "date_inclusion":          db_row[9],
                        "deceased_dissolved_status": db_row[10],
                        "deceased_dissolved_date": db_row[11],
                        "reg_date":                db_row[12],
                        "status":                  db_row[13],
                        "pob":                     db_row[14],
                    }
                    scraper_fields = {k: v for k, v in field_map.items() if k != "name" and k != "scraper_tag"}
                    diffs = [
                        f"      {field}: DB={repr(db_fields[field])} vs Scraper={repr(scraper_fields[field])}"
                        for field in db_fields
                        if str(db_fields[field]) != str(scraper_fields.get(field, ""))
                    ]
                    if diffs:
                        logger.info(f"[DELTA]   Differing main-table fields:\n" + "\n".join(diffs))
                    else:
                        logger.info(f"[DELTA]   No main-table field diffs detected (may be NULL/type mismatch).")
            else:
                logger.info(f"[DELTA]   No existing record found by name+scraper_tag — treating as BRAND NEW.")

            query_update_check = "SELECT main_id FROM main WHERE (name = %s) OR (father_name = %s) OR (gender = %s) OR (category = %s) OR (`desc` = %s) OR (source_list = %s) OR (list_category = %s) OR (list_type = %s) OR (updated_on = %s) OR (img_tag = %s) OR (scraper_tag = %s) OR (date_exclusion = %s) OR (date_inclusion = %s) OR (deceased_dissolved_status = %s) OR (deceased_dissolved_date = %s) OR (reg_date = %s) OR (status = %s) OR (pob = %s)"
            values_update_check = (
                row["Name"],
                row["Father Name"],
                row["Gender"],
                row["Category"],
                row["Description"],
                row["Source List"],
                row["List Category"],
                row["List Type"],
                row["Updated On"],
                row["Image Tag"],
                row["Scraper Tag"],
                row["Date of Exclusion"],
                row["Date of Inclusion"],
                row["Deceased Dissolved Status"],
                row["Deceased Dissolved Date"],
                row["Registration Date"],
                row["Status"],
                row["Place of Birth"],
            )
            cursor.execute(query_update_check, values_update_check)
            main_update_existss = cursor.fetchall()

        if main_existss:
            for ids in main_existss:
                main_exists = ids[0]
                if main_exists not in checkkk:
                    logger.info(f"[DELTA]   AND-query matched main_id={main_exists}. Checking child tables...")

                    # Check if record already exists in alias table
                    aliases = row["Alias"]
                    alias_types = row["Alias Type"]
                    query_alias_check = "SELECT * FROM alias WHERE main_id = %s"
                    values_alias_check = (main_exists,)
                    cursor.execute(query_alias_check, values_alias_check)
                    alias_exist = cursor.fetchall()
                    alias_exist = [t[2] for t in alias_exist]
                    alias_deletion = list(
                        (Counter(alias_exist) - Counter(aliases)).elements()
                    )
                    alias_updation = list(
                        (Counter(aliases) - Counter(alias_exist)).elements()
                    )
                    if alias_deletion or alias_updation:
                        logger.info(
                            f"[DELTA]   alias MISMATCH:"
                            f"\n      DB={alias_exist}"
                            f"\n      Scraper={aliases}"
                            f"\n      To remove={alias_deletion}  To add={alias_updation}"
                        )

                    # Check if record already exists in identity table
                    idts = row["ID Type"]
                    idns = [
                        str(idn) for idn in row["ID Number"]
                    ]  # Ensure idns are strings
                    query_identity_check = "SELECT * FROM identity WHERE main_id = %s"
                    values_identity_check = (main_exists,)
                    cursor.execute(query_identity_check, values_identity_check)
                    identity_exist = cursor.fetchall()
                    identity_exist = [t[2] for t in identity_exist]
                    identity_deletion = list(
                        (Counter(identity_exist) - Counter(idns)).elements()
                    )
                    identity_updation = list(
                        (Counter(idns) - Counter(identity_exist)).elements()
                    )
                    if identity_deletion or identity_updation:
                        logger.info(
                            f"[DELTA]   identity MISMATCH:"
                            f"\n      DB={identity_exist}"
                            f"\n      Scraper={idns}"
                            f"\n      To remove={identity_deletion}  To add={identity_updation}"
                        )

                    # nationality
                    nationalities = row["Nationality"]
                    query_nationality_check = (
                        "SELECT * FROM nationality WHERE main_id = %s"
                    )
                    values_nationality_check = (main_exists,)
                    cursor.execute(query_nationality_check, values_nationality_check)
                    nationality_exist = cursor.fetchall()
                    nationality_exist = [t[1] for t in nationality_exist]
                    nationality_deletion = list(
                        (Counter(nationality_exist) - Counter(nationalities)).elements()
                    )
                    nationality_updation = list(
                        (Counter(nationalities) - Counter(nationality_exist)).elements()
                    )
                    if nationality_deletion or nationality_updation:
                        logger.info(
                            f"[DELTA]   nationality MISMATCH:"
                            f"\n      DB={nationality_exist}"
                            f"\n      Scraper={nationalities}"
                            f"\n      To remove={nationality_deletion}  To add={nationality_updation}"
                        )

                    # date of birth
                    dobs = row["Date of Birth"]
                    query_dob_check = "SELECT * FROM dob WHERE main_id = %s"
                    values_dob_check = (main_exists,)
                    cursor.execute(query_dob_check, values_dob_check)
                    dob_exist = cursor.fetchall()
                    dob_exist = [t[1] for t in dob_exist]
                    dobbs = [
                        datetime.datetime.strptime(str(elem), "%Y-%m-%d").date()
                        for elem in dobs
                    ]
                    dob_deletion = list(
                        (Counter(dob_exist) - Counter(dobbs)).elements()
                    )
                    dob_updation = list(
                        (Counter(dobbs) - Counter(dob_exist)).elements()
                    )
                    if dob_deletion or dob_updation:
                        logger.info(
                            f"[DELTA]   dob MISMATCH:"
                            f"\n      DB={dob_exist}"
                            f"\n      Scraper={dobbs}"
                            f"\n      To remove={dob_deletion}  To add={dob_updation}"
                        )

                    # rca
                    relation_types = row["Relationship Type"]
                    relation_withs = row["Relation With"]
                    query_rtype_check = "SELECT * FROM rca WHERE main_id = %s"
                    values_rwith_check = (main_exists,)
                    cursor.execute(query_rtype_check, values_rwith_check)
                    rca_exist = cursor.fetchall()
                    rw_rca_exist = [t[2] for t in rca_exist]
                    rw_rca_deletion = list(
                        (Counter(rw_rca_exist) - Counter(relation_withs)).elements()
                    )
                    rw_rca_updation = list(
                        (Counter(relation_withs) - Counter(rw_rca_exist)).elements()
                    )
                    if rw_rca_deletion or rw_rca_updation:
                        logger.info(
                            f"[DELTA]   rca MISMATCH:"
                            f"\n      DB={rw_rca_exist}"
                            f"\n      Scraper={relation_withs}"
                            f"\n      To remove={rw_rca_deletion}  To add={rw_rca_updation}"
                        )

                    # address
                    ch = row["Primary Address"]
                    stt = row["Street"]
                    cty = row["City"]
                    sta = row["State"]
                    cor = row["Country of Residence"]
                    zp = row["ZIP"]
                    od = row["Other Details"]
                    query_address_check = "SELECT * FROM address WHERE main_id = %s"
                    values_address_check = (main_exists,)
                    cursor.execute(query_address_check, values_address_check)
                    address_exists = cursor.fetchall()
                    address_db_tuples = [
                        (t[1], t[2], t[3], t[4], t[5], t[6], t[7])
                        for t in address_exists
                    ]
                    address_df_tuples = list(
                        zip_longest(
                            ch,
                            stt,
                            cty,
                            sta,
                            cor,
                            zp,
                            od,
                            fillvalue=None,
                        )
                    )
                    address_tuple_deletion = list(
                        (
                            Counter(address_db_tuples) - Counter(address_df_tuples)
                        ).elements()
                    )
                    address_tuple_updation = list(
                        (
                            Counter(address_df_tuples) - Counter(address_db_tuples)
                        ).elements()
                    )
                    address_tuple_match = (
                        len(address_tuple_deletion) == 0
                        and len(address_tuple_updation) == 0
                    )
                    if not address_tuple_match:
                        logger.info(
                            f"[DELTA]   address MISMATCH:"
                            f"\n      DB tuples={address_db_tuples}"
                            f"\n      Scraper tuples={address_df_tuples}"
                            f"\n      To remove={address_tuple_deletion}  To add={address_tuple_updation}"
                        )

                    # role_type — compare as whole-row tuples to handle NULL-filled columns
                    # (insertion uses zip_longest with fillvalue=None, so DB may have NULL
                    #  where the scraper has an empty list; tuple comparison naturally aligns them)
                    po = row["Primary Occupation"]
                    dsg = row["Designation"]
                    sd = row["Start Date"]
                    ed = row["End Date"]
                    query_role_type_check = "SELECT `role_id`, `primary_occupation`, `designation`, DATE_FORMAT(start_date, '%Y-%m-%d'), DATE_FORMAT(end_date, '%Y-%m-%d'), `main_id` FROM role_type WHERE main_id = %s"
                    values_role_type_check = (main_exists,)
                    cursor.execute(query_role_type_check, values_role_type_check)
                    role_type_exists = cursor.fetchall()
                    po_role_type_exists = [t[1] for t in role_type_exists]
                    dsg_role_type_exists = [t[2] for t in role_type_exists]
                    sd_role_type_exists = [t[3] for t in role_type_exists]
                    ed_role_type_exists = [t[4] for t in role_type_exists]

                    # Build tuples matching the same zip_longest logic used at insertion time
                    role_type_db_tuples = list(
                        zip(po_role_type_exists, dsg_role_type_exists, sd_role_type_exists, ed_role_type_exists)
                    )
                    role_type_scraper_tuples = list(
                        zip_longest(po, dsg, sd, ed, fillvalue=None)
                    )
                    role_type_deletion = list(
                        (Counter(role_type_db_tuples) - Counter(role_type_scraper_tuples)).elements()
                    )
                    role_type_updation = list(
                        (Counter(role_type_scraper_tuples) - Counter(role_type_db_tuples)).elements()
                    )
                    role_type_match = len(role_type_deletion) == 0 and len(role_type_updation) == 0

                    # Keep individual diffs for backward-compat logging
                    po_role_type_deletion = list((Counter(po_role_type_exists) - Counter(po)).elements())
                    po_role_type_updation = list((Counter(po) - Counter(po_role_type_exists)).elements())
                    dsg_role_type_deletion = list((Counter(dsg_role_type_exists) - Counter(dsg)).elements())
                    dsg_role_type_updation = list((Counter(dsg) - Counter(dsg_role_type_exists)).elements())
                    sd_role_type_order_match = sd_role_type_exists == sd
                    ed_role_type_order_match = ed_role_type_exists == ed

                    if not role_type_match:
                        logger.info(
                            f"[DELTA]   role_type MISMATCH:"
                            f"\n      DB tuples:      {role_type_db_tuples}"
                            f"\n      Scraper tuples: {role_type_scraper_tuples}"
                            f"\n      To remove={role_type_deletion}  To add={role_type_updation}"
                        )

                    if (
                        row["Charges"] != "NULL"
                        or row["Case Details"] != "NULL"
                        or row["Notification Reference"] != "NULL"
                    ):
                        # case_details
                        query_check = "SELECT case_id FROM case_details WHERE (charges = %s) AND (case_details = %s) AND (notification_ref = %s) AND main_id = %s"
                        values_check = (
                            row["Charges"],
                            row["Case Details"],
                            row["Notification Reference"],
                            main_exists,
                        )
                        cursor.execute(query_check, values_check)
                        case_details_exists = cursor.fetchone()

                        if not case_details_exists:
                            logger.info(
                                f"[DELTA]   case_details MISMATCH:"
                                f"\n      Scraper: charges={repr(row['Charges'])}  case_details={repr(row['Case Details'])}  notification_ref={repr(row['Notification Reference'])}"
                            )
                            query_update_check = "SELECT case_id FROM case_details WHERE (charges = %s) OR (case_details = %s) OR (notification_ref = %s) OR main_id = %s"
                            values_update_check = (
                                row["Charges"],
                                row["Case Details"],
                                row["Notification Reference"],
                                main_exists,
                            )
                            cursor.execute(query_update_check, values_update_check)
                            case_details_update_exists = cursor.fetchone()
                    else:
                        case_details_exists = "Not None"

                    all_match = (
                        main_exists != 0
                        and len(alias_deletion) == 0
                        and len(alias_updation) == 0
                        and len(identity_deletion) == 0
                        and len(identity_updation) == 0
                        and len(nationality_deletion) == 0
                        and len(nationality_updation) == 0
                        and len(dob_deletion) == 0
                        and len(dob_updation) == 0
                        and len(rw_rca_deletion) == 0
                        and len(rw_rca_updation) == 0
                        and address_tuple_match
                        and role_type_match
                        and case_details_exists is not None
                    )

                    if all_match:
                        logger.info(f"[DELTA]   '{name}' (main_id={main_exists}) — SAME. Added to is_del_list_1.")
                        is_del_list_1.append(main_exists)
                        checkkk.append(main_exists)
                        break
                    else:
                        # Build a summary of which checks failed
                        failed = []
                        if main_exists == 0:
                            failed.append("main_id=0")
                        if alias_deletion or alias_updation:
                            failed.append("alias")
                        if identity_deletion or identity_updation:
                            failed.append("identity")
                        if nationality_deletion or nationality_updation:
                            failed.append("nationality")
                        if dob_deletion or dob_updation:
                            failed.append("dob")
                        if rw_rca_deletion or rw_rca_updation:
                            failed.append("rca")
                        if not address_tuple_match:
                            failed.append("address")
                        if not role_type_match:
                            failed.append(f"role_type (to_remove={role_type_deletion}, to_add={role_type_updation})")
                        if case_details_exists is None:
                            failed.append("case_details")
                        logger.info(
                            f"[DELTA]   '{name}' (main_id={main_exists}) — CHANGED. "
                            f"Failing check(s): {failed}. Added to new_df."
                        )
                        new_df = pd.concat(
                            [new_df, row.to_frame().transpose()], ignore_index=True
                        )
                        checkkk.append(main_exists)
                        break
                else:
                    continue

        elif (main_update_existss is not None) and (main_existss is None):
            logger.info(f"[DELTA]   '{name}' — OR-query matched but AND-query missed. Added to new_df.")
            new_df = pd.concat([new_df, row.to_frame().transpose()], ignore_index=True)
            continue

        else:
            logger.info(f"[DELTA]   '{name}' — No match at all (truly new record). Added to new_df.")
            new_df = pd.concat([new_df, row.to_frame().transpose()], ignore_index=True)

    disable_safe_updates_query = "SET SQL_SAFE_UPDATES = 0;"
    cursor.execute(disable_safe_updates_query)
    cnx.commit()
    query_status_change = """UPDATE `main` SET `name` = NULLIF(`name`, 'NULL'), `father_name` = NULLIF(`father_name`, 'NULL'), `gender` = NULLIF(`gender`, 'NULL'), `desc` = NULLIF(`desc`, 'NULL'), `head_bounty` = NULLIF(`head_bounty`, 'NULL'), `category` = NULLIF(`category`, 'NULL'), `source_list` = NULLIF(`source_list`, 'NULL'), `list_category` = NULLIF(`list_category`, 'NULL'), `list_type` = NULLIF(`list_type`, 'NULL'), `updated_on` = NULLIF(`updated_on`, '1890-01-01'), `added_on` = NULLIF(`added_on`, '1890-01-01'), `img_tag` = NULLIF(`img_tag`, 'NULL'), `scraper_tag` = NULLIF(`scraper_tag`, 'NULL'), `customer_id` = NULLIF(`customer_id`, 'NULL'), `date_exclusion` = NULLIF(`date_exclusion`, '1890-01-01'), `date_inclusion` = NULLIF(`date_inclusion`, '1890-01-01'), `deceased_dissolved_date` = NULLIF(`deceased_dissolved_date`, '1890-01-01'), `reg_date` = NULLIF(`reg_date`, '1890-01-01'), `extra_info` = NULLIF(`extra_info`, 'NULL'), `pob` = NULLIF(`pob`, 'NULL') WHERE `name` = 'NULL' OR `father_name` = 'NULL' OR `gender` = 'NULL' OR `desc` = 'NULL' OR `head_bounty` = 'NULL' OR `category` = 'NULL' OR `source_list` = 'NULL' OR `list_category` = 'NULL' OR `list_type` = 'NULL' OR `updated_on` = '1890-01-01' OR `added_on` = '1890-01-01' OR `img_tag` = 'NULL' OR `scraper_tag` = 'NULL' OR `customer_id` = 'NULL' OR `date_exclusion` = '1890-01-01' OR `date_inclusion` = '1890-01-01' OR `deceased_dissolved_date` = '1890-01-01' OR `reg_date` = '1890-01-01' OR `extra_info` = 'NULL' OR `pob` = 'NULL';"""
    cursor.execute(query_status_change)
    cnx.commit()
    query_status_change = """UPDATE `case_details` SET `charges` = NULLIF(`charges`, 'NULL'), `case_details` = NULLIF(`case_details`, 'NULL'), `notification_ref` = NULLIF(`notification_ref`, 'NULL') WHERE `charges` = 'NULL' OR `case_details` = 'NULL' OR `notification_ref` = 'NULL';"""
    cursor.execute(query_status_change)
    cnx.commit()
    if is_del_list_1:
        try:
            scraper_tags = df["Scraper Tag"].dropna().unique().tolist()
            scraper_tag_placeholders = ", ".join(["%s"] * len(scraper_tags))
            main_id_placeholders = ", ".join(["%s"] * len(is_del_list_1))
            query_status_change = f"""UPDATE main SET `status` = 0, `updated_on` = %s WHERE status = 1 
            AND scraper_tag IN ({scraper_tag_placeholders}) 
            AND main_id NOT IN ({main_id_placeholders})"""
            current_date = datetime.datetime.now().strftime("%Y-%m-%d")
            params = [current_date] + scraper_tags + is_del_list_1
            cursor.execute(query_status_change, params)
            cnx.commit()
        except Exception as e:
            logger.error(f"❌ ERROR while updating status 0")
            pass
    else:
        logger.info(f"No Existing Record Found")
    enable_safe_updates_query = "SET SQL_SAFE_UPDATES = 1;"
    cursor.execute(enable_safe_updates_query)
    cnx.commit()
    replacement_values = {
        "Deceased Dissolved Date": {"1890-01-01": "NULL"},
        "Registration Date": {"1890-01-01": "NULL"},
        "Date of Inclusion": {"1890-01-01": "NULL"},
        "Date of Exclusion": {"1890-01-01": "NULL"},
        "Updated On": {"1890-01-01": "NULL"},
    }

    new_df.replace(replacement_values, inplace=True)
    new_df.replace("NULL", "", inplace=True)
    new_df["Updated On"] = datetime.datetime.now().strftime("%Y-%m-%d")
    return new_df
