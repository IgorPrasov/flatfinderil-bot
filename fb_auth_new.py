import psycopg2
import json
import time
from playwright.sync_api import sync_playwright

DB_URL = "postgresql://postgres:NOgPcBAEMFuWIwVhLDtOJvxscXeEhtgI@kodama.proxy.rlwy.net:38517/railway"
FB_EMAIL = "djigorprasov@gmail.com"
FB_PASSWORD = "AgathaAlina0710."

print("🚀 Авторизация на Facebook...")

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=False, slow_mo=300)
    context = browser.new_context(viewport={"width": 1280, "height": 900}, locale="ru-RU")
    page = context.new_page()

    try:
        page.goto("https://www.facebook.com", wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
        
        print("📧 Вводю email...")
        page.locator('input[name="email"]').fill(FB_EMAIL)
        time.sleep(1)
        
        print("🔐 Вводю пароль...")
        page.locator('input[name="pass"]').fill(FB_PASSWORD)
        time.sleep(1)
        
        print("🔓 Нажимаю кнопку входа...")
        page.locator('button[name="login"]').click()
        
        # Ждем загрузки
        try:
            page.wait_for_url("https://www.facebook.com/", timeout=30000)
        except:
            pass
        
        time.sleep(3)
        print(f"✅ URL: {page.url}")

        cookies = [c for c in context.cookies() if ".facebook.com" in c.get("domain", "")]
        
        if cookies:
            print(f"✅ Найдено {len(cookies)} cookies")
            conn = psycopg2.connect(DB_URL, connect_timeout=15)
            cur = conn.cursor()
            cur.execute("INSERT INTO app_settings(key, value) VALUES(%s, %s) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value", ("fb_cookies_json", json.dumps(cookies)))
            conn.commit()
            print("✅ Cookies сохранены в базу!")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        time.sleep(2)
        browser.close()
