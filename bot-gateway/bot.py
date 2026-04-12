import asyncio
import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, PreCheckoutQueryHandler, filters,
)
from config import BOT_TOKEN
from handlers import (
    start, handle_menu, my_listings, handle_unknown, agent_cabinet,
    refer_command, handle_edit_text,
    handle_pre_checkout, handle_successful_payment,
    cmd_testpay,
)
from search_handler import SearchHandler
from listing_handler import ListingHandler
from commercial_handler import CommercialHandler
from service_handler import ServiceHandler
from crm_handler import CRMHandler

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Shared references set in main() so the HTTP thread can send messages
_bot_app = None
_bot_loop = None

def fix_city_migration():
    """Migration: re-detect city+district for ALL listings using description text."""
    try:
        import json
        from telegram_parser import detect_city, DISTRICT_MAP
        from database import DB_FILE
        db_path = DB_FILE
        with open(db_path) as f:
            db = json.load(f)
        fixed = 0
        for listing in db.get("listings", {}).values():
            # Skip manually added listings (they have correct data)
            if listing.get("source") == "manual":
                continue
            city = listing.get("city", "")
            desc = listing.get("description", "") or listing.get("title", "")
            if desc:
                detected = detect_city(desc)
                if detected and detected != city:
                    listing["city"] = detected
                    city = detected
                    fixed += 1
            # Fix district to match city
            correct_district = DISTRICT_MAP.get(city)
            if correct_district and listing.get("district") != correct_district:
                listing["district"] = correct_district
                fixed += 1
        if fixed:
            with open(db_path, "w") as f:
                json.dump(db, f, ensure_ascii=False, indent=2)
            logger.info(f"City/district migration: fixed {fixed} fields")
    except Exception as e:
        logger.warning(f"City migration failed: {e}")




async def cmd_testemail(update: Update, context):
    """Send test weekly report to the calling user (if they have email set)."""
    user_id = update.effective_user.id
    await update.message.reply_text("⏳ Отправляю тестовый отчёт...")
    try:
        import database as db
        from email_reporter import send_report, send_all_weekly_reports, send_all_service_reports
        email = db.get_agent_email(user_id)
        if email:
            ok = send_report(user_id)
            if ok:
                await update.message.reply_text(f"✅ Отчёт агента отправлен на {email}")
            else:
                await update.message.reply_text("❌ Ошибка отправки. Проверьте SMTP настройки в логах.")
        else:
            # Send to all agents with email (admin test)
            ok, total = send_all_weekly_reports()
            ok2, total2 = send_all_service_reports()
            await update.message.reply_text(
                f"✅ Отчёты отправлены:\n"
                f"• Агенты: {ok}/{total}\n"
                f"• Перевозчики/упаковщики: {ok2}/{total2}\n\n"
                f"(у вас нет email — добавьте через /add → Агент → введите email)"
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")


def main():
    global _bot_app, _bot_loop
    fix_city_migration()
    app = Application.builder().token(BOT_TOKEN).build()
    _bot_app = app
    _bot_loop = asyncio.get_event_loop()
    search = SearchHandler()
    listing = ListingHandler()
    commercial = CommercialHandler()
    services = ServiceHandler()
    crm = CRMHandler()
    # ── Debug: log every incoming update type (remove after payments are confirmed working) ──
    async def _debug_all_updates(update: Update, context) -> None:
        update_types = [k for k in update.to_dict().keys() if k != "update_id"]
        logger.info(f"[DEBUG_UPDATE] id={update.update_id} types={update_types}")
    from telegram.ext import TypeHandler
    app.add_handler(TypeHandler(Update, _debug_all_updates), group=-2)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search.start_search))
    app.add_handler(CommandHandler("listings", my_listings))
    app.add_handler(CommandHandler("add", listing.start_add))
    app.add_handler(CommandHandler("help", handle_unknown))
    app.add_handler(CommandHandler("cabinet", agent_cabinet))
    app.add_handler(CommandHandler("refer", refer_command))
    app.add_handler(CommandHandler("testemail", cmd_testemail))
    app.add_handler(CommandHandler("testpay", cmd_testpay))
    app.add_handler(commercial.get_conversation_handler())
    app.add_handler(services.get_conversation_handler())
    app.add_handler(crm.get_conversation_handler())
    app.add_handler(search.get_conversation_handler())
    app.add_handler(listing.get_conversation_handler())
    app.add_handler(CallbackQueryHandler(handle_menu))
    # Payment handlers in group=-1 so they run BEFORE any ConversationHandler
    # (prevents a mid-conversation state from swallowing the pre_checkout_query)
    app.add_handler(PreCheckoutQueryHandler(handle_pre_checkout), group=-1)
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, handle_successful_payment), group=-1)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_text))

    # Start background notification tasks
    from notifications import start_background_tasks
    start_background_tasks(app)


    # Start weekly email reporter (Sunday 10:00)
    _start_email_scheduler()

    logger.info("Bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


import threading
import os
import hmac
import secrets

INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json as json_module

DASHBOARD_FILE  = os.path.join(os.path.dirname(__file__), "dashboard.html")
BACKOFFICE_FILE = os.path.join(os.path.dirname(__file__), "backoffice.html")
BACKOFFICE_PASSWORD = os.environ.get("BACKOFFICE_PASSWORD", "FlatFinderIL2026")

_BO_SESSIONS: dict = {}
_BO_LOCK = threading.Lock()

def _bo_create_session():
    token = secrets.token_hex(32)
    with _BO_LOCK:
        _BO_SESSIONS[token] = datetime.utcnow() + timedelta(hours=24)
    return token

def _bo_check_session(headers):
    raw = headers.get("Cookie","")
    token = ""
    for part in raw.split(";"):
        k,_,v = part.strip().partition("=")
        if k.strip() == "bo_session":
            token = v.strip(); break
    with _BO_LOCK:
        exp = _BO_SESSIONS.get(token)
    if not exp: return False
    if datetime.utcnow() > exp:
        with _BO_LOCK: _BO_SESSIONS.pop(token, None)
        return False
    return True

def _bo_delete_session(headers):
    raw = headers.get("Cookie","")
    for part in raw.split(";"):
        k,_,v = part.strip().partition("=")
        if k.strip() == "bo_session":
            with _BO_LOCK: _BO_SESSIONS.pop(v.strip(), None)

class WebHandler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def _send_json(self, data, status=200):
        body = json_module.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type","application/json")
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, path):
        try:
            with open(path,"rb") as f: content = f.read()
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        except: self.send_response(500); self.end_headers()

    def _redirect(self, loc):
        self.send_response(302)
        self.send_header("Location", loc)
        self.end_headers()

    def _read_body(self):
        length = int(self.headers.get("Content-Length",0))
        if not length: return {}
        raw = self.rfile.read(length)
        try: return json_module.loads(raw)
        except:
            from urllib.parse import parse_qs as pqs
            d = pqs(raw.decode())
            return {k: v[0] for k,v in d.items()}

    def _handle_backoffice(self, method, path):
        from urllib.parse import parse_qs as pqs

        # login page
        if path in ("/backoffice/login","/backoffice/login/"):
            if method == "GET":
                error = "?error=1" in self.path
                html = f"""<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Back-office Login</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#f5f5f0;font-family:-apple-system,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}}
.card{{background:#fff;border-radius:16px;padding:40px 36px;width:360px;box-shadow:0 4px 20px rgba(0,0,0,.10)}}
h1{{font-size:22px;font-weight:700;color:#222;margin-bottom:6px}}p{{font-size:13px;color:#888;margin-bottom:28px}}
label{{font-size:12px;font-weight:600;color:#555;display:block;margin-bottom:6px}}
input{{width:100%;padding:11px 14px;border:1.5px solid #ddd;border-radius:8px;font-size:14px;outline:none}}
input:focus{{border-color:#2AABEE}}
button{{width:100%;margin-top:18px;padding:12px;background:#2AABEE;color:#fff;border:none;border-radius:8px;font-size:15px;font-weight:600;cursor:pointer}}
button:hover{{background:#1a9de0}}.err{{color:#E24B4A;font-size:12px;margin-top:10px;text-align:center}}</style></head>
<body><div class="card"><h1>🏠 Back-office</h1><p>FlatFinderIL Admin Panel</p>
<form method="POST" action="/backoffice/login">
<label>Пароль</label><input type="password" name="password" autofocus placeholder="Введите пароль...">
<button type="submit">Войти</button>
{'<div class="err">❌ Неверный пароль</div>' if error else ''}
</form></div></body></html>"""
                body = html.encode()
                self.send_response(200)
                self.send_header("Content-Type","text/html; charset=utf-8")
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)
                return
            if method == "POST":
                length = int(self.headers.get("Content-Length",0))
                raw = self.rfile.read(length).decode()
                params = pqs(raw)
                password = (params.get("password") or [""])[0]
                if hmac.compare_digest(password, BACKOFFICE_PASSWORD):
                    token = _bo_create_session()
                    self.send_response(302)
                    self.send_header("Location","/backoffice")
                    self.send_header("Set-Cookie",f"bo_session={token}; HttpOnly; SameSite=Strict; Max-Age=86400; Path=/")
                    self.end_headers()
                else:
                    self._redirect("/backoffice/login?error=1")
                return

        # logout
        if path == "/backoffice/logout":
            _bo_delete_session(self.headers)
            self.send_response(302)
            self.send_header("Location","/backoffice/login")
            self.send_header("Set-Cookie","bo_session=; HttpOnly; Max-Age=0; Path=/")
            self.end_headers()
            return

        # back-office main page
        if path in ("/backoffice","/backoffice/"):
            if not _bo_check_session(self.headers):
                return self._redirect("/backoffice/login")
            return self._send_html(BACKOFFICE_FILE)

        # API routes
        if path.startswith("/backoffice/api/"):
            if not _bo_check_session(self.headers):
                return self._send_json({"error":"Unauthorized"}, 401)
            return self._handle_bo_api(method, path)

        self._send_json({"error":"Not found"}, 404)

    def _handle_bo_api(self, method, path):
        import database as db
        parts = [p for p in path.split("/") if p]
        # parts: ["backoffice","api","resource","id","action"]
        resource = parts[2] if len(parts) > 2 else ""
        rid      = parts[3] if len(parts) > 3 else ""
        action   = parts[4] if len(parts) > 4 else ""
        qs = parse_qs(urlparse(self.path).query)
        def qp(k, d=None): return (qs.get(k) or [d])[0]

        # stats
        if resource == "stats":
            data = db._load()
            listings = list(data["listings"].values())
            services = list(data.get("services",{}).values())
            return self._send_json({
                "total_listings":  len(listings),
                "active_listings": sum(1 for l in listings if l.get("active")),
                "total_services":  len(services),
                "active_services": sum(1 for s in services if s.get("active",True)),
                "total_users":     len(data.get("user_listings",{})),
                "total_crm_contacts": len(data.get("crm_contacts",{})),
                "total_crm_deals": len(data.get("crm_deals",{})),
                "email_subscribers": len(db.get_all_agent_emails()) + len(db.get_all_service_emails() if hasattr(db,'get_all_service_emails') else []),
            })

        # listings
        if resource == "listings":
            if method == "GET" and not rid:
                filters = {}
                q = qp("q"); city = qp("city"); deal = qp("deal_type")
                ptype = qp("property_type"); active_qs = qp("active")
                if q: filters["q"] = q
                if city: filters["city"] = city
                if deal: filters["deal_type"] = deal
                if ptype: filters["property_type"] = ptype
                if active_qs == "true":  filters["active"] = True
                if active_qs == "false": filters["active"] = False
                all_l = db.get_all_listings_admin(filters or None)
                page = int(qp("page",1)); per_page = int(qp("per_page",50))
                start = (page-1)*per_page
                return self._send_json({"total":len(all_l),"page":page,"per_page":per_page,"items":all_l[start:start+per_page]})
            if method == "GET" and rid:
                l = db.get_listing(int(rid))
                return self._send_json(l) if l else self._send_json({"error":"Not found"},404)
            if method == "PATCH" and rid and action == "toggle":
                l = db.get_listing(int(rid))
                if not l: return self._send_json({"error":"Not found"},404)
                new_active = not l.get("active",True)
                db.update_listing(int(rid),{"active":new_active})
                return self._send_json({"ok":True,"active":new_active})
            if method == "PATCH" and rid:
                fields = self._read_body(); fields.pop("id",None)
                return self._send_json({"ok": db.update_listing(int(rid),fields)})
            if method == "DELETE" and rid:
                return self._send_json({"ok": db.admin_delete_listing(int(rid))})

        # users
        if resource == "users":
            if method == "GET" and not rid:
                users = db.get_all_users_admin()
                return self._send_json({"total":len(users),"items":users})
            if method == "GET" and rid:
                data = db._load()
                profile = data.get("agent_profiles",{}).get(rid,{})
                lid_list = data.get("user_listings",{}).get(rid,[])
                listings = [data["listings"][str(l)] for l in lid_list if str(l) in data["listings"]]
                return self._send_json({"user_id":rid,"profile":profile,"listings":listings})

        # services
        if resource == "services":
            if method == "GET" and not rid:
                data = db._load()
                svcs = list(data.get("services",{}).values())
                stype = qp("type"); active_qs = qp("active")
                if stype: svcs = [s for s in svcs if s.get("service_type")==stype]
                if active_qs=="true":  svcs=[s for s in svcs if s.get("active",True)]
                if active_qs=="false": svcs=[s for s in svcs if not s.get("active",True)]
                svcs.sort(key=lambda x:x.get("date_added",""),reverse=True)
                return self._send_json({"total":len(svcs),"items":svcs})
            if method == "PATCH" and rid and action == "toggle":
                data = db._load()
                svc = data.get("services",{}).get(rid)
                if not svc: return self._send_json({"error":"Not found"},404)
                new_active = not svc.get("active",True)
                db.update_service(rid,{"active":new_active})
                return self._send_json({"ok":True,"active":new_active})
            if method == "PATCH" and rid:
                fields = self._read_body(); fields.pop("id",None)
                return self._send_json({"ok": db.update_service(rid,fields)})
            if method == "DELETE" and rid:
                return self._send_json({"ok": db.delete_service(rid)})

        # CRM
        if resource == "crm":
            sub = rid; cid = action; act = parts[5] if len(parts)>5 else ""
            if sub == "contacts":
                if method=="GET" and not cid:
                    stype=qp("type"); contacts=db.get_crm_contacts(contact_type=stype)
                    return self._send_json({"total":len(contacts),"items":contacts})
                if method=="POST":
                    b=self._read_body()
                    new_id=db.add_crm_contact(0,b.get("contact_type","agent"),b.get("name",""),b.get("phone",""),b.get("telegram",""),b.get("region",""),b.get("city",""),b.get("notes",""))
                    return self._send_json({"ok":True,"id":new_id})
                if method=="PATCH" and cid:
                    return self._send_json({"ok":db.update_crm_contact(cid,self._read_body())})
                if method=="DELETE" and cid:
                    return self._send_json({"ok":db.deactivate_crm_contact(cid)})
                if method=="GET" and cid and act=="notes":
                    return self._send_json({"items":db.get_crm_notes(cid)})
                if method=="POST" and cid and act=="notes":
                    b=self._read_body(); db.add_crm_note(0,cid,b.get("text",""))
                    return self._send_json({"ok":True})
            if sub == "deals":
                if method=="GET":
                    status=qp("status"); deals=db.get_crm_deals()
                    if status: deals=[d for d in deals if d.get("status")==status]
                    return self._send_json({"total":len(deals),"items":deals})
                if method=="POST":
                    b=self._read_body(); db.add_crm_deal(0,b.get("contact_id",""),b.get("description",""),b.get("amount",0),b.get("status","new"))
                    return self._send_json({"ok":True})
                if method=="PATCH" and cid:
                    b=self._read_body()
                    return self._send_json({"ok":db.update_crm_deal_status(cid,b.get("status","new"))})

        # email subscribers
        if resource == "email-subscribers":
            if method=="GET":
                agents=db.get_all_agent_emails()
                try: svcs=db.get_all_service_emails()
                except: svcs=[]
                combined=[{**a,"subscriber_type":"agent"} for a in agents]+[{**s,"subscriber_type":s.get("service_type","service")} for s in svcs]
                return self._send_json({"total":len(combined),"items":combined})
            if method=="POST" and rid=="send-now":
                from email_reporter import send_all_weekly_reports
                threading.Thread(target=send_all_weekly_reports, daemon=True).start()
                return self._send_json({"ok":True,"queued":True})
            if method=="POST" and rid:
                from email_reporter import send_report
                try: ok=send_report(int(rid))
                except Exception as e: ok=False
                return self._send_json({"ok":ok})

        # subscriptions (stats.json + paid_subscriptions in DB)
        if resource == "subscriptions":
            from analytics import _load_stats, _save_stats
            if method == "GET":
                data = _load_stats()
                subs = data.get("subscriptions", {})
                return self._send_json({"total": len(subs), "items": subs})
            if method == "DELETE" and rid:
                # Remove from stats.json subscriptions
                data = _load_stats()
                subs = data.get("subscriptions", {})
                removed_stats = subs.pop(rid, None)
                if rid in data.get("users", {}):
                    data["users"][rid]["subscribed"] = False
                data["subscriptions"] = subs
                _save_stats(data)
                # Remove from listings_db.json paid_subscriptions
                db_data = db._load()
                removed_db = db_data.get("paid_subscriptions", {}).pop(rid, None)
                db._save(db_data)
                return self._send_json({"ok": True, "removed_stats": removed_stats, "removed_db": removed_db})

        # payments log
        if resource == "payments":
            from analytics import _load_stats, _save_stats
            if method == "GET":
                data = _load_stats()
                log = data.get("payments_log", [])
                return self._send_json({"total": len(log), "items": log})
            if method == "DELETE" and rid:
                try:
                    i = int(rid)
                except ValueError:
                    return self._send_json({"error": "Invalid index"}, 400)
                data = _load_stats()
                log = data.get("payments_log", [])
                if i < 0 or i >= len(log):
                    return self._send_json({"error": "Index out of range"}, 404)
                removed = log.pop(i)
                data["payments_log"] = log
                _save_stats(data)
                return self._send_json({"ok": True, "removed": removed})

        # logout via API
        if resource == "logout":
            _bo_delete_session(self.headers)
            return self._send_json({"ok":True})

        self._send_json({"error":"Not found"},404)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Back-office routes
        if path.startswith("/backoffice"):
            return self._handle_backoffice("GET", path)

        if path == "/analytics":
            try:
                from analytics import get_analytics
                qs = parse_qs(parsed.query)
                date_from = (qs.get("from") or [None])[0]
                date_to   = (qs.get("to")   or [None])[0]
                data = get_analytics(date_from=date_from, date_to=date_to)
            except Exception as e:
                data = {"error": str(e)}
            body = json_module.dumps(data, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/news":
            try:
                from news_fetcher import get_news
                qs = parse_qs(parsed.query)
                category = (qs.get("category") or [None])[0]
                lang     = (qs.get("lang")     or [None])[0]
                limit    = int((qs.get("limit")  or ["20"])[0])
                data = get_news(category=category, lang=lang, limit=limit)
            except Exception as e:
                data = {"error": str(e), "items": [], "ticker": []}
            self._send_json(data)
        else:
            self._send_html(DASHBOARD_FILE)

    def do_POST(self):
        path = urlparse(self.path).path
        if path.startswith("/backoffice"):
            return self._handle_backoffice("POST", path)
        if path == "/send-message":
            return self._handle_send_message()
        self._send_json({"error":"Not found"},404)

    def _handle_send_message(self):
        # Optional internal API key check
        if INTERNAL_API_KEY:
            auth = self.headers.get("X-Internal-Key", "")
            if not hmac.compare_digest(auth, INTERNAL_API_KEY):
                return self._send_json({"error": "Unauthorized"}, 401)

        body = self._read_body()
        chat_id = body.get("chat_id")
        text = body.get("text", "")
        parse_mode = body.get("parse_mode", "HTML")

        if not chat_id or not text:
            return self._send_json({"error": "chat_id and text are required"}, 400)

        if _bot_app is None or _bot_loop is None:
            return self._send_json({"error": "Bot not ready"}, 503)

        try:
            future = asyncio.run_coroutine_threadsafe(
                _bot_app.bot.send_message(
                    chat_id=int(chat_id),
                    text=text,
                    parse_mode=parse_mode,
                ),
                _bot_loop,
            )
            future.result(timeout=10)
            return self._send_json({"ok": True})
        except Exception as e:
            logger.error(f"send-message failed for chat_id={chat_id}: {e}")
            return self._send_json({"error": str(e)}, 500)

    def do_PATCH(self):
        path = urlparse(self.path).path
        if path.startswith("/backoffice/api/"):
            if not _bo_check_session(self.headers):
                return self._send_json({"error":"Unauthorized"},401)
            return self._handle_bo_api("PATCH", path)
        self._send_json({"error":"Not found"},404)

    def do_DELETE(self):
        path = urlparse(self.path).path
        if path.startswith("/backoffice/api/"):
            if not _bo_check_session(self.headers):
                return self._send_json({"error":"Unauthorized"},401)
            return self._handle_bo_api("DELETE", path)
        self._send_json({"error":"Not found"},404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","GET,POST,PATCH,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type")
        self.end_headers()

def start_web_server():
    port = int(os.environ.get("PORT", 3000))
    server = HTTPServer(("0.0.0.0", port), WebHandler)
    logger.info(f"Web server on port {port}")
    server.serve_forever()


def _email_scheduler_loop():
    """Background thread: every Sunday at 10:00 IL time send weekly reports."""
    import time
    from datetime import datetime, timezone, timedelta
    IL_TZ = timezone(timedelta(hours=3))  # Israel Standard Time (UTC+3)
    sent_this_week = None
    while True:
        now = datetime.now(IL_TZ)
        week_key = f"{now.isocalendar()[0]}-W{now.isocalendar()[1]}"
        # Sunday=6 in Python weekday(), 10:00–10:59
        if now.weekday() == 6 and now.hour == 10 and sent_this_week != week_key:
            try:
                from email_reporter import send_all_weekly_reports
                ok, total = send_all_weekly_reports()
                logger.info(f"Email scheduler: {ok}/{total} reports sent")
                sent_this_week = week_key
            except Exception as e:
                logger.error(f"Email scheduler error: {e}")
        time.sleep(60)   # check every minute


def _start_email_scheduler():
    t = threading.Thread(target=_email_scheduler_loop, daemon=True, name="email-scheduler")
    t.start()
    logger.info("Email scheduler started (runs every Sunday 10:00 IL)")

web_thread = threading.Thread(target=start_web_server, daemon=True)
web_thread.start()

# Start news refresh loop (fetches RSS every 60 min)
try:
    from news_fetcher import start_news_refresh_loop
    start_news_refresh_loop()
except Exception as _ne:
    logger.warning(f"News fetcher not started: {_ne}")

def start_telegram_parser():
    try:
        from telegram_parser import run_parser
        asyncio.run(run_parser())
    except Exception as e:
        logger.error(f"Telegram parser error: {e}")

parser_thread = threading.Thread(target=start_telegram_parser, daemon=True)
parser_thread.start()

if __name__ == "__main__":
    main()
