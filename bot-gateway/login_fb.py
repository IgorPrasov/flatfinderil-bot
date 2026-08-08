"""
login_fb.py — Открывает Facebook в браузере, ждёт ручного входа,
сохраняет сессию в fb_session/ для дальнейшего использования fb_page_content.py.

Запуск:
  python3 login_fb.py
"""
import json
import os
import time
from playwright.sync_api import sync_playwright

SESSION_DIR = os.path.join(os.path.dirname(__file__), "fb_session")
COOKIES_FILE = os.path.join(os.path.dirname(__file__), "cookies.txt")
PAGE_URL = "https://www.facebook.com"

def main():
    print("🌐 Открываем Facebook в браузере...")
    print("   Войдите в аккаунт и перейдите на вашу страницу.")
    print("   После входа нажмите Enter в этом терминале.")

    os.makedirs(SESSION_DIR, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,
            viewport={"width": 1280, "height": 900},
            locale="ru-RU",
        )
        page = browser.new_page() if browser.pages == [] else browser.pages[0]
        page.goto(PAGE_URL, wait_until="domcontentloaded")

        print("\n⏳ Ожидаем входа в Facebook (до 3 минут)...")
        print("   Войдите в аккаунт в открытом окне браузера.")

        # Poll until logged in (no login form visible)
        deadline = time.time() + 600
        logged_in = False
        while time.time() < deadline:
            time.sleep(3)
            try:
                url = page.url
                # After login, facebook.com/ redirects to feed or shows profile
                if "facebook.com" in url and "login" not in url and "checkpoint" not in url:
                    # Check for presence of user-specific element
                    is_logged = page.evaluate("""
                    () => {
                        // If there's no login form and we have a nav with profile link
                        const loginForm = document.querySelector('[data-testid="royal_login_form"]');
                        const loginBtn = [...document.querySelectorAll('[role="button"]')]
                            .find(b => b.textContent.trim() === 'Войти' || b.textContent.trim() === 'Log In');
                        return !loginForm && !loginBtn;
                    }
                    """)
                    if is_logged:
                        print("✅ Вход выполнен!")
                        logged_in = True
                        break
            except Exception:
                pass

        if not logged_in:
            print("⚠️  Время вышло. Сохраняем текущие cookies...")

        time.sleep(2)
        # Save cookies to Netscape format
        cookies = browser.cookies()
        fb_cookies = [c for c in cookies if "facebook.com" in c.get("domain", "")]
        print(f"🍪 Сохраняем {len(fb_cookies)} cookies...")

        with open(COOKIES_FILE, "w") as f:
            f.write("# Netscape HTTP Cookie File\n")
            for c in fb_cookies:
                domain = c["domain"]
                flag = "TRUE" if domain.startswith(".") else "FALSE"
                secure = "TRUE" if c.get("secure") else "FALSE"
                expires = int(c.get("expires") or 0)
                f.write(f"{domain}\t{flag}\t{c['path']}\t{secure}\t{expires}\t{c['name']}\t{c['value']}\n")

        print(f"✅ Сохранено в cookies.txt")
        print(f"✅ Постоянная сессия сохранена в fb_session/")
        browser.close()

if __name__ == "__main__":
    main()
