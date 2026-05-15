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
    # ══════════════════════════════════════════════════════════════════════════
    # РУССКОЯЗЫЧНЫЕ ГРУППЫ (lang="ru")
    # ══════════════════════════════════════════════════════════════════════════

    # ── Общеизраильские ───────────────────────────────────────────────────────
    {"id": "141464740539934",  "lang": "ru", "name": "Аренда квартир в Израиле"},
    {"id": "819372811594662",  "lang": "ru", "name": "Аренда квартир Израиль | דירות להשכרה"},
    {"id": "1697329423753683", "lang": "ru", "name": "Квартиры без маклера"},
    {"id": "321202505245057",  "lang": "ru", "name": "Из рук в руки – Аренда жилья без маклера"},
    {"id": "919120634860210",  "lang": "ru", "name": "Русскоязычный Израиль – жильё, услуги"},
    {"id": "TelAvivBoard",     "lang": "ru", "name": "Тель-Авив – Доска объявлений Израиля"},
    {"id": "2lumi",            "lang": "ru", "name": "ДОСКА ОБЪЯВЛЕНИЙ ИЗРАИЛЯ"},
    {"id": "adsisrael",        "lang": "ru", "name": "Объявления Израиля на русском"},
    {"id": "2928147683954852", "lang": "ru", "name": "Весь Гуш-Дан"},

    # ── Бат-Ям (русские) ─────────────────────────────────────────────────────
    {"id": "647964450757105",  "lang": "ru", "name": "Аренда жилья Израиль – Бат Ям"},
    {"id": "rentbatyam",       "lang": "ru", "name": "АРЕНДА БАТ ЯМ | השכרה בת ים"},
    {"id": "198851813933632",  "lang": "ru", "name": "Аренда квартир в Бат Яме"},
    {"id": "1903124356581754", "lang": "ru", "name": "Аренда без Маклера – граждане Бат Ям"},
    {"id": "RentBuySaleBatYam","lang": "ru", "name": "Аренда и продажа квартир в Бат Ям"},
    {"id": "holonandbatyam",   "lang": "ru", "name": "Продажа и аренда квартир Холон и Бат-Ям"},
    {"id": "batyam.ad",        "lang": "ru", "name": "Бат-Ям – Объявления"},

    # ══════════════════════════════════════════════════════════════════════════
    # ИВРИТОЯЗЫЧНЫЕ ГРУППЫ (lang="he")
    # ══════════════════════════════════════════════════════════════════════════

    # ── Тель-Авив ─────────────────────────────────────────────────────────────
    {"id": "101875683484689",  "lang": "he", "name": "דירות מפה לאוזן בתל אביב"},
    {"id": "295395253832427",  "lang": "he", "name": "דירות בתל אביב"},
    {"id": "457465901082882",  "lang": "he", "name": "דירות בתל אביב ללא תיווך"},
    {"id": "tel.aviv.dirot",   "lang": "he", "name": "לוח דירות תל אביב-יפו"},
    {"id": "341195019300726",  "lang": "he", "name": "דירות במרכז להשכרה/מכירה"},
    {"id": "191591524188001",  "lang": "he", "name": "דירות להשכרה בדרום תל אביב"},
    {"id": "1485565508385836", "lang": "he", "name": "דירות להשכרה בצפון תל אביב"},
    {"id": "184920528370332",  "lang": "he", "name": "דירות להשכרה בתל אביב"},
    {"id": "365588344194085",  "lang": "he", "name": "דירות להשכרה 2-3 חדרים בתל אביב"},
    {"id": "1664977427442936", "lang": "he", "name": "דירות להשכרה במרכז עד 5000"},

    # ── Хайфа ─────────────────────────────────────────────────────────────────
    {"id": "173351201739",     "lang": "he", "name": "דירות מפה לאוזן בחיפה"},
    {"id": "837431273097770",  "lang": "he", "name": "דירות להשכרה בחיפה"},
    {"id": "1591401697779759", "lang": "he", "name": "דירות להשכרה בקריות ללא תיווך"},
    {"id": "yad2k",            "lang": "he", "name": "דירות להשכרה בקריות"},
    {"id": "110907419268500",  "lang": "he", "name": "דירות לסטודנטים חיפה"},
    {"id": "611703096084191",  "lang": "he", "name": "דירות להשכרה בחיפה – עם מחיר"},
    {"id": "1896414753945570", "lang": "he", "name": "דירות להשכרה בחיפה (2)"},
    {"id": "783424098674651",  "lang": "he", "name": "דירות להשכרה בחיפה (3)"},
    {"id": "131650282168271",  "lang": "he", "name": "דירות להשכרה בחיפה ללא תיווך"},

    # ── Иерусалим ─────────────────────────────────────────────────────────────
    {"id": "172544843294",     "lang": "he", "name": "דירות מפה לאוזן בירושלים"},
    {"id": "325992450444",     "lang": "he", "name": "דירות להשכרה בירושלים"},
    {"id": "344780799040537",  "lang": "he", "name": "דירות להשכרה בירושלים (2)"},
    {"id": "apartmentsinjerusalem", "lang": "he", "name": "דירות בירושלים ללא תיווך"},

    # ── Ришон-ле-Цион ─────────────────────────────────────────────────────────
    {"id": "555578950202434",  "lang": "he", "name": "דירות להשכרה בראשון לציון"},
    {"id": "111163552234056",  "lang": "he", "name": "דירות מפה לאוזן בראשון לציון"},
    {"id": "959597644173111",  "lang": "he", "name": "דירות להשכרה ללא תיווך ראשון לציון"},
    {"id": "963153170558917",  "lang": "he", "name": "דירות להשכרה חולון בת ים ראשון לציון"},
    {"id": "201105170260427",  "lang": "he", "name": "דירות להשכרה ראשון לציון חולון בת ים"},

    # ── Холон ─────────────────────────────────────────────────────────────────
    {"id": "1354045801786047", "lang": "he", "name": "דירות להשכרה בעיר חולון"},
    {"id": "801470026653021",  "lang": "he", "name": "דירות להשכרה בחולון"},
    {"id": "266774507954665",  "lang": "he", "name": "דירות להשכרה בחולון בלבד"},
    {"id": "509654872819955",  "lang": "he", "name": "דירות להשכרה חולון בת-ים ללא תיווך"},
    {"id": "dirot.batyam.holon","lang": "he", "name": "דירות להשכרה בת ים חולון והסביבה"},

    # ── Нетания ───────────────────────────────────────────────────────────────
    {"id": "554754367898974",  "lang": "he", "name": "דירות מפה לאוזן בנתניה"},
    {"id": "rentflatnetanya",  "lang": "he", "name": "דירות להשכרה בנתניה / Аренда Нетания"},
    {"id": "228387647805774",  "lang": "he", "name": "דירות להשכרה בנתניה ללא תיווך"},
    {"id": "1153910968018350", "lang": "he", "name": "דירות להשכרה בנתניה והסביבה ללא תיווך"},

    # ── Ашдод ─────────────────────────────────────────────────────────────────
    {"id": "215752412333714",  "lang": "he", "name": "דירות להשכרה באשדוד"},
    {"id": "rent.in.ashdod",   "lang": "he", "name": "דירות להשכרה אשדוד / Аренда Ашдод"},
    {"id": "1624818081000281", "lang": "he", "name": "דירות להשכרה ומכירה אשדוד והסביבה"},
    {"id": "1087635731246729", "lang": "he", "name": "דירות להשכרה באשדוד ללא תיווך"},
    {"id": "585483232340913",  "lang": "he", "name": "דירות להשכרה אשדוד אשקלון"},

    # ── Рош-аАин ─────────────────────────────────────────────────────────────
    {"id": "1777924022257391", "lang": "he", "name": "דירות למכירה והשכרה ראש העין רבתי"},
    {"id": "1773509336205184", "lang": "he", "name": "דירות להשכרה ומכירה בראש העין"},
    {"id": "1824690151020636", "lang": "he", "name": "לוח הדירות של ראש העין ופסגות אפק"},
    {"id": "1797166367186177", "lang": "he", "name": "דירות להשכרה/מכירה – הפרלמנט ראש העין"},
    {"id": "509084853121039",  "lang": "he", "name": "דירות להשכרה בראש העין"},
    {"id": "308216903043626",  "lang": "he", "name": "הפרלמנט דירות להשכרה בראש העין ללא תיווך"},

    # ══════════════════════════════════════════════════════════════════════════
    # АНГЛОЯЗЫЧНЫЕ ГРУППЫ (lang="en")
    # ══════════════════════════════════════════════════════════════════════════
    {"id": "250663073164312",  "lang": "en", "name": "Tel Aviv – Housing, Rooms, Apartments"},
    {"id": "LiveandWork",      "lang": "en", "name": "Apartment Rentals and House Purchasing"},
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
                    all_cookies[name] = {"name": str(name), "value": str(val or ""),
                                         "domain": ".facebook.com", "path": "/"}
            elif isinstance(data, list):
                for c in data:
                    val = c.get("value", "") or ""
                    all_cookies[c["name"]] = {"name": str(c["name"]), "value": str(val),
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
        for subdir in ["Network/Cookies", "Cookies"]:
            cookie_file = os.path.join(chrome_base, profile, subdir)
            if not os.path.exists(cookie_file):
                continue
            try:
                cj = browser_cookie3.chrome(cookie_file=cookie_file,
                                             domain_name=".facebook.com")
                n = 0
                for c in cj:
                    # Playwright: только name, value, domain, path
                    all_cookies[c.name] = {
                        "name":   c.name,
                        "value":  c.value,
                        "domain": ".facebook.com",
                        "path":   "/",
                    }
                    n += 1
                if n:
                    log.info(f"   Chrome [{profile}/{subdir}]: {n} Facebook cookies")
                break  # нашли файл в этом профиле
            except Exception as e:
                log.debug(f"   Chrome [{profile}/{subdir}]: {e}")

    log.info(f"✅ Итого cookies: {len(all_cookies)} уникальных")
    return list(all_cookies.values())


# ══════════════════════════════════════════════════════════════════════════════
#  РЕДАКТИРОВАНИЕ СУЩЕСТВУЮЩЕГО ПОСТА В ГРУППЕ
# ══════════════════════════════════════════════════════════════════════════════

def edit_post_in_group(page, group: dict, new_message: str, dry_run: bool = False) -> bool:
    """
    Находит последний пост текущего пользователя в группе и редактирует его.
    Возвращает True при успехе, False при ошибке.
    """
    gid  = group["id"]
    name = group["name"]

    # Используем URL "мои посты в этой группе" — показывает только наши посты
    # c_user cookie = наш user_id
    import os as _os
    import json as _json
    _user_id = ""
    try:
        _raw = _os.environ.get("FB_COOKIES_JSON", "")
        if _raw:
            for c in _json.loads(_raw):
                if c.get("name") == "c_user":
                    _user_id = c["value"]
                    break
    except Exception:
        pass

    if _user_id:
        url = f"https://www.facebook.com/groups/{gid}/user/{_user_id}/"
    else:
        url = f"https://www.facebook.com/groups/{gid}/"

    log.info(f"\n✏️   {name}")
    log.info(f"    {url}")

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        time.sleep(PAGE_LOAD_WAIT)
    except PWTimeout:
        log.warning("   ⏳ Таймаут загрузки — пропускаем")
        return False
    except Exception as e:
        log.error(f"   ❌ Ошибка навигации: {e}")
        return False

    if "login" in page.url or "checkpoint" in page.url:
        log.warning("   🔐 Перенаправление на login — cookies устарели!")
        return False

    if dry_run:
        log.info("   🔍 [dry-run] Страница загружена, редактирование пропущено")
        return True

    # ── Переключаем ленту на «Новые публикации» ──────────────────────────────
    try:
        page.evaluate("""
        () => {
            // Ищем кнопку сортировки/фильтра ленты и кликаем "Новые"
            const btns = [...document.querySelectorAll('[role="button"]')];
            for (const b of btns) {
                const t = (b.textContent || '').trim();
                if (t.includes('Новые публика') || t.includes('New posts') || t.includes('פוסטים חדשים')) {
                    b.click();
                    return true;
                }
            }
            return false;
        }
        """)
    except Exception:
        pass
    time.sleep(2)

    # ── Ищем НАШ пост, прокручивая ленту вниз (до 5 раундов) ─────────────
    MARKER = "flatfinderil"

    def _find_and_click_menu():
        return page.evaluate("""
        (marker) => {
            const MENU_ATTRS = [
                '[aria-label*="Actions for this post"]',
                '[aria-label*="Действия для этой публикации"]',
                '[aria-label*="Действия с публикацией"]',
                '[aria-label*="פעולות לפוסט"]',
            ].join(', ');

            const articles = [...document.querySelectorAll('[role="article"]')];
            for (const art of articles) {
                const text = (art.innerText || art.textContent || '');
                if (!text.includes(marker)) continue;
                // Нашли — кликаем кнопку меню
                const menuBtn = art.querySelector(MENU_ATTRS);
                if (menuBtn) { menuBtn.click(); return "menu"; }
                // Запасной вариант: кнопка «Ещё» с иконкой
                const moreBtn = [...art.querySelectorAll('[role="button"]')]
                    .find(b => {
                        const lbl = (b.getAttribute('aria-label') || '');
                        return lbl === 'Ещё' || lbl === 'More' || lbl === 'עוד';
                    });
                if (moreBtn) { moreBtn.click(); return "more"; }
            }
            return null;
        }
        """, MARKER)

    found_menu = None
    for scroll_round in range(5):
        found_menu = _find_and_click_menu()
        if found_menu:
            break
        # Прокручиваем вниз и ждём подгрузки
        page.evaluate("window.scrollBy(0, 1500)")
        time.sleep(2.5)

    if not found_menu:
        log.warning("   ⚠️  Наш пост не найден на странице — возможно, ещё на модерации")
        return False

    log.info(f"   ✅ Меню поста открыто ({found_menu})")

    time.sleep(1.5)

    # ── Кликаем «Редактировать публикацию» в выпадающем меню ──────────────
    edited = page.evaluate("""
    () => {
        const EDIT_LABELS = [
            "Редактировать публикацию", "Edit post", "ערוך פוסט", "Edit Post"
        ];
        const items = [...document.querySelectorAll('[role="menuitem"], [role="option"], [role="button"]')];
        for (const item of items) {
            const t = (item.textContent || '').trim();
            const aria = item.getAttribute('aria-label') || '';
            for (const lbl of EDIT_LABELS) {
                if (t === lbl || aria === lbl) {
                    item.click();
                    return lbl;
                }
            }
        }
        return null;
    }
    """)

    if not edited:
        log.warning("   ⚠️  Пункт «Редактировать» не найден в меню")
        # Закрываем меню нажатием Escape
        page.keyboard.press("Escape")
        return False

    log.info(f"   ✅ Открыто редактирование: {edited!r}")
    time.sleep(2.0)

    # ── Очищаем текущий текст и вводим новый ──────────────────────────────
    TEXTBOX_SELECTORS = [
        "[role='dialog'] [contenteditable='true'][role='textbox']",
        "[role='dialog'] [contenteditable='true']",
        "[contenteditable='true'][role='textbox']",
        "[contenteditable='true']",
    ]

    cleared = False
    for sel in TEXTBOX_SELECTORS:
        try:
            tb = page.locator(sel).first
            if tb.is_visible(timeout=3000):
                tb.click()
                time.sleep(0.3)
                # Выделить всё и удалить
                page.keyboard.press("Meta+A" if sys.platform == "darwin" else "Control+A")
                time.sleep(0.3)
                page.keyboard.press("Delete")
                time.sleep(0.3)
                tb.type(new_message, delay=25)
                log.info(f"   ✅ Текст обновлён ({len(new_message)} симв.)")
                cleared = True
                break
        except Exception:
            continue

    if not cleared:
        log.warning("   ⚠️  Textbox для редактирования не найден")
        page.keyboard.press("Escape")
        return False

    time.sleep(1.5)

    # ── Сохраняем изменения ────────────────────────────────────────────────
    saved = page.evaluate("""
    () => {
        const SAVE_LABELS = ["Сохранить", "Save", "שמור"];
        // Сначала aria-label
        for (const lbl of SAVE_LABELS) {
            const el = document.querySelector(`[aria-label="${lbl}"]`);
            if (el && el.getAttribute('aria-disabled') !== 'true') {
                el.click();
                return lbl;
            }
        }
        // Затем textContent внутри диалога
        const buttons = [...document.querySelectorAll('[role="dialog"] [role="button"], [role="button"]')];
        for (const btn of buttons) {
            const t = (btn.textContent || '').trim();
            if (SAVE_LABELS.includes(t) && btn.getAttribute('aria-disabled') !== 'true') {
                btn.click();
                return t;
            }
        }
        return null;
    }
    """)

    if saved:
        log.info(f"   💾 Сохранено: {saved!r}")
        time.sleep(2.0)
        return True
    else:
        log.warning("   ⚠️  Кнопка «Сохранить» не найдена")
        page.keyboard.press("Escape")
        return False


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

    # ── Кликаем на кнопку «Напишите что-нибудь...» вверху группы ────────────
    # Facebook рендерит кнопку как div[role="button"] с текстом-плейсхолдером.
    # Кликаем через JS по первому совпадению — это всегда блок создания поста,
    # а не поле комментария (они ниже в DOM).

    clicked = False

    try:
        clicked = page.evaluate("""
        () => {
            const TEXTS = [
                "Напишите что-нибудь",
                "What's on your mind",
                "Write something",
                "כתוב משהו",
                "כתבו משהו",
                "О чём вы думаете",
            ];
            const buttons = [...document.querySelectorAll('[role="button"]')];
            for (const btn of buttons) {
                const t = (btn.textContent || '').trim();
                for (const needle of TEXTS) {
                    if (t.startsWith(needle)) {
                        btn.click();
                        return true;
                    }
                }
            }
            return false;
        }
        """)
    except Exception as e:
        log.debug(f"JS click error: {e}")

    if clicked:
        log.info("   ✅ Клик по кнопке создания поста")
    else:
        log.warning("   ⚠️  Поле для нового поста не найдено — пропускаем")
        return False

    time.sleep(1.5)

    # ── Вводим текст в поле создания поста ───────────────────────────────────
    # Facebook использует либо инлайн-редактор прямо в ленте, либо модальный
    # диалог. Проверяем оба варианта — берём первый видимый contenteditable.
    TEXTBOX_SELECTORS = [
        "[role='dialog'] [contenteditable='true'][role='textbox']",
        "[role='dialog'] [contenteditable='true']",
        "[contenteditable='true'][role='textbox']",
        "[contenteditable='true']",
        "[role='textbox']",
        "textarea",
    ]

    typed = False
    for sel in TEXTBOX_SELECTORS:
        try:
            tb = page.locator(sel).first
            if tb.is_visible(timeout=3000):
                tb.click()
                time.sleep(0.5)
                tb.type(message, delay=25)
                log.info(f"   ✅ Текст введён ({len(message)} симв.)")
                typed = True
                break
        except Exception:
            continue

    if not typed:
        log.warning("   ⚠️  Textbox не найден — пропускаем")
        return False

    time.sleep(1.5)

    # ── Нажимаем кнопку публикации ────────────────────────────────────────────
    # В зависимости от типа группы и языка кнопка может называться:
    # "Опубликовать" / "Отправить" / "Post" / "פרסם" / "שלח"
    # Ищем через JS — берём первую активную кнопку с нужным текстом
    posted = page.evaluate("""
    () => {
        const LABELS = [
            "Опубликовать", "Отправить", "Post", "פרסם", "שלח", "Publish"
        ];
        // Сначала пробуем aria-label
        for (const lbl of LABELS) {
            const el = document.querySelector(`[aria-label="${lbl}"]`);
            if (el && el.getAttribute('aria-disabled') !== 'true') {
                el.click();
                return lbl;
            }
        }
        // Затем textContent
        const buttons = [...document.querySelectorAll('[role="button"]')];
        for (const btn of buttons) {
            const t = (btn.textContent || '').trim();
            const disabled = btn.getAttribute('aria-disabled');
            if (LABELS.includes(t) && disabled !== 'true') {
                btn.click();
                return t;
            }
        }
        return null;
    }
    """)

    if posted:
        log.info(f"   📤 Нажата кнопка: {posted!r}")
    else:
        log.warning("   ⚠️  Кнопка «Опубликовать» не найдена")
        return False

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

def run_editor(message: str, groups: list[dict] | None = None,
               headful: bool = False, dry_run: bool = False,
               pause: float = PAUSE_BETWEEN) -> dict:
    """Редактирует существующий пост в каждой группе."""
    target = groups or POSTING_GROUPS
    log.info("=" * 65)
    log.info(f"✏️   Facebook Editor — старт")
    log.info(f"    групп: {len(target)},  dry_run: {dry_run}")
    log.info(f"    новый текст: {message[:80]}{'...' if len(message)>80 else ''}")
    log.info("=" * 65)

    if not message.strip():
        return {"ok": False, "error": "Пустой текст"}

    _ensure_chromium()
    cookies = load_facebook_cookies()
    if not cookies:
        return {"ok": False, "error": "Cookies не найдены"}

    results = []
    saved = failed = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=not headful,
            args=["--disable-blink-features=AutomationControlled",
                  "--no-sandbox", "--disable-dev-shm-usage", "--disable-notifications"],
        )
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
            viewport={"width": 1280, "height": 900},
            locale="ru-RU",
        )
        ctx.add_cookies(cookies)
        page = ctx.new_page()

        for i, group in enumerate(target):
            err = None
            try:
                ok = edit_post_in_group(page, group, message, dry_run=dry_run)
            except Exception as e:
                ok = False
                err = str(e)
                log.error(f"   ❌ Исключение: {e}")

            results.append({"name": group["name"], "id": group["id"], "ok": ok, "error": err})
            if ok:
                saved += 1
            else:
                failed += 1

            if i < len(target) - 1:
                log.info(f"   ⏳ Пауза {pause:.0f} сек...")
                time.sleep(pause)

        browser.close()

    log.info("\n" + "=" * 65)
    log.info(f"📊 Готово: обновлено={saved}, ошибок={failed}, всего={len(target)}")
    log.info("=" * 65)

    return {"ok": True, "sent": saved, "failed": failed, "total": len(target), "results": results}


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
    parser.add_argument("--lang", "-l",
                        help="Фильтр по языку: ru / he / en (по умолчанию — все)")
    parser.add_argument("--edit", action="store_true",
                        help="Редактировать существующий пост (не создавать новый)")
    parser.add_argument("--list", action="store_true",
                        help="Показать список групп и выйти")
    args = parser.parse_args()

    if args.list:
        print(f"\n{'#':>3}  {'LANG':5s}  {'ID':30s}  Название")
        print("-" * 80)
        for i, g in enumerate(POSTING_GROUPS, 1):
            lang = g.get("lang", "?")
            print(f"{i:>3}  {lang:5s}  {g['id']:30s}  {g['name']}")
        by_lang = {}
        for g in POSTING_GROUPS:
            l = g.get("lang", "?")
            by_lang[l] = by_lang.get(l, 0) + 1
        print(f"\nВсего: {len(POSTING_GROUPS)} групп  |  " +
              "  ".join(f"{l}={n}" for l, n in sorted(by_lang.items())))
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
    if args.lang:
        target_groups = [g for g in target_groups if g.get("lang") == args.lang]
        if not target_groups:
            print(f"❌ Группы с lang={args.lang!r} не найдены")
            sys.exit(1)
        log.info(f"🔤 Фильтр по языку '{args.lang}': {len(target_groups)} групп")
    if args.groups:
        ids = {g.strip() for g in args.groups.split(",")}
        target_groups = [g for g in target_groups if g["id"] in ids]
        if not target_groups:
            print(f"❌ Группы не найдены: {args.groups}")
            sys.exit(1)

    if args.edit:
        result = run_editor(
            message=message,
            groups=target_groups,
            headful=args.headful,
            dry_run=args.dry_run,
            pause=args.pause,
        )
    else:
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
