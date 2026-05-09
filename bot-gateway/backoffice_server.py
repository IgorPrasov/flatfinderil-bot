"""
FlatFinderIL — Back-office admin panel
Serves backoffice.html + REST API on BACKOFFICE_PORT (default 8081)
Protected by BACKOFFICE_PASSWORD environment variable.
"""

import os
import hmac
import json
import logging
import secrets
import threading
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import database as db
from email_reporter import send_report, send_all_weekly_reports

logger = logging.getLogger(__name__)

BACKOFFICE_PORT     = int(os.environ.get("BACKOFFICE_PORT", 8081))
BACKOFFICE_PASSWORD = os.environ.get("BACKOFFICE_PASSWORD", "")
BACKOFFICE_HTML     = os.path.join(os.path.dirname(__file__), "backoffice.html")

_SESSIONS: dict = {}          # token -> expires_at datetime
_SESSIONS_LOCK = threading.Lock()
SESSION_TTL_HOURS = 24


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _create_session() -> str:
    token = secrets.token_hex(32)
    with _SESSIONS_LOCK:
        _SESSIONS[token] = datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS)
    return token


def _validate_session(token: str) -> bool:
    with _SESSIONS_LOCK:
        exp = _SESSIONS.get(token)
    if not exp:
        return False
    if datetime.utcnow() > exp:
        with _SESSIONS_LOCK:
            _SESSIONS.pop(token, None)
        return False
    return True


def _delete_session(token: str):
    with _SESSIONS_LOCK:
        _SESSIONS.pop(token, None)


def _get_cookie(headers, name: str) -> str:
    raw = headers.get("Cookie", "")
    for part in raw.split(";"):
        k, _, v = part.strip().partition("=")
        if k.strip() == name:
            return v.strip()
    return ""


# ── HTTP handler ──────────────────────────────────────────────────────────────

class BackofficeHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        logger.info("backoffice %s - %s", self.address_string(), fmt % args)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _send_html_file(self, path):
        try:
            with open(path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", len(content))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self._send_json({"error": "backoffice.html not found"}, 404)

    def _redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def _is_authed(self) -> bool:
        token = _get_cookie(self.headers, "bo_session")
        return _validate_session(token)

    def _require_auth(self) -> bool:
        """Return True if OK; send 401 and return False if not authed."""
        if self._is_authed():
            return True
        self._send_json({"error": "Unauthorized"}, 401)
        return False

    def _get_qs(self):
        return parse_qs(urlparse(self.path).query)

    def _qs(self, key, default=None):
        return (self._get_qs().get(key) or [default])[0]

    # ── routing ──────────────────────────────────────────────────────────────

    def _route(self, method):
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip("/")
        parts  = [p for p in path.split("/") if p]
        # parts example: ["backoffice","api","listings","42","toggle"]

        # ── login / logout ────────────────────────────────────────────────
        if path in ("/backoffice/login", "/login"):
            if method == "GET":
                return self._handle_login_page()
            if method == "POST":
                return self._handle_login_post()

        if path in ("/backoffice/api/logout", "/backoffice/logout"):
            return self._handle_logout()

        # ── main panel ───────────────────────────────────────────────────
        if path in ("/backoffice", "/backoffice/", ""):
            if not self._is_authed():
                return self._redirect("/backoffice/login")
            return self._send_html_file(BACKOFFICE_HTML)

        # ── API routes (require auth) ──────────────────────────────────
        if not self._require_auth():
            return

        resource = parts[2] if len(parts) > 2 else ""
        rid      = parts[3] if len(parts) > 3 else ""
        action   = parts[4] if len(parts) > 4 else ""

        if resource == "stats":
            return self._handle_stats()
        if resource == "listings":
            return self._handle_listings(method, rid, action)
        if resource == "users":
            return self._handle_users(method, rid)
        if resource == "services":
            return self._handle_services(method, rid, action)
        if resource == "crm":
            sub = rid    # "contacts" or "deals"
            cid = action
            act = parts[5] if len(parts) > 5 else ""
            return self._handle_crm(method, sub, cid, act)
        if resource == "email-subscribers":
            return self._handle_email_subs(method, rid)
        if resource == "payments":
            return self._handle_payments(method, rid)
        if resource == "ig-session":
            return self._handle_ig_session(method)
        if resource == "fb-cookies":
            return self._handle_fb_cookies(method)

        self._send_json({"error": "Not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PATCH,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):    self._route("GET")
    def do_POST(self):   self._route("POST")
    def do_PATCH(self):  self._route("PATCH")
    def do_DELETE(self): self._route("DELETE")

    # ── Login / Logout ────────────────────────────────────────────────────────

    def _handle_login_page(self):
        html = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>FlatFinderIL — Back-office</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{background:#f5f5f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
         display:flex;align-items:center;justify-content:center;min-height:100vh}
    .card{background:#fff;border-radius:16px;padding:40px 36px;width:360px;
          box-shadow:0 4px 20px rgba(0,0,0,.10)}
    h1{font-size:22px;font-weight:700;color:#222;margin-bottom:6px}
    p{font-size:13px;color:#888;margin-bottom:28px}
    label{font-size:12px;font-weight:600;color:#555;display:block;margin-bottom:6px}
    input{width:100%;padding:11px 14px;border:1.5px solid #ddd;border-radius:8px;
          font-size:14px;outline:none;transition:border .15s}
    input:focus{border-color:#2AABEE}
    button{width:100%;margin-top:18px;padding:12px;background:#2AABEE;color:#fff;
           border:none;border-radius:8px;font-size:15px;font-weight:600;cursor:pointer;
           transition:background .15s}
    button:hover{background:#1a9de0}
    .err{color:#E24B4A;font-size:12px;margin-top:10px;text-align:center}
  </style>
</head>
<body>
  <div class="card">
    <h1>🏠 Back-office</h1>
    <p>FlatFinderIL Admin Panel</p>
    <form method="POST" action="/backoffice/login">
      <label>Пароль</label>
      <input type="password" name="password" autofocus placeholder="Введите пароль...">
      <button type="submit">Войти</button>
      <div class="err" id="err">WRONG_PASSWORD</div>
    </form>
  </div>
  <script>
    const err = document.getElementById('err');
    const show = new URLSearchParams(location.search).get('error');
    err.style.display = show ? 'block' : 'none';
  </script>
</body>
</html>"""
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _handle_login_post(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode()
        from urllib.parse import parse_qs as pqs
        params = pqs(raw)
        password = (params.get("password") or [""])[0]

        if not BACKOFFICE_PASSWORD:
            # No password set — deny all
            return self._redirect("/backoffice/login?error=1")

        if hmac.compare_digest(password, BACKOFFICE_PASSWORD):
            token = _create_session()
            self.send_response(302)
            self.send_header("Location", "/backoffice")
            self.send_header("Set-Cookie",
                f"bo_session={token}; HttpOnly; SameSite=Strict; Max-Age={SESSION_TTL_HOURS*3600}; Path=/")
            self.end_headers()
        else:
            self._redirect("/backoffice/login?error=1")

    def _handle_logout(self):
        token = _get_cookie(self.headers, "bo_session")
        _delete_session(token)
        self.send_response(302)
        self.send_header("Location", "/backoffice/login")
        self.send_header("Set-Cookie", "bo_session=; HttpOnly; Max-Age=0; Path=/")
        self.end_headers()

    # ── Stats ─────────────────────────────────────────────────────────────────

    def _handle_stats(self):
        data = db._load()
        listings = list(data["listings"].values())
        services = list(data.get("services", {}).values())
        crm_contacts = list(data.get("crm_contacts", {}).values())
        crm_deals    = list(data.get("crm_deals", {}).values())
        agents_with_email = len([p for p in data.get("agent_profiles", {}).values() if p.get("email")])
        svc_with_email    = len([s for s in services if s.get("email")])
        users = set(list(data.get("user_listings", {}).keys()))
        self._send_json({
            "total_listings":   len(listings),
            "active_listings":  sum(1 for l in listings if l.get("active")),
            "total_services":   len(services),
            "active_services":  sum(1 for s in services if s.get("active", True)),
            "total_users":      len(users),
            "total_crm_contacts": len(crm_contacts),
            "total_crm_deals":  len(crm_deals),
            "email_subscribers": agents_with_email + svc_with_email,
        })

    # ── Listings ──────────────────────────────────────────────────────────────

    def _handle_listings(self, method, lid, action):
        if method == "GET" and not lid:
            filters = {}
            q = self._qs("q")
            if q: filters["q"] = q
            city = self._qs("city")
            if city: filters["city"] = city
            deal = self._qs("deal_type")
            if deal: filters["deal_type"] = deal
            ptype = self._qs("property_type")
            if ptype: filters["property_type"] = ptype
            active_qs = self._qs("active")
            if active_qs == "true":  filters["active"] = True
            if active_qs == "false": filters["active"] = False
            all_l = db.get_all_listings_admin(filters or None)
            page     = int(self._qs("page", 1) or 1)
            per_page = int(self._qs("per_page", 50) or 50)
            start = (page-1)*per_page
            self._send_json({
                "total": len(all_l),
                "page": page, "per_page": per_page,
                "items": all_l[start:start+per_page],
            })

        elif method == "GET" and lid:
            l = db.get_listing(int(lid))
            if l: self._send_json(l)
            else: self._send_json({"error": "Not found"}, 404)

        elif method == "PATCH" and lid and action == "toggle":
            l = db.get_listing(int(lid))
            if not l:
                return self._send_json({"error": "Not found"}, 404)
            new_active = not l.get("active", True)
            db.update_listing(int(lid), {"active": new_active})
            self._send_json({"ok": True, "active": new_active})

        elif method == "PATCH" and lid:
            fields = self._read_body()
            fields.pop("id", None)
            ok = db.update_listing(int(lid), fields)
            self._send_json({"ok": ok})

        elif method == "DELETE" and lid:
            ok = db.admin_delete_listing(int(lid))
            self._send_json({"ok": ok})

        else:
            self._send_json({"error": "Not found"}, 404)

    # ── Users ─────────────────────────────────────────────────────────────────

    def _handle_users(self, method, uid):
        if method == "GET" and not uid:
            users = db.get_all_users_admin()
            self._send_json({"total": len(users), "items": users})
        elif method == "GET" and uid:
            data = db._load()
            profile = data.get("agent_profiles", {}).get(uid, {})
            lid_list = data.get("user_listings", {}).get(uid, [])
            listings = [data["listings"][str(l)] for l in lid_list if str(l) in data["listings"]]
            self._send_json({
                "user_id": uid, "profile": profile,
                "listings": sorted(listings, key=lambda x: x.get("date_added",""), reverse=True),
            })
        else:
            self._send_json({"error": "Not found"}, 404)

    # ── Services ──────────────────────────────────────────────────────────────

    def _handle_services(self, method, sid, action):
        if method == "GET" and not sid:
            data = db._load()
            svcs = list(data.get("services", {}).values())
            stype = self._qs("type")
            if stype: svcs = [s for s in svcs if s.get("service_type") == stype]
            active_qs = self._qs("active")
            if active_qs == "true":  svcs = [s for s in svcs if s.get("active", True)]
            if active_qs == "false": svcs = [s for s in svcs if not s.get("active", True)]
            svcs.sort(key=lambda x: x.get("date_added",""), reverse=True)
            self._send_json({"total": len(svcs), "items": svcs})

        elif method == "PATCH" and sid and action == "toggle":
            data = db._load()
            svc = data.get("services", {}).get(sid)
            if not svc:
                return self._send_json({"error": "Not found"}, 404)
            new_active = not svc.get("active", True)
            db.update_service(sid, {"active": new_active})
            self._send_json({"ok": True, "active": new_active})

        elif method == "PATCH" and sid:
            fields = self._read_body()
            fields.pop("id", None)
            ok = db.update_service(sid, fields)
            self._send_json({"ok": ok})

        elif method == "DELETE" and sid:
            ok = db.delete_service(sid)
            self._send_json({"ok": ok})

        else:
            self._send_json({"error": "Not found"}, 404)

    # ── CRM ───────────────────────────────────────────────────────────────────

    def _handle_crm(self, method, sub, cid, action):
        if sub == "contacts":
            if method == "GET" and not cid:
                stype = self._qs("type")
                contacts = db.get_crm_contacts(contact_type=stype)
                self._send_json({"total": len(contacts), "items": contacts})
            elif method == "POST":
                body = self._read_body()
                new_id = db.add_crm_contact(
                    user_id=0, contact_type=body.get("contact_type","agent"),
                    name=body.get("name",""), phone=body.get("phone",""),
                    telegram=body.get("telegram",""), region=body.get("region",""),
                    city=body.get("city",""), notes=body.get("notes",""),
                )
                self._send_json({"ok": True, "id": new_id})
            elif method == "PATCH" and cid:
                fields = self._read_body()
                ok = db.update_crm_contact(cid, fields)
                self._send_json({"ok": ok})
            elif method == "DELETE" and cid:
                ok = db.deactivate_crm_contact(cid)
                self._send_json({"ok": ok})
            elif method == "GET" and cid and action == "notes":
                notes = db.get_crm_notes(cid)
                self._send_json({"items": notes})
            elif method == "POST" and cid and action == "notes":
                body = self._read_body()
                db.add_crm_note(user_id=0, contact_id=cid, text=body.get("text",""))
                self._send_json({"ok": True})
            else:
                self._send_json({"error": "Not found"}, 404)

        elif sub == "deals":
            if method == "GET":
                contact_id = self._qs("contact_id")
                status = self._qs("status")
                deals = db.get_crm_deals(contact_id=contact_id)
                if status:
                    deals = [d for d in deals if d.get("status") == status]
                self._send_json({"total": len(deals), "items": deals})
            elif method == "POST":
                body = self._read_body()
                db.add_crm_deal(
                    user_id=0, contact_id=body.get("contact_id",""),
                    description=body.get("description",""),
                    amount=body.get("amount", 0),
                    status=body.get("status","new"),
                )
                self._send_json({"ok": True})
            elif method == "PATCH" and cid:
                body = self._read_body()
                ok = db.update_crm_deal_status(cid, body.get("status","new"))
                self._send_json({"ok": ok})
            else:
                self._send_json({"error": "Not found"}, 404)
        else:
            self._send_json({"error": "Not found"}, 404)

    # ── Email subscribers ─────────────────────────────────────────────────────

    def _handle_email_subs(self, method, uid):
        if method == "GET":
            agents = db.get_all_agent_emails()
            try:
                svcs = db.get_all_service_emails()
            except Exception:
                svcs = []
            combined = [
                {**a, "subscriber_type": "agent"} for a in agents
            ] + [
                {**s, "subscriber_type": s.get("service_type", "service")} for s in svcs
            ]
            self._send_json({"total": len(combined), "items": combined})

        elif method == "POST" and uid == "send-now":
            def _run():
                try:
                    send_all_weekly_reports()
                except Exception as e:
                    logger.error(f"send_all error: {e}")
            threading.Thread(target=_run, daemon=True).start()
            self._send_json({"ok": True, "queued": True})

        elif method == "POST" and uid:
            try:
                ok = send_report(int(uid))
                self._send_json({"ok": ok})
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)})

        else:
            self._send_json({"error": "Not found"}, 404)


    # ── Payments log ──────────────────────────────────────────────────────────

    def _handle_payments(self, method, idx):
        from analytics import _load_stats, _save_stats
        if method == "GET":
            data = _load_stats()
            log = data.get("payments_log", [])
            self._send_json({"total": len(log), "items": log})

        elif method == "DELETE" and idx:
            try:
                i = int(idx)
            except ValueError:
                return self._send_json({"error": "Invalid index"}, 400)
            data = _load_stats()
            log = data.get("payments_log", [])
            if i < 0 or i >= len(log):
                return self._send_json({"error": "Index out of range"}, 404)
            removed = log.pop(i)
            data["payments_log"] = log
            _save_stats(data)
            self._send_json({"ok": True, "removed": removed})

        else:
            self._send_json({"error": "Not found"}, 404)


# ── Instagram session ─────────────────────────────────────────────────────────

    def _handle_ig_session(self, method):
        import database as db
        if method == "GET":
            sid = db.get_ig_session()
            has_full = bool(db.get_ig_settings_json())
            masked = (sid[:12] + "…") if sid else ""
            return self._send_json({"sessionid": masked, "has_full_settings": has_full})

        if method == "POST":
            body = self._read_body()
            raw = (body.get("sessionid") or "").strip()
            if not raw:
                return self._send_json({"ok": False, "error": "sessionid is empty"}, 400)
            # Нормализуем: убираем префикс "sessionid=" если вставили с ним
            sessionid = raw.removeprefix("sessionid=")
            # Сохраняем sessionid в БД
            db.set_ig_session(sessionid)
            # Пробуем получить и сохранить полные настройки через instagrapi
            try:
                import json as _json
                from instagrapi import Client
                cl = Client()
                cl.delay_range = [1, 2]
                cl.login_by_sessionid(sessionid)
                settings_json = _json.dumps(cl.get_settings(), ensure_ascii=False)
                db.set_ig_settings_json(settings_json)
                username = cl.username or "unknown"
                logger.info(f"✅ IG session saved: @{username}")
                return self._send_json({"ok": True, "username": username, "full_settings": True})
            except Exception as e:
                logger.warning(f"⚠️ IG: saved sessionid but could not get full settings: {e}")
                return self._send_json({"ok": True, "full_settings": False,
                                        "warning": str(e)})

        self._send_json({"error": "Method not allowed"}, 405)


    # ── Facebook cookies ───────────────────────────────────────────────────────

    def _handle_fb_cookies(self, method):
        import os as _os
        import database as db
        if method == "GET":
            raw = db.get_fb_cookies()
            return self._send_json({"has_cookies": bool(raw),
                                    "length": len(raw) if raw else 0})

        if method == "POST":
            body = self._read_body()
            raw = (body.get("cookies") or "").strip()
            if not raw:
                return self._send_json({"ok": False, "error": "cookies is empty"}, 400)
            # Сохраняем в БД
            db.set_fb_cookies(raw)
            # Обновляем env var для текущего процесса, чтобы facebook_poster сразу видел
            _os.environ["FB_COOKIES_JSON"] = raw
            logger.info(f"✅ FB cookies saved ({len(raw)} bytes)")
            return self._send_json({"ok": True, "length": len(raw)})

        self._send_json({"error": "Method not allowed"}, 405)


# ── Start server ──────────────────────────────────────────────────────────────

def start_backoffice_server():
    if not BACKOFFICE_PASSWORD:
        logger.warning("BACKOFFICE_PASSWORD not set — back-office will reject all logins!")
    server = HTTPServer(("0.0.0.0", BACKOFFICE_PORT), BackofficeHandler)
    logger.info(f"Back-office server on port {BACKOFFICE_PORT}")
    server.serve_forever()
