from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import os, urllib.request, urllib.error, json, time, threading, ssl

# SSL context без верификации — для Railway (наш собственный сервер)
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

PORT           = int(os.environ.get("PORT", 3000))
ANALYTICS_PORT = int(os.environ.get("ANALYTICS_PORT", 8765))
RAILWAY_URL    = os.environ.get("RAILWAY_ANALYTICS_URL",
                    "https://flatfinderil-bot-production.up.railway.app/analytics")
_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Railway stats sync ─────────────────────────────────────────────────────
_railway_cache: dict = {}
_railway_cache_ts: float = 0
_RAILWAY_TTL = 300  # обновлять раз в 5 минут

def _fetch_railway():
    """Загружает свежую аналитику с Railway и кэширует."""
    global _railway_cache, _railway_cache_ts
    try:
        with urllib.request.urlopen(RAILWAY_URL, timeout=8, context=_SSL_CTX) as r:
            data = json.loads(r.read())
        _railway_cache = data
        _railway_cache_ts = time.time()
        # Обновляем локальный stats.json для аналитического сервера
        _sync_stats_json(data)
    except Exception:
        pass

def _sync_stats_json(railway_data: dict):
    """Обновляет локальный stats.json данными пользователей с Railway."""
    stats_file = os.path.join(_DIR, "stats.json")
    try:
        if os.path.exists(stats_file):
            with open(stats_file, encoding="utf-8") as f:
                stats = json.load(f)
        else:
            stats = {"users": {}, "members": {}, "searches": [], "subscriptions": {}, "daily": {}}

        for u in railway_data.get("users_list", []):
            uid = str(u["user_id"])
            stats["users"][uid] = {
                "first_seen": u.get("first_seen", ""),
                "last_seen":  u.get("last_seen", ""),
                "lang":       u.get("lang", "ru"),
                "searches":   u.get("searches", 0),
                "subscribed": u.get("subscribed", False),
                "first_name": u.get("first_name", ""),
                "last_name":  u.get("last_name", ""),
                "username":   u.get("username", ""),
                "phone":      u.get("phone", ""),
            }
            if uid not in stats["members"]:
                stats["members"][uid] = {"joined": u.get("first_seen", "")}

        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _bg_sync():
    """Фоновый поток: периодически синхронизирует данные с Railway."""
    while True:
        _fetch_railway()
        time.sleep(_RAILWAY_TTL)

threading.Thread(target=_bg_sync, daemon=True).start()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        # Proxy /analytics to analytics server + merge Railway data
        if parsed.path == "/analytics":
            query = ("?" + parsed.query) if parsed.query else ""
            target = f"http://127.0.0.1:{ANALYTICS_PORT}/analytics{query}"
            try:
                with urllib.request.urlopen(target, timeout=10) as resp:
                    local_data = json.loads(resp.read())
            except Exception as e:
                local_data = {"error": str(e)}

            # Merge fields from Railway that are empty locally
            rw = _railway_cache
            if rw:
                # Services: перевозки, упаковка, клининг
                local_svc = local_data.get("services", {})
                if not local_svc.get("total") and rw.get("services", {}).get("total"):
                    local_data["services"] = rw["services"]

                # Seller stats: агенты, частники
                local_sellers = local_data.get("seller_stats", {})
                rw_sellers = rw.get("seller_stats", {})
                if (not local_sellers.get("agent", {}).get("total")
                        and rw_sellers.get("agent", {}).get("total")):
                    local_data["seller_stats"] = rw_sellers

                # Email subscribers / email reporters
                if not local_data.get("email_subscribers") and rw.get("email_subscribers"):
                    local_data["email_subscribers"] = rw["email_subscribers"]

                # CRM
                if not local_data.get("crm") and rw.get("crm"):
                    local_data["crm"] = rw["crm"]

                # Users list (already synced via stats.json, but keep as fallback)
                if not local_data.get("users_list") and rw.get("users_list"):
                    local_data["users_list"] = rw["users_list"]

            body = json.dumps(local_data, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
            return
        # ── Proxy all /api/* and /rss.xml to analytics server ─────────────────
        if parsed.path.startswith("/api/") or parsed.path in ("/rss.xml",):
            query = ("?" + parsed.query) if parsed.query else ""
            target = f"http://127.0.0.1:{ANALYTICS_PORT}{parsed.path}{query}"
            try:
                with urllib.request.urlopen(target, timeout=15) as resp:
                    body = resp.read()
                    ctype = resp.headers.get("Content-Type", "application/json")
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                body = f'{{"error":"{e}"}}'.encode()
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)
            return
        if parsed.path == "/admin/cleanup-spam":
            target = f"http://127.0.0.1:{ANALYTICS_PORT}/admin/cleanup-spam"
            try:
                req = urllib.request.Request(target, data=b"", method="POST")
                with urllib.request.urlopen(req, timeout=30) as resp:
                    body = resp.read()
                self.send_response(200)
            except Exception as e:
                body = f'{{"error":"{e}"}}'.encode()
                self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/download-pdf":
            try:
                import sys
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                import bot_map_pdf
                pdf_bytes = bot_map_pdf.generate()
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Disposition", "attachment; filename=FlatFinderIL_Bot_Map.pdf")
                self.send_header("Content-Length", len(pdf_bytes))
                self.end_headers()
                self.wfile.write(pdf_bytes)
            except Exception as e:
                body = f"PDF generation error: {e}".encode()
                self.send_response(500)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)
        else:
            try:
                with open(os.path.join(_DIR, 'dashboard.html'), 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self.send_response(500)
                self.end_headers()
    def log_message(self, *args): pass

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Dashboard on port {PORT}")
    server.serve_forever()
