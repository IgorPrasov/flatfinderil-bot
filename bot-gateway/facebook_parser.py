#!/usr/bin/env python3
"""
facebook_parser.py — Парсинг объявлений о недвижимости из Facebook-групп.

Принцип работы:
  • Запускает Playwright Chromium (headless) с cookies из Chrome.
  • Открывает каждую группу, скроллит вниз и собирает посты [role="article"].
  • Фильтрует объявления через функции telegram_parser.py.
  • Сохраняет в общую БД (source="facebook").
  • Дедупликация по source_url.

Запуск:
  python3 facebook_parser.py                     # Один проход
  python3 facebook_parser.py --loop              # Цикл каждые 60 мин
  python3 facebook_parser.py --loop --interval 30
  python3 facebook_parser.py --group 141464740539934
  python3 facebook_parser.py --pages 5 --headful  # Видимый браузер (debug)
"""

import time
import logging
import re
import sys
import os
from datetime import datetime
from urllib.parse import unquote

import browser_cookie3
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ── Путь к модулям проекта ─────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import database as db

# ── Импорт вспомогательных функций из telegram_parser ─────────────────────────
try:
    from telegram_parser import (
        detect_city, extract_price, extract_rooms, extract_floor,
        extract_area, extract_parking, extract_pool,
        extract_property_type, extract_deal_type,
        extract_infrastructure, extract_neighborhood,
        is_listing, is_ad_or_spam, DISTRICT_MAP,
    )
    _IMPORT_OK = True
except ImportError:
    _IMPORT_OK = False
    def is_listing(t):       return len(t) > 120
    def is_ad_or_spam(t):    return False
    def detect_city(t):      return None
    def extract_price(t):    return None
    def extract_rooms(t):    return None
    def extract_floor(t):    return None
    def extract_area(t):     return None
    def extract_parking(t):  return False
    def extract_pool(t):     return False
    def extract_property_type(t):   return "apartment"
    def extract_deal_type(t):       return "rent"
    def extract_infrastructure(t):  return []
    def extract_neighborhood(t, c): return None
    DISTRICT_MAP = {}

# ── Логирование ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("fb_parser")
if _IMPORT_OK:
    log.info("✅ Функции извлечения загружены из telegram_parser")
else:
    log.warning("⚠️  telegram_parser не импортирован — используются заглушки")

# ══════════════════════════════════════════════════════════════════════════════
#  СПИСОК ГРУПП
# ══════════════════════════════════════════════════════════════════════════════
GROUPS = [
    # ── Тель-Авив ─────────────────────────────────────────────────────────────
    {"id": "101875683484689",  "name": "דירות מפה לאוזן בתל אביב"},          # 246k
    {"id": "295395253832427",  "name": "דירות בתל אביב"},                     # 104k
    {"id": "457465901082882",  "name": "דירות בתל אביב ללא תיווך"},           # 85k
    {"id": "tel.aviv.dirot",   "name": "לוח דירות תל אביב-יפו"},              # 68k
    {"id": "341195019300726",  "name": "דירות במרכז להשכרה/מכירה"},           # 61k
    {"id": "191591524188001",  "name": "דירות להשכרה בדרום תל אביב"},         # 52k
    {"id": "1485565508385836", "name": "דירות להשכרה בצפון תל אביב"},         # 42k
    {"id": "184920528370332",  "name": "דירות להשכרה בתל אביב"},              # 40k
    {"id": "365588344194085",  "name": "דירות להשכרה 2-3 חדרים בתל אביב"},   # 39k
    {"id": "250663073164312",  "name": "Tel Aviv – Housing, Rooms, Apartments"},
    {"id": "1664977427442936", "name": "דירות להשכרה במרכז עד 5000"},         # 26k

    # ── Хайфа ─────────────────────────────────────────────────────────────────
    {"id": "173351201739",     "name": "דירות מפה לאוזן בחיפה"},              # 84k
    {"id": "1591401697779759", "name": "דירות להשכרה בקריות ללא תיווך"},      # 84k
    {"id": "837431273097770",  "name": "דירות להשכרה בחיפה"},                 # 81k
    {"id": "yad2k",            "name": "דירות להשכרה בקריות"},                # 80k
    {"id": "110907419268500",  "name": "דירות לסטודנטים חיפה"},               # 55k
    {"id": "611703096084191",  "name": "דירות להשכרה בחיפה – עם מחיר"},      # 49k
    {"id": "1896414753945570", "name": "דירות להשכרה בחיפה"},                 # 48k
    {"id": "783424098674651",  "name": "דירות להשכרה בחיפה"},                 # 41k
    {"id": "131650282168271",  "name": "דירות להשכרה בחיפה ללא תיווך"},      # 41k

    # ── Иерусалим ─────────────────────────────────────────────────────────────
    {"id": "172544843294",     "name": "דירות מפה לאוזן בירושלים"},           # 117k
    {"id": "325992450444",     "name": "דירות להשכרה בירושלים"},              # 104k
    {"id": "344780799040537",  "name": "דירות להשכרה בירושלים"},              # 100k
    {"id": "apartmentsinjerusalem", "name": "דירות בירושלים ללא תיווך"},      # 31k

    # ── Ришон-ле-Цион ─────────────────────────────────────────────────────────
    {"id": "555578950202434",  "name": "דירות להשכרה בראשון לציון"},
    {"id": "959597644173111",  "name": "דירות להשכרה ללא תיווך ראשון לציון"},
    {"id": "111163552234056",  "name": "דירות מפה לאוזן בראשון לציון"},
    {"id": "963153170558917",  "name": "דירות להשכרה חולון בת ים ראשון לציון"},
    {"id": "201105170260427",  "name": "דירות להשכרה ראשון לציון חולון בת ים"},

    # ── Холон ─────────────────────────────────────────────────────────────────
    {"id": "1354045801786047", "name": "דירות להשכרה בעיר חולון"},
    {"id": "801470026653021",  "name": "דירות להשכרה בחולון"},
    {"id": "266774507954665",  "name": "דירות להשכרה בחולון בלבד"},
    {"id": "509654872819955",  "name": "דירות להשכרה חולון בת-ים ללא תיווך"},
    {"id": "dirot.batyam.holon","name": "דירות להשכרה בת ים חולון והסביבה"},

    # ── Ашдод ─────────────────────────────────────────────────────────────────
    {"id": "1624818081000281", "name": "דירות להשכרה ומכירה אשדוד והסביבה"},
    {"id": "1087635731246729", "name": "דירות להשכרה באשדוד ללא תיווך"},
    {"id": "215752412333714",  "name": "דירות להשכרה באשדוד"},
    {"id": "rent.in.ashdod",   "name": "דירות להשכרה אשדוד / Аренда Ашдод"},
    {"id": "585483232340913",  "name": "דירות להשכרה אשדוד אשקלון"},

    # ── Нетания ───────────────────────────────────────────────────────────────
    {"id": "228387647805774",  "name": "דירות להשכרה בנתניה ללא תיווך"},
    {"id": "554754367898974",  "name": "דירות מפה לאוזן בנתניה"},
    {"id": "1153910968018350", "name": "דירות להשכרה בנתניה והסביבה ללא תיווך"},
    {"id": "rentflatnetanya",  "name": "דירות להשכרה בנתניה / Аренда Нетания"},

    # ── Рамат-Ган / Гиватаим ──────────────────────────────────────────────────
    {"id": "1870209196564360", "name": "דירות להשכרה רמת גן גבעתיים"},
    {"id": "192850633573",     "name": "דירות מפה לאוזן ברמת גן"},
    {"id": "253957624766723",  "name": "דירות להשכרה ברמת גן"},
    {"id": "441654752934426",  "name": "דירות להשכרה רמת גן גבעתיים ללא תיווך"},

    # ── Бат-Ям ────────────────────────────────────────────────────────────────
    {"id": "647964450757105",  "name": "Аренда жилья Израиль – Бат Ям"},
    {"id": "rentbatyam",       "name": "АРЕНДА БАТ ЯМ | השכרה בת ים"},
    {"id": "198851813933632",  "name": "Аренда квартир в Бат Яме"},
    {"id": "1903124356581754", "name": "Аренда без Маклера – граждане Бат Ям"},
    {"id": "RentBuySaleBatYam","name": "Аренда и продажа квартир в Бат Ям"},
    {"id": "holonandbatyam",   "name": "Продажа и аренда квартир Холон и Бат-Ям"},
    {"id": "batyam.ad",        "name": "Бат-Ям – Объявления"},

    # ── Рош-аАин ─────────────────────────────────────────────────────────────
    {"id": "1777924022257391", "name": "דירות למכירה והשכרה ראש העין רבתי"},
    {"id": "1773509336205184", "name": "דירות להשכרה ומכירה בראש העין"},
    {"id": "1824690151020636", "name": "לוח הדירות של ראש העין ופסגות אפק"},
    {"id": "1797166367186177", "name": "דירות להשכרה/מכירה – הפרלמנט ראש העין"},
    {"id": "509084853121039",  "name": "דירות להשכרה בראש העין"},
    {"id": "308216903043626",  "name": "הפרלמנט דירות להשכרה בראש העין ללא תיווך"},

    # ── Общеизраильские ───────────────────────────────────────────────────────
    {"id": "819372811594662",  "name": "Аренда квартир Израиль | דירות להשכרה"},
    {"id": "141464740539934",  "name": "Аренда квартир в Израиле"},
    {"id": "1697329423753683", "name": "Квартиры без маклера"},
    {"id": "321202505245057",  "name": "Из рук в руки – Аренда жилья без маклера"},
    {"id": "2928147683954852", "name": "Весь Гуш-Дан"},
    {"id": "919120634860210",  "name": "Русскоязычный Израиль – жильё, услуги"},
    {"id": "LiveandWork",      "name": "Apartment Rentals and House Purchasing"},
    {"id": "TelAvivBoard",     "name": "Тель-Авив – Доска объявлений Израиля"},
    {"id": "2lumi",            "name": "ДОСКА ОБЪЯВЛЕНИЙ ИЗРАИЛЯ"},
    {"id": "adsisrael",        "name": "Объявления Израиля на русском"},
]

# ══════════════════════════════════════════════════════════════════════════════
#  НАСТРОЙКИ
# ══════════════════════════════════════════════════════════════════════════════
SCROLL_ROUNDS    = 4      # Сколько раз скроллить вниз на одной группе
SCROLL_PAUSE     = 2.5    # Сек между скроллами
PAGE_LOAD_WAIT   = 6.0    # Сек ожидания после открытия группы
PAUSE_GROUPS     = 10.0   # Сек между группами
MIN_TEXT_LEN     = 80     # Минимальная длина текста поста

# Паттерны шума интерфейса для удаления из текста
_UI_NOISE = re.compile(
    r"(Нравится|Like|Комментировать|Comment|Поделиться|Share|Ещё|See\s+More"
    r"|Подписаться|Follow|Ответить|Reply|Скопировать|Translate"
    r"|הגב|שתף|עוד|לייק|צפה\s+עוד|תרגם|שתף|עקוב"
    r"|\d+\s*(мин\.|ч\.|дн\.|нед\.|мес\.|г\.)\s*(назад)?"
    r"|Комментировать\s+как\s+\S+"
    r"|Написать\s+публичный\s+ответ"
    r"|Посмотреть\s+перевод)\b",
    re.IGNORECASE,
)

# ══════════════════════════════════════════════════════════════════════════════
#  ЗАГРУЗКА COOKIES ИЗ CHROME
# ══════════════════════════════════════════════════════════════════════════════

def load_facebook_cookies() -> list[dict]:
    """
    Загружает Facebook cookies.
    Сначала проверяет env FB_COOKIES_JSON (Railway), затем Chrome (macOS).
    Возвращает список dict в формате Playwright: {name, value, domain, path}.
    """
    import json as _json

    # ── Railway: cookies из переменной окружения ───────────────────────────────
    env_cookies_raw = os.environ.get("FB_COOKIES_JSON", "")
    if env_cookies_raw:
        try:
            env_data = _json.loads(env_cookies_raw)
            all_cookies = {}
            if isinstance(env_data, dict):
                # Формат: {"name": "value", ...}
                for name, value in env_data.items():
                    val = unquote(value) if "%" in (value or "") else (value or "")
                    all_cookies[name] = {"name": name, "value": val, "domain": ".facebook.com", "path": "/"}
            elif isinstance(env_data, list):
                # Формат: [{name, value, ...}, ...]
                for c in env_data:
                    val = unquote(c["value"]) if "%" in (c.get("value") or "") else (c.get("value") or "")
                    all_cookies[c["name"]] = {"name": c["name"], "value": val, "domain": ".facebook.com", "path": "/"}
            log.info(f"✅ Cookies из FB_COOKIES_JSON: {len(all_cookies)} шт.")
            return list(all_cookies.values())
        except Exception as e:
            log.warning(f"⚠️  Ошибка парсинга FB_COOKIES_JSON: {e}")

    # ── Локально: cookies из Chrome ────────────────────────────────────────────
    chrome_base = os.path.expanduser("~/Library/Application Support/Google/Chrome")
    all_cookies: list[dict] = {}  # name -> cookie (последнее значение побеждает)
    total = 0

    for profile in ["Default"] + [f"Profile {i}" for i in range(1, 10)]:
        cookie_file = os.path.join(chrome_base, profile, "Cookies")
        if not os.path.exists(cookie_file):
            continue
        try:
            cj = browser_cookie3.chrome(cookie_file=cookie_file, domain_name=".facebook.com")
            n = 0
            for c in cj:
                val = unquote(c.value) if "%" in (c.value or "") else (c.value or "")
                all_cookies[c.name] = {
                    "name":   c.name,
                    "value":  val,
                    "domain": ".facebook.com",
                    "path":   "/",
                }
                n += 1
            if n:
                log.info(f"   Chrome [{profile}]: {n} Facebook cookies")
            total += n
        except Exception as e:
            log.debug(f"   [{profile}] ошибка: {e}")

    log.info(f"✅ Итого cookies: {len(all_cookies)} уникальных")
    return list(all_cookies.values())


# ══════════════════════════════════════════════════════════════════════════════
#  ПАРСИНГ ПОСТОВ
# ══════════════════════════════════════════════════════════════════════════════

def _clean_post_text(raw: str) -> str:
    """Убирает UI-шум из текста поста."""
    text = _UI_NOISE.sub(" ", raw)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


def _expand_see_more(page) -> int:
    """
    Кликает все кнопки «Ещё» / «See More» на странице, чтобы раскрыть
    усечённые тексты постов. Возвращает количество нажатых кнопок.
    """
    try:
        clicked = page.evaluate("""
        () => {
            let count = 0;
            // Facebook рендерит «Ещё» как div[role="button"] с текстом «Ещё» или «See more»
            const all = document.querySelectorAll('div[role="button"], span[role="button"]');
            all.forEach(el => {
                const t = (el.textContent || '').trim();
                if (t === 'Ещё' || t === 'See more' || t === 'עוד' || t === '查看更多') {
                    try { el.click(); count++; } catch(e) {}
                }
            });
            return count;
        }
        """)
        return clicked
    except Exception:
        return 0


def _extract_posts_from_page(page) -> list[dict]:
    """
    Извлекает посты из загруженной Playwright страницы Facebook-группы.
    1. Кликает «Ещё» для раскрытия усечённых постов.
    2. Собирает все [role="article"] с permalink-ссылкой.
    """
    # Раскрываем усечённые посты
    expanded = _expand_see_more(page)
    if expanded:
        time.sleep(1.0)  # Ждём рендер развёрнутого текста

    posts: list[dict] = []
    seen_urls: set[str] = set()

    try:
        article_js = """
        () => {
            const articles = document.querySelectorAll('[role="article"]');
            const results = [];
            articles.forEach(art => {
                const text = art.innerText || '';

                // Ищем permalink: /groups/.../posts/... или /permalink/...
                let url = null;
                for (const a of art.querySelectorAll('a[href]')) {
                    const href = a.href || '';
                    if ((href.includes('/groups/') && (href.includes('/posts/') || href.includes('/permalink/')))
                        || href.includes('/story.php')) {
                        url = href.split('?')[0];
                        break;
                    }
                }

                if (text.length > 80 && url) {
                    results.push({ text: text, url: url });
                }
            });
            return results;
        }
        """
        raw_posts = page.evaluate(article_js)

        for item in raw_posts:
            url  = item.get("url", "")
            text = _clean_post_text(item.get("text", ""))

            if not url or url in seen_urls:
                continue
            if len(text) < MIN_TEXT_LEN:
                continue

            seen_urls.add(url)
            posts.append({"text": text, "url": url})

    except Exception as e:
        log.error(f"   Ошибка извлечения постов из DOM: {e}")

    return posts


# ══════════════════════════════════════════════════════════════════════════════
#  ФОРМИРОВАНИЕ ОБЪЯВЛЕНИЯ
# ══════════════════════════════════════════════════════════════════════════════

def _url_exists(url: str) -> bool:
    try:
        data = db._load()
        for listing in data.get("listings", {}).values():
            if listing.get("source_url") == url:
                return True
    except Exception:
        pass
    return False


def build_listing(post: dict) -> dict | None:
    text = post["text"]

    if not is_listing(text):
        return None
    if is_ad_or_spam(text):
        return None

    city  = detect_city(text)
    price = extract_price(text)

    if not city and not price:
        return None

    district  = DISTRICT_MAP.get(city or "", "") or "center"
    deal_type = extract_deal_type(text) or "rent"
    prop_type = extract_property_type(text) or "apartment"

    title = re.sub(r"\s+", " ", text[:100]).strip()
    if len(text) > 100:
        title += "…"

    return {
        "title":          title,
        "description":    text[:2000],
        "property_type":  prop_type,
        "city":           city or "Израиль",
        "district":       district,
        "neighborhood":   extract_neighborhood(text, city) if city else None,
        "rooms":          extract_rooms(text),
        "floor":          extract_floor(text),
        "area_sqm":       extract_area(text),
        "price":          price,
        "deal_type":      deal_type,
        "parking":        extract_parking(text),
        "pool":           extract_pool(text),
        "infrastructure": extract_infrastructure(text),
        "contact":        None,
        "photos":         [],
        "source":         "facebook",
        "source_url":     post["url"],
        "active":         True,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  ОБХОД ОДНОЙ ГРУППЫ
# ══════════════════════════════════════════════════════════════════════════════

def scrape_group(page, group: dict) -> int:
    gid   = group["id"]
    gname = group["name"]
    url   = f"https://www.facebook.com/groups/{gid}/"

    log.info(f"\n📂  {gname}")
    log.info(f"    {url}")

    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        time.sleep(PAGE_LOAD_WAIT)
    except PWTimeout:
        log.warning("   Таймаут загрузки — пропускаем")
        return 0
    except Exception as e:
        log.error(f"   Ошибка навигации: {e}")
        return 0

    # Проверяем — не попали ли на страницу входа
    if "login" in page.url or "checkpoint" in page.url:
        log.warning("   Перенаправление на login — cookies устарели?")
        return 0

    saved = 0
    seen_globally: set[str] = set()  # Чтобы не дублировать при скроллинге

    for scroll_round in range(SCROLL_ROUNDS):
        posts = _extract_posts_from_page(page)
        new_in_round = 0

        for post in posts:
            purl = post["url"]
            if purl in seen_globally:
                continue
            seen_globally.add(purl)

            if _url_exists(purl):
                continue

            listing = build_listing(post)
            if not listing:
                continue

            try:
                lid = db.add_listing(listing)
                city_s  = listing["city"] or "?"
                price_s = f"{listing['price']}₪" if listing["price"] else "?"
                rooms_s = f"{listing['rooms']}к" if listing["rooms"] else "?"
                log.info(
                    f"   ✅ #{lid}  {listing['deal_type']:4s}  "
                    f"{city_s:12s}  {rooms_s:3s}  {price_s:10s}  "
                    f"{listing['title'][:50]}"
                )
                saved       += 1
                new_in_round += 1
            except Exception as e:
                log.error(f"   ❌ БД: {e}")

        log.info(f"   Скролл {scroll_round+1}/{SCROLL_ROUNDS}: {len(posts)} постов, +{new_in_round} новых")

        if new_in_round == 0 and scroll_round >= 1:
            log.info("   Новых нет — останавливаемся")
            break

        # Скроллим вниз для загрузки следующих постов
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(SCROLL_PAUSE)

    log.info(f"   📊 Сохранено: {saved}")
    return saved


# ══════════════════════════════════════════════════════════════════════════════
#  ОСНОВНЫЕ ФУНКЦИИ ЗАПУСКА
# ══════════════════════════════════════════════════════════════════════════════

def run_once(groups: list[dict] | None = None, headful: bool = False) -> int:
    target = groups or GROUPS
    log.info("=" * 65)
    log.info(f"🚀  Facebook Parser — старт  |  групп: {len(target)},  скроллов: {SCROLL_ROUNDS}")
    log.info("=" * 65)

    cookies = load_facebook_cookies()
    if not cookies:
        log.error("❌ Cookies не найдены. Войдите в Facebook в Chrome и повторите.")
        return 0

    total = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=not headful,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
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

        for group in target:
            try:
                total += scrape_group(page, group)
            except Exception as e:
                log.error(f"Ошибка в группе '{group['name']}': {e}", exc_info=True)
            time.sleep(PAUSE_GROUPS)

        browser.close()

    log.info("=" * 65)
    log.info(f"✅  Готово.  Добавлено объявлений: {total}")
    log.info("=" * 65)
    return total


def run_loop(interval_min: int = 60, groups: list[dict] | None = None,
             headful: bool = False):
    log.info(f"🔄  Режим цикла: каждые {interval_min} мин")
    while True:
        try:
            run_once(groups, headful=headful)
        except Exception as e:
            log.error(f"Критическая ошибка: {e}", exc_info=True)
        log.info(f"💤  Следующий запуск через {interval_min} мин …\n")
        time.sleep(interval_min * 60)


# ══════════════════════════════════════════════════════════════════════════════
#  ТОЧКА ВХОДА
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(
        description="Facebook Real Estate Group Parser",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--loop",      action="store_true", help="Бесконечный цикл")
    ap.add_argument("--interval",  type=int, default=60, help="Интервал цикла (мин), default=60")
    ap.add_argument("--scrolls",   type=int, default=4,  help="Скроллов на группу, default=4")
    ap.add_argument("--group",     type=str, default=None, help="ID одной группы для теста")
    ap.add_argument("--headful",   action="store_true", help="Показывать браузер (отладка)")
    args = ap.parse_args()

    SCROLL_ROUNDS = args.scrolls

    if args.group:
        name = next((g["name"] for g in GROUPS if g["id"] == args.group), args.group)
        run_once([{"id": args.group, "name": name}], headful=args.headful)
    elif args.loop:
        run_loop(args.interval, headful=args.headful)
    else:
        run_once(headful=args.headful)
