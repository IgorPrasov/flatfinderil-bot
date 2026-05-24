"""
classifier.py — Классификатор объявлений FlatFinderIL

Функции:
  • extract_phones()     — извлечь израильские телефоны из текста → 05XXXXXXXX
  • classify_listing()   — пометить объявление как Agent/Private/Blacklist
  • report_phone()       — добавить жалобу (3 страйка → блэклист)
  • filter_for_tier()    — фильтрация выдачи по уровню подписки

База данных хранится в listings_db.json (через database.py).
"""

import re
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Optional

log = logging.getLogger("classifier")

# ─────────────────────────────────────────────────────────────────────────────
# 1. ИЗВЛЕЧЕНИЕ ТЕЛЕФОНОВ
# ─────────────────────────────────────────────────────────────────────────────

# Словарь цифр, написанных словами (иврит, русский, английский)
_WORD_DIGITS: dict[str, str] = {
    # English
    "zero":"0","one":"1","two":"2","three":"3","four":"4",
    "five":"5","six":"6","seven":"7","eight":"8","nine":"9",
    # Russian
    "ноль":"0","нуль":"0","один":"1","два":"2","три":"3","четыре":"4",
    "пять":"5","шесть":"6","семь":"7","восемь":"8","девять":"9",
    # Hebrew digits (written)
    "אפס":"0","אחת":"1","אחד":"1","שתיים":"2","שניים":"2","שלוש":"3",
    "ארבע":"4","חמש":"5","שש":"6","שבע":"7","שמונה":"8","תשע":"9",
}


def _normalize_word_digits(text: str) -> str:
    """Заменить цифры-слова на цифры-символы (лучший охват)."""
    pattern = re.compile(
        r'\b(' + '|'.join(map(re.escape, _WORD_DIGITS.keys())) + r')\b',
        re.IGNORECASE
    )
    def replace(m):
        return _WORD_DIGITS[m.group(0).lower()]
    return pattern.sub(replace, text)


def extract_phones(text: str) -> list[str]:
    """
    Извлечь израильские мобильные номера из текста и привести к формату 05XXXXXXXX.

    Поддерживает:
      • 050-123-4567, 050 123 4567, 0501234567
      • +972-50-123-4567, +972501234567
      • 972-50-1234567
      • Цифры, написанные словами (частично, через _normalize_word_digits)

    Возвращает список уникальных номеров в формате 05XXXXXXXX.
    """
    text = _normalize_word_digits(text)

    # Убираем форматирование — тире, точки, пробелы между цифрами
    # но сохраняем структуру текста
    MOBILE_PREFIXES = {
        '050','051','052','053','054','055','056','057','058','059',
        '070','071','072','073','074','075','076','077','078',
    }

    found = set()

    # ── Pattern A: international format  +972 or 972 prefix ───────────────────
    # Remove +972 or 972 (with optional - or space), then collect 9 local digits
    # Examples: +972-52-111-2222, +972521112222, 972-54-1234567, 972541234567
    intl_re = re.compile(r'(?:\+?972)[-\s]?(\d[\d\-\s]{6,11}\d)')
    for m in intl_re.finditer(text):
        raw = re.sub(r'[\-\s]', '', m.group(1))   # strip separators
        if len(raw) == 9:
            local = '0' + raw                      # 972-XX... → 0XX...
            if local[:3] in MOBILE_PREFIXES:
                found.add(local)

    # ── Pattern B: local format  0XX-XXXXXXX ──────────────────────────────────
    # Examples: 050-123-4567, 050 123 4567, 0501234567, 053-4567890
    local_re = re.compile(r'\b(0[5-9]\d)[\-\s]?(\d{3})[\-\s]?(\d{4})\b')
    for m in local_re.finditer(text):
        num = m.group(1) + m.group(2) + m.group(3)
        if num[:3] in MOBILE_PREFIXES:
            found.add(num)

    # ── Pattern C: 10-digit local without separators ───────────────────────────
    compact_re = re.compile(r'\b(0[5-9]\d{8})\b')
    for m in compact_re.finditer(text):
        num = m.group(1)
        if num[:3] in MOBILE_PREFIXES:
            found.add(num)

    return sorted(found)


# ─────────────────────────────────────────────────────────────────────────────
# 2. СТРУКТУРА ТАБЛИЦ В JSON-БД
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_classifier_tables(data: dict) -> dict:
    """Добавить таблицы классификатора если их нет."""
    for key, default in [
        ("phone_agents", {}),     # phone → {phone, added_date, post_count}
        ("phone_blacklist", {}),  # phone → {phone, reason, added_date}
        ("phone_reports", {}),    # phone → [{reporter_id, date, reason}]
        ("phone_post_counts", {}),# phone → [{date: "YYYY-MM-DD"}]  last 90 days
    ]:
        if key not in data:
            data[key] = default
    return data


# ─────────────────────────────────────────────────────────────────────────────
# 3. КЛАССИФИКАТОР
# ─────────────────────────────────────────────────────────────────────────────

AGENT_POST_THRESHOLD = 2          # >2 постов за 30 дней → Agent
BLACKLIST_STRIKES = 3             # 3 уникальных жалобы → Blacklist
DAYS_WINDOW = 30                  # окно для подсчёта активности (дней)


def classify_listing(phone: str, db_data: dict) -> str:
    """
    Определить тип объявления по номеру телефона.

    Возвращает:
      "blacklist"  — номер в чёрном списке (не сохранять)
      "agent"      — риелтор/агент (много постов или в таблице агентов)
      "private"    — частное лицо
    """
    db_data = _ensure_classifier_tables(db_data)

    # 1. Проверка блэклиста
    if phone in db_data["phone_blacklist"]:
        log.info(f"🚫 {phone} → BLACKLIST")
        return "blacklist"

    # 2. Проверка таблицы агентов
    if phone in db_data["phone_agents"]:
        log.info(f"🏢 {phone} → AGENT (in agents table)")
        return "agent"

    # 3. Подсчёт постов за последние 30 дней
    cutoff = (datetime.now() - timedelta(days=DAYS_WINDOW)).strftime("%Y-%m-%d")
    posts = db_data["phone_post_counts"].get(phone, [])
    recent = [p for p in posts if p.get("date", "") >= cutoff]
    count = len(recent)

    if count > AGENT_POST_THRESHOLD:
        # Автоматически добавляем в таблицу агентов
        db_data["phone_agents"][phone] = {
            "phone": phone,
            "added_date": datetime.now().strftime("%Y-%m-%d"),
            "post_count": count,
            "auto_detected": True,
        }
        log.info(f"🏢 {phone} → AGENT (auto: {count} posts in {DAYS_WINDOW}d)")
        return "agent"

    log.info(f"🏠 {phone} → PRIVATE ({count} posts)")
    return "private"


def record_phone_post(phone: str, db_data: dict) -> dict:
    """
    Зафиксировать новый пост с этим телефоном.
    Чистит записи старше 90 дней.
    """
    db_data = _ensure_classifier_tables(db_data)
    cutoff_90 = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

    posts = db_data["phone_post_counts"].get(phone, [])
    # Убираем записи старше 90 дней
    posts = [p for p in posts if p.get("date", "") >= cutoff_90]
    posts.append({"date": today})
    db_data["phone_post_counts"][phone] = posts
    return db_data


# ─────────────────────────────────────────────────────────────────────────────
# 4. БЛЭКЛИСТ И ЖАЛОБЫ (3 СТРАЙКА)
# ─────────────────────────────────────────────────────────────────────────────

def report_phone(phone: str, reporter_id: int, reason: str, db_data: dict) -> dict:
    """
    Добавить жалобу на номер телефона.
    После BLACKLIST_STRIKES (3) уникальных жалоб → автоматически в блэклист.

    Возвращает обновлённый db_data.
    """
    db_data = _ensure_classifier_tables(db_data)

    if phone not in db_data["phone_reports"]:
        db_data["phone_reports"][phone] = []

    reports = db_data["phone_reports"][phone]

    # Проверяем: этот пользователь уже жаловался?
    existing_reporters = {r["reporter_id"] for r in reports}
    if reporter_id in existing_reporters:
        log.info(f"ℹ️ {reporter_id} already reported {phone}")
        return db_data

    reports.append({
        "reporter_id": reporter_id,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "reason": reason,
    })
    db_data["phone_reports"][phone] = reports

    unique_reporters = len({r["reporter_id"] for r in reports})
    log.info(f"⚠️ Report #{unique_reporters} on {phone} by {reporter_id}: {reason}")

    # 3 страйка → блэклист
    if unique_reporters >= BLACKLIST_STRIKES:
        db_data["phone_blacklist"][phone] = {
            "phone": phone,
            "reason": f"auto: {unique_reporters} reports",
            "added_date": datetime.now().strftime("%Y-%m-%d"),
            "reports": reports,
        }
        log.warning(f"🚫 {phone} added to BLACKLIST ({unique_reporters} unique reports)")

    return db_data


def add_to_blacklist(phone: str, reason: str, db_data: dict) -> dict:
    """Добавить номер в блэклист вручную (администратор)."""
    db_data = _ensure_classifier_tables(db_data)
    db_data["phone_blacklist"][phone] = {
        "phone": phone,
        "reason": reason,
        "added_date": datetime.now().strftime("%Y-%m-%d"),
        "manual": True,
    }
    log.warning(f"🚫 {phone} manually added to blacklist: {reason}")
    return db_data


# ─────────────────────────────────────────────────────────────────────────────
# 5. KEYWORD-BASED SELLER TYPE CLASSIFIER (by listing text)
# ─────────────────────────────────────────────────────────────────────────────

# Keywords that strongly indicate a private owner
_PRIVATE_PATTERNS = re.compile(
    r'хозяин|хозяйка|хозяева|'
    r'собственник|собственница|'
    r'без\s+посредник|без\s+агент|без\s+комисси|'
    r'от\s+хозяин|сдаю\s+сам|сдаём\s+сами|сдает\s+хоз|'
    r'без\s+риелтор|без\s+риэлтор|'
    r'сдаю\s+напрямую|напрямую\s+от\s+владельц|'
    r'בעלים|ישירות\s+מ|מבעלים|ישיר\s+מהבעלים|'
    r'ללא\s+תיווך|בלי\s+תיווך|ללא\s+עמלה|בלי\s+עמלה|'
    r'ישירות\s+מבעל|private\s+owner|no\s+agent|no\s+commission|'
    r'directly\s+from\s+owner|owner\s+renting|owner\s+selling',
    re.IGNORECASE
)

# Keywords that strongly indicate a realtor / agency
_AGENT_PATTERNS = re.compile(
    r'агент\b|агентство|агенства|риелтор|риэлтор|брокер\b|'
    r'агент\s+по\s+недвижимости|комиссия\s+агента|'
    r'מתווך|תיווך|סוכן\s+נדל|משרד\s+תיווך|עמלת\s+תיווך|'
    r'\brealtor\b|\bagency\b|\bbroker\b|\bagent\s+fee\b|'
    r'estate\s+agent|real\s+estate\s+agent',
    re.IGNORECASE
)

# Known agent Telegram channels (contact handle → agent by default)
_KNOWN_AGENT_CHANNELS = {
    "@flamingorent", "@rentapartmentbatyam", "@ashdod_rent",
    "@izrailnedvizimosti", "@nagariyaapartments", "@rentbatyam",
    "@marianadlanru", "@happy_home_ashkelon", "@israel_rent",
    "@HaifaToRent", "@israel_apartments", "@isra_home_arenda",
    "@tlvapartments", "@haifa_arenda", "@israel_rent_haifa",
    "@sapirrent", "@brodsky_apartments", "@israelrealestate",
    "@Israel_arenda", "@snyat_kvartiruy", "@fishytlv",
    "@ambery_longrent_telaviv", "@aptfornew",
}


def classify_seller_type(listing: dict) -> str:
    """
    Keyword-based classification of a listing as 'agent' or 'private'.

    Priority:
      1. Known agent Telegram channel contact  → 'agent' (highest priority)
      2. Explicit agent keywords in text       → 'agent'
      3. Private keywords in title+description → 'private'
      4. Default                               → 'private' (assume private if unknown)

    Known agent channels take top priority because their text may mention
    "без посредника" / "without commission" when REPORTING about listings found,
    which would otherwise trigger the private keyword classifier incorrectly.

    Returns 'private' or 'agent'.
    """
    # 1. Known agent channels — highest priority
    contact = (listing.get("contact") or "").strip().lower()
    if contact in {c.lower() for c in _KNOWN_AGENT_CHANNELS}:
        return "agent"

    text = " ".join(filter(None, [
        listing.get("title", "") or "",
        listing.get("description", "") or "",
    ])).lower()

    # 2. Explicit agent keywords in text
    if _AGENT_PATTERNS.search(text):
        return "agent"

    # 3. Private owner signals
    if _PRIVATE_PATTERNS.search(text):
        return "private"

    # 4. Default: assume private (better UX — don't hide from private filter)
    return "private"


def add_to_agents(phone: str, db_data: dict) -> dict:
    """Добавить номер в таблицу агентов вручную."""
    db_data = _ensure_classifier_tables(db_data)
    db_data["phone_agents"][phone] = {
        "phone": phone,
        "added_date": datetime.now().strftime("%Y-%m-%d"),
        "manual": True,
    }
    return db_data


# ─────────────────────────────────────────────────────────────────────────────
# 5. ФИЛЬТРАЦИЯ ПО УРОВНЮ ПОДПИСКИ
# ─────────────────────────────────────────────────────────────────────────────

def filter_for_tier(listings: list[dict], is_premium: bool) -> list[dict]:
    """
    Фильтрация выдачи по уровню подписки:
      • Premium: только Private (частные лица) — чистая выдача без агентов
      • Free/Trial: все объявления (Private + Agent)

    Параметры:
      listings   — список объявлений из database.py
      is_premium — True если у пользователя Premium подписка

    Возвращает отфильтрованный список.

    Логика:
      Бесплатные пользователи видят всё → больше результатов,
      но среди них много агентских (шум).
      Premium видят только Private → меньше, но чище → ценность подписки.
    """
    if not is_premium:
        # Бесплатные: все объявления кроме блэклиста
        return [l for l in listings if l.get("poster_type") != "blacklist"]

    # Premium: только Private
    private = [l for l in listings if l.get("poster_type") == "private"]

    # Если нет Private — показываем всё (чтобы не было пустой выдачи)
    if not private:
        return [l for l in listings if l.get("poster_type") != "blacklist"]

    return private


# ─────────────────────────────────────────────────────────────────────────────
# 6. ИНТЕГРАЦИЯ С ПАРСЕРОМ (вызывается перед add_listing)
# ─────────────────────────────────────────────────────────────────────────────

def process_listing_phones(listing_data: dict, db_data: dict) -> tuple[dict, dict, bool]:
    """
    Полный pipeline перед сохранением объявления:

    1. Извлекаем телефоны из description + contact
    2. Для каждого телефона: record_phone_post → classify_listing
    3. Устанавливаем listing_data["poster_type"] и listing_data["phones"]
    4. Возвращаем (listing_data, db_data, should_save)
       should_save=False если все телефоны в блэклисте

    Использование в парсере:
        listing, db_data, ok = process_listing_phones(listing, db_data)
        if ok:
            db.add_listing(listing)
    """
    text = (listing_data.get("description", "") or "") + " " + (listing_data.get("contact", "") or "")
    phones = extract_phones(text)

    if not phones:
        # Нет телефона → считаем Private
        listing_data["phones"] = []
        listing_data["poster_type"] = "private"
        return listing_data, db_data, True

    listing_data["phones"] = phones
    poster_types = []

    for phone in phones:
        db_data = record_phone_post(phone, db_data)
        ptype = classify_listing(phone, db_data)
        poster_types.append(ptype)

    # Если хоть один телефон в блэклисте — не сохраняем
    if "blacklist" in poster_types:
        log.info(f"🚫 Listing skipped (blacklisted phone): {phones}")
        return listing_data, db_data, False

    # Если хоть один агент — весь пост помечаем как agent
    if "agent" in poster_types:
        listing_data["poster_type"] = "agent"
    else:
        listing_data["poster_type"] = "private"

    return listing_data, db_data, True


# ─────────────────────────────────────────────────────────────────────────────
# 7. БЫСТРЫЙ ТЕСТ
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    # Тест extract_phones
    test_cases = [
        ("Звоните: 050-123-4567", ["0501234567"]),
        ("Tel: +972-52-111-2222", ["0521112222"]),
        ("050 777 8899", ["0507778899"]),
        ("972541234567", ["0541234567"]),
        ("ноль пять два 111 22 33", []),  # частично слова — сложно
        ("0501234567 или 054-987-6543", ["0501234567", "0549876543"]),
        ("מספר: 053-4567890", ["0534567890"]),
    ]

    print("=== extract_phones tests ===")
    for text, expected in test_cases:
        result = extract_phones(text)
        status = "✅" if result == expected else "❌"
        print(f"{status} '{text}' → {result} (expected {expected})")

    # Тест classify + report
    print("\n=== classify + blacklist tests ===")
    db = {}
    phone = "0501234567"

    # Симулируем 3 поста за 30 дней
    for i in range(3):
        db = record_phone_post(phone, db)
    result = classify_listing(phone, db)
    print(f"After 3 posts: {result}")  # → agent

    # Симулируем 3 жалобы
    db2 = {}
    for uid in [101, 102, 103]:
        db2 = report_phone("0529999999", uid, "spam", db2)
    print(f"In blacklist: {'0529999999' in db2['phone_blacklist']}")  # → True

    # Тест filter_for_tier
    print("\n=== filter_for_tier tests ===")
    listings = [
        {"id": 1, "poster_type": "private", "title": "Private 1"},
        {"id": 2, "poster_type": "agent",   "title": "Agent 1"},
        {"id": 3, "poster_type": "private", "title": "Private 2"},
        {"id": 4, "poster_type": "blacklist","title": "Blacklisted"},
    ]
    free = filter_for_tier(listings, is_premium=False)
    premium = filter_for_tier(listings, is_premium=True)
    print(f"Free sees: {[l['title'] for l in free]}")     # All except blacklist
    print(f"Premium sees: {[l['title'] for l in premium]}")  # Only private
