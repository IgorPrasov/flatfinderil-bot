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

def _get_client():
    from instagrapi import Client
    from instagrapi.exceptions import LoginRequired, BadPassword, TwoFactorRequired

    cl = Client()
    cl.delay_range = [2, 5]

    # 1. Попытка загрузить сессию из env (Railway)
    env_session = os.environ.get("IG_SESSION_JSON", "").strip()
    if env_session:
        try:
            session_data = json.loads(env_session)
            cl.set_settings(session_data)
            cl.login(
                os.environ.get("IG_USERNAME", ""),
                os.environ.get("IG_PASSWORD", ""),
            )
            log.info("✅ Сессия из IG_SESSION_JSON восстановлена")
            return cl
        except Exception as e:
            log.warning(f"⚠️  Не удалось восстановить сессию из env: {e}")

    # 2. Попытка загрузить сессию из файла (локальный запуск)
    if os.path.exists(SESSION_FILE):
        try:
            cl.load_settings(SESSION_FILE)
            cl.login(
                os.environ.get("IG_USERNAME", ""),
                os.environ.get("IG_PASSWORD", ""),
            )
            log.info(f"✅ Сессия из {SESSION_FILE} восстановлена")
            return cl
        except Exception as e:
            log.warning(f"⚠️  Не удалось восстановить сессию из файла: {e}")

    # 3. Свежий логин
    username = os.environ.get("IG_USERNAME", "")
    password = os.environ.get("IG_PASSWORD", "")
    if not username or not password:
        raise RuntimeError(
            "❌ IG_USERNAME и IG_PASSWORD не заданы. "
            "Добавьте их в Railway Variables."
        )

    log.info(f"🔑 Входим в Instagram как @{username} …")
    try:
        cl.login(username, password)
    except TwoFactorRequired:
        code = input("Введите 2FA-код из Instagram: ").strip()
        cl.login(username, password, verification_code=code)
    except BadPassword:
        raise RuntimeError("❌ Неверный пароль Instagram (IG_PASSWORD)")
    except LoginRequired as e:
        raise RuntimeError(f"❌ Instagram требует повторного входа: {e}")

    # Сохраняем сессию локально
    cl.dump_settings(SESSION_FILE)
    log.info(f"💾 Сессия сохранена → {SESSION_FILE}")
    return cl


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

    if not image_path or not os.path.exists(image_path):
        log.info("📷 Изображение не задано — генерируем заглушку")
        image_path = _make_placeholder_image(caption)
        placeholder_created = True

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

    try:
        cl = _get_client()
        log.info("📤 Публикуем пост в Instagram …")
        media = cl.photo_upload(
            path=Path(image_path),
            caption=caption,
        )
        media_id  = str(media.id)
        media_url = f"https://www.instagram.com/p/{media.code}/"
        log.info(f"✅ Опубликовано: {media_url}")

        result["ok"]       = True
        result["media_id"] = media_id
        result["url"]      = media_url

        # Обновляем сессию после успешного поста
        cl.dump_settings(SESSION_FILE)

    except Exception as e:
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
