"""
Weekly email reports for agents.
Sends HTML report with listing views every Sunday at 10:00.

Required env vars:
  SMTP_HOST  (default: smtp.gmail.com)
  SMTP_PORT  (default: 587)
  SMTP_USER  — sender Gmail address
  SMTP_PASS  — Gmail App Password (not regular password)
  SMTP_FROM  — display name (default: FlatFinderIL)
"""

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import database as db

logger = logging.getLogger(__name__)

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "FlatFinderIL")


def _build_html(report: dict) -> str:
    name  = report.get("owner_name") or f"Агент #{report['user_id']}"
    week  = report.get("week", "")
    total = report.get("total_listings", 0)
    views = report.get("total_views", 0)
    listings = report.get("listings", [])

    rows = ""
    for l in listings:
        deal = {"rent": "Аренда", "buy": "Продажа", "sublet": "Сублет", "commercial": "Коммерческая"}.get(l["deal_type"], l["deal_type"])
        rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0">{l['title']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;color:#555">{l['city']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;color:#555">{l['rooms']} комн.</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;color:#555">{deal}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;text-align:right;color:#555">{l['price']:,} ₪</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;text-align:right;font-weight:600;color:#2AABEE">{l['views']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;text-align:right;color:#4CAF8A">{l['view_requests']}</td>
        </tr>"""

    if not rows:
        rows = '<tr><td colspan="7" style="padding:16px;text-align:center;color:#999">Активных объявлений нет</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f5f5f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<div style="max-width:640px;margin:24px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08)">

  <!-- Header -->
  <div style="background:#2AABEE;padding:24px 28px">
    <div style="font-size:22px;font-weight:700;color:#fff">🏠 FlatFinderIL</div>
    <div style="font-size:13px;color:rgba(255,255,255,.85);margin-top:4px">Еженедельный отчёт · {week}</div>
  </div>

  <!-- Greeting -->
  <div style="padding:24px 28px 0">
    <p style="font-size:15px;color:#333">Здравствуйте, <b>{name}</b>!</p>
    <p style="font-size:13px;color:#666;margin-top:6px">Вот статистика ваших объявлений за прошедшую неделю.</p>
  </div>

  <!-- KPI -->
  <div style="display:flex;gap:12px;padding:20px 28px;flex-wrap:wrap">
    <div style="flex:1;min-width:120px;background:#f0f8ff;border-radius:8px;padding:14px 16px;text-align:center">
      <div style="font-size:28px;font-weight:700;color:#2AABEE">{total}</div>
      <div style="font-size:11px;color:#888;margin-top:2px">активных объявлений</div>
    </div>
    <div style="flex:1;min-width:120px;background:#eafaf1;border-radius:8px;padding:14px 16px;text-align:center">
      <div style="font-size:28px;font-weight:700;color:#4CAF8A">{views}</div>
      <div style="font-size:11px;color:#888;margin-top:2px">просмотров всего</div>
    </div>
    <div style="flex:1;min-width:120px;background:#fff8e7;border-radius:8px;padding:14px 16px;text-align:center">
      <div style="font-size:28px;font-weight:700;color:#EF9F27">{sum(l['view_requests'] for l in listings)}</div>
      <div style="font-size:11px;color:#888;margin-top:2px">запросов контакта</div>
    </div>
  </div>

  <!-- Table -->
  <div style="padding:0 28px 24px">
    <div style="font-size:13px;font-weight:600;color:#333;margin-bottom:10px">📋 Все объявления</div>
    <div style="overflow-x:auto">
      <table style="width:100%;border-collapse:collapse;font-size:12px">
        <thead>
          <tr style="background:#f8f8f4">
            <th style="padding:8px 12px;text-align:left;color:#888;font-weight:500;border-bottom:2px solid #e0e0da">Название</th>
            <th style="padding:8px 12px;text-align:left;color:#888;font-weight:500;border-bottom:2px solid #e0e0da">Город</th>
            <th style="padding:8px 12px;text-align:left;color:#888;font-weight:500;border-bottom:2px solid #e0e0da">Комнат</th>
            <th style="padding:8px 12px;text-align:left;color:#888;font-weight:500;border-bottom:2px solid #e0e0da">Тип</th>
            <th style="padding:8px 12px;text-align:right;color:#888;font-weight:500;border-bottom:2px solid #e0e0da">Цена</th>
            <th style="padding:8px 12px;text-align:right;color:#2AABEE;font-weight:500;border-bottom:2px solid #e0e0da">👁 Просм.</th>
            <th style="padding:8px 12px;text-align:right;color:#4CAF8A;font-weight:500;border-bottom:2px solid #e0e0da">📞 Запросы</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
  </div>

  <!-- Footer -->
  <div style="background:#f8f8f4;padding:16px 28px;text-align:center;border-top:1px solid #e0e0da">
    <p style="font-size:11px;color:#aaa;margin:0">FlatFinderIL · Поиск недвижимости в Израиле</p>
    <p style="font-size:11px;color:#aaa;margin:4px 0 0">Отписаться от отчётов можно в настройках кабинета в боте.</p>
  </div>

</div>
</body>
</html>"""


def send_report(user_id: int) -> bool:
    """Send weekly report to a single agent. Returns True on success."""
    if not SMTP_USER or not SMTP_PASS:
        logger.warning("SMTP_USER or SMTP_PASS not set — skipping email")
        return False

    report = db.get_agent_report_data(user_id)
    email = report.get("email")
    if not email:
        return False

    html = _build_html(report)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 Отчёт FlatFinderIL · {report['week']}"
    msg["From"]    = f"{SMTP_FROM} <{SMTP_USER}>"
    msg["To"]      = email
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, email, msg.as_bytes())
        logger.info(f"Weekly report sent to {email} (user {user_id})")
        return True
    except Exception as e:
        logger.error(f"Failed to send report to {email}: {e}")
        return False


def send_all_weekly_reports():
    """Send reports to all agents with email set. Called every Sunday 10:00."""
    agents = db.get_all_agent_emails()
    logger.info(f"Sending weekly reports to {len(agents)} agents")
    ok = 0
    for agent in agents:
        if send_report(agent["user_id"]):
            ok += 1
    logger.info(f"Weekly reports: {ok}/{len(agents)} sent")
    return ok, len(agents)
