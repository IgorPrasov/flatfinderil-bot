"""
Generate FlatFinderIL Bot Map PDF — Russian, Arial Unicode font.
Call generate(output_path) to save to file.
"""
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_PATHS = [
    ("/Library/Fonts/Arial Unicode.ttf", "ArialUni"),
    ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", "ArialUni"),
]
BOLD_PATHS = [
    ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "ArialUni-Bold"),
    ("/Library/Fonts/Arial Bold.ttf", "ArialUni-Bold"),
]

import os

def _reg():
    reg = False
    for path, name in FONT_PATHS:
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont(name, path))
            reg = True
            break
    for path, name in BOLD_PATHS:
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont(name, path))
            break
    return reg

_FONT      = "ArialUni"
_FONT_BOLD = "ArialUni-Bold"

BLUE      = colors.HexColor("#2AABEE")
DARK      = colors.HexColor("#1a1a2e")
MID       = colors.HexColor("#2d3561")
LIGHT_BG  = colors.HexColor("#f0f8ff")
GRAY      = colors.HexColor("#666666")
WHITE     = colors.white
TEAL      = colors.HexColor("#009688")
PURPLE    = colors.HexColor("#9c27b0")
GREEN     = colors.HexColor("#27ae60")
ORANGE    = colors.HexColor("#e67e22")


def S(name, **kw):
    return ParagraphStyle(name, **kw)


def generate(output_path=None):
    _reg()
    buf = io.BytesIO()
    target = output_path or buf
    doc = SimpleDocTemplate(
        target, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm
    )
    W = A4[0] - 3*cm

    h1 = S("H1", fontSize=22, textColor=WHITE, spaceAfter=4, alignment=TA_CENTER, fontName=_FONT_BOLD)
    h2 = S("H2", fontSize=14, textColor=WHITE, spaceAfter=2, fontName=_FONT_BOLD)
    h3 = S("H3", fontSize=11, textColor=DARK,  spaceAfter=2, fontName=_FONT_BOLD, spaceBefore=6)
    body= S("Body", fontSize=9, textColor=DARK, spaceAfter=3, leading=13, fontName=_FONT)
    small=S("Small", fontSize=8, textColor=GRAY, spaceAfter=2, leading=11, fontName=_FONT)
    blt  =S("Blt",   fontSize=9, textColor=DARK, spaceAfter=2, leading=12, leftIndent=12, fontName=_FONT)

    story = []

    # ── ОБЛОЖКА ────────────────────────────────────────────────────────────
    cover = Table([
        [Paragraph("FlatFinderIL Bot", h1)],
        [Paragraph("Полная карта функций и архитектуры", S("s1", fontSize=13,
            textColor=colors.HexColor("#cce8ff"), alignment=TA_CENTER, fontName=_FONT))],
        [Paragraph("Версия 1.0  ·  Апрель 2026", S("s2", fontSize=10,
            textColor=colors.HexColor("#aaccee"), alignment=TA_CENTER, fontName=_FONT))],
    ], colWidths=[W])
    cover.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1), DARK),
        ("TOPPADDING",(0,0),(-1,-1), 18), ("BOTTOMPADDING",(0,0),(-1,-1), 18),
        ("LEFTPADDING",(0,0),(-1,-1), 20), ("RIGHTPADDING",(0,0),(-1,-1), 20),
    ]))
    story += [cover, Spacer(1, 0.4*cm)]

    # ── Статистика ─────────────────────────────────────────────────────────
    def stat(lbl, val, bg):
        t = Table([
            [Paragraph(val, S("sv", fontSize=13, fontName=_FONT_BOLD, textColor=WHITE, alignment=TA_CENTER))],
            [Paragraph(lbl, S("sl", fontSize=8,  fontName=_FONT, textColor=colors.HexColor("#ccddee"), alignment=TA_CENTER))],
        ], colWidths=[W/5 - 0.3*cm])
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1), bg),
                               ("TOPPADDING",(0,0),(-1,-1), 8), ("BOTTOMPADDING",(0,0),(-1,-1), 8)]))
        return t

    stats = Table([[
        stat("Шагов поиска", "10",  MID),
        stat("Городов",      "23",  TEAL),
        stat("Тарифов",      "4",   ORANGE),
        stat("Языков",       "3",   PURPLE),
        stat("Функций",      "20+", GREEN),
    ]], colWidths=[W/5]*5)
    stats.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),3),("RIGHTPADDING",(0,0),(-1,-1),3)]))
    story += [stats, Spacer(1, 0.4*cm)]

    # ── Хелперы ────────────────────────────────────────────────────────────
    def sec(title, color=BLUE):
        t = Table([[Paragraph(title, h2)]], colWidths=[W])
        t.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,-1), color),
            ("TOPPADDING",(0,0),(-1,-1), 7), ("BOTTOMPADDING",(0,0),(-1,-1), 7),
            ("LEFTPADDING",(0,0),(-1,-1), 12),
        ]))
        return t

    def tbl(rows, widths, header=None, alt=True):
        data = []
        if header:
            data.append([Paragraph(h, S("th", fontSize=9, fontName=_FONT_BOLD, textColor=WHITE)) for h in header])
        for row in rows:
            data.append([Paragraph(str(c), body) if isinstance(c, str) else c for c in row])
        t = Table(data, colWidths=widths)
        st = [("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#dddddd")),
              ("TOPPADDING",(0,0),(-1,-1),5), ("BOTTOMPADDING",(0,0),(-1,-1),5),
              ("LEFTPADDING",(0,0),(-1,-1),7), ("VALIGN",(0,0),(-1,-1),"TOP")]
        if header:
            st += [("BACKGROUND",(0,0),(-1,0), MID), ("TEXTCOLOR",(0,0),(-1,0), WHITE)]
        if alt:
            for i in range(1 if header else 0, len(data), 2):
                st.append(("BACKGROUND",(0,i),(-1,i), LIGHT_BG))
        t.setStyle(TableStyle(st))
        return t

    def buls(items):
        return [Paragraph(f"• {i}", blt) for i in items]

    # ── 1. КОМАНДЫ ─────────────────────────────────────────────────────────
    story += [sec("1. Команды бота"), Spacer(1, 0.2*cm)]
    story.append(tbl([
        ["/start",    "Главное меню, приветствие, выбор языка"],
        ["/search",   "Начать поиск недвижимости (10-шаговый фильтр)"],
        ["/add",      "Добавить объявление (18+ шагов)"],
        ["/listings", "Мои объявления — личный кабинет"],
        ["/cabinet",  "Панель агента"],
        ["/refer",    "Реферальная программа — поделиться ссылкой"],
        ["/help",     "Помощь и список команд"],
        ["/testemail","(Админ) Отправить тестовый email-отчёт"],
        ["/testpay",  "(Админ) Симуляция успешного платежа"],
    ], [3.5*cm, W-3.5*cm], header=["Команда", "Описание"]))
    story.append(Spacer(1, 0.3*cm))

    # ── 2. ПОИСК ────────────────────────────────────────────────────────────
    story += [sec("2. Поток поиска недвижимости (10 шагов)", MID), Spacer(1, 0.2*cm)]
    story.append(tbl([
        ["1",  "Тип сделки",       "Купить / Снять / Субаренда"],
        ["2",  "Тип объекта",      "Квартира, дом, вилла, пентхаус, студия, дуплекс (мульти-выбор)"],
        ["3",  "Район",            "Тель-Авив, Иерусалим, Хайфа, Шарон, Центр, Юг / Весь Израиль"],
        ["4",  "Город",            "23 города (мульти-выбор) / Любой город"],
        ["5",  "Комнат (мин.)",    "1 / 1.5 / 2 / 2.5 / 3 / 3.5 / 4 / 4.5 / 5 / 5+"],
        ["6",  "Комнат (макс.)",   "Тот же диапазон / Без ограничений"],
        ["7",  "Цена (мин.)",      "Аренда: 0–10 000 ₪/мес | Покупка: 0–5 млн ₪"],
        ["8",  "Цена (макс.)",     "Аренда: до 15 000+ ₪/мес | Покупка: до 10 млн+ ₪"],
        ["9",  "Парковка",         "Нет / 1 / 2 / 3+ / Любая"],
        ["10", "Бассейн",          "Да / Любой (только для домов и вилл)"],
    ], [1*cm, 3.5*cm, W-4.5*cm], header=["№", "Шаг", "Варианты"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph("Дополнительные фильтры:", h3))
    story += buls([
        "Убежище (Мамад / Миклат / Нет / Любое)",
        "Лифт (Да / Любой)",
        "Инфраструктура: Детсад, Школа, ТЦ, Парк, Спортзал, Больница, Пляж, Транспорт, Ресторан, Синагога, Бассейн",
        "Только с фото",
    ])
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph("Действия в результатах:", h3))
    story += buls([
        "В избранное  |  Контакты продавца  |  Google Maps",
        "Запросить просмотр  |  Оставить отзыв  |  Я арендовал / купил",
        "Подписаться на поиск  |  Новый поиск  |  Главное меню",
    ])
    story.append(Spacer(1, 0.3*cm))

    # ── 3. ДОБАВЛЕНИЕ ОБЪЯВЛЕНИЯ ────────────────────────────────────────────
    story += [sec("3. Добавление объявления (18+ шагов)", TEAL), Spacer(1, 0.2*cm)]
    story.append(tbl([
        ["1–2",  "Тип продавца + Тип сделки", "Частное лицо / Агент  →  Купить / Снять"],
        ["3–5",  "Объект + Район + Город",    "Тип недвижимости, район из 6, город из 23"],
        ["6",    "Адрес / Район",             "Текстовый ввод"],
        ["7–9",  "Комнаты + Этаж + Площадь", "Комнат: 1–5+, Этаж: подвал/1–21+/пентхаус, м²"],
        ["10",   "Цена (₪)",                 "Числовой ввод"],
        ["11–14","Удобства",                 "Парковка, Бассейн, Убежище, Лифт"],
        ["15",   "Инфраструктура",           "Мульти-выбор (11 вариантов)"],
        ["16",   "Описание",                 "Произвольный текст"],
        ["17–18","Владелец + Телефон",       "Имя, номер телефона"],
        ["19",   "Способ связи",             "Telegram / WhatsApp / Телефон / Email"],
        ["20",   "Фото",                     "Загрузка нескольких фото (опционально)"],
        ["21",   "Публикация",               "Предпросмотр  →  Опубликовать / Отменить"],
    ], [1.5*cm, 3.5*cm, W-5*cm], header=["Шаг", "Поле", "Детали"]))
    story.append(Spacer(1, 0.3*cm))

    # ── 4. ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ ────────────────────────────────────────────
    story += [sec("4. Дополнительные функции", ORANGE), Spacer(1, 0.2*cm)]
    half = (W - 0.3*cm) / 2

    def mini(title, items, bg=LIGHT_BG):
        rows = [[Paragraph(title, S("mh", fontSize=10, fontName=_FONT_BOLD, textColor=WHITE))]]
        for it in items:
            rows.append([Paragraph(f"• {it}", small)])
        t = Table(rows, colWidths=[half])
        t.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0), MID), ("BACKGROUND",(0,1),(-1,-1), bg),
            ("TOPPADDING",(0,0),(-1,-1),5), ("BOTTOMPADDING",(0,0),(-1,-1),4),
            ("LEFTPADDING",(0,0),(-1,-1),8), ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#cccccc")),
        ]))
        return t

    r1 = Table([[
        mini("Коммерческая недвижимость", [
            "5-шаговый поиск (Тип → Город → Цена)",
            "Типы: Офис, Ритейл, Склад, Ресторан, Студия, Парковка",
            "Аренда от 3 000 ₪ / Покупка от 500 000 ₪",
        ]),
        mini("Маркетплейс услуг", [
            "Переезд / Упаковка / Уборка",
            "Поиск по региону: Север / Центр / Юг",
            "Добавление своей услуги (9 шагов)",
        ]),
    ]], colWidths=[half, half])
    r1.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),
                             ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0)]))
    r2 = Table([[
        mini("CRM контакты", [
            "Типы: Агенты, Грузчики, Упаковщики, Уборщики",
            "Добавление: имя, телефон, регион",
            "Статусы: Новый / В работе / Готово / Отменено",
        ]),
        mini("Избранное", [
            "Сохранение объявлений",
            "Уведомления о снижении цены",
            "Быстрый доступ из меню",
        ]),
    ]], colWidths=[half, half])
    r2.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),
                             ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0)]))
    story += [r1, Spacer(1, 0.25*cm), r2, Spacer(1, 0.3*cm)]

    # ── 5. ПОДПИСКИ ──────────────────────────────────────────────────────────
    story += [sec("5. Подписки и монетизация", GREEN), Spacer(1, 0.2*cm)]
    trial = Table([[
        Paragraph("Тестовый период", S("tp", fontSize=11, fontName=_FONT_BOLD, textColor=WHITE)),
        Paragraph("Бесплатный доступ ко всем функциям до 15 мая 2026",
                  S("td", fontSize=10, fontName=_FONT, textColor=WHITE)),
    ]], colWidths=[5*cm, W-5*cm])
    trial.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1), GREEN),
        ("TOPPADDING",(0,0),(-1,-1),10), ("BOTTOMPADDING",(0,0),(-1,-1),10),
        ("LEFTPADDING",(0,0),(-1,-1),12),
    ]))
    story += [trial, Spacer(1, 0.2*cm)]
    story.append(tbl([
        ["Неделя",        "19.90 ₪",  "7 дней",  "Безлимитный поиск + размещение объявлений"],
        ["2 недели",      "29.90 ₪",  "14 дней", "Безлимитный поиск + размещение объявлений"],
        ["Месяц",         "39.90 ₪",  "30 дней", "Безлимитный поиск + размещение объявлений"],
        ["Поиск-алерты",  "39.90 ₪",  "30 дней", "Уведомления о новых объявлениях по фильтрам"],
    ], [3*cm, 2.5*cm, 2.5*cm, W-8*cm], header=["Тариф", "Цена", "Срок", "Включено"]))
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph("После окончания триала (бесплатный уровень):", h3))
    story += buls([
        "Ограничение: 3 поиска в сессию",
        "Нельзя добавлять объявления",
        "Просмотр публичных объявлений доступен",
        "Реферальный бонус: +7 дней за каждого приведённого пользователя",
        "Бонус за закрытие сделки: +3 дня",
    ])
    story.append(Spacer(1, 0.3*cm))

    # ── 6. ПЛАТЕЖИ ──────────────────────────────────────────────────────────
    story += [sec("6. Платёжная система", ORANGE), Spacer(1, 0.2*cm)]
    story.append(tbl([
        ["1", "Пользователь выбирает тариф",     "Кнопки в меню подписки"],
        ["2", "Бот отправляет инвойс",           "Telegram sendInvoice (ILS)"],
        ["3", "Пользователь вводит карту",       "Форма платёжного провайдера"],
        ["4", "Telegram → pre_checkout",         "Бот проверяет payload, отвечает ok=True"],
        ["5", "Провайдер списывает деньги",      "Smart Glocal LIVE (ожидание верификации)"],
        ["6", "Бот получает successful_payment", "Активирует подписку в БД"],
        ["7", "Квитанция на email",              "HTML-письмо через Resend API"],
    ], [0.8*cm, 5*cm, W-5.8*cm], header=["№", "Шаг", "Детали"]))
    story.append(Spacer(1, 0.15*cm))
    story.append(tbl([
        ["Smart Glocal TEST", "Банковские карты (ILS)", "Подключён",              "Тест-карты не работают в форме"],
        ["Smart Glocal LIVE", "Банковские карты (ILS)", "Ожидание верификации",   "~5 рабочих дней"],
        ["CryptoPay",         "USDT / TON / BTC / ETH", "Готов (нужен токен)",    "Polling через @CryptoBot API"],
        ["PayPal",            "Фиат / карты",           "Не подключён",           "Требует отдельной разработки"],
    ], [3.5*cm, 3.5*cm, 3.5*cm, W-10.5*cm], header=["Провайдер", "Тип", "Статус", "Примечание"]))
    story.append(Spacer(1, 0.3*cm))

    # ── 7. УВЕДОМЛЕНИЯ ──────────────────────────────────────────────────────
    story += [sec("7. Уведомления (фоновые задачи)", PURPLE), Spacer(1, 0.2*cm)]
    story.append(tbl([
        ["Новые объявления по фильтрам", "Каждые 30 мин", "Уведомляет подписчиков о совпадениях"],
        ["Снижение цены в избранном",   "Каждый час",    "Отслеживает цены, уведомляет о снижении"],
        ["Напоминание о старых объявл.","Раз в день",    "Объявления 30+ дней — напомнить закрыть сделку"],
        ["Еженедельный email-отчёт",    "Воскресенье",   "Отчёт агентам: просмотры, запросы, рейтинг"],
        ["CryptoPay опрос",             "Каждые 60 сек", "Проверка оплаченных крипто-инвойсов"],
    ], [4.5*cm, 3*cm, W-7.5*cm], header=["Тип", "Период", "Описание"]))
    story.append(Spacer(1, 0.3*cm))

    # ── 8. МУЛЬТИЯЗЫЧНОСТЬ ──────────────────────────────────────────────────
    story += [sec("8. Мультиязычность и города", TEAL), Spacer(1, 0.2*cm)]
    lang_t = Table([
        [Paragraph("Русский", body), Paragraph("English", body), Paragraph("עברית (RTL)", body)],
        [Paragraph("Все кнопки, сообщения,\nуведомления", small),
         Paragraph("All buttons, messages,\nnotifications", small),
         Paragraph("כל הכפתורים, הודעות\n(right-to-left)", small)],
    ], colWidths=[W/3]*3)
    lang_t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0), MID), ("TEXTCOLOR",(0,0),(-1,0), WHITE),
        ("BACKGROUND",(0,1),(-1,-1), LIGHT_BG), ("ALIGN",(0,0),(-1,-1),"CENTER"),
        ("TOPPADDING",(0,0),(-1,-1),7), ("BOTTOMPADDING",(0,0),(-1,-1),7),
        ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#dddddd")),
    ]))
    story.append(lang_t)
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph("23 поддерживаемых города:", h3))
    story.append(Paragraph(
        "Тель-Авив, Иерусалим, Хайфа, Ришон-ле-Цион, Петах-Тиква, Ашдод, "
        "Нетания, Беэр-Шева, Бней-Брак, Холон, Рамат-Ган, Реховот, Ашкелон, "
        "Бат-Ям, Кфар-Саба, Хадера, Эйлат, Герцлия, Раанана, Лод, Нес-Циона, "
        "Ор-Иегуда, Модиин", small))
    story.append(Spacer(1, 0.3*cm))

    # ── 9. АНАЛИТИКА ────────────────────────────────────────────────────────
    story += [sec("9. Аналитика и администрирование", DARK), Spacer(1, 0.2*cm)]
    story.append(tbl([
        ["Пользователи", "Дата регистрации, язык, имя, username, активность"],
        ["Поиски",       "Все фильтры: тип сделки, тип объекта, город, комнаты, цена"],
        ["Подписки",     "Активации по тарифу, конверсия триала, платёжные логи"],
        ["Объявления",   "Количество, по городам/районам, просмотры, запросы, сделки"],
        ["Платежи",      "История: дата, пользователь, тариф, сумма, тип оплаты"],
    ], [3.5*cm, W-3.5*cm], header=["Что отслеживается", "Детали"]))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph("Дашборд (admin panel):", h3))
    story += buls([
        "URL: flatfinderil-bot-production.up.railway.app (защищён паролем)",
        "Вкладки: Обзор, Поиски, Объявления, Пользователи, Платежи",
        "Графики: Chart.js — активность, поиски, подписки, платежи",
        "Скачать PDF: кнопка «Скачать PDF» в шапке дашборда",
    ])
    story.append(Spacer(1, 0.3*cm))

    # ── 10. АРХИТЕКТУРА ─────────────────────────────────────────────────────
    story += [sec("10. Техническая архитектура", colors.HexColor("#37474f")), Spacer(1, 0.2*cm)]
    story.append(tbl([
        ["Язык",           "Python 3.11.6"],
        ["Фреймворк",      "python-telegram-bot 20.7 (async)"],
        ["База данных",    "JSON-файлы: listings_db.json, stats.json"],
        ["Деплой",         "Railway (cloud) — автодеплой из GitHub"],
        ["Email",          "Resend API — HTML-квитанции на иврите"],
        ["Порты",          "8080 — Analytics API  |  3000 — Dashboard"],
        ["Парсеры",        "Yad2, Telegram-каналы, Facebook (отдельные скрипты)"],
        ["Уведомления",    "asyncio фоновые задачи + threading"],
        ["Крипто-платежи", "CryptoPay API (@CryptoBot) — USDT / TON / BTC / ETH"],
    ], [3.5*cm, W-3.5*cm]))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph("Ключевые файлы:", h3))
    story += buls([
        "bot.py — точка входа, регистрация всех handlers",
        "handlers.py — главное меню, платежи, подписки, inline-кнопки",
        "search_handler.py — 10-шаговый ConversationHandler поиска",
        "listing_handler.py — 18+-шаговый ConversationHandler объявлений",
        "subscription.py — логика тарифов, триала, активации",
        "analytics.py — трекинг событий, payments_log",
        "cryptopay.py — интеграция с CryptoPay API",
        "dashboard.html — SPA дашборд (Chart.js)",
        "notifications.py — фоновые задачи уведомлений",
    ])
    story.append(Spacer(1, 0.3*cm))

    # ── ПОДВАЛ ──────────────────────────────────────────────────────────────
    story.append(HRFlowable(width=W, thickness=1, color=colors.HexColor("#dddddd")))
    story.append(Spacer(1, 0.2*cm))
    footer = Table([[
        Paragraph("FlatFinderIL Bot · Карта функций v1.0",
                  S("fl", fontSize=9, fontName=_FONT, textColor=GRAY)),
        Paragraph("Апрель 2026 · Python + Telegram Bot API",
                  S("fc", fontSize=9, fontName=_FONT, textColor=GRAY, alignment=TA_CENTER)),
        Paragraph("CryptoPay готов · Smart Glocal LIVE ожидается",
                  S("fr", fontSize=9, fontName=_FONT, textColor=ORANGE, alignment=TA_CENTER)),
    ]], colWidths=[W/3]*3)
    footer.setStyle(TableStyle([("TOPPADDING",(0,0),(-1,-1),3)]))
    story.append(footer)

    doc.build(story)
    if output_path:
        return output_path
    return buf.getvalue()


if __name__ == "__main__":
    out = "/Users/alinatsarenko/Desktop/FlatFinderIL_Bot_Map_RU.pdf"
    generate(out)
    print(f"Сохранён: {out}")
