import logging
import smtplib
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import HTTPException

from app.config import SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USERNAME, SMTP_USE_TLS

log = logging.getLogger(__name__)

_EVENT_META = {
    "sent":      ("📤 Email Yuborildi",   "#6366f1"),
    "opened":    ("📨 Email O'qildi",     "#a855f7"),
    "viewed":    ("👁  Forma Ochildi",    "#f59e0b"),
    "submitted": ("✅ Forma To'ldirildi", "#10b981"),
}


def smtp_ready() -> bool:
    return bool(SMTP_HOST and SMTP_PORT and SMTP_FROM)


def _open_smtp() -> smtplib.SMTP:
    server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=25)
    server.ehlo()
    if SMTP_USE_TLS:
        server.starttls()
        server.ehlo()
    if SMTP_USERNAME:
        password = SMTP_PASSWORD.replace(" ", "")
        server.login(SMTP_USERNAME, password)
    return server


def _make_message(to_email: str, subject: str, html_body: str) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    return msg


def send_html_email(*, to_email: str, subject: str, html_body: str) -> None:
    if not smtp_ready():
        raise HTTPException(status_code=400, detail="SMTP is not configured")
    msg = _make_message(to_email, subject, html_body)
    server = _open_smtp()
    try:
        server.sendmail(SMTP_FROM, [to_email], msg.as_string())
    finally:
        server.quit()


def notify_admin(
    *,
    event_type: str,
    recipient_email: str,
    ip_address: str = "—",
    user_agent: str = "—",
    extra: dict | None = None,
) -> None:
    if not smtp_ready():
        return

    # "sent" notification runs right after employee email — wait 4s to avoid Gmail throttle
    if event_type == "sent":
        time.sleep(4)

    label, color = _EVENT_META.get(event_type, (event_type, "#6366f1"))
    now = datetime.now().strftime("%d.%m.%Y  %H:%M:%S")
    subject = f"{label} → {recipient_email}"

    def row(key: str, val: str, mono: bool = False) -> str:
        mono_style = "font-family:monospace;font-size:12px;" if mono else ""
        return f"""
        <tr>
          <td style="padding:12px 16px 12px 28px;color:#64748b;font-size:13px;
                     border-bottom:1px solid #1e293b;width:36%;vertical-align:top">{key}</td>
          <td style="padding:12px 28px 12px 16px;color:#f1f5f9;font-size:13px;font-weight:600;
                     border-bottom:1px solid #1e293b;word-break:break-word;{mono_style}">{val}</td>
        </tr>"""

    ua_short = (user_agent[:100] + "…") if len(user_agent) > 100 else user_agent
    extra_rows = "".join(row(k, str(v)) for k, v in (extra or {}).items())

    body = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body style="background:#05070f;margin:0;padding:32px 16px;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<div style="max-width:560px;margin:0 auto">

  <!-- Event badge -->
  <div style="margin-bottom:18px">
    <span style="display:inline-block;background:{color}20;color:{color};
                 border:1px solid {color}44;padding:6px 16px;border-radius:999px;
                 font-size:13px;font-weight:700;letter-spacing:.05em">
      {label}
    </span>
  </div>

  <!-- Card -->
  <div style="background:#0d1117;border:1px solid #1e293b;border-radius:18px;
              overflow:hidden;box-shadow:0 20px 40px rgba(0,0,0,.5)">

    <div style="height:3px;background:linear-gradient(90deg,{color},{color}55)"></div>

    <!-- Hodim email — ASOSIY MA'LUMOT -->
    <div style="padding:24px 28px 16px;border-bottom:1px solid #1e293b">
      <p style="margin:0 0 4px;color:#475569;font-size:11px;font-weight:700;
                letter-spacing:.1em;text-transform:uppercase">Hodim email</p>
      <p style="margin:0;color:#818cf8;font-size:20px;font-weight:700;
                word-break:break-all">{recipient_email}</p>
    </div>

    <!-- Info jadval -->
    <table style="width:100%;border-collapse:collapse">
      {row("📅 Sana va vaqt", now)}
      {row("🌐 IP manzil", ip_address, mono=True)}
      {row("💻 Brauzer / Qurilma", ua_short)}
      {extra_rows}
    </table>

    <div style="padding:16px 28px;background:#080b12">
      <p style="margin:0;color:#1e293b;font-size:11px">
        Contact Sender · avtomatik bildirishnoma
      </p>
    </div>
  </div>

</div>
</body></html>"""

    try:
        msg = _make_message(SMTP_FROM, subject, body)
        server = _open_smtp()
        try:
            server.sendmail(SMTP_FROM, [SMTP_FROM], msg.as_string())
        finally:
            server.quit()
        log.info("notify_admin OK: %s -> %s", event_type, recipient_email)
    except Exception as exc:
        log.error("notify_admin FAILED: %s -> %s | %s", event_type, recipient_email, exc)
