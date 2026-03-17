from http.server import HTTPServer, BaseHTTPRequestHandler
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PORT = int(os.environ.get("PORT", 8765))

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/analytics" or self.path == "/":
            try:
                from analytics import get_analytics
                data = get_analytics()
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

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Analytics API on port {PORT}")
    server.serve_forever()
