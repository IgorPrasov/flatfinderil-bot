import psycopg2
import json
import time
from playwright.sync_api import sync_playwright

DB_URL = "postgresql://postgres:NOgPcBAEMFuWIwVhLDtOJvxscXeEhtgI@kodama.proxy.rlwy.net:38517/railway"

print("🚀 Авторизация на Facebook с 2FA на Railway сервере\n")

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=False, args=["--disable-gpu"])
    context = browser.new_context(viewport={"width": 1280, "height": 900}, locale="ru-RU")
    page = context.new_page()

    try:
        print("📱 Открываю Facebook...")
        page.goto("https://www.facebook.com/login", wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
        
        print("📧 Вводю djigorprasov@gmail.com...")
        page.locator('input[name="email"]').fill("djigorprasov@gmail.com", delay=50)
        time.sleep(1)
        
        print("🔐 Вводю пароль...")
        page.locator('input[name="pass"]').fill("AgathaAlina0710.", delay=50)
        time.sleep(1)
        
        print("🔓 Нажимаю кнопку входа...")
        page.locator('button[name="login"]').click()
        
        print("\n⏳ Жду загрузки (проверь браузер)...\n")
        time.sleep(5)
        
        # Ждем ввода кода 2FA
        print("📲 Если Facebook попросил код 2FA:")
        print("   1. Проверь SMS/Email")
        print("   2. Введи код в браузер")
        print("   3. Нажми Enter здесь когда страница загрузится\n")
        
        input("🔓 Нажми ENTER когда ты залогинен: ")
        
        time.sleep(2)
        
        print("\n💾 Экспортирую cookies...")
        cookies = [c for c in context.cookies() if ".facebook.com" in c.get("domain", "")]
        
        if cookies:
            print(f"✅ Найдено {len(cookies)} Facebook cookies")
            
            conn = psycopg2.connect(DB_URL, connect_timeout=15)
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO app_settings(key, value) VALUES(%s, %s) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",
                ("fb_cookies_json", json.dumps(cookies))
            )
            conn.commit()
            conn.close()
            
            print("✅ Cookies сохранены в базу Railway!")
            print("\n🎉 Авторизация успешна!")
            print("   🚀 Парсер начнет работать через 1-2 минуты")
        else:
            print("❌ Cookies не найдены")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        time.sleep(2)
        browser.close()
