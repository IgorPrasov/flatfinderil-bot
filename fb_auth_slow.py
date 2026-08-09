import psycopg2
import json
import time
from playwright.sync_api import sync_playwright

DB_URL = "postgresql://postgres:NOgPcBAEMFuWIwVhLDtOJvxscXeEhtgI@kodama.proxy.rlwy.net:38517/railway"
FB_EMAIL = "djigorprasov@gmail.com"
FB_PASSWORD = "AgathaAlina0710."

print("🚀 Авторизация на Facebook...")
print("   Браузер откроется - введи данные и пройди верификацию если нужна")
print()

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=False, slow_mo=1000)
    context = browser.new_context(viewport={"width": 1280, "height": 900}, locale="ru-RU")
    page = context.new_page()

    try:
        page.goto("https://www.facebook.com", wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        
        print("📧 Вводю email...")
        page.locator('input[name="email"]').fill(FB_EMAIL, delay=100)
        time.sleep(2)
        
        print("🔐 Вводю пароль...")
        page.locator('input[name="pass"]').fill(FB_PASSWORD, delay=100)
        time.sleep(2)
        
        print("🔓 Нажимаю кнопку входа...")
        page.locator('button[name="login"]').click()
        
        print("\n⏳ Жду загрузки (30 сек)...")
        print("   Если появится верификация - пройди её в браузере")
        print()
        
        time.sleep(10)
        
        # Ждем когда пользователь завершит верификацию
        input("🔓 Нажми ENTER когда ты залогинен в браузере: ")
        
        time.sleep(2)

        cookies = [c for c in context.cookies() if ".facebook.com" in c.get("domain", "")]
        
        if cookies:
            print(f"\n✅ Найдено {len(cookies)} cookies")
            conn = psycopg2.connect(DB_URL, connect_timeout=15)
            cur = conn.cursor()
            cur.execute("INSERT INTO app_settings(key, value) VALUES(%s, %s) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value", ("fb_cookies_json", json.dumps(cookies)))
            conn.commit()
            print("✅ Cookies сохранены в базу!")
            print("\n🎉 Готово! Браузер закроется через 5 сек...")
            time.sleep(5)
        else:
            print("❌ Cookies не найдены")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        browser.close()
