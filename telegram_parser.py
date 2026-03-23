import asyncio
import os
import re
import requests
import database as db
from datetime import datetime

API_ID = 35002061
API_HASH = "e0868efd711084c61c6bdee94006815e"

CHANNELS = [
    "israel_rent",
    "tlvapartments",
    "israelrealestate",
    "israel_apartments",
    "nadlan_israel",
    "RealEstateIsraelBot",
    "izrailnedvizimosti",
    "rentapartmentbatyam",
    "isra_home_arenda",
    "Sublet_Israel",
    "snyat_kvartiruy",
    "nagariyaapartments",
    "ashdod_rent",
    "happy_home_ashkelon",
]

CITY_KEYWORDS = {
    "тель-авив": "Тель-Авив", "tel aviv": "Тель-Авив", "תל אביב": "Тель-Авив",
    "яффо": "Тель-Авив", "флорентин": "Тель-Авив",
    "рамат-ган": "Рамат-Ган", "ramat gan": "Рамат-Ган",
    "иерусалим": "Иерусалим", "jerusalem": "Иерусалим", "ירושלים": "Иерусалим",
    "хайфа": "Хайфа", "haifa": "Хайфа", "חיפה": "Хайфа",
    "нетания": "Нетания", "netanya": "Нетания", "נתניה": "Нетания",
    "герцлия": "Герцлия", "herzliya": "Герцлия", "הרצליה": "Герцлия",
    "реховот": "Реховот", "ришон": "Ришон-ле-Цион",
    "петах": "Петах-Тиква", "модиин": "Модиин",
    "ашдод": "Ашдод", "ашкелон": "Ашкелон",
    "беэр-шева": "Беэр-Шева", "beer sheva": "Беэр-Шева", "באר שבע": "Беэр-Шева",
    "эйлат": "Эйлат", "eilat": "Эйлат", "אילת": "Эйлат",
    "ashkelon": "Ашкелон", "אשקלון": "Ашкелон",
    "ashdod": "Ашдод", "אשדוד": "Ашдод",
    "нетивот": "Нетивот", "netivot": "Нетивот", "נתיבות": "Нетивот",
    "сдерот": "Сдерот", "sderot": "Сдерот", "שדרות": "Сдерот",
    "холон": "Холон", "holon": "Холон", "חולון": "Холон",
    "бат-ям": "Бат-Ям", "bat yam": "Бат-Ям", "בת ים": "Бат-Ям",
    "кфар-саба": "Кфар-Саба", "kfar saba": "Кфар-Саба", "כפר סבא": "Кфар-Саба",
    "раанана": "Раанана", "raanana": "Раанана", "רעננה": "Раанана",
    "димона": "Димона", "dimona": "Димона", "דימונה": "Димона",
    "арад": "Арад", "arad": "Арад", "ערד": "Арад",
    "нагария": "Нагария", "nahariya": "Нагария", "נהריה": "Нагария",
    "субаренда": "Тель-Авив", "sublet": "Тель-Авив",
}

DISTRICT_MAP = {
    "Тель-Авив": "tel_aviv", "Рамат-Ган": "tel_aviv",
    "Холон": "tel_aviv", "Бат-Ям": "tel_aviv",
    "Иерусалим": "jerusalem",
    "Хайфа": "haifa",
    "Нетания": "sharon", "Герцлия": "sharon",
    "Кфар-Саба": "sharon", "Раанана": "sharon",
    "Петах-Тиква": "center", "Ришон-ле-Цион": "center",
    "Реховот": "center", "Модиин": "center",
    "Нагария": "haifa",
    "Ашдод": "south", "Ашкелон": "south",
    "Беэр-Шева": "south", "Эйлат": "south",
}

# ─── helpers ────────────────────────────────────────────────────────────────

def detect_city(text):
    text_lower = text.lower()
    for keyword, city in CITY_KEYWORDS.items():
        if keyword in text_lower:
            return city
    return "Тель-Авив"

def extract_price(text):
    patterns = [
        r'(\d[\d\s,]{2,6})\s*₪',
        r'(\d[\d\s,]{2,6})\s*[Nn][Ii][Ss]',
        r'(\d[\d\s,]{2,6})\s*шек',
        r'(\d[\d\s,]{2,6})\s*שקל',
        r'מחיר[:\s]+(\d[\d\s,]+)',
        r'цена[:\s]+(\d[\d\s,]+)',
        r'price[:\s]+(\d[\d\s,]+)',
        r'(\d{3,6})\s*לחודש',
        r'(\d{3,6})\s*в\s*мес',
        r'(\d{3,6})\s*/\s*мес',
        r'(\d{4,6})\s*в\s*month',
        r'💰\s*(\d[\d\s,]+)',
        r'(\d{4,6})(?=\s*₪)',
    ]
    found = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            try:
                price_str = match.group(1).replace(" ", "").replace(",", "")
                price = int(price_str)
                if 1000 <= price <= 100000:
                    found.append(price)
            except:
                pass
    if found:
        counts = {}
        for p in found:
            counts[p] = counts.get(p, 0) + 1
        return max(counts, key=counts.get)
    return 0

def extract_rooms(text):
    patterns = [
        r'(\d[.,]?\d?)\s*комн',
        r'(\d[.,]?\d?)\s*חד',
        r'(\d[.,]?\d?)\s*room',
        r'(\d[.,]?\d?)-к',
    ]
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            try:
                val = float(match.group(1).replace(",", "."))
                if 1 <= val <= 10:
                    return str(val).replace(".0", "")
            except:
                pass
    return "3"

def is_listing(text):
    if len(text) < 50:
        return False
    rent_words = ["аренда", "сдам", "снять", "להשכרה", "שכירות", "rent", "for rent",
                  "מחיר", "цена", "₪", "сдается", "сдаётся", "аренд"]
    return any(w in text.lower() for w in rent_words)

def url_exists(source_url: str) -> bool:
    """Check if a listing with this source URL already exists in the DB."""
    data = db._load()
    for listing in data["listings"].values():
        if listing.get("source_url") == source_url:
            return True
    return False

# ─── web scraping (no auth required) ────────────────────────────────────────

def scrape_channel_web(channel: str, limit: int = 50) -> list:
    """
    Scrape a public Telegram channel via t.me/s/<channel>.
    Returns list of (post_id, text, source_url).
    No Telethon / authentication required.
    """
    results = []
    url = f"https://t.me/s/{channel}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            print(f"  HTTP {resp.status_code} для @{channel}")
            return results

        from lxml import html as lhtml
        tree = lhtml.fromstring(resp.text)

        # Each message lives inside a .tgme_widget_message_wrap
        wraps = tree.xpath('//div[contains(@class,"tgme_widget_message_wrap")]')
        for wrap in wraps[-limit:]:
            # data-post="channelname/12345"  (lives on the inner article/div)
            post_elems = wrap.xpath('.//*[@data-post]')
            if not post_elems:
                continue
            data_post = post_elems[0].get("data-post", "")
            post_id = data_post.split("/")[-1]
            if not post_id or not post_id.isdigit():
                continue

            text_elems = wrap.xpath('.//div[contains(@class,"tgme_widget_message_text")]')
            if not text_elems:
                continue
            text = text_elems[0].text_content().strip()
            if text:
                source_url = f"https://t.me/{channel}/{post_id}"
                results.append((post_id, text, source_url))
    except Exception as e:
        print(f"  Ошибка веб-скрапинга @{channel}: {e}")

    return results


def parse_channel_web(channel: str, limit: int = 50) -> int:
    """Parse one channel via web scraping. Returns count of newly added listings."""
    added = 0
    messages = scrape_channel_web(channel, limit)
    for _post_id, text, source_url in messages:
        if url_exists(source_url):
            continue
        if not is_listing(text):
            continue
        city = detect_city(text)
        listing = {
            "title": f"📱 {text[:70].replace(chr(10), ' ').strip()}...",
            "description": text[:600],
            "property_type": "apartment",
            "city": city,
            "district": DISTRICT_MAP.get(city, "center"),
            "neighborhood": "",
            "rooms": extract_rooms(text),
            "floor": "1",
            "area_sqm": 0,
            "price": extract_price(text),
            "deal_type": "rent",
            "parking": 0,
            "pool": False,
            "infrastructure": [],
            "contact": f"@{channel}",
            "photos": ["🏢"],
            "source": "telegram",
            "source_url": source_url,
        }
        db.add_listing(listing)
        added += 1
    return added

# ─── telethon (optional, requires SESSION_STRING) ───────────────────────────

async def parse_channel_telethon(client, channel: str, limit: int = 50) -> int:
    added = 0
    try:
        async for message in client.iter_messages(channel, limit=limit):
            if not message.text:
                continue
            text = message.text
            source_url = f"https://t.me/{channel}/{message.id}"
            if url_exists(source_url):
                continue
            if not is_listing(text):
                continue
            city = detect_city(text)
            listing = {
                "title": f"📱 {text[:70].replace(chr(10), ' ').strip()}...",
                "description": text[:600],
                "property_type": "apartment",
                "city": city,
                "district": DISTRICT_MAP.get(city, "center"),
                "neighborhood": "",
                "rooms": extract_rooms(text),
                "floor": "1",
                "area_sqm": 0,
                "price": extract_price(text),
                "deal_type": "rent",
                "parking": 0,
                "pool": False,
                "infrastructure": [],
                "contact": f"@{channel}",
                "photos": ["🏢"],
                "source": "telegram",
                "source_url": source_url,
            }
            db.add_listing(listing)
            added += 1
    except Exception as e:
        print(f"  Ошибка Telethon @{channel}: {e}")
    return added

# ─── main loop ───────────────────────────────────────────────────────────────

async def run_parser():
    print("=" * 50)
    print("Telegram Parser — FlatFinderIL")
    print(f"Каналов: {len(CHANNELS)}")
    print("=" * 50)

    session_str = os.environ.get("SESSION_STRING")
    session_file = "flatfinderil_session.session"
    use_telethon = bool(session_str) or os.path.exists(session_file)

    client = None
    if use_telethon:
        try:
            from telethon import TelegramClient
            if session_str:
                from telethon.sessions import StringSession
                client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
            else:
                client = TelegramClient(session_file, API_ID, API_HASH)
            await client.start()
            print("✅ Telethon подключён!")
        except Exception as e:
            print(f"⚠️  Telethon ошибка: {e} — переключаемся на веб-скрапинг")
            client = None
    else:
        print("📡 Режим: веб-скрапинг (без авторизации)")

    while True:
        now = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{now}] Запуск парсинга {len(CHANNELS)} каналов...")
        total = 0

        for channel in CHANNELS:
            print(f"  @{channel} ...", end=" ", flush=True)
            try:
                if client:
                    n = await parse_channel_telethon(client, channel)
                else:
                    n = parse_channel_web(channel)
                    await asyncio.sleep(0)   # yield to event loop
                print(f"+{n}")
                total += n
            except Exception as e:
                print(f"❌ {e}")
            await asyncio.sleep(3)   # be polite between channels

        print(f"\n✅ Итого новых: {total} | Следующий запуск через 30 мин.")
        await asyncio.sleep(1800)


if __name__ == "__main__":
    asyncio.run(run_parser())
