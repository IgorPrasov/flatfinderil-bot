"""
Weekly email reports for agents.
Sends HTML report with listing views every Sunday at 10:00.

Tries in order:
  1. SMTP SSL  port 465 (smtp.gmail.com)
  2. SMTP STARTTLS port 587
  3. Gmail REST API via urllib (HTTPS — always open on Railway)

Required env vars:
  SMTP_USER  — Gmail address (flatfinderilbot@gmail.com)
  SMTP_PASS  — Gmail App Password (16 chars, no spaces)
  SMTP_FROM  — display name (default: FlatFinderIL)
"""

import os
import ssl
import smtplib
import logging
import json
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import database as db

logger = logging.getLogger(__name__)

SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "FlatFinderIL")


def _build_html(report: dict) -> str:
    lang = report.get("lang", "ru")
    name  = report.get("owner_name") or f"Агент #{report['user_id']}"
    week  = report.get("week", "")
    total = report.get("total_listings", 0)
    views = report.get("total_views", 0)
    listings = report.get("listings", [])

    # Translations
    tr = {
        "ru": {
            "subtitle": "Еженедельный отчёт",
            "greeting": "Здравствуйте",
            "subgreeting": "Вот статистика ваших объявлений за прошедшую неделю.",
            "kpi1": "активных объявлений",
            "kpi2": "просмотров всего",
            "kpi3": "запросов контакта",
            "table_title": "📋 Все объявления",
            "col_title": "Название",
            "col_city": "Город",
            "col_rooms": "Комнат",
            "col_type": "Тип",
            "col_price": "Цена",
            "col_views": "👁 Просм.",
            "col_requests": "📞 Запросы",
            "no_listings": "Активных объявлений нет",
            "footer": "Отписаться от отчётов можно в настройках кабинета в боте.",
        },
        "en": {
            "subtitle": "Weekly Report",
            "greeting": "Hello",
            "subgreeting": "Here are the stats for your listings over the past week.",
            "kpi1": "active listings",
            "kpi2": "total views",
            "kpi3": "contact requests",
            "table_title": "📋 All listings",
            "col_title": "Title",
            "col_city": "City",
            "col_rooms": "Rooms",
            "col_type": "Type",
            "col_price": "Price",
            "col_views": "👁 Views",
            "col_requests": "📞 Requests",
            "no_listings": "No active listings",
            "footer": "Unsubscribe in bot settings.",
        },
        "he": {
            "subtitle": "דוח שבועי",
            "greeting": "שלום",
            "subgreeting": "הנה הסטטיסטיקה של המודעות שלך לשבוע האחרון.",
            "kpi1": "מודעות פעילות",
            "kpi2": "צפיות סה\"כ",
            "kpi3": "בקשות קשר",
            "table_title": "📋 כל המודעות",
            "col_title": "כותרת",
            "col_city": "עיר",
            "col_rooms": "חדרים",
            "col_type": "סוג",
            "col_price": "מחיר",
            "col_views": "👁 צפיות",
            "col_requests": "📞 בקשות",
            "no_listings": "אין מודעות פעילות",
            "footer": "לביטול המינוי — פנה לבוט.",
        },
    }.get(lang, {})
    if not tr:
        tr = {
            "subtitle": "Еженедельный отчёт",
            "greeting": "Здравствуйте",
            "subgreeting": "Вот статистика ваших объявлений за прошедшую неделю.",
            "kpi1": "активных объявлений",
            "kpi2": "просмотров всего",
            "kpi3": "запросов контакта",
            "table_title": "📋 Все объявления",
            "col_title": "Название",
            "col_city": "Город",
            "col_rooms": "Комнат",
            "col_type": "Тип",
            "col_price": "Цена",
            "col_views": "👁 Просм.",
            "col_requests": "📞 Запросы",
            "no_listings": "Активных объявлений нет",
            "footer": "Отписаться от отчётов можно в настройках кабинета в боте.",
        }

    deal_labels = {
        "ru": {"rent": "Аренда", "buy": "Продажа", "sublet": "Саблет", "commercial": "Коммерческая"},
        "en": {"rent": "Rent", "buy": "Sale", "sublet": "Sublet", "commercial": "Commercial"},
        "he": {"rent": "השכרה", "buy": "מכירה", "sublet": "סאבלט", "commercial": "מסחרי"},
    }.get(lang, {"rent": "Аренда", "buy": "Продажа", "sublet": "Саблет", "commercial": "Коммерческая"})

    rooms_suffix = {"ru": " комн.", "en": "", "he": " חד'"}.get(lang, "")

    rows = ""
    for l in listings:
        deal = deal_labels.get(l.get("deal_type", ""), l.get("deal_type", ""))
        rooms_str = f"{l['rooms']}{rooms_suffix}"
        rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0">{l['title']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;color:#555">{l['city']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;color:#555">{rooms_str}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;color:#555">{deal}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;text-align:right;color:#555">{l['price']:,} ₪</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;text-align:right;font-weight:600;color:#2AABEE">{l['views']}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;text-align:right;color:#4CAF8A">{l['view_requests']}</td>
        </tr>"""

    if not rows:
        rows = f'<tr><td colspan="7" style="padding:16px;text-align:center;color:#999">{tr["no_listings"]}</td></tr>'

    html_lang = lang if lang in ("ru", "en", "he") else "ru"
    dir_attr = ' dir="rtl"' if lang == "he" else ""

    return f"""<!DOCTYPE html>
<html lang="{html_lang}"{dir_attr}>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f5f5f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<div style="max-width:640px;margin:24px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08)">

  <!-- Header -->
  <div style="background:#2AABEE;padding:24px 28px">
    <div style="font-size:22px;font-weight:700;color:#fff">🏠 FlatFinderIL</div>
    <div style="font-size:13px;color:rgba(255,255,255,.85);margin-top:4px">{tr["subtitle"]} · {week}</div>
  </div>

  <!-- Greeting -->
  <div style="padding:24px 28px 0">
    <p style="font-size:15px;color:#333">{tr["greeting"]}, <b>{name}</b>!</p>
    <p style="font-size:13px;color:#666;margin-top:6px">{tr["subgreeting"]}</p>
  </div>

  <!-- KPI -->
  <div style="display:flex;gap:12px;padding:20px 28px;flex-wrap:wrap">
    <div style="flex:1;min-width:120px;background:#f0f8ff;border-radius:8px;padding:14px 16px;text-align:center">
      <div style="font-size:28px;font-weight:700;color:#2AABEE">{total}</div>
      <div style="font-size:11px;color:#888;margin-top:2px">{tr["kpi1"]}</div>
    </div>
    <div style="flex:1;min-width:120px;background:#eafaf1;border-radius:8px;padding:14px 16px;text-align:center">
      <div style="font-size:28px;font-weight:700;color:#4CAF8A">{views}</div>
      <div style="font-size:11px;color:#888;margin-top:2px">{tr["kpi2"]}</div>
    </div>
    <div style="flex:1;min-width:120px;background:#fff8e7;border-radius:8px;padding:14px 16px;text-align:center">
      <div style="font-size:28px;font-weight:700;color:#EF9F27">{sum(l['view_requests'] for l in listings)}</div>
      <div style="font-size:11px;color:#888;margin-top:2px">{tr["kpi3"]}</div>
    </div>
  </div>

  <!-- Table -->
  <div style="padding:0 28px 24px">
    <div style="font-size:13px;font-weight:600;color:#333;margin-bottom:10px">{tr["table_title"]}</div>
    <div style="overflow-x:auto">
      <table style="width:100%;border-collapse:collapse;font-size:12px">
        <thead>
          <tr style="background:#f8f8f4">
            <th style="padding:8px 12px;text-align:left;color:#888;font-weight:500;border-bottom:2px solid #e0e0da">{tr["col_title"]}</th>
            <th style="padding:8px 12px;text-align:left;color:#888;font-weight:500;border-bottom:2px solid #e0e0da">{tr["col_city"]}</th>
            <th style="padding:8px 12px;text-align:left;color:#888;font-weight:500;border-bottom:2px solid #e0e0da">{tr["col_rooms"]}</th>
            <th style="padding:8px 12px;text-align:left;color:#888;font-weight:500;border-bottom:2px solid #e0e0da">{tr["col_type"]}</th>
            <th style="padding:8px 12px;text-align:right;color:#888;font-weight:500;border-bottom:2px solid #e0e0da">{tr["col_price"]}</th>
            <th style="padding:8px 12px;text-align:right;color:#2AABEE;font-weight:500;border-bottom:2px solid #e0e0da">{tr["col_views"]}</th>
            <th style="padding:8px 12px;text-align:right;color:#4CAF8A;font-weight:500;border-bottom:2px solid #e0e0da">{tr["col_requests"]}</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
  </div>

  <!-- Footer -->
  <div style="background:#f8f8f4;padding:16px 28px;text-align:center;border-top:1px solid #e0e0da">
    <p style="font-size:11px;color:#aaa;margin:0">FlatFinderIL · Israel Real Estate</p>
    <p style="font-size:11px;color:#aaa;margin:4px 0 0">{tr["footer"]}</p>
  </div>

</div>
</body>
</html>"""


def _build_service_html(report: dict) -> str:
    lang = report.get("lang", "ru")
    name = report.get("owner_name") or f"#{report['user_id']}"
    week = report.get("week", "")
    total = report.get("total_services", 0)
    views = report.get("total_views", 0)
    services = report.get("services", [])

    tr = {
        "ru": {
            "subtitle": "Еженедельный отчёт по вашим услугам",
            "greeting": "Здравствуйте",
            "subgreeting": "Вот статистика ваших услуг за прошедшую неделю.",
            "kpi1": "активных услуг",
            "kpi2": "просмотров всего",
            "table_title": "📋 Ваши услуги",
            "col_type": "Тип",
            "col_region": "Регион",
            "col_city": "Город",
            "col_price": "Цена",
            "col_views": "👁 Просм.",
            "no_services": "Активных услуг нет",
            "footer": "Отписаться можно в боте",
        },
        "en": {
            "subtitle": "Weekly report on your services",
            "greeting": "Hello",
            "subgreeting": "Here are the stats for your services over the past week.",
            "kpi1": "active services",
            "kpi2": "total views",
            "table_title": "📋 Your services",
            "col_type": "Type",
            "col_region": "Region",
            "col_city": "City",
            "col_price": "Price",
            "col_views": "👁 Views",
            "no_services": "No active services",
            "footer": "Unsubscribe in bot settings",
        },
        "he": {
            "subtitle": "דוח שבועי על השירותים שלך",
            "greeting": "שלום",
            "subgreeting": "הנה הסטטיסטיקה של השירותים שלך לשבוע האחרון.",
            "kpi1": "שירותים פעילים",
            "kpi2": "צפיות סה\"כ",
            "table_title": "📋 השירותים שלך",
            "col_type": "סוג",
            "col_region": "אזור",
            "col_city": "עיר",
            "col_price": "מחיר",
            "col_views": "👁 צפיות",
            "no_services": "אין שירותים פעילים",
            "footer": "לביטול המינוי — פנה לבוט",
        },
    }.get(lang, {})
    if not tr:
        tr = {
            "subtitle": "Еженедельный отчёт по вашим услугам",
            "greeting": "Здравствуйте",
            "subgreeting": "Вот статистика ваших услуг за прошедшую неделю.",
            "kpi1": "активных услуг",
            "kpi2": "просмотров всего",
            "table_title": "📋 Ваши услуги",
            "col_type": "Тип",
            "col_region": "Регион",
            "col_city": "Город",
            "col_price": "Цена",
            "col_views": "👁 Просм.",
            "no_services": "Активных услуг нет",
            "footer": "Отписаться можно в боте",
        }

    svc_type_labels = {
        "ru": {"moving": "🚚 Перевозки", "packing": "📦 Упаковка", "cleaning": "🧹 Клининг"},
        "en": {"moving": "🚚 Moving", "packing": "📦 Packing", "cleaning": "🧹 Cleaning"},
        "he": {"moving": "🚚 הובלות", "packing": "📦 אריזה", "cleaning": "🧹 ניקיון"},
    }.get(lang, {"moving": "🚚 Перевозки", "packing": "📦 Упаковка", "cleaning": "🧹 Клининг"})

    region_labels = {
        "ru": {"north": "Север", "center": "Центр", "south": "Юг", "all": "Вся страна"},
        "en": {"north": "North", "center": "Center", "south": "South", "all": "All country"},
        "he": {"north": "צפון", "center": "מרכז", "south": "דרום", "all": "כל הארץ"},
    }.get(lang, {"north": "Север", "center": "Центр", "south": "Юг", "all": "Вся страна"})

    rows = ""
    for s in services:
        stype = svc_type_labels.get(s.get("service_type", ""), s.get("service_type", ""))
        region = region_labels.get(s.get("region", "all"), s.get("region", ""))
        city = s.get("city", "") or region
        price = s.get("price", 0)
        price_str = f"{price:,} ₪".replace(",", " ") if price else {"ru": "Договорная", "en": "Negotiable", "he": "לפי הסכמה"}.get(lang, "—")
        svc_views = s.get("views", 0)
        rows += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0">{stype}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;color:#555">{region}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;color:#555">{city}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;text-align:right;color:#555">{price_str}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;text-align:right;font-weight:600;color:#2AABEE">{svc_views}</td>
        </tr>"""

    if not rows:
        rows = f'<tr><td colspan="5" style="padding:16px;text-align:center;color:#999">{tr["no_services"]}</td></tr>'

    html_lang = lang if lang in ("ru", "en", "he") else "ru"
    dir_attr = ' dir="rtl"' if lang == "he" else ""

    return f"""<!DOCTYPE html>
<html lang="{html_lang}"{dir_attr}>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f5f5f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<div style="max-width:640px;margin:24px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08)">

  <!-- Header -->
  <div style="background:#2AABEE;padding:24px 28px">
    <div style="font-size:22px;font-weight:700;color:#fff">🏠 FlatFinderIL</div>
    <div style="font-size:13px;color:rgba(255,255,255,.85);margin-top:4px">{tr["subtitle"]} · {week}</div>
  </div>

  <!-- Greeting -->
  <div style="padding:24px 28px 0">
    <p style="font-size:15px;color:#333">{tr["greeting"]}, <b>{name}</b>!</p>
    <p style="font-size:13px;color:#666;margin-top:6px">{tr["subgreeting"]}</p>
  </div>

  <!-- KPI -->
  <div style="display:flex;gap:12px;padding:20px 28px;flex-wrap:wrap">
    <div style="flex:1;min-width:140px;background:#f0f8ff;border-radius:8px;padding:14px 16px;text-align:center">
      <div style="font-size:28px;font-weight:700;color:#2AABEE">{total}</div>
      <div style="font-size:11px;color:#888;margin-top:2px">{tr["kpi1"]}</div>
    </div>
    <div style="flex:1;min-width:140px;background:#eafaf1;border-radius:8px;padding:14px 16px;text-align:center">
      <div style="font-size:28px;font-weight:700;color:#4CAF8A">{views}</div>
      <div style="font-size:11px;color:#888;margin-top:2px">{tr["kpi2"]}</div>
    </div>
  </div>

  <!-- Table -->
  <div style="padding:0 28px 24px">
    <div style="font-size:13px;font-weight:600;color:#333;margin-bottom:10px">{tr["table_title"]}</div>
    <div style="overflow-x:auto">
      <table style="width:100%;border-collapse:collapse;font-size:12px">
        <thead>
          <tr style="background:#f8f8f4">
            <th style="padding:8px 12px;text-align:left;color:#888;font-weight:500;border-bottom:2px solid #e0e0da">{tr["col_type"]}</th>
            <th style="padding:8px 12px;text-align:left;color:#888;font-weight:500;border-bottom:2px solid #e0e0da">{tr["col_region"]}</th>
            <th style="padding:8px 12px;text-align:left;color:#888;font-weight:500;border-bottom:2px solid #e0e0da">{tr["col_city"]}</th>
            <th style="padding:8px 12px;text-align:right;color:#888;font-weight:500;border-bottom:2px solid #e0e0da">{tr["col_price"]}</th>
            <th style="padding:8px 12px;text-align:right;color:#2AABEE;font-weight:500;border-bottom:2px solid #e0e0da">{tr["col_views"]}</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
  </div>

  <!-- Footer -->
  <div style="background:#f8f8f4;padding:16px 28px;text-align:center;border-top:1px solid #e0e0da">
    <p style="font-size:11px;color:#aaa;margin:0">FlatFinderIL · Israel Real Estate</p>
    <p style="font-size:11px;color:#aaa;margin:4px 0 0">{tr["footer"]}</p>
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

    # ── Try 1: SMTP SSL port 465 ────────────────────────────────────────────
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx, timeout=15) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, email, msg.as_bytes())
        logger.info(f"[SSL-465] Report sent to {email}")
        return True
    except Exception as e1:
        logger.warning(f"[SSL-465] Failed: {e1} — trying STARTTLS 587")

    # ── Try 2: SMTP STARTTLS port 587 ───────────────────────────────────────
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, email, msg.as_bytes())
        logger.info(f"[STARTTLS-587] Report sent to {email}")
        return True
    except Exception as e2:
        logger.warning(f"[STARTTLS-587] Failed: {e2} — trying Gmail REST API")

    # ── Try 3: Resend HTTP API (port 443 — always open on Railway) ──────────
    # Requires RESEND_API_KEY env var (free at resend.com — 100 emails/day)
    resend_key = os.environ.get("RESEND_API_KEY", "")
    if resend_key:
        try:
            payload = json.dumps({
                "from":    f"{SMTP_FROM} <onboarding@resend.dev>",
                "to":      [email],
                "subject": msg["Subject"],
                "html":    html,
            }).encode()
            req = urllib.request.Request(
                "https://api.resend.com/emails",
                data=payload,
                headers={
                    "Authorization": f"Bearer {resend_key}",
                    "Content-Type":  "application/json",
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read())
            if result.get("id"):
                logger.info(f"[RESEND] Report sent to {email}, id={result['id']}")
                return True
        except Exception as e3:
            logger.error(f"[RESEND] Failed: {e3}")

    logger.error(f"[ALL-METHODS] Could not send to {email}. "
                 f"Errors: SSL={e1} | STARTTLS={e2} | "
                 f"{'No RESEND_API_KEY' if not resend_key else 'Resend failed'}")
    return False


def send_all_weekly_reports():
    """Send reports to all agents with email set. Called every Sunday 10:00."""
    agents = db.get_all_agent_emails()
    logger.info(f"Sending weekly reports to {len(agents)} agents")
    ok = 0
    for agent in agents:
        if send_report(agent["user_id"]):
            ok += 1
    logger.info(f"Weekly reports (agents): {ok}/{len(agents)} sent")

    ok2, total2 = send_all_service_reports()
    logger.info(f"Weekly reports (services): {ok2}/{total2} sent")

    return ok, len(agents)


def send_service_report(user_id: int) -> bool:
    """Send weekly report to a single service provider. Returns True on success."""
    if not SMTP_USER or not SMTP_PASS:
        logger.warning("SMTP_USER or SMTP_PASS not set — skipping service email")
        return False

    report = db.get_service_report_data(user_id)
    email = report.get("email")
    if not email:
        return False

    html = _build_service_html(report)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 FlatFinderIL — отчёт по услугам · {report['week']}"
    msg["From"]    = f"{SMTP_FROM} <{SMTP_USER}>"
    msg["To"]      = email
    msg.attach(MIMEText(html, "html", "utf-8"))

    # ── Try 1: SMTP SSL port 465 ────────────────────────────────────────────
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx, timeout=15) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, email, msg.as_bytes())
        logger.info(f"[SSL-465] Service report sent to {email}")
        return True
    except Exception as e1:
        logger.warning(f"[SSL-465] Service report failed: {e1} — trying STARTTLS 587")

    # ── Try 2: SMTP STARTTLS port 587 ───────────────────────────────────────
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, email, msg.as_bytes())
        logger.info(f"[STARTTLS-587] Service report sent to {email}")
        return True
    except Exception as e2:
        logger.warning(f"[STARTTLS-587] Service report failed: {e2} — trying Resend API")

    # ── Try 3: Resend HTTP API ──────────────────────────────────────────────
    resend_key = os.environ.get("RESEND_API_KEY", "")
    if resend_key:
        try:
            payload = json.dumps({
                "from":    f"{SMTP_FROM} <onboarding@resend.dev>",
                "to":      [email],
                "subject": msg["Subject"],
                "html":    html,
            }).encode()
            req = urllib.request.Request(
                "https://api.resend.com/emails",
                data=payload,
                headers={
                    "Authorization": f"Bearer {resend_key}",
                    "Content-Type":  "application/json",
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read())
            if result.get("id"):
                logger.info(f"[RESEND] Service report sent to {email}, id={result['id']}")
                return True
        except Exception as e3:
            logger.error(f"[RESEND] Service report failed: {e3}")

    logger.error(f"[ALL-METHODS] Could not send service report to {email}. "
                 f"Errors: SSL={e1} | STARTTLS={e2} | "
                 f"{'No RESEND_API_KEY' if not resend_key else 'Resend failed'}")
    return False


def send_all_service_reports():
    """Send reports to all service providers (movers/packers) with email set."""
    providers = db.get_all_service_emails()
    logger.info(f"Sending weekly service reports to {len(providers)} providers")
    ok = 0
    for p in providers:
        if send_service_report(p["user_id"]):
            ok += 1
    return ok, len(providers)


def _send_email_simple(to_email: str, subject: str, html: str) -> bool:
    """Shared helper: send an HTML email via SMTP or Resend."""
    if not to_email:
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{SMTP_FROM} <{SMTP_USER}>"
    msg["To"]      = to_email
    msg.attach(MIMEText(html, "html", "utf-8"))

    if SMTP_USER and SMTP_PASS:
        # Try SSL 465
        try:
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx, timeout=15) as s:
                s.login(SMTP_USER, SMTP_PASS)
                s.sendmail(SMTP_USER, to_email, msg.as_bytes())
            logger.info(f"[SSL-465] Sent to {to_email}: {subject}")
            return True
        except Exception as e1:
            logger.warning(f"[SSL-465] {e1}")
        # Try STARTTLS 587
        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as s:
                s.ehlo(); s.starttls(); s.login(SMTP_USER, SMTP_PASS)
                s.sendmail(SMTP_USER, to_email, msg.as_bytes())
            logger.info(f"[STARTTLS-587] Sent to {to_email}: {subject}")
            return True
        except Exception as e2:
            logger.warning(f"[STARTTLS-587] {e2}")

    # Try Resend
    resend_key = os.environ.get("RESEND_API_KEY", "")
    if resend_key:
        try:
            payload = json.dumps({
                "from": f"{SMTP_FROM} <onboarding@resend.dev>",
                "to": [to_email], "subject": subject, "html": html,
            }).encode()
            req = urllib.request.Request(
                "https://api.resend.com/emails", data=payload,
                headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read())
            if result.get("id"):
                logger.info(f"[RESEND] Sent to {to_email}: {subject}")
                return True
        except Exception as e3:
            logger.error(f"[RESEND] {e3}")
    return False


def send_contact_request_email(to_email: str, listing_title: str,
                                customer_username: str, customer_tg_id: int) -> bool:
    """Notify agent/owner that someone requested their contact via the bot."""
    subject = "📞 FlatFinderIL — Новый запрос контакта по объявлению"
    html = f"""<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:20px">
<div style="max-width:500px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1)">
  <div style="background:#2AABEE;padding:20px 28px">
    <h2 style="color:#fff;margin:0;font-size:18px">📞 Новый запрос на просмотр</h2>
  </div>
  <div style="padding:24px 28px">
    <p style="color:#333;font-size:14px">Пользователь <b>{customer_username}</b> (ID: {customer_tg_id})
    запросил ваш контакт по объявлению:</p>
    <div style="background:#f0f8ff;border-left:4px solid #2AABEE;padding:12px 16px;border-radius:4px;margin:16px 0">
      <b style="color:#333">{listing_title}</b>
    </div>
    <p style="color:#555;font-size:13px">Свяжитесь с ним в Telegram — он уже видит ваши контактные данные.</p>
  </div>
  <div style="background:#f8f8f4;padding:14px 28px;text-align:center;border-top:1px solid #eee">
    <p style="font-size:11px;color:#aaa;margin:0">FlatFinderIL · Israel Real Estate</p>
  </div>
</div></body></html>"""
    return _send_email_simple(to_email, subject, html)


def send_deal_closed_email(to_email: str, listing_title: str,
                            deal_price: int, listed_price: int,
                            tenant_username: str, deal_type: str = "rent") -> bool:
    """Notify agent/owner that a deal was successfully closed."""
    deal_label = "аренда" if deal_type == "rent" else "продажа"
    price_diff = deal_price - listed_price
    diff_html = ""
    if price_diff != 0 and listed_price > 0:
        sign  = "+" if price_diff > 0 else ""
        color = "#e74c3c" if price_diff > 0 else "#27ae60"
        diff_html = f'<span style="color:{color};font-size:12px"> ({sign}{price_diff:,} ₪ от выставленной цены)</span>'

    subject = f"🎉 FlatFinderIL — Сделка закрыта: {listing_title}"
    html = f"""<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:20px">
<div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1)">
  <div style="background:linear-gradient(135deg,#0f3460,#2AABEE);padding:24px 28px">
    <h2 style="color:#fff;margin:0;font-size:20px">🎉 Сделка закрыта!</h2>
    <p style="color:rgba(255,255,255,.8);margin:6px 0 0;font-size:13px">FlatFinderIL · {deal_label.capitalize()}</p>
  </div>
  <div style="padding:24px 28px">
    <p style="color:#333;font-size:14px;margin:0 0 16px">Поздравляем! Ваше объявление успешно закрыто:</p>
    <div style="background:#f0f8ff;border-left:4px solid #2AABEE;padding:14px 18px;border-radius:4px;margin-bottom:20px">
      <div style="font-size:16px;font-weight:700;color:#0f3460">{listing_title}</div>
      <div style="margin-top:8px;font-size:14px;color:#333">
        💰 Цена сделки: <b>{deal_price:,} ₪</b>{diff_html}
      </div>
      <div style="margin-top:4px;font-size:13px;color:#555">
        👤 Покупатель/арендатор: <b>{tenant_username}</b>
      </div>
    </div>
    <div style="background:#f0fff4;border-radius:8px;padding:12px 16px;font-size:13px;color:#27ae60">
      ✨ Вам начислено <b>+3 бонусных дня</b> подписки FlatFinderIL
    </div>
    <p style="color:#888;font-size:12px;margin-top:20px">
      Объявление деактивировано. Вы можете разместить новое через бот.
    </p>
  </div>
  <div style="background:#f8f8f4;padding:14px 28px;text-align:center;border-top:1px solid #eee">
    <p style="font-size:11px;color:#aaa;margin:0">FlatFinderIL · Israel Real Estate</p>
  </div>
</div></body></html>"""
    return _send_email_simple(to_email, subject, html)


def send_service_order_email(to_email: str, service_type: str,
                              customer_username: str, customer_tg_id: int) -> bool:
    """Notify service provider of a new order from the bot."""
    subject = f"✅ FlatFinderIL — Новый заказ: {service_type}"
    html = f"""<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:20px">
<div style="max-width:500px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1)">
  <div style="background:#4CAF50;padding:20px 28px">
    <h2 style="color:#fff;margin:0;font-size:18px">✅ Новый заказ услуги</h2>
  </div>
  <div style="padding:24px 28px">
    <p style="color:#333;font-size:14px">Пользователь <b>{customer_username}</b> (ID: {customer_tg_id})
    оформил заказ на вашу услугу:</p>
    <div style="background:#f0fff4;border-left:4px solid #4CAF50;padding:12px 16px;border-radius:4px;margin:16px 0">
      <b style="color:#333;font-size:16px">{service_type}</b>
    </div>
    <p style="color:#555;font-size:13px">Клиент ожидает вашего звонка. Свяжитесь с ним в Telegram как можно скорее.</p>
  </div>
  <div style="background:#f8f8f4;padding:14px 28px;text-align:center;border-top:1px solid #eee">
    <p style="font-size:11px;color:#aaa;margin:0">FlatFinderIL · Israel Real Estate</p>
  </div>
</div></body></html>"""
    return _send_email_simple(to_email, subject, html)
