#!/usr/bin/env python3
"""
fb_poster.py — Публикация рекламного поста в Facebook-группы.

Запуск:
  python3 fb_poster.py                  # все группы
  python3 fb_poster.py --limit 5        # только первые 5 групп
  python3 fb_poster.py --group 141464740539934  # одна группа (тест)
  python3 fb_poster.py --headful        # видимый браузер (отладка)
  python3 fb_poster.py --dry-run        # показать план без публикации
"""

import sys, os, time, logging, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from facebook_parser import load_facebook_cookies, _ensure_chromium

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
#  ТЕКСТЫ ПОСТОВ
# ══════════════════════════════════════════════════════════════════════════════

POST_RU = """\
🏠 FlatFinderIL — ищем квартиры. Приглашаем к сотрудничеству!

Мы — Telegram-бот по поиску недвижимости в Израиле. Помогаем людям находить жильё по всей стране — от Эйлата до Нагарии.

📲 t.me/flatfinderil_bot

🤝 Ищем партнёров — специалистов в сфере услуг:

🏡 Агенты по недвижимости / маклеры
⚖️ Адвокаты (сделки с недвижимостью, ипотека)
💰 Ипотечные консультанты
🚛 Компании по переезду
🧹 Клининговые компании
🔧 Сантехники / электрики / мастера на час

💡 Что вы получаете:
✅ Прямые обращения от клиентов, которые прямо сейчас ищут жильё
✅ Охват по всему Израилю — все города и районы
✅ Многоязычная аудитория: русский, иврит, английский

📩 Telegram: t.me/flatfinderil_bot
📸 Instagram: instagram.com/flatfinderil

🇮🇱 FlatFinderIL — всё для вашего нового дома в Израиле"""

POST_HE = """\
🏠 FlatFinderIL — מחפשים דירה? אנחנו כאן. ומזמינים אתכם לשיתוף פעולה!

אנחנו בוט טלגרם לחיפוש נדל״ן בישראל. עוזרים לאנשים למצוא דירה — מאילת ועד נהריה.

📲 t.me/flatfinderil_bot

🤝 מחפשים שותפים — בעלי מקצוע בתחום השירותים:

🏡 סוכני נדל״ן ומתווכים
⚖️ עורכי דין (נדל״ן, חוזים, משכנתאות)
💰 יועצי משכנתאות
🚛 חברות הובלה ואחסון
🧹 שירותי ניקיון
🔧 אינסטלטורים / חשמלאים / בעלי מלאכה

💡 מה מקבלים:
✅ פניות ישירות מלקוחות שמחפשים דירה עכשיו
✅ חשיפה בכל הארץ — כל הערים והאזורים
✅ קהל דובר רוסית, עברית ואנגלית

📩 טלגרם: t.me/flatfinderil_bot
📸 אינסטגרם: instagram.com/flatfinderil

🇮🇱 FlatFinderIL — הכל לבית החדש שלך בישראל"""

POST_EN = """\
🏠 FlatFinderIL — Israel's Real Estate Search Bot. Looking for Service Partners!

We're a Telegram bot for finding apartments across Israel — from Tel Aviv to Haifa and everywhere in between.

📲 t.me/flatfinderil_bot

🤝 Looking for partners — service professionals:

🏡 Real estate agents & property consultants
⚖️ Lawyers (real estate, contracts, visas)
💰 Mortgage advisors
🚛 Moving companies & storage
🧹 Cleaning services
🔧 Plumbers / electricians / handymen

💡 What you get:
✅ Direct leads from active apartment seekers
✅ Nationwide coverage — all cities and regions
✅ Multilingual audience: Russian, Hebrew & English speakers

📩 Telegram: t.me/flatfinderil_bot
📸 Instagram: instagram.com/flatfinderil

🇮🇱 FlatFinderIL — Everything for your new home in Israel"""

# ══════════════════════════════════════════════════════════════════════════════
#  ГРУППЫ с привязкой языка
# ══════════════════════════════════════════════════════════════════════════════

GROUPS = [
    # ── Тель-Авив (иврит) ────────────────────────────────────────────────────
    {"id": "101875683484689",  "name": "דירות מפה לאוזן בתל אביב",          "lang": "he"},
    {"id": "295395253832427",  "name": "דירות בתל אביב",                     "lang": "he"},
    {"id": "457465901082882",  "name": "דירות בתל אביב ללא תיווך",           "lang": "he"},
    {"id": "tel.aviv.dirot",   "name": "לוח דירות תל אביב-יפו",              "lang": "he"},
    {"id": "341195019300726",  "name": "דירות במרכז להשכרה/מכירה",           "lang": "he"},
    {"id": "191591524188001",  "name": "דירות להשכרה בדרום תל אביב",         "lang": "he"},
    {"id": "1485565508385836", "name": "דירות להשכרה בצפון תל אביב",         "lang": "he"},
    {"id": "184920528370332",  "name": "דירות להשכרה בתל אביב",              "lang": "he"},
    {"id": "365588344194085",  "name": "דירות להשכרה 2-3 חדרים בתל אביב",   "lang": "he"},
    {"id": "250663073164312",  "name": "Tel Aviv – Housing, Rooms, Apartments", "lang": "en"},
    {"id": "1664977427442936", "name": "דירות להשכרה במרכז עד 5000",         "lang": "he"},

    # ── Хайфа (иврит) ────────────────────────────────────────────────────────
    {"id": "173351201739",     "name": "דירות מפה לאוזן בחיפה",              "lang": "he"},
    {"id": "1591401697779759", "name": "דירות להשכרה בקריות ללא תיווך",      "lang": "he"},
    {"id": "837431273097770",  "name": "דירות להשכרה בחיפה",                 "lang": "he"},
    {"id": "yad2k",            "name": "דירות להשכרה בקריות",                "lang": "he"},
    {"id": "110907419268500",  "name": "דירות לסטודנטים חיפה",               "lang": "he"},
    {"id": "611703096084191",  "name": "דירות להשכרה בחיפה – עם מחיר",      "lang": "he"},
    {"id": "1896414753945570", "name": "דירות להשכרה בחיפה",                 "lang": "he"},
    {"id": "783424098674651",  "name": "דירות להשכרה בחיפה",                 "lang": "he"},
    {"id": "131650282168271",  "name": "דירות להשכרה בחיפה ללא תיווך",      "lang": "he"},

    # ── Иерусалим (иврит) ────────────────────────────────────────────────────
    {"id": "172544843294",     "name": "דירות מפה לאוזן בירושלים",           "lang": "he"},
    {"id": "325992450444",     "name": "דירות להשכרה בירושלים",              "lang": "he"},
    {"id": "344780799040537",  "name": "דירות להשכרה בירושלים",              "lang": "he"},
    {"id": "apartmentsinjerusalem", "name": "דירות בירושלים ללא תיווך",      "lang": "he"},

    # ── Ришон (иврит) ─────────────────────────────────────────────────────────
    {"id": "555578950202434",  "name": "דירות להשכרה בראשון לציון",          "lang": "he"},
    {"id": "959597644173111",  "name": "דירות להשכרה ללא תיווך ראשון לציון", "lang": "he"},
    {"id": "111163552234056",  "name": "דירות מפה לאוזן בראשון לציון",       "lang": "he"},
    {"id": "963153170558917",  "name": "דירות להשכרה חולון בת ים ראשון לציון", "lang": "he"},
    {"id": "201105170260427",  "name": "דירות להשכרה ראשון לציון חולון בת ים", "lang": "he"},

    # ── Холон (иврит) ─────────────────────────────────────────────────────────
    {"id": "1354045801786047", "name": "דירות להשכרה בעיר חולון",            "lang": "he"},
    {"id": "801470026653021",  "name": "דירות להשכרה בחולון",                "lang": "he"},
    {"id": "266774507954665",  "name": "דירות להשכרה בחולון בלבד",           "lang": "he"},
    {"id": "509654872819955",  "name": "דירות להשכרה חולון בת-ים ללא תיווך", "lang": "he"},
    {"id": "dirot.batyam.holon","name": "דירות להשכרה בת ים חולון והסביבה",  "lang": "he"},

    # ── Ашдод (иврит) ─────────────────────────────────────────────────────────
    {"id": "1624818081000281", "name": "דירות להשכרה ומכירה אשדוד והסביבה",  "lang": "he"},
    {"id": "1087635731246729", "name": "דירות להשכרה באשדוד ללא תיווך",      "lang": "he"},
    {"id": "215752412333714",  "name": "דירות להשכרה באשדוד",                "lang": "he"},
    {"id": "rent.in.ashdod",   "name": "דירות להשכרה אשדוד / Аренда Ашдод",  "lang": "ru"},
    {"id": "585483232340913",  "name": "דירות להשכרה אשדוד אשקלון",          "lang": "he"},

    # ── Нетания (иврит) ───────────────────────────────────────────────────────
    {"id": "228387647805774",  "name": "דירות להשכרה בנתניה ללא תיווך",      "lang": "he"},
    {"id": "554754367898974",  "name": "דירות מפה לאוזן בנתניה",             "lang": "he"},
    {"id": "1153910968018350", "name": "דירות להשכרה בנתניה והסביבה ללא תיווך", "lang": "he"},
    {"id": "rentflatnetanya",  "name": "דירות להשכרה בנתניה / Аренда Нетания", "lang": "ru"},

    # ── Рамат-Ган / Гиватаим (иврит) ─────────────────────────────────────────
    {"id": "1870209196564360", "name": "דירות להשכרה רמת גן גבעתיים",        "lang": "he"},
    {"id": "192850633573",     "name": "דירות מפה לאוזן ברמת גן",            "lang": "he"},
    {"id": "253957624766723",  "name": "דירות להשכרה ברמת גן",               "lang": "he"},
    {"id": "441654752934426",  "name": "דירות להשכרה רמת גן גבעתיים ללא תיווך", "lang": "he"},

    # ── Бат-Ям (русский) ─────────────────────────────────────────────────────
    {"id": "647964450757105",  "name": "Аренда жилья Израиль – Бат Ям",       "lang": "ru"},
    {"id": "rentbatyam",       "name": "АРЕНДА БАТ ЯМ | השכרה בת ים",        "lang": "ru"},
    {"id": "198851813933632",  "name": "Аренда квартир в Бат Яме",            "lang": "ru"},
    {"id": "1903124356581754", "name": "Аренда без Маклера – граждане Бат Ям","lang": "ru"},
    {"id": "RentBuySaleBatYam","name": "Аренда и продажа квартир в Бат Ям",   "lang": "ru"},
    {"id": "holonandbatyam",   "name": "Продажа и аренда квартир Холон и Бат-Ям", "lang": "ru"},
    {"id": "batyam.ad",        "name": "Бат-Ям – Объявления",                 "lang": "ru"},

    # ── Рош-аАин (иврит) ─────────────────────────────────────────────────────
    {"id": "1777924022257391", "name": "דירות למכירה והשכרה ראש העין רבתי",   "lang": "he"},
    {"id": "1773509336205184", "name": "דירות להשכרה ומכירה בראש העין",       "lang": "he"},
    {"id": "1824690151020636", "name": "לוח הדירות של ראש העין ופסגות אפק",   "lang": "he"},
    {"id": "1797166367186177", "name": "דירות להשכרה/מכירה – הפרלמנט ראש העין", "lang": "he"},
    {"id": "509084853121039",  "name": "דירות להשכרה בראש העין",              "lang": "he"},
    {"id": "308216903043626",  "name": "הפרלמנט דירות להשכרה בראש העין ללא תיווך", "lang": "he"},

    # ── Общеизраильские ───────────────────────────────────────────────────────
    {"id": "819372811594662",  "name": "Аренда квартир Израиль",              "lang": "ru"},
    {"id": "141464740539934",  "name": "Аренда квартир в Израиле",            "lang": "ru"},
    {"id": "1697329423753683", "name": "Квартиры без маклера",                "lang": "ru"},
    {"id": "321202505245057",  "name": "Из рук в руки – Аренда жилья без маклера", "lang": "ru"},
    {"id": "2928147683954852", "name": "Весь Гуш-Дан",                        "lang": "ru"},
    {"id": "919120634860210",  "name": "Русскоязычный Израиль – жильё, услуги", "lang": "ru"},
    {"id": "LiveandWork",      "name": "Apartment Rentals and House Purchasing", "lang": "en"},
    {"id": "TelAvivBoard",     "name": "Тель-Авив – Доска объявлений",        "lang": "ru"},
    {"id": "2lumi",            "name": "ДОСКА ОБЪЯВЛЕНИЙ ИЗРАИЛЯ",            "lang": "ru"},
    {"id": "adsisrael",        "name": "Объявления Израиля на русском",       "lang": "ru"},
]

LANG_TO_POST = {"ru": POST_RU, "he": POST_HE, "en": POST_EN}

# ══════════════════════════════════════════════════════════════════════════════

PAUSE_BETWEEN_GROUPS = 45   # секунд между группами (не торопимся)
PAGE_LOAD_WAIT       = 7    # секунд ожидания после открытия группы


def _click_first_visible(page, selectors: list, timeout: int = 4000):
    """Попробовать каждый селектор, кликнуть на первый видимый элемент."""
    for sel in selectors:
        try:
            el = page.locator(sel).first
            el.wait_for(state="visible", timeout=timeout)
            el.click()
            return True
        except Exception:
            continue
    return False


def post_to_group(page, group: dict, dry_run: bool = False) -> bool:
    """Открыть группу и опубликовать новый пост. Возвращает True при успехе."""
    url = f"https://www.facebook.com/groups/{group['id']}"
    post_text = LANG_TO_POST.get(group["lang"], POST_RU)

    if dry_run:
        log.info(f"[DRY-RUN] {group['name']} ({group['lang']}) → {url}")
        return True

    log.info(f"→ {group['name']} ({group['lang']})")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=35000)
        page.wait_for_timeout(PAGE_LOAD_WAIT * 1000)

        # ── Шаг 1: открыть модалку — JS-клик по role=button "Напишите что-нибудь" ──
        page.evaluate("""
        () => {
            // Ищем именно role=button с этим текстом (не div без роли)
            const btn = [...document.querySelectorAll('[role="button"]')]
                .find(e => e.innerText?.trim().startsWith('Напишите что-нибудь') ||
                           e.innerText?.trim().startsWith('Write something') ||
                           e.innerText?.trim().startsWith('כתוב משהו') ||
                           e.innerText?.trim().startsWith('מה חדש'));
            if (btn) btn.click();
        }
        """)

        # Ждём появления диалога создания поста
        try:
            page.wait_for_selector(
                '[aria-label="Закрыть диалог создания публикаций"], '
                '[aria-label="Close"], '
                '[aria-label="סגור"]',
                timeout=8000
            )
        except Exception:
            log.warning(f"  ⚠️  Модалка «Создать пост» не открылась в «{group['name']}»")
            return False

        page.wait_for_timeout(1000)

        # ── Шаг 2: ввести текст в поле поста внутри модалки ──────────────────
        # Поле — contenteditable без aria-label (не комментарий, не чат)
        # Находим его внутри диалога
        editor = None
        try:
            # Внутри диалога ищем contenteditable без aria-label
            editor = page.locator(
                '[role="dialog"] [contenteditable="true"]:not([aria-label]), '
                '[aria-label*="диалог"] ~ * [contenteditable="true"]:not([aria-label])'
            ).first
            editor.wait_for(state="visible", timeout=5000)
        except Exception:
            # Запасной: второй contenteditable на странице (первый — комментарий, второй — пост)
            editors = page.locator('[contenteditable="true"]').all()
            for ed in editors:
                aria = ed.get_attribute("aria-label") or ""
                if not aria:  # без aria-label — это поле поста
                    editor = ed
                    break

        if not editor:
            log.warning(f"  ⚠️  Поле ввода не найдено в «{group['name']}»")
            return False

        editor.click()
        page.wait_for_timeout(500)

        # Вводим построчно (keyboard.type поддерживает emoji)
        for i, line in enumerate(post_text.split("\n")):
            page.keyboard.type(line)
            if i < len(post_text.split("\n")) - 1:
                page.keyboard.press("Shift+Enter")
        page.wait_for_timeout(1500)

        # ── Шаг 3: нажать «Отправить» / «Опубликовать» внутри модалки ────────
        # Кнопка называется "Отправить" (aria-label) и изначально disabled
        posted = False
        submit_labels = ["Отправить", "Post", "פרסם", "Опубликовать", "Publish"]
        for label in submit_labels:
            try:
                btn = page.locator(f'[role="button"][aria-label="{label}"]').first
                btn.wait_for(state="visible", timeout=3000)
                # Подождём пока кнопка станет активной
                page.wait_for_timeout(500)
                if btn.get_attribute("aria-disabled") != "true":
                    btn.click()
                    posted = True
                    break
                # Если всё ещё disabled — жмём всё равно (иногда disabled снимается после JS-клика)
                btn.click(force=True)
                posted = True
                break
            except Exception:
                continue

        if not posted:
            log.warning(f"  ⚠️  Кнопка «Отправить» не найдена в «{group['name']}»")
            return False

        page.wait_for_timeout(5000)
        log.info(f"  ✅ Опубликовано: {group['name']}")
        return True

    except PWTimeout:
        log.error(f"  ❌ Таймаут: {group['name']}")
        return False
    except Exception as e:
        log.error(f"  ❌ Ошибка «{group['name']}»: {e}")
        return False


def run(target: list, headful: bool = False, dry_run: bool = False):
    log.info("=" * 60)
    log.info(f"FB Poster — FlatFinderIL | групп: {len(target)}")
    log.info(f"Режим: {'DRY-RUN' if dry_run else 'ПУБЛИКАЦИЯ'} | браузер: {'видимый' if headful else 'headless'}")
    log.info("=" * 60)

    if not dry_run:
        _ensure_chromium()
        cookies = load_facebook_cookies()
        if not cookies:
            log.error("❌ Cookies не найдены. Войдите в Facebook в Chrome и повторите.")
            return

    ok = fail = skip = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=not headful,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="ru-RU",
        )
        if not dry_run:
            ctx.add_cookies(cookies)
        page = ctx.new_page()

        for i, group in enumerate(target, 1):
            log.info(f"[{i}/{len(target)}] ", )
            result = post_to_group(page, group, dry_run=dry_run)
            if result:
                ok += 1
            else:
                fail += 1

            if i < len(target) and not dry_run:
                log.info(f"  ⏳ Пауза {PAUSE_BETWEEN_GROUPS}с перед следующей группой…")
                time.sleep(PAUSE_BETWEEN_GROUPS)

        browser.close()

    log.info("=" * 60)
    log.info(f"✅ Опубликовано: {ok} | ❌ Ошибок: {fail} | Всего: {len(target)}")
    log.info("=" * 60)


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Facebook Group Poster — FlatFinderIL")
    ap.add_argument("--limit",   type=int,  default=None, help="Сколько групп постить (для теста)")
    ap.add_argument("--group",   type=str,  default=None, help="ID одной группы (для теста)")
    ap.add_argument("--lang",    type=str,  default=None, help="Фильтр по языку: ru / he / en")
    ap.add_argument("--headful", action="store_true",     help="Показывать браузер")
    ap.add_argument("--dry-run", action="store_true",     help="Только показать план, не постить")
    args = ap.parse_args()

    if args.group:
        target = [g for g in GROUPS if g["id"] == args.group]
        if not target:
            target = [{"id": args.group, "name": args.group, "lang": "ru"}]
    elif args.lang:
        target = [g for g in GROUPS if g["lang"] == args.lang]
    else:
        target = list(GROUPS)

    if args.limit:
        target = target[:args.limit]

    run(target, headful=args.headful, dry_run=args.dry_run)
