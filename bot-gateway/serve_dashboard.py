from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import os

PORT = int(os.environ.get("PORT", 3000))

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
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
                with open('dashboard.html', 'rb') as f:
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
