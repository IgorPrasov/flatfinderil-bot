from facebook_scraper import get_posts
from datetime import datetime
import database as db
import time
import re

# Целевые группы
GROUPS = [
    "ArendaBezMaklera",
    "gush.dan.arenda",
    "arenda.bez.maklera.israel",
    "556789234",
]

# Ключевые слова для фильтрации объявлений
RENT_KEYWORDS = [
    "аренда","сдам","снять","сдается","להשכרה","שכירות",
    "rent","for rent","שכר","מחפש","מחפשת"
]

# Ключевые слова-исключения (не объявления)
EXCLUDE_KEYWORDS = [
    "ищу","мне нужна","помогите найти","посоветуйте","вопрос"
]

# Города Гуш-Дана
GUSH_DAN_CITIES = {
    "тель-авив": "Тель-Авив", "tel aviv": "Тель-Авив", "תל אביב": "Тель-Авив",
    "рамат-ган": "Рамат-Ган", "ramat gan": "Рамат-Ган", "רמת גן": "Рамат-Ган",
    "гиватаим": "Гиватаим", "givatayim": "Гиватаим", "גבעתיים": "Гиватаим",
    "бней-брак": "Бней-Брак", "bnei brak": "Бней-Брак", "בני ברק": "Бней-Брак",
    "бат-ям": "Бат-Ям", "bat yam": "Бат-Ям", "בת ים": "Бат-Ям",
    "холон": "Холон", "holon": "Холон", "חולון": "Холон",
    "петах-тиква": "Петах-Тиква", "petah tikva": "Петах-Тиква", "פתח תקווה": "Петах-Тиква",
    "ришон": "Ришон-ле-Цион", "rishon": "Ришон-ле-Цион", "ראשון לציון": "Ришон-ле-Цион",
    "рамла": "Рамла", "лод": "Лод", "ор-иегуда": "Ор-Иегуда",
}

def detect_city(text):
    """Определяет город из текста объявления."""
    text_lower = text.lower()
    for keyword, city in GUSH_DAN_CITIES.items():
        if keyword in text_lower:
            return city
    return "Тель-Авив"

def detect_district(city):
    """Определяет округ по городу."""
    center_cities = ["Петах-Тиква","Ришон-ле-Цион","Лод","Рамла"]
    if city in center_cities:
        return "center"
    return "tel_aviv"

def extract_price(text):
    """Извлекает цену из текста."""
    patterns = [
        r'(\d[\d\s]*)\s*[₪nis]',
        r'(\d[\d\s]*)\s*шек',
        r'(\d[\d\s]*)\s*шк',
        r'цена[:\s]+(\d[\d\s]*)',
        r'(\d{3,6})\s*в месяц',
    ]
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            price_str = match.group(1).replace(" ", "")
            try:
                price = int(price_str)
                if 1000 <= price <= 50000:
                    return price
            except:
                pass
    return 0

def extract_rooms(text):
    """Извлекает количество комнат."""
    patterns = [
        r'(\d[.,]?\d?)\s*комн',
        r'(\d[.,]?\d?)\s*חד',
        r'(\d[.,]?\d?)\s*room',
        r'(\d[.,]?\d?)-комнат',
    ]
    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            try:
                rooms = match.group(1).replace(",", ".")
                val = float(rooms)
                if 1 <= val <= 10:
                    return str(val).replace(".0", "")
            except:
                pass
    return "3"

def is_valid_listing(text):
    """Проверяет что пост является объявлением."""
    text_lower = text.lower()
    has_rent = any(kw in text_lower for kw in RENT_KEYWORDS)
    is_excluded = any(kw in text_lower for kw in EXCLUDE_KEYWORDS)
    is_long_enough = len(text) > 80
    return has_rent and not is_excluded and is_long_enough

def parse_group(group_name, max_posts=30):
    """Парсит посты из Facebook группы."""
    print(f"  Парсинг группы: {group_name}")
    added = 0
    try:
        for post in get_posts(group_name, pages=3, cookies="cookies.txt"):
            text = post.get("text", "") or ""
            if not is_valid_listing(text):
                continue

            city = detect_city(text)
            district = detect_district(city)
            price = extract_price(text)
            rooms = extract_rooms(text)

            # Создаём заголовок из первых слов
            title_raw = text[:80].strip().replace("\n", " ")
            title = f"🏢 {title_raw}..."

            listing = {
                "title": title,
                "description": text[:600],
                "property_type": "apartment",
                "city": city,
                "district": district,
                "neighborhood": "",
                "rooms": rooms,
                "floor": "1",
                "area_sqm": 0,
                "price": price,
                "deal_type": "rent",
                "parking": 0,
                "pool": False,
                "infrastructure": [],
                "contact": f"@{post.get('username', 'facebook')}",
                "photos": ["🏢"],
                "source": "facebook",
                "source_url": post.get("post_url", ""),
            }
            db.add_listing(listing)
            added += 1
            print(f"  ✅ {city} | {rooms} комн | {price}₪ | {title[:40]}")

    except Exception as e:
        print(f"  ❌ Ошибка {group_name}: {e}")
    return added

def run_parser(interval_minutes=30):
    """Запускает парсер по расписанию."""
    print("=" * 50)
    print("Facebook Parser для FlatFinderIL")
    print(f"Группы: {', '.join(GROUPS)}")
    print(f"Интервал: каждые {interval_minutes} минут")
    print("=" * 50)
    while True:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Запуск парсинга...")
        total = 0
        for group in GROUPS:
            total += parse_group(group)
        print(f"Итого добавлено: {total} объявлений")
        print(f"Следующий запуск через {interval_minutes} мин...")
        time.sleep(interval_minutes * 60)

if __name__ == "__main__":
    run_parser()
