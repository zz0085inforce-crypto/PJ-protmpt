"""透過 SMTP 寄送 HTML 信件,逐一收件回報結果。"""
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .config import get_settings


def send_html(recipients: list[str], subject: str, body_html: str) -> list[dict]:
    """對每位收件人個別寄送(避免互相看到彼此),回傳 [{email, ok, error}]。"""
    s = get_settings()
    results: list[dict] = []
    context = ssl.create_default_context()

    # port 465 用 SMTP_SSL;587 用 starttls
    if s.smtp_port == 465:
        server = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, context=context)
    else:
        server = smtplib.SMTP(s.smtp_host, s.smtp_port)
        server.starttls(context=context)
    try:
        server.login(s.smtp_user, s.smtp_password)
        for to in recipients:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = s.mail_from
                msg["To"] = to
                msg.attach(MIMEText(body_html, "html", "utf-8"))
                server.sendmail(s.mail_from, [to], msg.as_string())
                results.append({"email": to, "ok": True, "error": ""})
            except Exception as e:  # noqa: BLE001
                results.append({"email": to, "ok": False, "error": str(e)})
    finally:
        server.quit()
    return results
