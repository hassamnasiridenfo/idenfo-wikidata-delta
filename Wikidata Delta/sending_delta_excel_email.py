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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def send_emails(email_from, email_name, email_to, email_cc, smtp_server, smtp_port, smtp_user, smtp_pswd, subject, folder_paths):
    latest_delta_date = datetime.now().date().strftime("%Y-%m-%d")

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
                    unique_source_lists = ", ".join(map(str, df['Source List'].dropna().unique())) if 'Source List' in df.columns else "N/A"
                    total_records = len(df)

                    row_color = "#ffffff" if counter % 2 != 0 else "#f9f9f9"

                    table_rows.append(f"""
                        <tr style="background-color: {row_color};">
                            <td>{counter}</td>
                            <td>{unique_scraper_tags}</td>
                            <td>{unique_source_lists}</td>
                            <td style="text-align: right;">{total_records}</td>
                        </tr>
                    """)
                    counter += 1
                except Exception as e:
                    table_rows.append(f"""
                        <tr style="background-color: #ffe6e6;">
                            <td>{counter}</td>
                            <td colspan="3">Could not read file '{file}': {e}</td>
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
                <th>Source Lists</th>
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
