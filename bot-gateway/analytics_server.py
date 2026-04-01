from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PORT = int(os.environ.get("PORT", 8765))

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/analytics", "/"):
            try:
                from analytics import get_analytics
                qs = parse_qs(parsed.query)
                date_from = (qs.get("from") or [None])[0]
                date_to   = (qs.get("to")   or [None])[0]
                data = get_analytics(date_from=date_from, date_to=date_to)
            except Exception as e:
                data = {"error": str(e)}
            body = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/admin/cleanup-spam":
            try:
                result = _cleanup_spam_listings()
                body = json.dumps(result, ensure_ascii=False).encode()
                self.send_response(200)
            except Exception as e:
                body = json.dumps({"error": str(e)}, ensure_ascii=False).encode()
                self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        pass


def _cleanup_spam_listings():
    import database as db
    from telegram_parser import is_ad_or_spam
    data = db._load()
    removed = []
    for lid, listing in list(data["listings"].items()):
        if listing.get("source") != "telegram":
            continue
        text = (listing.get("description") or "") + " " + (listing.get("title") or "")
        if is_ad_or_spam(text):
            removed.append(lid)
    for lid in removed:
        del data["listings"][lid]
        # Remove from user_listings references too
        for uid in data.get("user_listings", {}):
            if lid in data["user_listings"][uid]:
                data["user_listings"][uid].remove(lid)
    db._save(data)
    return {"removed": len(removed), "ids": removed[:50]}

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Analytics API on port {PORT}")
    server.serve_forever()
