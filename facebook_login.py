#!/usr/bin/env python3
import psycopg2
import json
import time
import sys
from playwright.sync_api import sync_playwright

DB_URL = "postgresql://postgres:NOgPcBAEMFuWIwVhLDtOJvxscXeEhtgI@kodama.proxy.rlwy.net:38517/railway"
FB_EMAIL = "djigorprasov@gmail.com"
FB_PASSWORD = "AgathaAlina0710."

print("\n" + "=" * 70)
print("🔐 FACEBOOK 2FA LOGIN - VERBOSE MODE")
print("=" * 70 + "\n")

browser = None
page = None

try:
    print("[1/10] Запускаю Playwright...")
    pw = sync_playwright().__enter__()
    print("[2/10] Запускаю браузер...")
    browser = pw.chromium.launch(headless=False, slow_mo=1000)
    print(f"       ✓ Браузер открыт: {browser}")
    
    print("[3/10] Создаю контекст...")
    context = browser.new_context(
        viewport={"width": 1280, "height": 900},
        locale="ru-RU"
    )
    print(f"       ✓ Контекст создан")
    
    print("[4/10] Создаю страницу...")
    page = context.new_page()
    print(f"       ✓ Страница создана")

    print("[5/10] Открываю Facebook...")
    try:
        page.goto("https://www.facebook.com", wait_until="domcontentloaded", timeout=30000)
        print(f"       ✓ Facebook загружен")
        print(f"       URL: {page.url}")
    except Exception as e:
        print(f"       ❌ Ошибка загрузки: {e}")
        raise

    time.sleep(3)

    print("[6/10] Вводю email...")
    try:
        email_input = page.locator('input[name="email"]')
        email_input.fill(FB_EMAIL)
        print(f"       ✓ Email введен")
    except Exception as e:
        print(f"       ❌ Ошибка: {e}")
        raise

    time.sleep(1)

    print("[7/10] Вводю пароль...")
    try:
        password_input = page.locator('input[name="pass"]')
        password_input.fill(FB_PASSWORD)
        print(f"       ✓ Пароль введен")
    except Exception as e:
        print(f"       ❌ Ошибка: {e}")
        raise

    time.sleep(1)

    print("[8/10] Нажимаю кнопку входа...")
    try:
        login_button = page.locator('button[name="login"]')
        login_button.click()
        print(f"       ✓ Кнопка нажата")
    except Exception as e:
        print(f"       ❌ Ошибка: {e}")
        raise

    time.sleep(3)
    print(f"       URL после клика: {page.url}")

    print("[9/10] Жду 2FA (до 2 минут)...")
    for i in range(24):
        time.sleep(5)
        elapsed = (i + 1) * 5
        print(f"        {elapsed:3d}с | URL: {page.url[:70]}")

        if "facebook.com/" in page.url and "login" not in page.url.lower():
            print("       ✅ Успех!")
            break

    print("[10/10] Экспортирую cookies...")
    try:
        cookies = context.cookies()
        print(f"        Всего cookies: {len(cookies)}")
        
        fb_cookies = [c for c in cookies if ".facebook.com" in c.get("domain", "")]
        print(f"        Facebook cookies: {len(fb_cookies)}")
        
        if fb_cookies:
            print(f"        Сохраняю в БД...")
            conn = psycopg2.connect(DB_URL, connect_timeout=15)
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO app_settings(key, value) VALUES(%s, %s) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value",
                ("fb_cookies_json", json.dumps(fb_cookies))
            )
            conn.commit()
            conn.close()
            print(f"        ✅ Сохранено!")
        else:
            print(f"        ⚠️ Facebook cookies не найдены!")
            
    except Exception as e:
        print(f"        ❌ Ошибка: {e}")
        raise

    print("\n" + "=" * 70)
    print("🎉 УСПЕШНО ЗАВЕРШЕНО!")
    print("=" * 70)

except Exception as e:
    print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА:")
    print(f"   {e}")
    import traceback
    traceback.print_exc()
    print("\n💡 Возможные причины:")
    print("   • Facebook блокирует новое подключение")
    print("   • Требуется 2FA проверка на новом месте")
    print("   • HTML структура изменилась")

finally:
    print("\n⏳ Жду 3 сек перед закрытием браузера...")
    time.sleep(3)
    
    if page:
        print("Закрываю страницу...")
        try:
            page.close()
        except:
            pass
    
    if browser:
        print("Закрываю браузер...")
        try:
            browser.close()
        except:
            pass
    
    print("✅ Завершено")