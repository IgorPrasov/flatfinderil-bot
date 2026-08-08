"""Local proxy server for testing dashboard.html with production API."""
import http.server, socketserver, urllib.request, os, sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
PORT = 8765
PROD = 'https://flatfinderil-bot-production.up.railway.app'

class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args): pass  # quiet
    def do_GET(self):
        # Proxy API calls to production
        if (self.path.startswith('/api/') or self.path == '/analytics'
            or self.path.startswith('/news') or self.path.startswith('/rss')
            or self.path.startswith('/analytics?')):
            try:
                u = PROD + self.path
                req = urllib.request.Request(u, headers={'User-Agent':'Mozilla/5.0'})
                r = urllib.request.urlopen(req, timeout=20)
                body = r.read()
                self.send_response(200)
                self.send_header('Content-Type', r.headers.get('Content-Type', 'application/json'))
                self.send_header('Content-Length', len(body))
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(502); self.end_headers()
                self.wfile.write(f"proxy error: {e}".encode())
            return
        # Serve dashboard.html for /
        if self.path == '/' or self.path.startswith('/?'):
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dashboard.html'), 'rb') as f:
                body = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.send_header('Content-Length', len(body))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(('', PORT), H) as srv:
    print(f"Proxy on http://localhost:{PORT}", flush=True)
    srv.serve_forever()
