from http.server import HTTPServer, BaseHTTPRequestHandler
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/analytics":
            try:
                from analytics import get_analytics
                data = get_analytics()
            except Exception as e:
                data = {"error": str(e)}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    server = HTTPServer(("localhost", 8765), Handler)
    print("✅ Analytics API: http://localhost:8765/analytics")
    server.serve_forever()
