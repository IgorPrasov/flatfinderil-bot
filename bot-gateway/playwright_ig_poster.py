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
    """
    Возвращает полный список web-cookies для instagram.com.
    Приоритет:
      1. IG_WEB_COOKIES_JSON env var — полный список из браузера (csrftoken, datr, etc.)
      2. DB/файл/IG_SESSION_JSON — только sessionid + ds_user_id (минимум)
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    # Priority 1: full web cookies JSON (set by admin from browser export)
    web_json = os.environ.get("IG_WEB_COOKIES_JSON", "").strip()
    if not web_json:
        try:
            import database as _db
            web_json = _db.get_setting("ig_web_cookies_json") or ""
        except Exception:
            pass
    if web_json:
        try:
            cookies = json.loads(web_json)
            if isinstance(cookies, list) and any(c.get("name") == "sessionid" for c in cookies):
                log.info(f"🍪 Используем полные web-cookies ({len(cookies)} шт.)")
                return cookies
        except Exception as e:
            log.debug(f"IG_WEB_COOKIES_JSON parse error: {e}")

    # Priority 2: minimal cookies from instagrapi settings (DB → file → env)
    for source_name, get_cookies in [
        ("DB", lambda: _get_cookies_from_db()),
        ("file", lambda: _get_cookies_from_file()),
        ("IG_SESSION_JSON", lambda: _get_cookies_from_env()),
    ]:
        try:
            cookies = get_cookies()
            if cookies:
                log.info(f"🍪 Используем минимальные cookies из {source_name}")
                return cookies
        except Exception as e:
            log.debug(f"{source_name}: {e}")

    raise RuntimeError("❌ Instagram cookies не найдены для Playwright")


def _get_cookies_from_db() -> list:
    import database as _db
    settings_json = _db.get_ig_settings_json()
    if not settings_json:
        return []
    return _dict_to_playwright_cookies(json.loads(settings_json).get("cookies", {}))


def _get_cookies_from_file() -> list:
    if not os.path.exists(SESSION_FILE):
        return []
    with open(SESSION_FILE) as f:
        settings = json.load(f)
    return _dict_to_playwright_cookies(settings.get("cookies", {}))


def _get_cookies_from_env() -> list:
    env_json = os.environ.get("IG_SESSION_JSON", "").strip()
    if not env_json:
        return []
    return _dict_to_playwright_cookies(json.loads(env_json).get("cookies", {}))


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
                # The "+" button in the left sidebar
                'span[class*="x1lliihq"]:has-text("Create")',
                '[role="button"]:has(svg)',
                'a[role="link"]:has(svg[aria-label])',
            ]
            create_btn = None
            for sel in create_selectors:
                try:
                    create_btn = await page.wait_for_selector(sel, timeout=5000)
                    if create_btn:
                        log.info(f"  ✅ Кнопка Create найдена: {sel}")
                        break
                except PWTimeout:
                    pass

            # If not found by selectors, look for "Create new post" dialog already open
            try:
                dialog = await page.wait_for_selector('text="Create new post"', timeout=2000)
                if dialog:
                    log.info("  ℹ️  Диалог 'Create new post' уже открыт")
                    create_btn = None  # No need to click
            except PWTimeout:
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

            # Step 3: Click "Select from computer" and upload file
            log.info(f"📁 Загружаем файл: {image_path}")
            # Click "Select from computer" button to activate the file input
            try:
                select_btn = await page.wait_for_selector(
                    'button:has-text("Select from computer")', timeout=8000
                )
                # Set up file chooser handler before clicking
                async with page.expect_file_chooser() as fc_info:
                    await select_btn.click()
                fc = await fc_info.value
                await fc.set_files(image_path)
                log.info(f"  ✅ Файл загружен через file chooser")
            except Exception as fc_err:
                log.warning(f"  ⚠️  File chooser не сработал ({fc_err}), прямой ввод…")
                # Fallback: set directly on hidden input
                file_input = page.locator('input[type="file"]').first
                await file_input.set_input_files(image_path)
            await page.wait_for_timeout(3000)

            # Step 4: Navigate through dialog (may need multiple "Next" clicks)
            log.info("➡️  Переходим к следующим шагам…")
            for step in range(3):
                try:
                    next_btn = await page.wait_for_selector(
                        '[role="button"]:has-text("Next"), button:has-text("Next")',
                        timeout=5000,
                    )
                    if next_btn:
                        await next_btn.click(force=True)
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
            # Instagram puts "Share" in the dialog header — scope search to dialog
            log.info("🚀 Публикуем пост…")
            share_clicked = await page.evaluate("""
                () => {
                    // The dialog has header with "Create new post" and a "Share" button
                    // Find the dialog container first
                    const dialogs = document.querySelectorAll('[role="dialog"], div[class*="modal"], div[class*="Modal"]');
                    const containers = dialogs.length > 0
                        ? [...dialogs]
                        : [document.body];

                    // Look for Share in dialog header area
                    for (const container of containers) {
                        const buttons = [...container.querySelectorAll('[role="button"], button, div')];
                        // Prefer exact match of leaf-node "Share"
                        const share = buttons.find(e =>
                            e.children.length === 0 && e.textContent.trim() === 'Share'
                        );
                        if (share) {
                            share.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
                            return 'leaf:' + share.tagName;
                        }
                    }

                    // Fallback: any element whose direct text is Share
                    const allEls = [...document.querySelectorAll('*')];
                    const leafShare = allEls.find(e =>
                        e.children.length === 0 &&
                        e.textContent.trim() === 'Share' &&
                        !e.closest('article')  // exclude feed posts
                    );
                    if (leafShare) {
                        leafShare.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
                        return 'fallback:' + leafShare.tagName;
                    }
                    return null;
                }
            """)
            if share_clicked:
                log.info(f"  ✅ Share нажата через JS ({share_clicked})")
            else:
                # Last resort: Playwright selector scoped to dialog
                share_btn = None
                for sel in [
                    '[role="dialog"] [role="button"]:has-text("Share")',
                    '[role="dialog"] button:has-text("Share")',
                    '[role="button"]:has-text("Share")',
                ]:
                    try:
                        share_btn = page.locator(sel).last
                        await share_btn.click(force=True, timeout=3000)
                        log.info(f"  ✅ Share нажата через Playwright ({sel})")
                        share_clicked = True
                        break
                    except Exception:
                        pass
                if not share_clicked:
                    raise RuntimeError("Кнопка Share не найдена")

            # Step 7: Wait for success / submission processing
            log.info("⏳ Ожидаем публикации…")
            await page.wait_for_timeout(8000)

            # Check for success indicators
            success = False
            success_selectors = [
                'text="Your post has been shared."',
                'text="Post shared"',
                '[aria-label="Post shared"]',
                'text="Your reel has been shared."',
            ]
            for sel in success_selectors:
                try:
                    await page.wait_for_selector(sel, timeout=6000)
                    success = True
                    log.info(f"  ✅ Успех! Найден индикатор: {sel}")
                    break
                except PWTimeout:
                    pass

            if not success:
                # Check URL or dialog disappearance
                await page.wait_for_timeout(2000)
                current_url = page.url
                # If redirected to the new post page
                if "instagram.com/p/" in current_url or "instagram.com/reel/" in current_url:
                    success = True
                    log.info(f"  ✅ Успех! Перенаправлен на пост: {current_url}")

                # Check if dialog is gone (post was shared and dialog closed)
                if not success:
                    dialog_gone = await page.evaluate("""
                        () => {
                            const hasCreateHeader = document.body.innerText.includes('Create new post');
                            return !hasCreateHeader;
                        }
                    """)
                    if dialog_gone:
                        success = True
                        log.info("  ✅ Диалог закрылся — пост, вероятно, опубликован")

            if success:
                log.info("✅ Пост опубликован!")
                return {"ok": True, "method": "playwright"}
            else:
                log.warning("⚠️  Статус публикации неизвестен (success indicator not found)")
                return {"ok": True, "method": "playwright", "note": "status unknown — check Instagram manually"}

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
