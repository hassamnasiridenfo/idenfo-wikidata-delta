import os
import re
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.utils import formataddr
from email import encoders


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

    # ── Find today's log file ─────────────────────────────────────
    log_file_path = None

    if delta_log_file_path and os.path.isdir(delta_log_file_path):
        for file_name in os.listdir(delta_log_file_path):
            if current_date in file_name and file_name.endswith(".log"):
                log_file_path = os.path.join(delta_log_file_path, file_name)
                break

    # ── Determine subject based on errors in log ──────────────────
    email_subject = normal_log_email_subject
    body_text = "No Delta log file found for today."

    if log_file_path:
        body_text = "Please find the attached log file for today's delta run."
        try:
            with open(log_file_path, "r", encoding="utf-8", errors="ignore") as f:
                log_content = f.read()
                if re.search(r"\berror\b", log_content, re.IGNORECASE):
                    email_subject = f"⚠️ {error_log_email_subject}"
        except Exception as e:
            print(f"⚠️ Could not read log file: {e}")

    # ── Build email using MIMEMultipart ───────────────────────────
    # MIMEMultipart is used instead of EmailMessage because
    # EmailMessage.add_alternative() + add_attachment() has a known
    # bug where attachment is silently dropped.
    msg = MIMEMultipart("mixed")
    msg["From"]    = formataddr((email_name, email_from))
    msg["To"]      = ", ".join(email_to) if isinstance(email_to, list) else email_to
    msg["Subject"] = f"{email_subject} — {current_date}"

    if email_cc:
        msg["Cc"] = ", ".join(email_cc) if isinstance(email_cc, list) else email_cc

    # ── HTML body ─────────────────────────────────────────────────
    html_content = f"""
    <html>
        <body>
            <p>{body_text}</p>
            <br>
            <p>Regards,<br>
            <i>Name Screening Support,<br>Idenfo</i></p>
        </body>
    </html>
    """
    msg.attach(MIMEText(html_content, "html"))

    # ── Attach log file ───────────────────────────────────────────
    if log_file_path:
        try:
            with open(log_file_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename={os.path.basename(log_file_path)}",
                )
                msg.attach(part)
            print(f"📎 Log file attached: {os.path.basename(log_file_path)}")
        except Exception as e:
            print(f"⚠️ Could not attach log file: {e}")
    else:
        print(f"⚠️ No log file found for date: {current_date}")
        print(f"   Looked in: {delta_log_file_path}")

    # ── Send email ────────────────────────────────────────────────
    recipients = []
    if isinstance(email_to, list):
        recipients.extend(email_to)
    else:
        recipients.append(email_to)

    if email_cc:
        if isinstance(email_cc, list):
            recipients.extend(email_cc)
        else:
            recipients.append(email_cc)

    try:
        with smtplib.SMTP(smtp_server, int(smtp_port)) as server:
            server.starttls()
            server.login(smtp_user, smtp_pswd)
            server.sendmail(email_from, recipients, msg.as_string())
        print(f"✅ Log email sent: '{msg['Subject']}'")
    except Exception as e:
        print(f"❌ Failed to send log email: {e}")