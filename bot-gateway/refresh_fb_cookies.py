"""
refresh_fb_cookies.py — Обновляет cookies.txt из Chrome Profile 1.

Запускать перед facebook_parser.py если куки устарели:
  python3 refresh_fb_cookies.py

Работает только когда Chrome открыт и залогинен в Facebook.
"""
import os, sys, time

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "cookies.txt")
SESSION_DIR  = os.path.join(os.path.dirname(__file__), "fb_session")
CHROME_PROFILE = os.path.expanduser(
    "~/Library/Application Support/Google/Chrome/Profile 1/Cookies"
)


def refresh():
    try:
        import browser_cookie3
    except ImportError:
        print("❌ browser_cookie3 не установлен: pip install browser_cookie3")
        sys.exit(1)

    if not os.path.exists(CHROME_PROFILE):
        print(f"❌ Chrome Profile 1 не найден: {CHROME_PROFILE}")
        sys.exit(1)

    print("🍪 Читаем cookies из Chrome Profile 1...")
    jar = browser_cookie3.chrome(domain_name="facebook.com", cookie_file=CHROME_PROFILE)
    cookies = list(jar)

    has_auth = any(c.name == "c_user" for c in cookies) and any(c.name == "xs" for c in cookies)
    if not has_auth:
        print("⚠️  Не нашли c_user / xs — убедитесь что залогинены в Facebook в Chrome (Profile 1)")
        sys.exit(1)

    # Сохраняем в Netscape format
    with open(COOKIE_FILE, "w") as f:
        f.write("# Netscape HTTP Cookie File\n")
        f.write(f"# Extracted from Chrome Profile 1 at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        for c in cookies:
            domain = c.domain if c.domain.startswith(".") else "." + c.domain
            path   = c.path or "/"
            secure = "TRUE" if c.secure else "FALSE"
            expires = int(c.expires) if c.expires else int(time.time()) + 86400 * 365
            f.write(f"{domain}\tTRUE\t{path}\t{secure}\t{expires}\t{c.name}\t{c.value}\n")

    print(f"✅ Сохранено {len(cookies)} cookies → cookies.txt")
    print(f"   Имена: {[c.name for c in cookies]}")

    # Обновляем fb_session persistent context
    if os.path.isdir(SESSION_DIR):
        print("📁 Обновляем fb_session...")
        try:
            from playwright.sync_api import sync_playwright

            cookies_data = []
            with open(COOKIE_FILE) as f:
                for line in f:
                    if line.startswith("#") or not line.strip():
                        continue
                    parts = line.strip().split("\t")
                    if len(parts) >= 7:
                        domain, _, path, secure, expiry, name, value = parts[:7]
                        cookies_data.append({
                            "name": name, "value": value,
                            "domain": domain, "path": path,
                            "secure": secure == "TRUE",
                            "expires": int(expiry) if expiry.isdigit() else -1,
                        })

            with sync_playwright() as pw:
                ctx = pw.chromium.launch_persistent_context(
                    user_data_dir=SESSION_DIR,
                    headless=True,
                )
                ctx.add_cookies(cookies_data)
                ctx.close()
            print("✅ fb_session обновлён")
        except Exception as e:
            print(f"⚠️  fb_session не обновлён: {e}")

    print("\n🚀 Готово! Теперь запускайте: python3 facebook_parser.py")


if __name__ == "__main__":
    refresh()
