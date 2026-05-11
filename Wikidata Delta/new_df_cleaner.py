import datetime
import os

def new_df_cleaner(new_df, cursor, cnx):
    query_status_change = "SELECT MAX(CAST(SUBSTRING_INDEX(customer_id, '-', -1) AS SIGNED)) AS max_number FROM main WHERE scraper_tag LIKE %s"
    list_type_value = new_df['Scraper Tag'].iloc[0]
    cursor.execute(query_status_change, (list_type_value,))
    max_id_number = cursor.fetchone()[0]

    query_status_change = "SELECT CONCAT(SUBSTRING_INDEX(customer_id, '-', LENGTH(customer_id) - LENGTH(REPLACE(customer_id, '-', '')) - 1), '-') AS part_before_last_hyphen FROM main WHERE scraper_tag LIKE %s;"
    list_type_value = new_df['Scraper Tag'].iloc[0]
    cursor.execute(query_status_change, (list_type_value,))
    part_before_last_hyphen = cursor.fetchone()[0]

    max_id_number += 1
    new_df['ID'] = [f'{part_before_last_hyphen}E-{max_id_number + i}' if 'Entity' in list_type else f'{part_before_last_hyphen}I-{max_id_number + i}'for i, list_type in enumerate(new_df['List Type'])]
    updated_on_date = datetime.datetime.today().strftime('%Y-%m-%d')
    new_df['Updated On'] = updated_on_date

    new_df.replace('', 'NULL', inplace=True)
    replacement_values = {'Deceased Dissolved Date': {'NULL': '1890-01-01'},  # Replace NaN in 'column1' with 0
                        'Registration Date': {'NULL': '1890-01-01'},
                        'Date of Inclusion': {'NULL': '1890-01-01'},
                        'Date of Exclusion': {'NULL': '1890-01-01'},
                        'Updated On': {'NULL': '1890-01-01'}}  # Replace empty string in 'column2' with 'Unknown'

    # Apply fillna to specific columns with replacement values
    new_df.replace(replacement_values, inplace=True)
    
    return new_df