# Emails the URL -> ID images Excel(s) for manual S3 upload
# Created By Hassam nasir
#
# Mirrors sending_delta_excel_email.py but:
#   - scans the per-tag folders for files named *_images_url_<date>.xlsx
#   - goes to a SEPARATE recipient list (image_email_to / image_email_cc in .env)
#   - has its own subject (image_email_subject)
#
# Each row in the attached Excel has two columns: URL (Wikidata image link) and
# ID (the record's customer id). Whoever receives it uploads each image manually
# to the S3 bucket as <scraper_tag>/<ID>.jpg.

import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def send_image_url_emails(email_from, email_name, email_to, email_cc,
                          smtp_server, smtp_port, smtp_user, smtp_pswd,
                          subject, folder_paths):
    """Find today's *_images_url_<date>.xlsx file(s) in folder_paths and email them."""
    latest_date = datetime.now().date().strftime("%Y-%m-%d")

    attachments = []
    for folder_path in folder_paths:
        if not os.path.isdir(folder_path):
            continue
        for file in os.listdir(folder_path):
            if "_images_url_" in file and latest_date in file and file.endswith(".xlsx"):
                attachments.append(os.path.join(folder_path, file))

    # Build HTML body
    if attachments:
        html_body = f"""
        <p>Please find attached the image <b>URL</b> Excel file(s) for {latest_date}.</p>
        <p><b>NOTE:</b> This is an auto-generated email. If you reply, please make sure to keep the
        NameScreening team members in CC.</p>
        <br><br>
        <p>Regards,<br><i>NAME SCREENING SUPPORT,<br>IDENFO</i></p>
        <br><br>
        """
    else:
        html_body = f"""
        <p>No image URLs to upload for {latest_date}.</p>
        <p><b>NOTE:</b> This is an auto-generated email. If you reply, please make sure to keep the
        NameScreening team members in CC.</p>
        <br><br>
        <p>Regards,<br><i>NAME SCREENING SUPPORT,<br>IDENFO</i></p>
        <br><br>
        """

    msg = MIMEMultipart()
    msg['From'] = formataddr((email_name, email_from))
    msg['To'] = ', '.join(email_to)
    if email_cc:
        msg['Cc'] = ', '.join(email_cc)
    msg['Subject'] = f'{subject} of {latest_date}'
    msg.attach(MIMEText(html_body, 'html'))

    # Attach all matching Excel files
    for filepath in attachments:
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

    all_recipients = list(email_to) + list(email_cc)

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pswd)
            server.sendmail(email_from, all_recipients, msg.as_string())
        print(f"✅ Images-URL email sent successfully for date: '{latest_date}'.")
    except Exception as e:
        print(f"❌ Error while sending Images-URL email: {e} for date: '{latest_date}'")
