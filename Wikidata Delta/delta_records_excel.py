import pandas as pd
import json
import datetime
import os
import logging

_log = logging.getLogger(__name__)



def delta_excel_df_creator(log_file, cursor_dict, cnx_dict):
    updated_on = datetime.datetime.now().strftime("%Y-%m-%d")
    query = """
            SELECT main.name AS `Name`, main.father_name AS `Father Name`, main.gender AS `Gender`, main.desc AS `Description`, main.head_bounty AS `Head Bounty`, main.category AS `Category`, 
                               main.source_list AS `Source List`, main.list_category AS `List Category`, main.list_type AS `List Type`, main.updated_on AS `Updated On`, main.added_on AS `Added On`, main.img_tag AS `Image Tag`, 
                               main.scraper_tag AS `Scraper Tag`, main.customer_id AS `ID`, main.date_exclusion AS `Date of Exclusion`, main.date_inclusion AS `Date of Inclusion`, main.deceased_dissolved_status AS `Deceased Dissolved Status`, 
                               main.deceased_dissolved_date AS `Deceased Dissolved Date`, main.reg_date AS `Registration Date`, main.extra_info AS `Extra Information`, main.status AS `Status`, main.pob AS `Place of Birth`, 
                               address.primary_address AS `Primary Address`, address.street AS `Street`, address.city AS `City`, address.state AS `State`, address.country_of_residence AS `Country of Residence`, address.zip AS `ZIP`, address.other_details AS `Other Details`,
                               alias.alias_type AS `Alias Type`, alias.alias AS `Alias`,
                               case_details.charges AS `Charges`, case_details.case_details AS `Case Details`, case_details.notification_ref AS `Notification Reference`,
                               dob.dob AS `Date of Birth`,
                               identity.id_type AS `ID Type`, identity.id_number AS `ID Number`,
                               nationality.nationality AS `Nationality`,
                               rca.relationship_type AS `Relationship Type`, rca.relation_with AS `Relation With`,
                               role_type.primary_occupation AS `Primary Occupation`, role_type.designation AS `Designation`, role_type.start_date AS `Start Date`, role_type.end_date AS `End Date`
                        FROM main
                        LEFT JOIN (
                            SELECT main_id, GROUP_CONCAT(primary_address SEPARATOR '|||') AS primary_address,
                                        GROUP_CONCAT(street SEPARATOR '|||') AS street,
                                        GROUP_CONCAT(city SEPARATOR '|||') AS city,
                                        GROUP_CONCAT(state SEPARATOR '|||') AS state,
                                        GROUP_CONCAT(country_of_residence SEPARATOR '|||') AS country_of_residence,
                                        GROUP_CONCAT(zip SEPARATOR '|||') AS zip,
                                        GROUP_CONCAT(other_details SEPARATOR '|||') AS other_details
                            FROM address
                            GROUP BY main_id
                        ) AS address ON main.main_id = address.main_id
                        LEFT JOIN (
                            SELECT main_id, GROUP_CONCAT(alias_type SEPARATOR '|||') AS alias_type,
                                        GROUP_CONCAT(alias SEPARATOR '|||') AS alias
                            FROM alias
                            GROUP BY main_id
                        ) AS alias ON main.main_id = alias.main_id
                        LEFT JOIN (
                            SELECT main_id, GROUP_CONCAT(charges SEPARATOR '|||') AS charges,
                                        GROUP_CONCAT(case_details SEPARATOR '|||') AS case_details,
                                        GROUP_CONCAT(notification_ref SEPARATOR '|||') AS notification_ref
                            FROM case_details
                            GROUP BY main_id
                        ) AS case_details ON main.main_id = case_details.main_id
                        LEFT JOIN (
                            SELECT main_id, GROUP_CONCAT(dob SEPARATOR '|||') AS dob
                            FROM dob
                            GROUP BY main_id
                        ) AS dob ON main.main_id = dob.main_id
                        LEFT JOIN (
                            SELECT main_id, GROUP_CONCAT(id_type SEPARATOR '|||') AS id_type,
                                        GROUP_CONCAT(id_number SEPARATOR '|||') AS id_number
                            FROM identity
                            GROUP BY main_id
                        ) AS identity ON main.main_id = identity.main_id
                        LEFT JOIN (
                            SELECT main_id, GROUP_CONCAT(nationality SEPARATOR '|||') AS nationality
                            FROM nationality
                            GROUP BY main_id
                        ) AS nationality ON main.main_id = nationality.main_id
                        LEFT JOIN (
                            SELECT main_id, GROUP_CONCAT(relationship_type SEPARATOR '|||') AS relationship_type,
                                        GROUP_CONCAT(relation_with SEPARATOR '|||') AS relation_with
                            FROM rca
                            GROUP BY main_id
                        ) AS rca ON main.main_id = rca.main_id
                        LEFT JOIN (
                            SELECT main_id, GROUP_CONCAT(primary_occupation SEPARATOR '|||') AS primary_occupation,
                                        GROUP_CONCAT(designation SEPARATOR '|||') AS designation,
                                        GROUP_CONCAT(start_date SEPARATOR '|||') AS start_date,
                                        GROUP_CONCAT(end_date SEPARATOR '|||') AS end_date
                            FROM role_type
                            GROUP BY main_id
                        ) AS role_type ON main.main_id = role_type.main_id
                        WHERE main.scraper_tag = %s AND `updated_on` = %s;
        """

    cursor_dict.execute(query, (log_file, updated_on))
    results = cursor_dict.fetchall()

    cursor_dict.close()
    cnx_dict.close()

    df2 = pd.DataFrame(results)

    # Convert the concatenated string columns into lists using custom separator
    separator = "|||"
    list_columns = [
        "Primary Address",
        "Street",
        "City",
        "State",
        "Country of Residence",
        "ZIP",
        "Other Details",
        "Alias Type",
        "Alias",
        "Date of Birth",
        "ID Type",
        "ID Number",
        "Nationality",
        "Relationship Type",
        "Relation With",
        "Primary Occupation",
        "Designation",
        "Start Date",
        "End Date",
    ]

    for col in list_columns:
        # df2[col] = df2[col].apply(lambda x: x.split(separator) if x is not None else [])
          df2[col] = df2[col].apply(lambda x: x.split(separator) if isinstance(x, str) else [])
    df2["Extra Information"] = df2["Extra Information"].apply(
        lambda x: json.loads(x) if x is not None else {}
    )

    # # Replace '1890-01-01' back to 'NULL' for the specific columns
    # revert_replacement_values = {'Deceased Dissolved Date': {'1890-01-01': 'NULL'},
    #                              'Registration Date': {'1890-01-01': 'NULL'},
    #                              'Date of Inclusion': {'1890-01-01': 'NULL'},
    #                              'Date of Exclusion': {'1890-01-01': 'NULL'},
    #                              'Updated On': {'1890-01-01': 'NULL'}}

    # # Apply the replacements to revert the dates back to 'NULL'
    # cleaned_df.replace(revert_replacement_values, inplace=True)

    # # Replace 'NULL' back to an empty string for all columns
    # cleaned_df.replace('NULL', '', inplace=True)

    # df2 = df2[cleaned_df.columns]
    # if not df2.empty:
    #     # Concatenate cleaned_df and df2 along the rows (axis=0)
    #     concatenated_df = pd.concat([cleaned_df, df2], axis=0)
    # else:
    #     print('NO STATUS ZERO')
    #     concatenated_df = cleaned_df

    # delta_time = datetime.datetime.now().strftime("%Y-%m-%d")

    previous_delta_files = [
        file
        for file in os.listdir()
        if f"{log_file}_DELTA_" in file and file.endswith(".xlsx")
    ]
    for previous_delta_file in previous_delta_files:
        os.remove(previous_delta_file)

    # df2.to_excel(f"{log_file}_excels/{log_file}_DELTA_{updated_on}.xlsx", index=False)
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(BASE_DIR, f"{log_file}_excels")
    os.makedirs(output_dir, exist_ok=True)


    # ── S3: delete images for status=0 records ─────────────────────
    # TEST MODE (Hassam Nasir) — S3 image deletion TEMPORARILY DISABLED for testing (Netherlands).
    # ⚠️ Testing ke baad neeche ka block DOBARA UNCOMMENT karna hai (warna prod mein
    #    status=0 records ki S3 images delete nahi hongi).
    _log.warning('[IMAGE][TEST MODE] delete_inactive_images SKIPPED — S3 images NOT deleted')
    # try:
    #     from image_handler import delete_inactive_images
    #     delete_inactive_images(df2, log_file, _log)
    # except Exception as _img_exc:
    #     _log.warning('[IMAGE] delete_inactive_images failed: %s', _img_exc)

    df2.to_excel(os.path.join(output_dir, f"{log_file}_DELTA_{updated_on}.xlsx"),index=False
)