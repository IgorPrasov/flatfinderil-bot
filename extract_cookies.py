import browser_cookie3
import psycopg2
import json

DB_URL = "postgresql://postgres:NOgPcBAEMFuWIwVhLDtOJvxscXeEhtgI@kodama.proxy.rlwy.net:38517/railway"

try:
    cj = browser_cookie3.chrome(domain_name=".facebook.com")
    cookies = [{"name": c.name, "value": c.value, "domain": ".facebook.com", "path": "/"} for c in cj]
    
    if cookies:
        print(f"✅ Найдено {len(cookies)} cookies из Chrome")
        conn = psycopg2.connect(DB_URL, connect_timeout=15)
        cur = conn.cursor()
        cur.execute("INSERT INTO app_settings(key, value) VALUES(%s, %s) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value", ("fb_cookies_json", json.dumps(cookies)))
        conn.commit()
        print("✅ Cookies сохранены в базу!")
except Exception as e:
    print(f"❌ Ошибка: {e}")
