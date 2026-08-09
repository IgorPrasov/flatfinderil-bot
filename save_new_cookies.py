import psycopg2
import json

DB_URL = "postgresql://postgres:NOgPcBAEMFuWIwVhLDtOJvxscXeEhtgI@kodama.proxy.rlwy.net:38517/railway"

cookies = [
  {"domain": ".facebook.com", "expirationDate": 1820775294.229059, "hostOnly": False, "httpOnly": True, "name": "datr", "path": "/", "sameSite": "no_restriction", "secure": True, "session": False, "storeId": "0", "value": "fnt3asexf_NJ3t-76Yyn42bj"},
  {"domain": ".facebook.com", "expirationDate": 1820775426.943836, "hostOnly": False, "httpOnly": True, "name": "sb", "path": "/", "sameSite": "no_restriction", "secure": True, "session": False, "storeId": "0", "value": "kHt3agfR3AEr5JoHOSRu2FZO"},
  {"domain": ".facebook.com", "expirationDate": 1820775343.358376, "hostOnly": False, "httpOnly": True, "name": "ps_l", "path": "/", "sameSite": "lax", "secure": True, "session": False, "storeId": "0", "value": "1"},
  {"domain": ".facebook.com", "expirationDate": 1820775343.358549, "hostOnly": False, "httpOnly": True, "name": "ps_n", "path": "/", "sameSite": "no_restriction", "secure": True, "session": False, "storeId": "0", "value": "1"},
  {"domain": ".facebook.com", "expirationDate": 1786820212.9023, "hostOnly": False, "httpOnly": False, "name": "locale", "path": "/", "sameSite": "no_restriction", "secure": True, "session": False, "storeId": "0", "value": "ru_RU"},
  {"domain": ".facebook.com", "expirationDate": 1817755688.745352, "hostOnly": False, "httpOnly": False, "name": "c_user", "path": "/", "sameSite": "no_restriction", "secure": True, "session": False, "storeId": "0", "value": "1138688454"},
  {"domain": ".facebook.com", "hostOnly": False, "httpOnly": False, "name": "presence", "path": "/", "sameSite": "unspecified", "secure": True, "session": True, "storeId": "0", "value": "C%7B%22t3%22%3A%5B%5D%2C%22utc3%22%3A1786219001995%2C%22v%22%3A1%7D"},
  {"domain": ".facebook.com", "expirationDate": 1793995688.745461, "hostOnly": False, "httpOnly": True, "name": "fr", "path": "/", "sameSite": "no_restriction", "secure": True, "session": False, "storeId": "0", "value": "1p6XVXJlRu8jlIsbL.AWcCuLnn3n_YPaPxxTzJzXn1P8HDDfm0QT8j0Gn34OfN_geBHow.Bqd4yo..AAA.0.0.Bqd4yo.AWcVJu5TS1C30um2jmCOEeX0rGY"},
  {"domain": ".facebook.com", "expirationDate": 1817755688.745499, "hostOnly": False, "httpOnly": True, "name": "xs", "path": "/", "sameSite": "no_restriction", "secure": True, "session": False, "storeId": "0", "value": "15%3AZYEkSUzwebObXw%3A2%3A1786215425%3A-1%3A-1%3A%3AAcy0u7S7eHkP2gDkvp35LFfMmX26fo7HiLHboUPWAA"},
  {"domain": ".facebook.com", "expirationDate": 1786824693, "hostOnly": False, "httpOnly": False, "name": "wd", "path": "/", "sameSite": "lax", "secure": True, "session": False, "storeId": "0", "value": "1081x743"}
]

conn = psycopg2.connect(DB_URL, connect_timeout=15)
cur = conn.cursor()
cur.execute("INSERT INTO app_settings(key, value) VALUES(%s, %s) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value", ("fb_cookies_json", json.dumps(cookies)))
conn.commit()
conn.close()

print("✅ Новые куки сохранены!")
print(f"   Куки: {len(cookies)} штук")
print(f"   c_user: 1138688454")
print(f"   xs обновлен: ✓")
print(f"\n🚀 Railway перезагрузится и начнет парсить!")
