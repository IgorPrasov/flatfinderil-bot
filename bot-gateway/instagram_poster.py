#!/usr/bin/env python3
"""
instagram_poster.py — Публикация фото/текста в Instagram через instagrapi.

Использование:
  python3 instagram_poster.py --caption "текст" --image path/to/image.jpg
  python3 instagram_poster.py --caption "текст"              # только текст → заглушка-картинка
  python3 instagram_poster.py --dry-run --caption "текст" --image img.jpg

Переменные окружения (Railway):
  IG_USERNAME  — логин Instagram (без @)
  IG_PASSWORD  — пароль Instagram
  IG_SESSION_JSON — JSON сессии (если есть, логин не нужен)
"""

import os
import sys
import json
import logging
import argparse
import tempfile
import time
from pathlib import Path

log = logging.getLogger("ig_poster")
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

SESSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ig_session.json")
LOG_FILE     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ig_posting_log.json")


# ──────────────────────────────────────────────────────────────────────────────
#  Сессия / логин
# ──────────────────────────────────────────────────────────────────────────────

def _restore_full_settings(cl, settings_json: str, source: str) -> bool:
    """
    Восстанавливает клиент из полного JSON настроек instagrapi.
    Сохраняет device fingerprint → Instagram не замечает смену устройства.
    НЕ делает live-запрос к Instagram — серверные IP блокируются для этого.
    Возвращает True при успехе.
    """
    try:
        settings = json.loads(settings_json)
        auth_data = settings.get("authorization_data", {})

        # Если authorization_data говорит «использовать header вместо cookies»,
        # оставляем в cookies только sessionid (как это делает login_by_sessionid).
        # Это предотвращает конфликт: Instagram отклоняет запрос с ds_user_id в cookie
        # при одновременном наличии Authorization-заголовка.
        if auth_data.get("should_use_header_over_cookies"):
            sid = auth_data.get("sessionid") or settings.get("cookies", {}).get("sessionid", "")
            if sid:
                settings = dict(settings)  # shallow copy
                settings["cookies"] = {"sessionid": sid}

        cl.set_settings(settings)
        log.info(f"✅ Полные настройки из {source} применены"
                 f" (cookie-only: {not auth_data.get('should_use_header_over_cookies')})")
        return True
    except Exception as e:
        log.warning(f"⚠️  Не удалось применить настройки из {source}: {e}")
        return False


def _restore_by_sessionid(cl, sessionid: str, source: str) -> bool:
    """Резервный вариант: вход только по sessionid (без сохранения fingerprint)."""
    try:
        cl.login_by_sessionid(sessionid)
        log.info(f"✅ Сессия из {source} (sessionid) восстановлена")
        return True
    except Exception as e:
        log.warning(f"⚠️  Не удалось восстановить сессию из {source}: {e}")
        return False


def _save_settings_to_db(cl):
    """
    Сохраняет полные настройки клиента в БД.
    Вызывается после каждой успешной операции, чтобы обновить cookies/token.
    """
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import database as _db
        settings_json = json.dumps(cl.get_settings(), ensure_ascii=False)
        _db.set_ig_settings_json(settings_json)
        # Дублируем sessionid для обратной совместимости
        sessionid = cl.cookie_dict.get("sessionid", "")
        if sessionid:
            _db.set_ig_session(sessionid)
        log.info("💾 Полные настройки Instagram сохранены в БД")
    except Exception as e:
        log.warning(f"⚠️  Не удалось сохранить настройки в БД: {e}")


def _get_client():
    from instagrapi import Client

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    cl = Client()
    cl.delay_range = [2, 5]

    # ── Приоритет 1: полные настройки из БД (переживают редеплои, сохраняют fingerprint)
    try:
        import database as _db
        full_json = _db.get_ig_settings_json()
        if full_json and _restore_full_settings(cl, full_json, "БД (полные настройки)"):
            return cl
    except Exception as e:
        log.warning(f"⚠️  БД недоступна: {e}")

    # ── Приоритет 2: полные настройки из файла ig_session.json
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                file_json = f.read()
            if _restore_full_settings(cl, file_json, f"файла {SESSION_FILE}"):
                _save_settings_to_db(cl)   # переносим в БД, чтобы пережить редеплой
                return cl
        except Exception as e:
            log.warning(f"⚠️  Не удалось прочитать {SESSION_FILE}: {e}")

    # ── Приоритет 3: полные настройки из env IG_SESSION_JSON
    env_session = os.environ.get("IG_SESSION_JSON", "").strip()
    if env_session:
        if _restore_full_settings(cl, env_session, "IG_SESSION_JSON"):
            _save_settings_to_db(cl)       # переносим в БД
            return cl
        # Fallback: достаём sessionid из env JSON и входим только по нему
        try:
            session_data = json.loads(env_session)
            sessionid = session_data.get("cookies", {}).get("sessionid", "")
            if sessionid and _restore_by_sessionid(cl, sessionid, "IG_SESSION_JSON"):
                _save_settings_to_db(cl)
                return cl
        except Exception:
            pass

    # ── Приоритет 4: только sessionid из БД (старый формат, резервный вариант)
    try:
        import database as _db
        sessionid = _db.get_ig_session()
        if sessionid and _restore_by_sessionid(cl, sessionid, "БД (sessionid)"):
            _save_settings_to_db(cl)       # сохраняем полные настройки для следующего раза
            return cl
    except Exception as e:
        log.warning(f"⚠️  Не удалось получить sessionid из БД: {e}")

    raise RuntimeError(
        "❌ Instagram сессия не найдена. "
        "Подключи аккаунт в бэкофисе → Instagram → 🔑 Сохранить sessionid."
    )


# ──────────────────────────────────────────────────────────────────────────────
#  Генерация заглушки-картинки (если изображение не передано)
# ──────────────────────────────────────────────────────────────────────────────

def _make_placeholder_image(caption: str) -> str:
    """Создаёт простую 1080×1080 картинку с текстом для публикации без фото."""
    from PIL import Image, ImageDraw, ImageFont
    import textwrap

    img = Image.new("RGB", (1080, 1080), color=(26, 31, 58))
    draw = ImageDraw.Draw(img)

    # Логотип-текст
    try:
        font_big  = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 80)
        font_main = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 42)
    except Exception:
        font_big  = ImageFont.load_default()
        font_main = font_big

    draw.text((540, 200), "🏠 FlatFinderIL", fill="#4FC3F7", font=font_big, anchor="mm")
    draw.text((540, 310), "@FlatFinderIL_bot", fill="#90CAF9", font=font_main, anchor="mm")

    # Текст объявления (обёртка)
    lines = textwrap.wrap(caption[:300], width=38)
    y = 440
    for line in lines[:8]:
        draw.text((540, y), line, fill="white", font=font_main, anchor="mm")
        y += 58

    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    img.save(tmp.name, "JPEG", quality=92)
    log.info(f"🖼  Заглушка-картинка: {tmp.name}")
    return tmp.name


# ──────────────────────────────────────────────────────────────────────────────
#  Playwright subprocess helper
# ──────────────────────────────────────────────────────────────────────────────

def _run_playwright_subprocess(caption: str, image_path: str, timeout: int = 180) -> dict:
    """
    Запускает playwright_ig_poster.py как ОТДЕЛЬНЫЙ процесс.
    Если Chromium убьёт OOM — умрёт только subprocess, основной процесс (бот/дашборд) выживет.
    """
    import subprocess
    import tempfile

    _script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "playwright_ig_poster.py")

    # Пишем caption во временный файл (может быть длинным)
    cap_file = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as _f:
            _f.write(caption)
            cap_file = _f.name

        log.info(f"🚀 Запускаем Playwright subprocess: {_script}")
        proc = subprocess.run(
            [sys.executable, _script, "--caption-file", cap_file, "--image", image_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),   # передаём все env vars (cookies, сессии)
        )

        # Логируем stderr (там Playwright-логи)
        if proc.stderr:
            for line in proc.stderr.strip().splitlines():
                log.info(f"[PW] {line}")

        if proc.returncode == 0 and proc.stdout.strip():
            try:
                return json.loads(proc.stdout.strip())
            except Exception as parse_err:
                log.error(f"Playwright stdout не является JSON: {parse_err}\n{proc.stdout[:300]}")
                return {"ok": False, "error": f"JSON parse error: {parse_err}"}
        else:
            err_msg = proc.stderr.strip()[-500:] if proc.stderr else f"exit code {proc.returncode}"
            log.error(f"Playwright subprocess завершился с кодом {proc.returncode}: {err_msg}")
            return {"ok": False, "error": err_msg}

    except subprocess.TimeoutExpired:
        log.error(f"Playwright subprocess превысил таймаут {timeout}s")
        return {"ok": False, "error": f"Playwright timeout after {timeout}s"}
    except Exception as sub_err:
        log.error(f"Не удалось запустить Playwright subprocess: {sub_err}")
        return {"ok": False, "error": str(sub_err)}
    finally:
        if cap_file and os.path.exists(cap_file):
            os.unlink(cap_file)


# ──────────────────────────────────────────────────────────────────────────────
#  Публикация
# ──────────────────────────────────────────────────────────────────────────────

def post_to_instagram(
    caption: str,
    image_path: str | None = None,
    dry_run: bool = False,
) -> dict:
    """
    Публикует фото с подписью в Instagram.
    Возвращает dict с результатом.
    """
    placeholder_created = False

    VIDEO_EXT = {".mp4", ".mov", ".avi"}
    is_video = image_path and os.path.splitext(image_path)[1].lower() in VIDEO_EXT

    if not image_path or not os.path.exists(image_path):
        log.info("📷 Изображение не задано — генерируем заглушку")
        image_path = _make_placeholder_image(caption)
        placeholder_created = True
        is_video = False

    result = {
        "ok": False,
        "image": image_path,
        "caption_preview": caption[:120],
        "dry_run": dry_run,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    if dry_run:
        log.info(f"[DRY-RUN] Пост готов к публикации:")
        log.info(f"  Картинка: {image_path}")
        log.info(f"  Подпись:  {caption[:80]}…")
        result["ok"] = True
        result["note"] = "dry-run: ничего не опубликовано"
        return result

    instagrapi_error = None
    try:
        cl = _get_client()
        log.info("📤 Публикуем пост через мобильный API …")
        if is_video:
            log.info("🎬 Видео-пост (Reels) …")
            media = cl.clip_upload(path=Path(image_path), caption=caption)
        else:
            media = cl.photo_upload(path=Path(image_path), caption=caption)

        media_id  = str(media.id)
        media_url = f"https://www.instagram.com/p/{media.code}/"
        log.info(f"✅ Опубликовано (API): {media_url}")

        result["ok"]       = True
        result["media_id"] = media_id
        result["url"]      = media_url
        result["method"]   = "instagrapi"

        # Обновляем сессию после успешного поста: файл + БД
        cl.dump_settings(SESSION_FILE)
        _save_settings_to_db(cl)

    except Exception as e:
        instagrapi_error = e
        err_lower = str(e).lower()
        # 403/login_required/ip blocked → пробуем через Playwright (браузер)
        if any(x in err_lower for x in ("login_required", "loginrequired", "403", "forbidden")):
            log.warning(f"⚠️  Мобильный API заблокирован ({e}). Пробуем Playwright (subprocess) …")
            try:
                pw_result = _run_playwright_subprocess(caption, image_path)
                if pw_result.get("ok"):
                    result.update(pw_result)
                    result["ok"]    = True
                    result["note"]  = "posted via browser (Playwright subprocess)"
                    instagrapi_error = None
                    log.info("✅ Опубликовано через Playwright subprocess")
                else:
                    result["error"] = pw_result.get("error", "Playwright failed")
            except Exception as pw_e:
                log.error(f"❌ Playwright тоже не сработал: {pw_e}", exc_info=True)
                result["error"] = f"API: {e} | Playwright: {pw_e}"
        else:
            log.error(f"❌ Ошибка публикации: {e}", exc_info=True)
            result["error"] = str(e)
    finally:
        if placeholder_created and os.path.exists(image_path):
            os.unlink(image_path)

    # Пишем лог
    _append_log(result)
    return result


def _append_log(entry: dict):
    existing = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            pass
    existing.append(entry)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(existing[-200:], f, ensure_ascii=False, indent=2)


# ──────────────────────────────────────────────────────────────────────────────
#  Сохранить сессию в env-формате (для Railway)
# ──────────────────────────────────────────────────────────────────────────────

def export_session_json() -> str:
    """Возвращает JSON сессии для вставки в IG_SESSION_JSON."""
    cl = _get_client()
    return json.dumps(cl.get_settings(), ensure_ascii=False)


# ──────────────────────────────────────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Публикация в Instagram")
    parser.add_argument("--caption",       default="", help="Текст поста")
    parser.add_argument("--caption-file",  help="Файл с текстом поста")
    parser.add_argument("--image",         help="Путь к изображению (jpg/png)")
    parser.add_argument("--dry-run",       action="store_true", help="Тест без публикации")
    parser.add_argument("--export-session", action="store_true",
                        help="Войти и вывести IG_SESSION_JSON (для Railway)")
    args = parser.parse_args()

    if args.export_session:
        session_json = export_session_json()
        print("\n✅ Скопируй это значение в Railway → Variables → IG_SESSION_JSON:\n")
        print(session_json)
        return

    caption = args.caption
    if args.caption_file:
        with open(args.caption_file, "r", encoding="utf-8") as f:
            caption = f.read().strip()

    if not caption:
        parser.error("Укажи --caption или --caption-file")

    result = post_to_instagram(
        caption=caption,
        image_path=args.image,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
