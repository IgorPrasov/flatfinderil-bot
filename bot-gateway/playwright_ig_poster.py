#!/usr/bin/env python3
"""
playwright_ig_poster.py — Публикация в Instagram через браузер (Playwright).

Использует веб-интерфейс instagram.com, а не мобильный API instagrapi.
Это обходит блокировку дата-центровых IP для мобильного API.
"""
import asyncio
import json
import logging
import os
import sys
import tempfile
import time
from pathlib import Path

log = logging.getLogger("pw_ig")

SESSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ig_session.json")


def _get_session_cookies() -> list:
    """Возвращает список cookies для instagram.com из сохранённой сессии."""
    # Priority 1: DB
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import database as _db
        settings_json = _db.get_ig_settings_json()
        if settings_json:
            settings = json.loads(settings_json)
            cookies_dict = settings.get("cookies", {})
            if cookies_dict.get("sessionid"):
                return _dict_to_playwright_cookies(cookies_dict)
    except Exception as e:
        log.debug(f"DB cookies: {e}")

    # Priority 2: file
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE) as f:
                settings = json.load(f)
            cookies_dict = settings.get("cookies", {})
            if cookies_dict.get("sessionid"):
                return _dict_to_playwright_cookies(cookies_dict)
        except Exception as e:
            log.debug(f"File cookies: {e}")

    # Priority 3: env var
    env_json = os.environ.get("IG_SESSION_JSON", "").strip()
    if env_json:
        try:
            settings = json.loads(env_json)
            cookies_dict = settings.get("cookies", {})
            if cookies_dict.get("sessionid"):
                return _dict_to_playwright_cookies(cookies_dict)
        except Exception as e:
            log.debug(f"Env var cookies: {e}")

    raise RuntimeError("❌ Instagram сессия не найдена для Playwright")


def _dict_to_playwright_cookies(cookies_dict: dict) -> list:
    """Конвертирует dict cookies в формат Playwright."""
    result = []
    for name, value in cookies_dict.items():
        if value:
            result.append({
                "name": name,
                "value": str(value),
                "domain": ".instagram.com",
                "path": "/",
                "httpOnly": name in ("sessionid", "ds_user_id"),
                "secure": True,
                "sameSite": "None",
            })
    return result


async def _post_to_instagram_async(caption: str, image_path: str) -> dict:
    """Асинхронная функция публикации через Playwright."""
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout

    cookies = _get_session_cookies()
    sessionid = next((c["value"] for c in cookies if c["name"] == "sessionid"), "")
    log.info(f"🌐 Playwright: сессия {sessionid[:20]}…")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )
        await ctx.add_cookies(cookies)
        page = await ctx.new_page()

        try:
            # Step 1: Verify logged in
            log.info("🔑 Проверяем авторизацию…")
            await page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            # Check if logged in by looking for "Create" button or profile icon
            is_logged_in = False
            for selector in [
                'svg[aria-label="New post"]',
                'svg[aria-label="Home"]',
                '[data-testid="new-post-button"]',
                'a[href="/"]',
            ]:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                    is_logged_in = True
                    break
                except PWTimeout:
                    pass

            # Also check URL (might redirect to login)
            if "accounts/login" in page.url:
                is_logged_in = False

            if not is_logged_in:
                log.warning("⚠️  Не удалось подтвердить авторизацию Instagram")
                # Try navigating anyway and see if we can proceed

            log.info(f"✅ Страница загружена: {page.url[:50]}")

            # Step 2: Click "Create" / "+" button
            log.info("📸 Открываем форму создания поста…")
            create_selectors = [
                'svg[aria-label="New post"]',
                '[aria-label="New post"]',
                'svg[aria-label="Create"]',
                '[aria-label="Create"]',
                'a[href="#"][role="link"]:has(svg)',
            ]
            create_btn = None
            for sel in create_selectors:
                try:
                    create_btn = await page.wait_for_selector(sel, timeout=5000)
                    if create_btn:
                        break
                except PWTimeout:
                    pass

            if not create_btn:
                raise RuntimeError("Не найдена кнопка создания поста (Create/New post)")

            await create_btn.click()
            await page.wait_for_timeout(2000)

            # May need to click "Post" from a submenu
            try:
                post_option = await page.wait_for_selector('text="Post"', timeout=3000)
                if post_option:
                    await post_option.click()
                    await page.wait_for_timeout(1500)
            except PWTimeout:
                pass  # No submenu needed

            # Step 3: Upload file
            log.info(f"📁 Загружаем файл: {image_path}")
            file_input = await page.wait_for_selector('input[type="file"]', timeout=10000)
            await file_input.set_input_files(image_path)
            await page.wait_for_timeout(3000)

            # Step 4: Navigate through dialog (may need multiple "Next" clicks)
            log.info("➡️  Переходим к следующим шагам…")
            for step in range(3):
                try:
                    next_btn = await page.wait_for_selector(
                        'button:has-text("Next"), div[role="button"]:has-text("Next")',
                        timeout=5000,
                    )
                    if next_btn:
                        await next_btn.click()
                        await page.wait_for_timeout(2000)
                        log.info(f"  ➡️  Шаг {step + 1}/3 пройден")
                except PWTimeout:
                    log.info(f"  ⚠️  Кнопка Next не найдена на шаге {step + 1}")
                    break

            # Step 5: Enter caption
            log.info("✍️  Вводим подпись…")
            caption_selectors = [
                '[aria-label="Write a caption..."]',
                'div[aria-label*="caption"]',
                'textarea[aria-label*="caption"]',
                '[placeholder*="caption"]',
                'div[contenteditable="true"]',
            ]
            caption_field = None
            for sel in caption_selectors:
                try:
                    caption_field = await page.wait_for_selector(sel, timeout=5000)
                    if caption_field:
                        break
                except PWTimeout:
                    pass

            if caption_field:
                await caption_field.click()
                await page.wait_for_timeout(500)
                await caption_field.type(caption, delay=20)
                await page.wait_for_timeout(1000)
                log.info(f"  ✅ Подпись введена ({len(caption)} символов)")
            else:
                log.warning("  ⚠️  Поле подписи не найдено")

            # Step 6: Share
            log.info("🚀 Публикуем пост…")
            share_selectors = [
                'button:has-text("Share")',
                'div[role="button"]:has-text("Share")',
                '[aria-label="Share"]',
            ]
            share_btn = None
            for sel in share_selectors:
                try:
                    share_btn = await page.wait_for_selector(sel, timeout=5000)
                    if share_btn:
                        break
                except PWTimeout:
                    pass

            if not share_btn:
                raise RuntimeError("Кнопка Share не найдена")

            await share_btn.click()
            log.info("  ✅ Кнопка Share нажата")

            # Step 7: Wait for success
            await page.wait_for_timeout(5000)

            # Check for success indicators
            success = False
            success_selectors = [
                'text="Your post has been shared."',
                'text="Post shared"',
                '[aria-label="Post shared"]',
            ]
            for sel in success_selectors:
                try:
                    await page.wait_for_selector(sel, timeout=8000)
                    success = True
                    break
                except PWTimeout:
                    pass

            if not success:
                # Check if we're still on the share page or redirected
                await page.wait_for_timeout(3000)
                current_url = page.url
                if "instagram.com/p/" in current_url or "instagram.com/" == current_url:
                    success = True  # Likely posted successfully

            if success:
                log.info("✅ Пост опубликован!")
                return {"ok": True, "method": "playwright"}
            else:
                log.warning("⚠️  Статус публикации неизвестен (Success indic. not found)")
                return {"ok": True, "method": "playwright", "note": "status unknown — may have posted"}

        except Exception as e:
            log.error(f"❌ Playwright ошибка: {e}", exc_info=True)
            # Take screenshot for debugging
            try:
                ss_path = f"/tmp/ig_error_{int(time.time())}.png"
                await page.screenshot(path=ss_path)
                log.info(f"📸 Screenshot: {ss_path}")
            except Exception:
                pass
            raise
        finally:
            await browser.close()


def post_via_playwright(caption: str, image_path: str) -> dict:
    """
    Синхронная обёртка для публикации через Playwright.
    Возвращает dict с результатом.
    """
    return asyncio.run(_post_to_instagram_async(caption, image_path))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--caption", required=True)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = post_via_playwright(args.caption, args.image)
    print(json.dumps(result, ensure_ascii=False, indent=2))
