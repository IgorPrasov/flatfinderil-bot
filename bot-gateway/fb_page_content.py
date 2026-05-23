"""
fb_page_content.py — Автопостинг контента на страницу FlatFinderIL в Facebook.

Три типа контента:
  1. Объявления из базы (топ по просмотрам / свежие)
  2. Новости о недвижимости и машканте (из news_fetcher.py)
  3. Образовательные посты / советы (ротация из библиотеки)

Запуск:
  python fb_page_content.py --mode listings --count 5
  python fb_page_content.py --mode news --count 3
  python fb_page_content.py --mode tips --count 2
  python fb_page_content.py --mode all
  python fb_page_content.py --dry-run --mode all
"""

import argparse
import logging
import os
import random
import sys
import time
from datetime import datetime

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ── Настройки ──────────────────────────────────────────────────────────────────
PAGE_ID   = "61573274147412"
PAGE_URL  = f"https://www.facebook.com/profile.php?id={PAGE_ID}"
BOT_LINK  = "https://t.me/FlatFinderIL_bot"
PAGE_LOAD_WAIT   = 7.0
PAUSE_BETWEEN    = 30.0   # секунд между постами


# ── Библиотека образовательных постов ─────────────────────────────────────────

TIPS = [
    # ── Аренда ────────────────────────────────────────────────────────────────
    """\
🏠 **Снимаете квартиру в Израиле? Знайте свои права!**

✅ Арендодатель обязан вернуть залог (פיקדון) в течение 60 дней после выезда
✅ Вы имеете право на работающее отопление и горячую воду
✅ Арендодатель не может войти без предупреждения за 24 часа
✅ При поломке оборудования — арендодатель обязан починить за разумный срок

📌 Всегда заключайте договор и фотографируйте квартиру при въезде.

🔍 Ищите квартиру без посредников → {bot}""",

    """\
💡 **5 вещей, которые нужно проверить перед подписанием договора аренды**

1️⃣ Состояние сантехники — включите воду везде
2️⃣ Электропроводка — проверьте все розетки
3️⃣ Горячая вода — подождите пока нагреется
4️⃣ Соседи — поговорите с ними до переезда
5️⃣ Парковка — убедитесь что место действительно ваше

💬 Сохраните этот пост — пригодится при просмотре!

🏠 База квартир без комиссии → {bot}""",

    """\
📋 **Что обязательно должно быть в договоре аренды (שכירות)?**

🔑 Точный адрес и описание квартиры
📅 Даты начала и конца аренды
💰 Сумма ежемесячной арендной платы
🔐 Размер залога и условия возврата
🔧 Кто платит за ремонт и что входит в аренду (ваад бает и др.)
📸 Протокол осмотра при въезде

⚠️ Никогда не платите без подписанного договора!

🔍 Найти квартиру → {bot}""",

    """\
🏘️ **Права арендатора в Израиле — что изменилось в 2024-2025**

📜 Закон о «справедливой аренде» (שכירות הוגנת) обязывает арендодателей:
• Предоставить квартиру в пригодном для проживания состоянии
• Не повышать аренду чаще раза в год без согласования
• Вернуть залог с процентами

📌 При нарушениях — обращайтесь в Суд по малым искам (בית משפט לתביעות קטנות)

🔍 Квартиры для аренды → {bot}""",

    # ── Машканта / покупка ─────────────────────────────────────────────────────
    """\
🏦 **Машканта (משכנתא) в Израиле — с чего начать?**

📊 Базовые факты:
• Максимальный кредит: 75% от стоимости для первой квартиры
• Минимальный первоначальный взнос: 25%
• Срок: до 30 лет
• Ставка: зависит от prime rate Банка Израиля

💡 Совет: сначала получите предварительное одобрение (אישור עקרוני) — это бесплатно и действует 30 дней.

🏠 Квартиры на продажу → {bot}""",

    """\
💰 **Сколько реально стоит купить квартиру в Израиле? Считаем все расходы**

🏠 Цена квартиры: X ₪
➕ Налог на покупку (מס רכישה): 0-10% в зависимости от цены
➕ Адвокат: 0.5-1.5% от стоимости
➕ Нотариус и оформление: ~3,000-5,000 ₪
➕ Оценщик (שמאי): ~2,000-4,000 ₪
➕ Брокер (если есть): 1-2% + НДС

📌 Итого: к цене квартиры добавьте ~5-8% на расходы.

🔍 Найти квартиру → {bot}""",

    """\
📉 **Prime rate и машканта — как это связано?**

🏦 Prime rate (ריבית הפריים) = ставка ЦБ Израиля + 1.5%
🔢 Сейчас prime ≈ 6% (ставка ЦБ 4.5%)

Треки машканты:
• Переменная (prime) — сейчас дороже, но снизится при снижении ставки
• Фиксированная (קבועה) — стабильность, но дороже в начале
• Смешанная — берут 1/3 на каждый трек

💡 Не берите более 40% дохода на выплату машканты!

🏠 Квартиры для покупки → {bot}""",

    """\
🔑 **Что такое «квартира с нулевым НДС» (דירה ב-0% מע"מ)?**

📜 По программе правительства Израиля:
• Молодые пары и те, кто впервые покупает — могут купить без НДС (17%)
• Экономия: до 200,000+ ₪ на квартиру стоимостью 1.5 млн

Условия:
✅ Нет в собственности другой квартиры
✅ Проект включён в программу
✅ Подаётся заявка в מיסוי מקרקעין

🔍 Новые проекты → {bot}""",

    # ── Районы / советы по городам ─────────────────────────────────────────────
    """\
📍 **Тель-Авив vs Гиватаим vs Рамат-Ган — где выгоднее снимать?**

🏙️ Тель-Авив центр: 4,500-7,000 ₪ / 2 комнаты
🏘️ Гиватаим: 3,800-5,500 ₪ / 2 комнаты (10 мин до ТА)
🏠 Рамат-Ган: 3,500-5,000 ₪ / 2 комнаты (отличная инфраструктура)

💡 Гиватаим и Рамат-Ган — лучший баланс цена/качество для работающих в ТА.

🔍 Сравнить квартиры → {bot}""",

    """\
🌊 **Хайфа — почему всё больше людей переезжают сюда?**

📊 Средняя аренда 3 комнаты:
• Хайфа: 3,000-4,500 ₪
• Тель-Авив: 5,500-8,000 ₪
• Разница: экономия 25,000-40,000 ₪ В ГОД

🚂 Поезд Хайфа → ТА: 55 минут
💼 Хайфа — центр хайтека (Intel, Google, Microsoft)
🏖️ Море, горы, Бахайские сады

📌 Многие работают удалённо и живут в Хайфе значительно дешевле!

🔍 Квартиры в Хайфе → {bot}""",

    """\
🏠 **Ваад бает (ועד בית) — что это и сколько платить?**

ועד בית = плата на обслуживание дома:
• Лифт, уборка, сад, охрана и т.д.
• Обычно: 100-400 ₪/мес в зависимости от дома
• При аренде: как правило платит арендатор
• При покупке: обязательный платёж собственника

❓ Размер ваад бает обязательно уточняйте ДО подписания договора.

🔍 Квартиры с указанием ваад бает → {bot}""",

    # ── Общие советы ──────────────────────────────────────────────────────────
    """\
🔍 **FlatFinderIL — ищем квартиру без лишних звонков**

Как работает наш бот:
✅ Объявления из Facebook-групп и Telegram-каналов
✅ Без посредников и дополнительных комиссий
✅ Фильтры: город, район, комнаты, цена, парковка, бассейн
✅ Оповещения о новых объявлениях по вашим параметрам
✅ Карта и инфраструктура рядом

📱 Попробуйте бесплатно → {bot}

#недвижимость #аренда #израиль #квартира""",

    """\
💡 **Как не попасть на мошенника при аренде квартиры?**

🚩 Красные флаги:
• Цена значительно ниже рыночной
• «Хозяин за границей» и просит перевод до показа
• Нет возможности лично осмотреть квартиру
• Требуют оплату только криптой или Western Union
• Торопят с решением без времени на раздумья

✅ Правило: НИКОГДА не платите залог до подписания договора и осмотра!

🏠 Проверенные объявления → {bot}""",

    """\
📊 **Рынок аренды Израиля 2025 — что происходит?**

📈 Тенденции:
• Средняя аренда в ТА выросла на 8-12% за 2 года
• Хайфа и Беэр-Шева — стабилизация после роста
• Дефицит: квартир с парковкой и бомбоубежищем (מרחב מוגן)
• Спрос: 3-4 комнаты для семей с детьми

💡 Совет: ищите квартиры добавленные свежо — они разбираются за 1-3 дня.

🔍 Свежие объявления каждый день → {bot}

#рынокнедвижимости #аренда #израиль""",

    # ── На иврите ──────────────────────────────────────────────────────────────
    """\
🏠 **5 דברים שחייבים לבדוק לפני חתימת חוזה שכירות**

1️⃣ מצב האינסטלציה — פתחו את כל הברזים
2️⃣ החשמל — בדקו את כל השקעים
3️⃣ מים חמים — המתינו שיתחמם
4️⃣ שכנים — דברו איתם לפני המעבר
5️⃣ חניה — ודאו שהמקום אכן שלכם

💬 שמרו את הפוסט הזה — יהיה שימושי בסיור הדירה!

🏠 דירות ללא עמלה → {bot}""",

    """\
💰 **כמה עולה משכנתא בישראל ב-2025?**

📊 לדירה של 1,500,000 ₪:
• מקדמה מינימלית (25%): 375,000 ₪
• הלוואה: 1,125,000 ₪
• החזר חודשי ל-25 שנה: ~6,500-7,500 ₪/חודש

💡 טיפ: קבלו אישור עקרוני מהבנק לפני שמתחילים לחפש — זה בחינם ומזרז את התהליך.

🔍 דירות למכירה → {bot}

#משכנתא #נדלן #ישראל""",
]


# ── Функция публикации на страницу ────────────────────────────────────────────

def post_to_page(page, message: str, dry_run: bool = False) -> bool:
    """Публикует message на Facebook-странице через Playwright."""
    from playwright.sync_api import TimeoutError as PWTimeout

    log.info(f"\n📄 Постинг на страницу FlatFinderIL")
    log.info(f"    {PAGE_URL}")

    try:
        page.goto(PAGE_URL, wait_until="domcontentloaded", timeout=30_000)
        time.sleep(PAGE_LOAD_WAIT)
    except PWTimeout:
        log.warning("   ⏳ Таймаут загрузки страницы")
        return False
    except Exception as e:
        log.error(f"   ❌ Ошибка навигации: {e}")
        return False

    if "login" in page.url or "checkpoint" in page.url:
        log.warning("   🔐 Перенаправление на login — cookies устарели!")
        return False

    if dry_run:
        log.info(f"   🔍 [dry-run] Текст:\n{message[:200]}...")
        return True

    # Клик на поле создания поста
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
                "На что вы хотите обратить внимание",
            ];
            // Try role="button" first (create post area)
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
            // Fallback: click contenteditable that isn't a comment box
            const editors = [...document.querySelectorAll('[contenteditable="true"]')];
            if (editors.length > 0) {
                editors[0].click();
                return true;
            }
            return false;
        }
        """)
    except Exception as e:
        log.debug(f"JS click error: {e}")

    if not clicked:
        log.warning("   ⚠️  Поле создания поста не найдено — попробуем альтернативный селектор")
        try:
            page.click('[data-pagelet="ProfileComposer"] [role="button"]', timeout=5000)
            clicked = True
        except Exception:
            pass

    if not clicked:
        log.warning("   ❌ Не удалось найти поле для поста")
        return False

    time.sleep(2.0)

    # Вводим текст
    TEXTBOX_SELECTORS = [
        "[role='dialog'] [contenteditable='true'][role='textbox']",
        "[role='dialog'] [contenteditable='true']",
        "[contenteditable='true'][role='textbox']",
        "[contenteditable='true'][data-lexical-editor='true']",
    ]

    tb = None
    for sel in TEXTBOX_SELECTORS:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=3000):
                tb = el
                break
        except Exception:
            continue

    if tb is None:
        log.warning("   ❌ Текстовое поле не найдено")
        return False

    try:
        tb.click()
        time.sleep(0.5)
        # Вставляем через JavaScript (Lexical editor)
        injected = page.evaluate("""
        (text) => {
            const editors = [...document.querySelectorAll('[contenteditable="true"]')];
            let target = null;
            for (const ed of editors) {
                if (ed.getAttribute('role') === 'textbox' || ed.dataset.lexicalEditor) {
                    target = ed;
                    break;
                }
            }
            if (!target && editors.length > 0) target = editors[0];
            if (!target) return false;
            target.focus();
            const lines = text.split('\\n');
            for (let i = 0; i < lines.length; i++) {
                const line = lines[i];
                if (line) {
                    document.execCommand('insertText', false, line);
                }
                if (i < lines.length - 1) {
                    document.execCommand('insertParagraph', false);
                }
            }
            return true;
        }
        """, message)

        if not injected:
            tb.type(message, delay=8)

        time.sleep(1.5)

        # Нажимаем Опубликовать
        posted = page.evaluate("""
        () => {
            const LABELS = ["Опубликовать", "Post", "פרסם", "Публикувати"];
            const buttons = [...document.querySelectorAll('[role="button"]')];
            for (const btn of buttons) {
                const t = (btn.textContent || '').trim();
                if (LABELS.includes(t)) {
                    btn.click();
                    return true;
                }
            }
            // Fallback: aria-label
            for (const btn of buttons) {
                const label = (btn.getAttribute("aria-label") || "").toLowerCase();
                if (label.includes("post") || label.includes("publish") || label.includes("פרסם")) {
                    btn.click();
                    return true;
                }
            }
            return false;
        }
        """)

        if posted:
            log.info("   ✅ Пост опубликован!")
            time.sleep(3.0)
            return True
        else:
            log.warning("   ⚠️  Кнопка «Опубликовать» не найдена")
            return False

    except Exception as e:
        log.error(f"   ❌ Ошибка при вводе текста: {e}")
        return False


# ── Генераторы контента ────────────────────────────────────────────────────────

def format_listing_post(listing: dict) -> str:
    """Форматирует объявление из базы в пост для Facebook-страницы."""
    title = listing.get("title", "").strip()
    city  = listing.get("city", "")
    hood  = listing.get("neighborhood", "")
    rooms = listing.get("rooms", "")
    floor = listing.get("floor", "")
    area  = listing.get("area_sqm", "")
    price = listing.get("price", 0)
    deal  = listing.get("deal_type", "rent")
    desc  = (listing.get("description", "") or "").strip()
    pool  = listing.get("pool", False)
    parking = listing.get("parking", 0)

    deal_str = {"rent": "🔑 Аренда", "buy": "🏠 Продажа", "sublet": "🔄 Субаренда"}.get(deal, "🔑 Аренда")
    price_str = ""
    if price:
        if deal in ("rent", "sublet"):
            price_str = f"💰 {price:,} ₪/мес".replace(",", " ")
        else:
            price_str = f"💰 {price:,} ₪".replace(",", " ") if price < 1_000_000 else f"💰 {price/1_000_000:.1f} млн ₪"

    location = city
    if hood:
        location += f", {hood}"

    features = []
    if rooms:
        features.append(f"🚪 {rooms} комн.")
    if floor:
        features.append(f"🏗 {floor} эт.")
    if area:
        features.append(f"📐 {area} кв.м")
    if pool:
        features.append("🏊 Бассейн")
    if parking:
        features.append("🚗 Парковка")

    # Обрезаем описание до 300 символов
    short_desc = ""
    if desc:
        clean = desc.replace("\n", " ").strip()
        # Убираем технические Facebook заголовки (имя автора, дата)
        lines = desc.split("\n")
        content_lines = [l for l in lines if len(l) > 20 and not any(
            x in l for x in ["ч.", "д.", "нед.", "мес.", "Показать", "перевод"]
        )]
        clean = " ".join(content_lines).strip()
        short_desc = clean[:280] + ("..." if len(clean) > 280 else "")

    parts = [
        f"🏠 НОВОЕ ОБЪЯВЛЕНИЕ | FlatFinderIL\n",
        f"📍 {location}",
    ]
    if price_str:
        parts.append(price_str)
    parts.append(f"{deal_str}  |  {' | '.join(features)}")
    if short_desc:
        parts.append(f"\n📝 {short_desc}")
    parts.append(f"\n🔍 Найти ещё квартир без комиссии → {BOT_LINK}")
    parts.append("\n#недвижимость #аренда #израиль #квартира #flatfinderil")

    return "\n".join(parts)


def format_news_post(item: dict) -> str:
    """Форматирует новость в пост для Facebook-страницы."""
    title   = item.get("title", "").strip()
    summary = (item.get("summary") or item.get("description", "")).strip()
    link    = item.get("link", "")
    cat     = item.get("category", "news")
    source  = item.get("source_name", "")

    cat_emoji = {
        "mortgage": "🏦",
        "program":  "🏛",
        "project":  "🏗",
        "news":     "📰",
    }.get(cat, "📰")

    cat_label = {
        "mortgage": "МАШКАНТА И СТАВКИ",
        "program":  "ГОСУДАРСТВЕННЫЕ ПРОГРАММЫ",
        "project":  "НОВЫЕ ПРОЕКТЫ",
        "news":     "РЫНОК НЕДВИЖИМОСТИ",
    }.get(cat, "НОВОСТИ НЕДВИЖИМОСТИ")

    # Обрезаем summary
    clean_summary = ""
    if summary:
        import re
        clean_summary = re.sub(r"<[^>]+>", "", summary).strip()
        clean_summary = clean_summary[:350] + ("..." if len(clean_summary) > 350 else "")

    parts = [f"{cat_emoji} {cat_label} | FlatFinderIL\n"]
    parts.append(f"📌 {title}")
    if clean_summary:
        parts.append(f"\n{clean_summary}")
    if source:
        parts.append(f"\n🗞 Источник: {source}")
    if link:
        parts.append(f"🔗 Читать: {link}")
    parts.append(f"\n💬 Вопросы о недвижимости? Наш бот поможет → {BOT_LINK}")
    parts.append("\n#недвижимость #израиль #рынокнедвижимости #машканта #flatfinderil")

    return "\n".join(parts)


def get_tip_post() -> str:
    """Возвращает случайный образовательный пост."""
    tip = random.choice(TIPS)
    return tip.format(bot=BOT_LINK)


# ── Основная логика ────────────────────────────────────────────────────────────

def run_listings_posts(page, count: int = 5, dry_run: bool = False):
    """Постит N объявлений из базы (топ по просмотрам / свежие)."""
    import database as db

    log.info(f"\n📋 Загружаем объявления из базы...")
    all_listings = db.get_all_listings(limit=500)

    # Фильтруем: только активные, из Telegram/Facebook, с описанием
    candidates = [
        l for l in all_listings
        if l.get("active", True)
        and l.get("source") in ("telegram", "facebook")
        and l.get("description")
        and len(l.get("description", "")) > 50
        and l.get("price", 0) > 0
    ]

    # Сортируем: сначала с фото, потом по дате
    candidates.sort(key=lambda l: (
        -len([p for p in l.get("photos", []) if len(p) > 20]),
        -(l.get("views") or 0),
    ))

    # Берём первые count
    to_post = candidates[:count]
    log.info(f"   Будет опубликовано {len(to_post)} объявлений")

    posted = 0
    for listing in to_post:
        message = format_listing_post(listing)
        ok = post_to_page(page, message, dry_run=dry_run)
        if ok:
            posted += 1
        if not dry_run:
            time.sleep(PAUSE_BETWEEN)

    log.info(f"\n✅ Опубликовано объявлений: {posted}/{len(to_post)}")
    return posted


def run_news_posts(page, count: int = 3, dry_run: bool = False):
    """Постит N новостей о недвижимости и машканте."""
    from news_fetcher import get_news

    log.info(f"\n📰 Загружаем новости...")
    news = get_news(limit=30)
    items = news.get("items", [])

    # Приоритет: машканта > программы > остальное
    def priority(item):
        cat = item.get("category", "news")
        return {"mortgage": 0, "program": 1, "project": 2, "news": 3}.get(cat, 4)

    items.sort(key=priority)
    to_post = items[:count]

    log.info(f"   Будет опубликовано {len(to_post)} новостей")

    posted = 0
    for item in to_post:
        message = format_news_post(item)
        ok = post_to_page(page, message, dry_run=dry_run)
        if ok:
            posted += 1
        if not dry_run:
            time.sleep(PAUSE_BETWEEN)

    log.info(f"\n✅ Опубликовано новостей: {posted}/{len(to_post)}")
    return posted


def run_tips_posts(page, count: int = 2, dry_run: bool = False):
    """Постит N образовательных постов."""
    log.info(f"\n💡 Публикуем образовательные посты...")
    posted = 0
    for _ in range(count):
        message = get_tip_post()
        ok = post_to_page(page, message, dry_run=dry_run)
        if ok:
            posted += 1
        if not dry_run:
            time.sleep(PAUSE_BETWEEN)
    log.info(f"\n✅ Опубликовано советов: {posted}/{count}")
    return posted


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Постинг контента на страницу FlatFinderIL в Facebook")
    parser.add_argument("--mode", choices=["listings", "news", "tips", "all"], default="all")
    parser.add_argument("--count", type=int, default=None, help="Количество постов каждого типа")
    parser.add_argument("--dry-run", action="store_true", help="Не постить, только показать текст")
    parser.add_argument("--headless", action="store_true", default=False)
    args = parser.parse_args()

    counts = {
        "listings": args.count or 5,
        "news":     args.count or 3,
        "tips":     args.count or 2,
    }

    # Загружаем Playwright и cookies
    from playwright.sync_api import sync_playwright
    import json

    COOKIES_FILE = os.path.join(os.path.dirname(__file__), "cookies.txt")
    if not os.path.exists(COOKIES_FILE):
        log.error(f"❌ Файл cookies не найден: {COOKIES_FILE}")
        log.error("   Запустите python get_cookies.py для авторизации")
        sys.exit(1)

    with open(COOKIES_FILE) as f:
        raw = f.read().strip()
    try:
        cookies_data = json.loads(raw)
        if isinstance(cookies_data, dict):
            cookies_data = cookies_data.get("cookies", [])
    except Exception:
        log.error("❌ Не удалось прочитать cookies.txt")
        sys.exit(1)

    log.info(f"🍪 Загружено {len(cookies_data)} cookies")
    log.info(f"📄 Страница: {PAGE_URL}")
    log.info(f"🔧 Режим: {args.mode} | dry-run: {args.dry_run}")

    results = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=args.headless)
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
            locale="ru-RU",
        )
        ctx.add_cookies(cookies_data)
        pg = ctx.new_page()

        if args.mode in ("listings", "all"):
            results["listings"] = run_listings_posts(pg, counts["listings"], args.dry_run)
            if not args.dry_run and args.mode == "all":
                time.sleep(10)

        if args.mode in ("news", "all"):
            results["news"] = run_news_posts(pg, counts["news"], args.dry_run)
            if not args.dry_run and args.mode == "all":
                time.sleep(10)

        if args.mode in ("tips", "all"):
            results["tips"] = run_tips_posts(pg, counts["tips"], args.dry_run)

        browser.close()

    log.info("\n" + "="*50)
    log.info("📊 ИТОГИ:")
    for k, v in results.items():
        log.info(f"   {k}: {v} постов")
    log.info("="*50)


if __name__ == "__main__":
    main()
