import os
import re
from datetime import datetime
import smtplib
from email.message import EmailMessage
from email.utils import formataddr


def send_main_delta_logs(
    email_from,
    email_name,
    email_to,
    email_cc,
    smtp_server,
    smtp_port,
    smtp_user,
    smtp_pswd,
    normal_log_email_subject,
    error_log_email_subject,
    delta_log_file_path,
):

    current_date = datetime.now().strftime("%Y-%m-%d")

    # Find today's log file
    log_file_path = None
    for file_name in os.listdir(delta_log_file_path):
        if f"Delta_main_file{current_date}" in file_name and file_name.endswith(".log"):
            log_file_path = os.path.join(delta_log_file_path, file_name)
            break

    # Default subject and emoji
    email_subject = normal_log_email_subject

    body_text = "No Delta logs file found!"
    signature_html = "<i>Name Screening Support,<br>Idenfo</i>"

    # If log file exists, attach and check for errors
    if log_file_path:
        body_text = "Please find the attached log file."

        try:
            with open(log_file_path, "r", encoding="utf-8", errors="ignore") as f:
                log_content = f.read()
                # Check for the word "error" as a complete word
                if re.search(r"\berror\b", log_content, re.IGNORECASE):
                    email_subject = f"⚠️ {error_log_email_subject}"
        except Exception as e:
            print(f"⚠️ Could not read log file for error checking: {e}")

    # Create the email
    msg = EmailMessage()
    msg["From"] = formataddr((email_name, email_from))
    msg["To"] = ", ".join(email_to) if isinstance(email_to, list) else email_to
    if email_cc:
        msg["Cc"] = ", ".join(email_cc) if isinstance(email_cc, list) else email_cc
    msg["Subject"] = f"{email_subject} of {current_date}"

    # Add HTML content with italic signature
    html_content = f"""
    <html>
        <body>
            <p>{body_text}</p>
            <br>
            <p>Regards,<br>{signature_html}</p>
        </body>
    </html>
    """
    msg.add_alternative(html_content, subtype="html")

    # Attach log file if found
    if log_file_path:
        try:
            with open(log_file_path, "rb") as f:
                file_data = f.read()
                file_name = os.path.basename(log_file_path)
                msg.add_attachment(
                    file_data,
                    maintype="application",
                    subtype="octet-stream",
                    filename=file_name,
                )
        except Exception as e:
            print(f"⚠️ Could not attach log file: {e}")

    # Send email
    recipients = email_to + email_cc if email_cc else email_to
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pswd)
            server.send_message(msg, from_addr=email_from, to_addrs=recipients)
        print(
            f"✅ Email sent successfully with subject: '{msg['Subject']}' for date: '{current_date}'"
        )
    except Exception as e:
        print(f"❌ Failed to send email: {e} for date: '{current_date}'")
