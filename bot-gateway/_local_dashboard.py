"""Local dashboard server — serves dashboard.html + proxies /analytics to local analytics_server on 8080."""
import http.server, socketserver, urllib.request, os, threading, sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
PORT = 8766
LOCAL_API = 'http://localhost:8081'

class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args): pass
    def do_GET(self):
        if (self.path.startswith('/analytics') or self.path.startswith('/api/')):
            try:
                u = LOCAL_API + self.path
                req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
                r = urllib.request.urlopen(req, timeout=20)
                body = r.read()
                self.send_response(200)
                self.send_header('Content-Type', r.headers.get('Content-Type', 'application/json'))
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-Length', len(body))
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                self.send_response(502); self.end_headers()
                self.wfile.write(f"proxy error: {e}".encode())
            return
        if self.path == '/' or self.path.startswith('/?'):
            with open('dashboard.html', 'rb') as f:
                body = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', len(body))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(('', PORT), H) as srv:
    print(f"Local dashboard: http://localhost:{PORT}", flush=True)
    srv.serve_forever()
