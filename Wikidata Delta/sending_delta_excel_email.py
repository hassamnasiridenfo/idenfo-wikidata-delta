import os
import shutil
import pandas as pd
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr

from mysql_connection_dictionary import create_mysql_connection_dictionary

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


DB_TOTALS_QUERY = """
    SELECT SUM(`status` = 1) AS active,
           SUM(`status` = 0) AS inactive,
           COUNT(*)          AS total
    FROM main
"""

# breakdown limited to THIS project's PEP lists
# (scraper_tag ending in "_gen"; the `main` table is shared with other projects).
# RCA rows (list_category 'Relative Close Associate') are folded into the
# Politically Exposed Person count -- list_category is dropped from GROUP BY and
# reported as 'Politically Exposed Person' so each scraper_tag is one combined row.
DELTA_BREAKDOWN_QUERY = """
    SELECT scraper_tag, category AS list_name, source_list,
           'Politically Exposed Person' AS list_category,
           SUM(`status` = 1) AS status_1,
           SUM(`status` = 0) AS status_0,
           COUNT(*)          AS total
    FROM main
    WHERE updated_on = %s AND scraper_tag LIKE %s
    GROUP BY scraper_tag, category, source_list
    ORDER BY scraper_tag
"""


def _fetch_db_totals(db_config):
    if not db_config:
        return None
    cnx = cursor = None
    try:
        cnx, cursor = create_mysql_connection_dictionary(**db_config)
        if not cnx or not cursor:
            return None
        cursor.execute(DB_TOTALS_QUERY)
        row = cursor.fetchone() or {}
        return {k: int(row.get(k) or 0) for k in ("active", "inactive", "total")}
    except Exception as e:
        print(f"⚠️ Could not read record totals from MySQL: {e}")
        return None
    finally:
        try:
            if cursor:
                cursor.close()
            if cnx:
                cnx.close()
        except Exception:
            pass


def _fetch_delta_breakdown(db_config, delta_date):
    if not db_config:
        return None
    cnx = cursor = None
    try:
        cnx, cursor = create_mysql_connection_dictionary(**db_config)
        if not cnx or not cursor:
            return None
        # "%_gen" limits to this project's PEP scraper_tags
        cursor.execute(DELTA_BREAKDOWN_QUERY, (delta_date, "%_gen"))
        rows = cursor.fetchall() or []
        return [{
            "scraper_tag":   r.get("scraper_tag") or "",
            # List Name comes from `category` (e.g. "General Bahrain")
            "list_name":     r.get("list_name") or "",
            "source_list":   r.get("source_list") or "",
            "list_category": r.get("list_category") or "",
            "status_1":      int(r.get("status_1") or 0),
            "status_0":      int(r.get("status_0") or 0),
            "total":         int(r.get("total") or 0),
        } for r in rows]
    except Exception as e:
        print(f"⚠️ Could not read delta breakdown from MySQL: {e}")
        return None
    finally:
        try:
            if cursor:
                cursor.close()
            if cnx:
                cnx.close()
        except Exception:
            pass


def send_emails(email_from, email_name, email_to, email_cc, smtp_server, smtp_port, smtp_user, smtp_pswd, subject, folder_paths, db_config=None):
    latest_delta_date = datetime.now().date().strftime("%Y-%m-%d")
    db_totals = _fetch_db_totals(db_config)
    delta_breakdown = _fetch_delta_breakdown(db_config, latest_delta_date)

    total_excel = []
    table_rows = []
    counter = 1

    # Collect all .xlsx files matching the DELTA date
    for folder_path in folder_paths:
        if not os.path.isdir(folder_path):
            continue  # skip invalid folder

        for file in os.listdir(folder_path):
            if f"_DELTA_{latest_delta_date}" in file and file.endswith(".xlsx"):
                file_path = os.path.join(folder_path, file)
                total_excel.append(file_path)

                # Copy to dated folder (your shutil part kept)
                newpath = os.path.join(BASE_DIR, 'Delta Record', f'Delta of {latest_delta_date}').replace("\\", "/")
                if not os.path.exists(newpath):
                    os.makedirs(newpath)
                shutil.copy(file_path, newpath)

                # Try reading and summarizing file
                try:
                    df = pd.read_excel(file_path)

                    unique_scraper_tags = ", ".join(map(str, df['Scraper Tag'].dropna().unique())) if 'Scraper Tag' in df.columns else "N/A"
                    unique_list_name = ", ".join(map(str, df['Category'].dropna().unique())) if 'Category' in df.columns else "N/A"
                    unique_source_lists = ", ".join(map(str, df['Source List'].dropna().unique())) if 'Source List' in df.columns else "N/A"
                    unique_list_categories = ", ".join(map(str, df['List Category'].dropna().unique())) if 'List Category' in df.columns else "N/A" 
                    total_records = len(df)

                    row_color = "#ffffff" if counter % 2 != 0 else "#f9f9f9"

                    table_rows.append(f"""
                        <tr style="background-color: {row_color};">
                            <td>{counter}</td>
                            <td>{unique_scraper_tags}</td>
                            <td>{unique_list_name}</td>
                            <td>{unique_source_lists}</td>
                            <td>{unique_list_categories}</td>
                            <td style="text-align: right;">{total_records}</td>
                        </tr>
                    """)
                    counter += 1
                except Exception as e:
                    table_rows.append(f"""
                        <tr style="background-color: #ffe6e6;">
                            <td>{counter}</td>
                            <td colspan="4">Could not read file '{file}': {e}</td>
                        </tr>   
                    """)
                    counter += 1

    # Build HTML body
    if table_rows:
        html_body = f"""
        <p>Please find attached the Delta file(s). These file(s) contain all the records that have been newly updated. Kindly test them and let us know if there are any issues. You will also find the insertion summary below.</p>
        <br>
        <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; font-family: Arial, sans-serif; font-size: 14px;">
            <tr style="background-color: #f2f2f2; font-weight: bold;">
                <th>#</th>
                <th>Scraper Tags</th>
                <th>List Name</th>
                <th>Source Lists</th>
                <th>List Category</th>
                <th>Total Records</th>
            </tr>
            {''.join(table_rows)}
        </table>
        <br>
        <p><b>NOTE:</b> This is an auto-generated email. If you reply, please make sure to keep the NameScreening team members in CC.</p>
        <br><br>
        <p>Regards,<br><i>NAME SCREENING SUPPORT,<br>IDENFO</i></p>
        <br><br>
        """
    else:
        html_body = f"""
        <p>No Delta Found for {latest_delta_date}.</p>
        <p><b>NOTE:</b> This is an auto-generated email. If you reply, please make sure to keep the NameScreening team members in CC.</p>
        <br><br>
        <p>Regards,<br><i>NAME SCREENING SUPPORT,<br>IDENFO</i></p>
        <br><br>
        """

    # table with a per-scraper_tag Status 1 / Status 0 breakdown + DB totals
    # (requested format). Falls back to the file-based table above if the DB is
    # down or db_config is not passed.
    if delta_breakdown is not None:
        _bd_rows = []
        for _i, _r in enumerate(delta_breakdown):
            _shade = "#ffffff" if _i % 2 == 0 else "#f9f9f9"
            _bd_rows.append(f"""
                        <tr style="background-color: {_shade};">
                            <td>{_r['scraper_tag']}</td>
                            <td>{_r['list_name']}</td>
                            <td>{_r['source_list']}</td>
                            <td>{_r['list_category']}</td>
                            <td style="text-align: right;">{_r['status_1']:,}</td>
                            <td style="text-align: right;">{_r['status_0']:,}</td>
                            <td style="text-align: right;">{_r['total']:,}</td>
                        </tr>""")
        _d_s1 = sum(_r["status_1"] for _r in delta_breakdown)
        _d_s0 = sum(_r["status_0"] for _r in delta_breakdown)
        _d_tot = sum(_r["total"] for _r in delta_breakdown)
        _delta_total_row = f"""
                        <tr style="font-weight: bold;">
                            <td colspan="4" style="text-align: left;">Total Delta Records for {latest_delta_date}</td>
                            <td style="text-align: right;">{_d_s1:,}</td>
                            <td style="text-align: right;">{_d_s0:,}</td>
                            <td style="text-align: right;">{_d_tot:,}</td>
                        </tr>"""

        def _db_row7(label, value, shade):
            return f"""
                        <tr style="font-weight: bold; background-color: {shade};">
                            <td colspan="6" style="text-align: left;">{label}</td>
                            <td style="text-align: right;">{value:,}</td>
                        </tr>"""

        _db_rows7 = ""
        _db_note = ""
        if db_totals:
            _db_rows7 = (
                _db_row7("Total Active (Status 1) Records in the MySQL", db_totals["active"], "#eef7ee")
                + _db_row7("Total In-Active (Status 0) Records in the MySQL", db_totals["inactive"], "#fdf3ec")
                + _db_row7("Total Records", db_totals["total"], "#eceff7")
            )
            _counted = db_totals["active"] + db_totals["inactive"]
            if _counted != db_totals["total"]:
                _db_note = (
                    f"<p><i>Note: {db_totals['total'] - _counted} record(s) have a status "
                    f"other than 0 or 1 and are counted only in Total Records.</i></p>"
                )

        _intro = (
            "<p>Please find attached the Delta file(s). These file(s) contain all the records that have been newly updated. Kindly test them and let us know if there are any issues. You will also find the insertion summary below.</p>"
            if _bd_rows
            else f"<p>No Delta Found for {latest_delta_date}.</p>"
        )
        html_body = f"""
        {_intro}
        <br>
        <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse; font-family: Arial, sans-serif; font-size: 14px;">
            <tr style="background-color: #f2f2f2; font-weight: bold;">
                <th style="text-align: left;">Scraper Tags</th>
                <th style="text-align: left;">List Name</th>
                <th style="text-align: left;">Source Lists</th>
                <th style="text-align: left;">List Category</th>
                <th style="text-align: right;">Status 1</th>
                <th style="text-align: right;">Status 0</th>
                <th style="text-align: right;">Total Records</th>
            </tr>
            {''.join(_bd_rows)}
            {_delta_total_row if _bd_rows else ''}
            {_db_rows7}
        </table>
        {_db_note}
        <br>
        <p><b>NOTE:</b> This is an auto-generated email. If you reply, please make sure to keep the NameScreening team members in CC.</p>
        <br><br>
        <p>Regards,<br><i>NAME SCREENING SUPPORT,<br>IDENFO</i></p>
        <br><br>
        """

    # Create MIME multipart message
    msg = MIMEMultipart()
    msg['From'] = formataddr((email_name, email_from))
    msg['To'] = ', '.join(email_to)
    msg['Cc'] = ', '.join(email_cc)
    msg['Subject'] = f'{subject} of {latest_delta_date}'

    # Attach HTML body
    msg.attach(MIMEText(html_body, 'html'))

    # Attach all Excel files
    for filepath in total_excel:
        try:
            with open(filepath, 'rb') as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename="{os.path.basename(filepath)}"'
            )
            msg.attach(part)
        except Exception as e:
            print(f"Error attaching file {filepath}: {e}")

    # Combine recipients
    all_recipients = email_to + email_cc

    # Send email once
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pswd)
            server.sendmail(email_from, all_recipients, msg.as_string())
        print(f"✅ Delta report email sent successfully for date: '{latest_delta_date}'.")
    except Exception as e:
        print(f"❌ Error while sending Delta report email: {e} for date: '{latest_delta_date}'")
