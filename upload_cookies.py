#!/usr/bin/env python3
import psycopg2
import json

DB_URL = "postgresql://postgres:NOgPcBAEMFuWIwVhLDtOJvxscXeEhtgI@kodama.proxy.rlwy.net:38517/railway"

COOKIES = [
  {"domain": ".facebook.com", "expirationDate": 1820775294.229059, "hostOnly": False, "httpOnly": True, "name": "datr", "path": "/", "sameSite": "no_restriction", "secure": True, "session": False, "storeId": "0", "value": "fnt3asexf_NJ3t-76Yyn42bj"},
  {"domain": ".facebook.com", "expirationDate": 1820775426.943836, "hostOnly": False, "httpOnly": True, "name": "sb", "path": "/", "sameSite": "no_restriction", "secure": True, "session": False, "storeId": "0", "value": "kHt3agfR3AEr5JoHOSRu2FZO"},
  {"domain": ".facebook.com", "expirationDate": 1820775343.358376, "hostOnly": True, "httpOnly": True, "name": "ps_l", "path": "/", "sameSite": "lax", "secure": True, "session": False, "storeId": "0", "value": "1"},
  {"domain": ".facebook.com", "expirationDate": 1820775343.358549, "hostOnly": False, "httpOnly": True, "name": "ps_n", "path": "/", "sameSite": "no_restriction", "secure": True, "session": False, "storeId": "0", "value": "1"},
  {"domain": ".facebook.com", "expirationDate": 1786820212.9023, "hostOnly": False, "httpOnly": False, "name": "locale", "path": "/", "sameSite": "no_restriction", "secure": True, "session": False, "storeId": "0", "value": "ru_RU"},
  {"domain": ".facebook.com", "expirationDate": 1817755000.694685, "hostOnly": False, "httpOnly": False, "name": "c_user", "path": "/", "sameSite": "no_restriction", "secure": True, "session": False, "storeId": "0", "value": "1138688454"},
  {"domain": ".facebook.com", "expirationDate": 1793995000.694767, "hostOnly": False, "httpOnly": True, "name": "fr", "path": "/", "sameSite": "no_restriction", "secure": True, "session": False, "storeId": "0", "value": "1HyNzueFoaT82n8UD.AWdxEyfcjk7wub0PzfNqB9coKBHgIGViy_HNAmNwPtruhnu7j7Q.Bqd4n3..AAA.0.0.Bqd4n3.AWebSvGy7UQnRw_j3bhsONv-RqM"},
  {"domain": ".facebook.com", "expirationDate": 1817755000.694808, "hostOnly": False, "httpOnly": True, "name": "xs", "path": "/", "sameSite": "no_restriction", "secure": True, "session": False, "storeId": "0", "value": "15%3AZYEkSUzwebObXw%3A2%3A1786215425%3A-1%3A-1%3A%3AAcwxW_ZJDqOw_y_MCdW5DnzFiUBJ1YdhHdB4jVE4PQ"},
  {"domain": ".facebook.com", "hostOnly": False, "httpOnly": False, "name": "presence", "path": "/", "sameSite": "unspecified", "secure": True, "session": True, "storeId": "0", "value": "C%7B%22t3%22%3A%5B%5D%2C%22utc3%22%3A1786219001995%2C%22v%22%3A1%7D"},
  {"domain": ".facebook.com", "expirationDate": 1786823808, "hostOnly": False, "httpOnly": False, "name": "wd", "path": "/", "sameSite": "lax", "secure": True, "session": False, "storeId": "0", "value": "1081x743"}
]

print("\n" + "=" * 70)
print("🔐 ЗАГРУЗКА FACEBOOK COOKIES")
print("=" * 70 + "\n")
print(f"📋 Cookies к загрузке: {len(COOKIES)} шт")
print(f"   ✓ c_user: да")
print(f"   ✓ xs: да")
print("\n📤 Загружаю в базу Railway...")

try:
    conn = psycopg2.connect(DB_URL, connect_timeout=15)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO app_settings(key, value) VALUES(%s, %s) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",
        ("fb_cookies_json", json.dumps(COOKIES))
    )
    conn.commit()
    conn.close()
    print("   ✅ Cookies успешно загружены!\n")
    print("=" * 70)
    print("🎉 ГОТОВО!")
    print("=" * 70)
    print("\n🚀 Railway парсер начнет собирать объявления за 1-2 минуты!\n")
except Exception as e:
    print(f"\n❌ Ошибка: {e}")
    import traceback
    traceback.print_exc()
