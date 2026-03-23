import requests
import time
import json
from datetime import datetime
import database as db

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-RU,ru;q=0.9,he;q=0.8,en;q=0.7",
    "Referer": "https://www.yad2.co.il/",
    "Origin": "https://www.yad2.co.il",
}

CITY_MAP = {
    "תל אביב יפו": "Тель-Авив", "רמת גן": "Рамат-Ган",
    "גבעתיים": "Гиватаим", "בני ברק": "Бней-Брак",
    "בת ים": "Бат-Ям", "חולון": "Холон",
    "ירושלים": "Иерусалим", "חיפה": "Хайфа",
    "נתניה": "Нетания", "פתח תקווה": "Петах-Тиква",
    "ראשון לציון": "Ришон-ле-Цион", "אשדוד": "Ашдод",
    "באר שבע": "Беэр-Шева", "רחובות": "Реховот",
    "הרצליה": "Герцлия", "כפר סבא": "Кфар-Саба",
    "רעננה": "Раанана", "מודיעין מכבים רעות": "Модиин",
    "אשקלון": "Ашкелон", "אילת": "Эйлат",
    "נס ציונה": "Нес-Циона", "לוד": "Лод",
    "רמלה": "Рамла", "הוד השרון": "Ход-ха-Шарон",
    "ראש העין": "Рош-аин", "רמת השרון": "Рамат-ха-Шарон",
}

DISTRICT_MAP = {
    "Тель-Авив": "tel_aviv", "Рамат-Ган": "tel_aviv",
    "Гиватаим": "tel_aviv", "Бней-Брак": "tel_aviv",
    "Бат-Ям": "tel_aviv", "Холон": "tel_aviv",
    "Иерусалим": "jerusalem", "Хайфа": "haifa",
    "Нетания": "sharon", "Герцлия": "sharon",
    "Кфар-Саба": "sharon", "Раанана": "sharon",
    "Ход-ха-Шарон": "sharon", "Рош-аин": "sharon",
    "Рамат-ха-Шарон": "sharon",
    "Петах-Тиква": "center", "Ришон-ле-Цион": "center",
    "Реховот": "center", "Нес-Циона": "center",
    "Лод": "center", "Рамла": "center", "Модиин": "center",
    "Ашдод": "south", "Ашкелон": "south",
    "Беэр-Шева": "south", "Эйлат": "south",
}

PTYPE_MAP = {
    "דירה": "apartment", "בית פרטי": "house",
    "וילה": "villa", "פנטהאוז": "penthouse",
    "סטודיו": "studio", "דופלקס": "duplex",
    "דירת גן": "apartment", "דירה": "apartment",
}

def get_listings_rent(page=1):
    # NOTE: gw.yad2.co.il/feed-search-legacy/* returns 404 (endpoint removed).
    # www.yad2.co.il/api/* returns ShieldSquare CAPTCHA challenge.
    # Yad2 blocks automated access. This parser is currently non-functional.
    print("⚠️  Yad2 API is blocked (CAPTCHA / endpoint removed). Skipping.")
    return None

def get_listings_buy(page=1):
    return None

def parse_listing(item, deal_type):
    try:
        city_he = item.get("city", "") or ""
        city_ru = CITY_MAP.get(city_he, city_he)
        district = DISTRICT_MAP.get(city_ru, "center")

        price = 0
        try:
            price_raw = item.get("price", 0) or 0
            price = int(str(price_raw).replace(",", "").replace(" ", ""))
        except:
            pass

        rooms = "3"
        try:
            r = float(item.get("rooms", 3) or 3)
            rooms = str(r).replace(".0", "")
        except:
            pass

        floor_raw = item.get("floor", "1") or "1"
        floor = str(floor_raw)

        area = 0
        try:
            area = int(item.get("squareMeter", 0) or 0)
        except:
            pass

        ptype_he = item.get("propertyType", "") or ""
        ptype = PTYPE_MAP.get(ptype_he, "apartment")

        neighborhood = item.get("neighborhood", "") or ""
        street = item.get("street", "") or ""
        hood = neighborhood or street or city_ru

        title_parts = []
        if ptype == "apartment": title_parts.append("🏢 Квартира")
        elif ptype == "house": title_parts.append("🏠 Дом")
        elif ptype == "villa": title_parts.append("🏡 Вилла")
        elif ptype == "penthouse": title_parts.append("🌆 Пентхаус")
        elif ptype == "studio": title_parts.append("🛋 Студия")
        elif ptype == "duplex": title_parts.append("🏘 Дуплекс")
        else: title_parts.append("🏢 Квартира")

        if rooms: title_parts.append(f"{rooms} комн.")
        if city_ru: title_parts.append(f"в {city_ru}")
        if neighborhood: title_parts.append(f"({neighborhood})")

        title = " ".join(title_parts)

        desc_parts = []
        if area: desc_parts.append(f"Площадь: {area} кв.м")
        if floor: desc_parts.append(f"Этаж: {floor}")
        info = item.get("infoBox", "") or ""
        if info: desc_parts.append(info[:200])
        description = ". ".join(desc_parts) or "Объявление с Yad2"

        contact = "@yad2_israel"
        source_url = f"https://www.yad2.co.il/item/{item.get('token','')}"

        return {
            "title": title[:100],
            "description": description[:500],
            "property_type": ptype,
            "city": city_ru,
            "district": district,
            "neighborhood": hood,
            "rooms": rooms,
            "floor": floor,
            "area_sqm": area,
            "price": price,
            "deal_type": deal_type,
            "parking": 0,
            "pool": False,
            "infrastructure": [],
            "contact": contact,
            "photos": ["🏢"],
            "source": "yad2",
            "source_url": source_url,
        }
    except Exception as e:
        print(f"Ошибка парсинга объявления: {e}")
        return None

def run_parser(pages=5, interval_minutes=30):
    print("=" * 50)
    print("Yad2 Parser для FlatFinderIL")
    print(f"Страниц за запуск: {pages}")
    print(f"Интервал: каждые {interval_minutes} мин")
    print("=" * 50)

    while True:
        total = 0
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Запуск парсинга Yad2...")

        for deal_type, fetch_func in [("rent", get_listings_rent), ("buy", get_listings_buy)]:
            label = "Аренда" if deal_type == "rent" else "Продажа"
            print(f"\n  {label}:")
            for page in range(1, pages + 1):
                data = fetch_func(page)
                if not data:
                    print(f"    Страница {page}: нет данных")
                    break
                items = data.get("data", {}).get("feed", {}).get("feed_items", [])
                if not items:
                    print(f"    Страница {page}: пусто")
                    break
                added = 0
                for item in items:
                    if item.get("type") != "ad":
                        continue
                    listing = parse_listing(item, deal_type)
                    if listing and listing["price"] > 0:
                        db.add_listing(listing)
                        added += 1
                        total += 1
                print(f"    Страница {page}: +{added} объявлений")
                time.sleep(2)

        print(f"\nИтого добавлено: {total} объявлений")
        print(f"Следующий запуск через {interval_minutes} мин...")
        time.sleep(interval_minutes * 60)

if __name__ == "__main__":
    run_parser(pages=3, interval_minutes=30)
