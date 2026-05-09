#!/usr/bin/env python3
"""
facebook_poster.py — Публикация рекламного поста в Facebook-группах.

Принцип работы:
  • Загружает cookies из Chrome (локально) или из FB_COOKIES_JSON (Railway).
  • Открывает каждую группу через Playwright Chromium (headless).
  • Кликает «Написать что-нибудь...», вводит текст, нажимает «Опубликовать».
  • Ведёт лог результатов; между группами делает паузу.

Запуск:
  python3 facebook_poster.py --message "Ваш текст здесь"
  python3 facebook_poster.py --file message.txt
  python3 facebook_poster.py --message "..." --headful          # видимый браузер
  python3 facebook_poster.py --message "..." --groups 141464740539934,819372811594662
  python3 facebook_poster.py --message "..." --dry-run          # не постит, только проверяет
  python3 facebook_poster.py --list                             # показать список групп

Переменные окружения:
  FB_COOKIES_JSON — JSON с cookies Facebook (для Railway / CI)
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime

import browser_cookie3
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ── Логирование ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fb_poster")

# ══════════════════════════════════════════════════════════════════════════════
#  СПИСОК ГРУПП ДЛЯ ПОСТИНГА
#  (можно передать подмножество через --groups)
# ══════════════════════════════════════════════════════════════════════════════
POSTING_GROUPS = [
    # ── Общеизраильские (русскоязычные) ────────────────────────────────────────
    {"id": "141464740539934",  "name": "Аренда квартир в Израиле"},
    {"id": "819372811594662",  "name": "Аренда квартир Израиль | דירות להשכרה"},
    {"id": "1697329423753683", "name": "Квартиры без маклера"},
    {"id": "321202505245057",  "name": "Из рук в руки – Аренда жилья без маклера"},
    {"id": "919120634860210",  "name": "Русскоязычный Израиль – жильё, услуги"},
    {"id": "TelAvivBoard",     "name": "Тель-Авив – Доска объявлений Израиля"},
    {"id": "2lumi",            "name": "ДОСКА ОБЪЯВЛЕНИЙ ИЗРАИЛЯ"},
    {"id": "adsisrael",        "name": "Объявления Израиля на русском"},

    # ── Бат-Ям ────────────────────────────────────────────────────────────────
    {"id": "647964450757105",  "name": "Аренда жилья Израиль – Бат Ям"},
    {"id": "rentbatyam",       "name": "АРЕНДА БАТ ЯМ | השכרה בת ים"},
    {"id": "198851813933632",  "name": "Аренда квартир в Бат Яме"},
    {"id": "1903124356581754", "name": "Аренда без Маклера – граждане Бат Ям"},
    {"id": "RentBuySaleBatYam","name": "Аренда и продажа квартир в Бат Ям"},
    {"id": "holonandbatyam",   "name": "Продажа и аренда квартир Холон и Бат-Ям"},
    {"id": "batyam.ad",        "name": "Бат-Ям – Объявления"},

    # ── Тель-Авив ─────────────────────────────────────────────────────────────
    {"id": "101875683484689",  "name": "דירות מפה לאוזן בתל אביב"},
    {"id": "295395253832427",  "name": "דירות בתל אביב"},
    {"id": "457465901082882",  "name": "דירות בתל אביב ללא תיווך"},
    {"id": "tel.aviv.dirot",   "name": "לוח דירות תל אביב-יפו"},
    {"id": "250663073164312",  "name": "Tel Aviv – Housing, Rooms, Apartments"},

    # ── Хайфа ─────────────────────────────────────────────────────────────────
    {"id": "173351201739",     "name": "דירות מפה לאוזן בחיפה"},
    {"id": "837431273097770",  "name": "דירות להשכרה בחיפה"},

    # ── Иерусалим ─────────────────────────────────────────────────────────────
    {"id": "172544843294",     "name": "דירות מפה לאוזן בירושלים"},
    {"id": "325992450444",     "name": "דירות להשכרה בירושלים"},

    # ── Ришон-ле-Цион ─────────────────────────────────────────────────────────
    {"id": "555578950202434",  "name": "דירות להשכרה בראשון לציון"},
    {"id": "111163552234056",  "name": "דירות מפה לאוזן בראשון לציון"},

    # ── Нетания ───────────────────────────────────────────────────────────────
    {"id": "554754367898974",  "name": "דירות מפה לאוזן בנתניה"},
    {"id": "rentflatnetanya",  "name": "דירות להשכרה בנתניה / Аренда Нетания"},

    # ── Ашдод ─────────────────────────────────────────────────────────────────
    {"id": "215752412333714",  "name": "דירות להשכרה באשדוד"},
    {"id": "rent.in.ashdod",   "name": "דירות להשכרה אשדוד / Аренда Ашдод"},

    # ── Рамат-Ган / Гиватаим ──────────────────────────────────────────────────
    {"id": "192850633573",     "name": "דירות מפה לאוזן ברמת גן"},
    {"id": "253957624766723",  "name": "דירות להשכרה ברמת גן"},
]

# ══════════════════════════════════════════════════════════════════════════════
#  НАСТРОЙКИ
# ══════════════════════════════════════════════════════════════════════════════
PAGE_LOAD_WAIT  = 6.0   # сек ожидания после открытия группы
PAUSE_BETWEEN   = 20.0  # сек между группами (снижает риск бана)
POST_TIMEOUT    = 20_000  # мс ожидания элементов

# ══════════════════════════════════════════════════════════════════════════════
#  ЗАГРУЗКА COOKIES
# ══════════════════════════════════════════════════════════════════════════════

def load_facebook_cookies() -> list[dict]:
    """Cookies: из FB_COOKIES_JSON (Railway) или из Chrome (локально)."""
    import json as _json

    # ── Приоритет 0: из базы данных (переживает редеплои) ────────────────────
    try:
        import sys as _sys
        _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import database as _db
        db_raw = _db.get_fb_cookies()
        if db_raw:
            # Обновляем env var для совместимости с остальным кодом
            os.environ["FB_COOKIES_JSON"] = db_raw
            log.info("✅ Facebook cookies загружены из БД")
    except Exception as _e:
        log.debug(f"FB cookies: БД недоступна: {_e}")

    # ── Railway: из переменной окружения ──────────────────────────────────────
    env_raw = os.environ.get("FB_COOKIES_JSON", "")
    if env_raw:
        try:
            data = _json.loads(env_raw)
            all_cookies: dict[str, dict] = {}
            if isinstance(data, dict):
                for name, val in data.items():
                    all_cookies[name] = {"name": name, "value": val,
                                         "domain": ".facebook.com", "path": "/"}
            elif isinstance(data, list):
                for c in data:
                    val = c.get("value", "")
                    all_cookies[c["name"]] = {"name": c["name"], "value": val,
                                              "domain": ".facebook.com", "path": "/"}
            log.info(f"✅ Cookies из FB_COOKIES_JSON: {len(all_cookies)} шт.")
            return list(all_cookies.values())
        except Exception as e:
            log.error(f"Ошибка разбора FB_COOKIES_JSON: {e}")

    # ── Локально: из Chrome ────────────────────────────────────────────────────
    chrome_base = os.path.expanduser(
        "~/Library/Application Support/Google/Chrome"
        if sys.platform == "darwin"
        else "~/.config/google-chrome"
    )
    profiles = ["Default"] + [f"Profile {i}" for i in range(1, 6)]
    all_cookies: dict[str, dict] = {}
    for profile in profiles:
        cookie_file = os.path.join(chrome_base, profile, "Cookies")
        if not os.path.exists(cookie_file):
            continue
        try:
            cj = browser_cookie3.chrome(cookie_file=cookie_file,
                                         domain_name=".facebook.com")
            n = 0
            for c in cj:
                all_cookies[c.name] = {"name": c.name, "value": c.value,
                                        "domain": ".facebook.com", "path": "/"}
                n += 1
            if n:
                log.info(f"   Chrome [{profile}]: {n} Facebook cookies")
        except Exception as e:
            log.debug(f"   Chrome [{profile}]: {e}")

    log.info(f"✅ Итого cookies: {len(all_cookies)} уникальных")
    return list(all_cookies.values())


# ══════════════════════════════════════════════════════════════════════════════
#  ПОСТИНГ В ОДНУ ГРУППУ
# ══════════════════════════════════════════════════════════════════════════════

def post_to_group(page, group: dict, message: str, dry_run: bool = False) -> bool:
    """
    Публикует message в Facebook-группе.
    Возвращает True при успехе, False при ошибке.
    """
    gid  = group["id"]
    name = group["name"]
    url  = f"https://www.facebook.com/groups/{gid}/"

    log.info(f"\n📌  {name}")
    log.info(f"    {url}")

    # ── Переход на страницу группы ─────────────────────────────────────────────
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        time.sleep(PAGE_LOAD_WAIT)
    except PWTimeout:
        log.warning("   ⏳ Таймаут загрузки — пропускаем")
        return False
    except Exception as e:
        log.error(f"   ❌ Ошибка навигации: {e}")
        return False

    # Проверяем: не редиректнуло на логин?
    if "login" in page.url or "checkpoint" in page.url:
        log.warning("   🔐 Перенаправление на login — cookies устарели!")
        return False

    if dry_run:
        log.info("   🔍 [dry-run] Страница загружена, постинг пропущен")
        return True

    # ── Кликаем на поле «Написать что-нибудь...» ──────────────────────────────
    # Facebook меняет UI, поэтому пробуем несколько вариантов
    COMPOSER_SELECTORS = [
        # Текстовые плейсхолдеры
        "text=What's on your mind",
        "text=Write something",
        "text=Написать что-нибудь",
        "text=כתוב משהו",
        "text=כתבו משהו",
        # Aria-метки
        "[aria-label='Write something...']",
        "[aria-label='Написать что-нибудь...']",
        "[aria-label='כתוב משהו...']",
        # Роль
        "[data-visualcompletion='ignore-dynamic'] [role='button']",
    ]

    clicked = False
    for sel in COMPOSER_SELECTORS:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                el.click(timeout=3000)
                log.info(f"   ✅ Клик на поле: {sel!r}")
                clicked = True
                break
        except Exception:
            continue

    if not clicked:
        # Попытка найти что-либо кликабельное с плейсхолдерным текстом
        try:
            page.get_by_placeholder("Write something").first.click(timeout=3000)
            clicked = True
            log.info("   ✅ Клик по placeholder")
        except Exception:
            pass

    if not clicked:
        log.warning("   ⚠️  Поле для поста не найдено — пропускаем")
        return False

    time.sleep(1.5)

    # ── Вводим текст ───────────────────────────────────────────────────────────
    TEXTBOX_SELECTORS = [
        "[contenteditable='true'][role='textbox']",
        "[contenteditable='true']",
        "[role='textbox']",
        "textarea",
    ]

    typed = False
    for sel in TEXTBOX_SELECTORS:
        try:
            tb = page.locator(sel).last
            if tb.is_visible(timeout=3000):
                tb.click()
                time.sleep(0.5)
                tb.type(message, delay=30)  # delay=30ms — чуть медленнее, меньше подозрений
                log.info(f"   ✅ Текст введён ({len(message)} симв.)")
                typed = True
                break
        except Exception:
            continue

    if not typed:
        log.warning("   ⚠️  Textbox не найден — пропускаем")
        return False

    time.sleep(1.0)

    # ── Нажимаем «Опубликовать» ────────────────────────────────────────────────
    POST_BTN_SELECTORS = [
        "[aria-label='Post']",
        "[aria-label='Опубликовать']",
        "[aria-label='פרסם']",
        "text=Post",
        "text=Опубликовать",
        "text=פרסם",
        # По роли
        "div[role='button']:has-text('Post')",
        "div[role='button']:has-text('Опубликовать')",
        "div[role='button']:has-text('פרסם')",
    ]

    posted = False
    for sel in POST_BTN_SELECTORS:
        try:
            btn = page.locator(sel).last
            if btn.is_visible(timeout=2000) and btn.is_enabled():
                btn.click(timeout=3000)
                log.info(f"   📤 Нажата кнопка: {sel!r}")
                posted = True
                break
        except Exception:
            continue

    if not posted:
        log.warning("   ⚠️  Кнопка «Опубликовать» не найдена")
        return False

    # Ждём закрытия модального окна как подтверждения
    time.sleep(3.0)

    # Проверяем: нет ли ошибки / CAPTCHA
    if "checkpoint" in page.url or "captcha" in page.url.lower():
        log.warning("   🔒 Обнаружен checkpoint/captcha — нужна ручная проверка!")
        return False

    log.info("   ✅ Пост опубликован!")
    return True


# ══════════════════════════════════════════════════════════════════════════════
#  УСТАНОВКА CHROMIUM
# ══════════════════════════════════════════════════════════════════════════════

def _ensure_chromium():
    import subprocess
    pw_cache = os.path.expanduser("~/.cache/ms-playwright")
    if os.path.exists(pw_cache) and any(
        e.name.startswith("chromium") for e in os.scandir(pw_cache)
    ):
        return
    log.info("Chromium не найден — устанавливаем...")
    result = subprocess.run(
        ["playwright", "install", "--with-deps", "chromium"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        log.info("✅ Chromium установлен")
    else:
        log.error(f"❌ Ошибка установки: {result.stderr[-500:]}")


# ══════════════════════════════════════════════════════════════════════════════
#  ОСНОВНАЯ ФУНКЦИЯ
# ══════════════════════════════════════════════════════════════════════════════

def run_poster(message: str, groups: list[dict] | None = None,
               headful: bool = False, dry_run: bool = False,
               pause: float = PAUSE_BETWEEN) -> dict:
    """
    Постит message во все указанные группы.

    Возвращает:
      {
        "ok": True,
        "sent": 12,    # успешно опубликовано
        "failed": 3,   # ошибки
        "skipped": 0,  # пропущено (нет поля / редирект)
        "total": 15,
        "results": [{"name": ..., "id": ..., "ok": bool, "error": str|None}, ...]
      }
    """
    target = groups or POSTING_GROUPS
    log.info("=" * 65)
    log.info(f"🚀  Facebook Poster — старт")
    log.info(f"    групп: {len(target)},  dry_run: {dry_run},  headful: {headful}")
    log.info(f"    текст: {message[:80]}{'...' if len(message)>80 else ''}")
    log.info("=" * 65)

    if not message.strip():
        return {"ok": False, "error": "Пустой текст"}

    _ensure_chromium()

    cookies = load_facebook_cookies()
    if not cookies:
        log.error("❌ Cookies не найдены. Войдите в Facebook в Chrome и повторите.")
        return {"ok": False, "error": "Cookies не найдены"}

    results = []
    sent = failed = skipped = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=not headful,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-notifications",
            ],
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="ru-RU",
        )
        ctx.add_cookies(cookies)
        page = ctx.new_page()

        for i, group in enumerate(target):
            err = None
            try:
                ok = post_to_group(page, group, message, dry_run=dry_run)
            except Exception as e:
                ok = False
                err = str(e)
                log.error(f"   ❌ Исключение: {e}")

            results.append({
                "name": group["name"],
                "id":   group["id"],
                "ok":   ok,
                "error": err,
            })
            if ok:
                sent += 1
            else:
                failed += 1

            # Пауза между группами (кроме последней)
            if i < len(target) - 1:
                log.info(f"   ⏳ Пауза {pause:.0f} сек...")
                time.sleep(pause)

        browser.close()

    log.info("\n" + "=" * 65)
    log.info(f"📊 Готово: отправлено={sent}, ошибок={failed}, всего={len(target)}")
    log.info("=" * 65)

    return {
        "ok": True,
        "sent":    sent,
        "failed":  failed,
        "skipped": skipped,
        "total":   len(target),
        "results": results,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  СОХРАНЕНИЕ РЕЗУЛЬТАТОВ
# ══════════════════════════════════════════════════════════════════════════════

def save_results(result: dict, message: str):
    """Сохраняет лог постинга в fb_posting_log.json."""
    log_file = os.path.join(os.path.dirname(__file__), "fb_posting_log.json")
    try:
        if os.path.exists(log_file):
            with open(log_file, "r", encoding="utf-8") as f:
                history = json.load(f)
        else:
            history = []
    except Exception:
        history = []

    entry = {
        "date": datetime.now().isoformat(timespec="seconds"),
        "message_preview": message[:120],
        **{k: v for k, v in result.items() if k != "results"},
        "details": result.get("results", []),
    }
    history.insert(0, entry)
    history = history[:50]  # хранить последние 50 рассылок

    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    log.info(f"📄 Лог сохранён: {log_file}")


# ══════════════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Публикует рекламный пост в Facebook-группах",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--message", "-m", help="Текст поста")
    parser.add_argument("--file", "-f", help="Файл с текстом поста")
    parser.add_argument("--groups", "-g",
                        help="Через запятую: ID групп (по умолчанию — все)")
    parser.add_argument("--headful", action="store_true",
                        help="Видимый браузер (для отладки)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Проверить без реального постинга")
    parser.add_argument("--pause", type=float, default=PAUSE_BETWEEN,
                        help=f"Пауза между группами, сек (по умолчанию {PAUSE_BETWEEN})")
    parser.add_argument("--list", action="store_true",
                        help="Показать список групп и выйти")
    args = parser.parse_args()

    if args.list:
        print(f"\n{'#':>3}  {'ID':30s}  Название")
        print("-" * 70)
        for i, g in enumerate(POSTING_GROUPS, 1):
            print(f"{i:>3}  {g['id']:30s}  {g['name']}")
        print(f"\nВсего: {len(POSTING_GROUPS)} групп")
        return

    # Текст сообщения
    message = ""
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            message = f.read().strip()
    elif args.message:
        message = args.message.strip()
    else:
        # Интерактивный ввод
        print("Введите текст поста (Ctrl+D для завершения):")
        try:
            message = sys.stdin.read().strip()
        except KeyboardInterrupt:
            print("\nОтменено.")
            sys.exit(0)

    if not message:
        print("❌ Текст поста не указан.")
        sys.exit(1)

    # Фильтрация групп
    target_groups = POSTING_GROUPS
    if args.groups:
        ids = {g.strip() for g in args.groups.split(",")}
        target_groups = [g for g in POSTING_GROUPS if g["id"] in ids]
        if not target_groups:
            print(f"❌ Группы не найдены: {args.groups}")
            sys.exit(1)

    result = run_poster(
        message=message,
        groups=target_groups,
        headful=args.headful,
        dry_run=args.dry_run,
        pause=args.pause,
    )

    save_results(result, message)

    # Итоговый вывод
    print(f"\n{'='*50}")
    print(f"📊 Результат рассылки:")
    print(f"   ✅ Опубликовано: {result.get('sent', 0)}")
    print(f"   ❌ Ошибок:       {result.get('failed', 0)}")
    print(f"   📦 Всего групп:  {result.get('total', 0)}")
    print(f"{'='*50}\n")

    if result.get("results"):
        print("Детали:")
        for r in result["results"]:
            status = "✅" if r["ok"] else "❌"
            err = f"  ({r['error']})" if r.get("error") else ""
            print(f"  {status} {r['name']}{err}")


if __name__ == "__main__":
    main()
