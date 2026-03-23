"""Generate FlatFinderIL Bot — product document PDF."""
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

OUT = "/Users/alinatsarenko/projects/flatfinderil-bot/FlatFinderIL_Bot.pdf"

# ── Fonts (system) ────────────────────────────────────────────────────────────
def reg_font(name, path):
    if os.path.exists(path):
        pdfmetrics.registerFont(TTFont(name, path))
        return True
    return False

# Try DejaVu (usually present via reportlab or system)
FONT_PATHS = [
    ("/Library/Fonts/Arial Unicode.ttf",          "Arial Unicode"),
    ("/System/Library/Fonts/Supplemental/Arial Unicode MS.ttf", "Arial Unicode"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVu"),
    ("/usr/share/fonts/dejavu/DejaVuSans.ttf",    "DejaVu"),
]
BASE_FONT = "Helvetica"
for path, name in FONT_PATHS:
    if reg_font(name, path):
        BASE_FONT = name
        break

# ── Colour palette ─────────────────────────────────────────────────────────────
TG     = colors.HexColor("#2AABEE")
GREEN  = colors.HexColor("#4CAF8A")
GOLD   = colors.HexColor("#EF9F27")
PURPLE = colors.HexColor("#7F77DD")
DARK   = colors.HexColor("#1A1A1A")
GREY   = colors.HexColor("#666666")
LIGHT  = colors.HexColor("#F5F5F0")
WHITE  = colors.white

W, H = A4

# ── Styles ─────────────────────────────────────────────────────────────────────
def make_styles():
    s = {}
    def p(name, **kw):
        s[name] = ParagraphStyle(name, fontName=BASE_FONT, **kw)

    p("h1",     fontSize=26, leading=32, textColor=DARK,   spaceAfter=6,  spaceBefore=0,  alignment=TA_LEFT)
    p("h2",     fontSize=16, leading=22, textColor=TG,     spaceAfter=4,  spaceBefore=14, alignment=TA_LEFT)
    p("h3",     fontSize=12, leading=16, textColor=DARK,   spaceAfter=3,  spaceBefore=8,  alignment=TA_LEFT)
    p("body",   fontSize=10, leading=15, textColor=DARK,   spaceAfter=4,  spaceBefore=0,  alignment=TA_LEFT)
    p("small",  fontSize=8,  leading=12, textColor=GREY,   spaceAfter=2,  spaceBefore=0,  alignment=TA_LEFT)
    p("bullet", fontSize=10, leading=15, textColor=DARK,   spaceAfter=3,  spaceBefore=0,
                leftIndent=12, firstLineIndent=0)
    p("center", fontSize=10, leading=14, textColor=GREY,   spaceAfter=0,  spaceBefore=0,  alignment=TA_CENTER)
    p("tag",    fontSize=9,  leading=12, textColor=WHITE,  spaceAfter=0,  spaceBefore=0,  alignment=TA_CENTER)
    p("cover_title", fontSize=32, leading=40, textColor=WHITE, alignment=TA_LEFT, spaceAfter=8)
    p("cover_sub",   fontSize=14, leading=20, textColor=WHITE, alignment=TA_LEFT, spaceAfter=0)
    return s

ST = make_styles()

# ── Helpers ────────────────────────────────────────────────────────────────────
def hr(color=TG, thickness=0.5):
    return HRFlowable(width="100%", thickness=thickness, color=color, spaceAfter=6, spaceBefore=4)

def sp(h=6):
    return Spacer(1, h)

def h2(text):
    return Paragraph(text, ST["h2"])

def h3(text):
    return Paragraph(text, ST["h3"])

def body(text):
    return Paragraph(text, ST["body"])

def bullet(text):
    return Paragraph(f"• {text}", ST["bullet"])

def kpi_table(items):
    """items = [(icon, label, value, color), ...]"""
    cols = 3
    rows = []
    row = []
    for i, (icon, label, value, color) in enumerate(items):
        cell_content = [
            Paragraph(icon,  ParagraphStyle("ci", fontName=BASE_FONT, fontSize=18, leading=22, alignment=TA_CENTER)),
            Paragraph(value, ParagraphStyle("cv", fontName=BASE_FONT, fontSize=18, leading=22, textColor=color, alignment=TA_CENTER)),
            Paragraph(label, ParagraphStyle("cl", fontName=BASE_FONT, fontSize=8,  leading=11, textColor=GREY, alignment=TA_CENTER)),
        ]
        row.append(cell_content)
        if len(row) == cols:
            rows.append(row)
            row = []
    if row:
        while len(row) < cols:
            row.append([""])
        rows.append(row)

    col_w = (W - 40*mm) / cols
    flat = []
    for r in rows:
        flat_row = []
        for cell in r:
            if isinstance(cell, list) and cell and isinstance(cell[0], Paragraph):
                flat_row.append(cell)
            else:
                flat_row.append([""])
        flat.append(flat_row)

    t = Table(flat, colWidths=[col_w]*cols, rowHeights=None)
    t.setStyle(TableStyle([
        ("BACKGROUND",  (0,0),(-1,-1), LIGHT),
        ("ROWBACKGROUND",(0,0),(-1,-1), LIGHT),
        ("BOX",         (0,0),(-1,-1), 0.3, colors.HexColor("#E0E0DA")),
        ("INNERGRID",   (0,0),(-1,-1), 0.3, colors.HexColor("#E0E0DA")),
        ("ALIGN",       (0,0),(-1,-1), "CENTER"),
        ("VALIGN",      (0,0),(-1,-1), "MIDDLE"),
        ("TOPPADDING",  (0,0),(-1,-1), 10),
        ("BOTTOMPADDING",(0,0),(-1,-1), 10),
        ("LEFTPADDING", (0,0),(-1,-1), 8),
        ("RIGHTPADDING",(0,0),(-1,-1), 8),
    ]))
    return t

def feature_table(rows_data, col_widths=None):
    """rows_data = [("icon + title", "description"), ...]"""
    if col_widths is None:
        col_widths = [55*mm, W - 40*mm - 55*mm]
    rows = []
    for title, desc in rows_data:
        rows.append([
            Paragraph(f"<b>{title}</b>", ParagraphStyle("ft", fontName=BASE_FONT, fontSize=10, leading=14, textColor=DARK)),
            Paragraph(desc,              ParagraphStyle("fd", fontName=BASE_FONT, fontSize=9,  leading=13, textColor=GREY)),
        ])
    t = Table(rows, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("VALIGN",       (0,0),(-1,-1), "TOP"),
        ("TOPPADDING",   (0,0),(-1,-1), 7),
        ("BOTTOMPADDING",(0,0),(-1,-1), 7),
        ("LEFTPADDING",  (0,0),(-1,-1), 10),
        ("RIGHTPADDING", (0,0),(-1,-1), 10),
        ("ROWBACKGROUNDS",(0,0),(-1,-1), [WHITE, LIGHT]),
        ("LINEBELOW",    (0,0),(-1,-1), 0.3, colors.HexColor("#E8E8E4")),
        ("ROUNDEDCORNERS",(0,0),(-1,-1), 4),
    ]))
    return t

def cmd_table(rows_data):
    col_widths = [45*mm, W - 40*mm - 45*mm]
    rows = []
    for cmd, desc in rows_data:
        rows.append([
            Paragraph(f"<b>{cmd}</b>", ParagraphStyle("ct", fontName=BASE_FONT, fontSize=10, leading=14, textColor=TG)),
            Paragraph(desc,            ParagraphStyle("cd", fontName=BASE_FONT, fontSize=9,  leading=13, textColor=DARK)),
        ])
    t = Table(rows, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("VALIGN",       (0,0),(-1,-1), "MIDDLE"),
        ("TOPPADDING",   (0,0),(-1,-1), 7),
        ("BOTTOMPADDING",(0,0),(-1,-1), 7),
        ("LEFTPADDING",  (0,0),(-1,-1), 10),
        ("RIGHTPADDING", (0,0),(-1,-1), 10),
        ("ROWBACKGROUNDS",(0,0),(-1,-1), [WHITE, LIGHT]),
        ("LINEBELOW",    (0,0),(-1,-1), 0.3, colors.HexColor("#E8E8E4")),
    ]))
    return t

# ── Cover page flowable ────────────────────────────────────────────────────────
from reportlab.platypus.flowables import Flowable

class CoverPage(Flowable):
    def __init__(self, w, h):
        super().__init__()
        self.w = w
        self.h = h

    def draw(self):
        c = self.canv
        # Background gradient via rectangles
        c.setFillColor(colors.HexColor("#0D1B2A"))
        c.rect(0, 0, self.w, self.h, fill=1, stroke=0)
        # Accent strip
        c.setFillColor(TG)
        c.rect(0, self.h - 8, self.w, 8, fill=1, stroke=0)
        # Large circle decoration
        c.setFillColor(colors.HexColor("#1A2F42"))
        c.circle(self.w - 40, self.h * 0.35, 110, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#152233"))
        c.circle(self.w - 10, self.h * 0.3, 70, fill=1, stroke=0)

        # Logo circle
        c.setFillColor(TG)
        c.circle(50, self.h - 60, 22, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont(BASE_FONT, 14)
        c.drawCentredString(50, self.h - 65, "FF")

        # Bot name
        c.setFillColor(WHITE)
        c.setFont(BASE_FONT, 36)
        c.drawString(30, self.h - 160, "FlatFinderIL Bot")

        c.setFillColor(TG)
        c.setFont(BASE_FONT, 14)
        c.drawString(30, self.h - 185, "@FlatFinderIL_bot")

        # Tagline
        c.setFillColor(colors.HexColor("#A0B8C8"))
        c.setFont(BASE_FONT, 12)
        c.drawString(30, self.h - 220, "Telegram-bot для поиска недвижимости в Израиле")

        # Divider
        c.setStrokeColor(colors.HexColor("#2A4A6A"))
        c.setLineWidth(1)
        c.line(30, self.h - 240, self.w - 30, self.h - 240)

        # Key stats
        stats = [
            ("19+", "функций"),
            ("10",  "Tg-каналов"),
            ("3",   "языка"),
            ("30m", "парсинг"),
        ]
        x = 30
        for val, lbl in stats:
            c.setFillColor(TG)
            c.setFont(BASE_FONT, 22)
            c.drawString(x, self.h - 270, val)
            c.setFillColor(colors.HexColor("#A0B8C8"))
            c.setFont(BASE_FONT, 9)
            c.drawString(x, self.h - 284, lbl)
            x += 120

        # Version / date
        c.setFillColor(colors.HexColor("#506070"))
        c.setFont(BASE_FONT, 9)
        c.drawString(30, 30, "Версия 2.0  |  Март 2026  |  Развёртывание: Railway")
        c.drawRightString(self.w - 30, 30, "Конфиденциально")

    def wrap(self, aw, ah):
        return aw, ah

# ── Section header flowable ───────────────────────────────────────────────────
class SectionHeader(Flowable):
    def __init__(self, text, color=TG, w=None):
        super().__init__()
        self._text  = text
        self._color = color
        self._w     = w or (A4[0] - 40*mm)

    def draw(self):
        c = self.canv
        c.setFillColor(self._color)
        c.roundRect(0, 0, self._w, 26, 4, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont(BASE_FONT, 12)
        c.drawString(12, 8, self._text)

    def wrap(self, aw, ah):
        return self._w, 30

# ── Build document ─────────────────────────────────────────────────────────────
def build():
    doc = SimpleDocTemplate(
        OUT,
        pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=20*mm,  bottomMargin=20*mm,
        title="FlatFinderIL Bot — Product Document",
        author="FlatFinderIL Team",
    )

    story = []
    IW = W - 40*mm  # inner width

    # ──────────────────────────────────────────────────────────────────────────
    # COVER
    # ──────────────────────────────────────────────────────────────────────────
    from reportlab.platypus import PageBreak

    story.append(CoverPage(IW, H - 40*mm))
    story.append(PageBreak())

    # ──────────────────────────────────────────────────────────────────────────
    # 1. OVERVIEW
    # ──────────────────────────────────────────────────────────────────────────
    story.append(SectionHeader("1. Обзор продукта"))
    story.append(sp(8))
    story.append(body(
        "FlatFinderIL Bot — Telegram-бот для поиска и публикации объявлений "
        "о недвижимости в Израиле. Поддерживает аренду и покупку, "
        "многошаговую фильтрацию, автоматический парсинг Telegram-каналов, "
        "избранное, подписки на поиск, уведомления, отзывы и аналитику."
    ))
    story.append(sp(10))

    story.append(kpi_table([
        ("19+",  "Функций",          "19+",    TG),
        ("10",   "Telegram-каналов", "10",     GREEN),
        ("3",    "Языка интерфейса", "RU/EN/HE", PURPLE),
        ("690+", "Объявлений в БД",  "690+",   GOLD),
        ("30m",  "Интервал парсинга","30 мин", TG),
        ("Free", "До 15 апр 2026",   "Триал",  GREEN),
    ]))
    story.append(sp(14))

    # ──────────────────────────────────────────────────────────────────────────
    # 2. COMMANDS
    # ──────────────────────────────────────────────────────────────────────────
    story.append(SectionHeader("2. Команды бота"))
    story.append(sp(8))
    story.append(cmd_table([
        ("/start",    "Главное меню — точка входа"),
        ("/search",   "Начать поиск недвижимости (10 шагов)"),
        ("/add",      "Добавить объявление (19 шагов)"),
        ("/listings", "Мои объявления"),
        ("/cabinet",  "Кабинет агента — статистика по объявлениям"),
        ("/refer",    "Реферальная ссылка для приглашения друзей"),
        ("/help",     "Справка"),
    ]))
    story.append(sp(14))

    # ──────────────────────────────────────────────────────────────────────────
    # 3. SEARCH
    # ──────────────────────────────────────────────────────────────────────────
    story.append(SectionHeader("3. Поиск недвижимости", color=GREEN))
    story.append(sp(8))
    story.append(body("Многошаговый диалог (/search) с 10 фильтрами:"))
    story.append(sp(4))
    story.append(feature_table([
        ("1. Тип сделки",       "Аренда / Покупка"),
        ("2. Тип жилья",        "Квартира, Дом, Вилла, Пентхаус, Студия, Дуплекс"),
        ("3. Округ",            "6 округов: Тель-Авив, Иерусалим, Хайфа, Шарон, Центр, Юг"),
        ("4. Город",            "23 города с мультивыбором"),
        ("5. Комнаты",          "Мин / Макс (1 — 5+)"),
        ("6. Цена",             "От / До (аренда ₪/мес или покупка ₪)"),
        ("7. Парковка",         "0 / 1 / 2 / 3+ мест или неважно"),
        ("8. Бассейн",          "Есть / Неважно"),
        ("9. Лифт + Убежище",   "Мамад / Миклат / Нет / Неважно"),
        ("10. Инфраструктура",  "Школа, сад, ТЦ, парк, спортзал, больница, пляж, транспорт..."),
    ], col_widths=[55*mm, IW - 55*mm]))
    story.append(sp(14))

    # ──────────────────────────────────────────────────────────────────────────
    # 4. LISTING CARD
    # ──────────────────────────────────────────────────────────────────────────
    story.append(SectionHeader("4. Карточка объявления", color=GOLD))
    story.append(sp(8))
    story.append(body("Каждая карточка содержит:"))
    story.append(sp(4))

    card_items = [
        "Название, тип жилья, тип сделки",
        "Цена (аренда: ₪/мес, покупка: млн ₪)",
        "Город, округ, квартал",
        "Комнаты, этаж, площадь (кв.м)",
        "Парковка, бассейн, инфраструктура",
        "Описание и дата добавления",
        "Фотографии (Telegram file_id)",
        "Счётчик просмотров (👁 N просмотров)",
        "Рейтинг и число отзывов (★ 4.2 · 12 отзывов)",
        "Оценка цены по рынку (📊 Ниже рынка на 12%)",
    ]
    for item in card_items:
        story.append(bullet(item))
    story.append(sp(8))
    story.append(body("Кнопки действий в карточке:"))
    story.append(sp(4))
    story.append(feature_table([
        ("❤️ В избранное",         "Сохранить / убрать из избранного"),
        ("📞 Связаться",           "Показать контакт владельца (alert)"),
        ("📍 На карте",            "Открыть Google Maps по адресу объявления"),
        ("👁 Запросить просмотр",  "Уведомить владельца о запросе просмотра"),
        ("⭐ Оставить отзыв",      "Оценить 1–5 звёзд + текстовый комментарий"),
        ("🔔 Подписаться на поиск","Сохранить текущие фильтры, получать уведомления"),
    ], col_widths=[55*mm, IW - 55*mm]))
    story.append(sp(14))

    # ──────────────────────────────────────────────────────────────────────────
    # 5. ADD LISTING
    # ──────────────────────────────────────────────────────────────────────────
    story.append(SectionHeader("5. Добавление объявления", color=PURPLE))
    story.append(sp(8))
    story.append(body("Диалог /add — 19 шагов:"))
    story.append(sp(4))
    story.append(feature_table([
        ("1–4. Основное",      "Тип сделки → тип жилья → округ → город"),
        ("5. Квартал",         "Название квартала / района"),
        ("6–8. Параметры",     "Комнаты → этаж → площадь (кв.м)"),
        ("9. Цена",            "Ввод числом (₪)"),
        ("10–13. Удобства",    "Парковка → бассейн → убежище → лифт"),
        ("14. Инфраструктура", "Мультивыбор объектов инфраструктуры"),
        ("15. Описание",       "Свободный текст"),
        ("16–18. Контакт",     "Имя → телефон → Telegram-ник"),
        ("19. Фото",           "Загрузка фотографий или пропустить"),
        ("Подтверждение",      "Предпросмотр → Опубликовать / Отмена"),
    ], col_widths=[45*mm, IW - 45*mm]))
    story.append(sp(6))
    story.append(body(
        "После публикации пользователь получает: "
        "<b>+3 бонусных дня</b> к подписке."
    ))
    story.append(sp(14))

    # ──────────────────────────────────────────────────────────────────────────
    # 6. NOTIFICATIONS
    # ──────────────────────────────────────────────────────────────────────────
    story.append(SectionHeader("6. Уведомления и алерты", color=TG))
    story.append(sp(8))
    story.append(feature_table([
        ("🔔 Подписка на поиск",
         "Пользователь сохраняет фильтры. Каждые 30 мин бот проверяет новые объявления "
         "под подписку и отправляет уведомление при появлении новых совпадений."),
        ("📉 Алерт о снижении цены",
         "При добавлении в избранное сохраняется цена. Каждый час бот сравнивает "
         "текущую цену с сохранённой и уведомляет при снижении."),
        ("📞 Запрос на просмотр",
         "Покупатель нажимает кнопку — владелец (если публиковал через бота) "
         "получает мгновенное уведомление с именем пользователя."),
    ], col_widths=[55*mm, IW - 55*mm]))
    story.append(sp(14))

    # ──────────────────────────────────────────────────────────────────────────
    # 7. TELEGRAM PARSING
    # ──────────────────────────────────────────────────────────────────────────
    story.append(SectionHeader("7. Парсинг Telegram-каналов", color=GREEN))
    story.append(sp(8))
    story.append(body(
        "Каждые 30 минут бот автоматически собирает объявления из 10 каналов:"
    ))
    story.append(sp(6))
    channels = [
        ("@izrailnedvizimosti",   "Израиль недвижимость"),
        ("@rentapartmentbatyam",  "Аренда квартир Бат-Ям"),
        ("@isra_home_arenda",     "Isra Home Аренда"),
        ("@Sublet_Israel",        "Sublet Israel"),
        ("@snyat_kvartiruy",      "Снять квартиру"),
        ("@nagariyaapartments",   "Нагария апартаменты"),
        ("@ashdod_rent",          "Ашдод аренда"),
        ("@happy_home_ashkelon",  "Happy Home Ашкелон"),
        ("+ 2 дополнительных",    "Расширение списка в работе"),
    ]
    story.append(feature_table(channels, col_widths=[60*mm, IW - 60*mm]))
    story.append(sp(6))
    story.append(body(
        "Из каждого поста извлекаются: город, цена, количество комнат, "
        "контакт. Дубликаты автоматически исключаются."
    ))
    story.append(sp(14))

    # ──────────────────────────────────────────────────────────────────────────
    # 8. ENGAGEMENT FEATURES
    # ──────────────────────────────────────────────────────────────────────────
    story.append(SectionHeader("8. Вовлечённость и геймификация", color=GOLD))
    story.append(sp(8))
    story.append(feature_table([
        ("⭐ Отзывы и рейтинг",
         "После просмотра — кнопка «Оставить отзыв». Оценка 1–5 + текст. "
         "Один пользователь — один отзыв на объявление. Средний рейтинг "
         "отображается в карточке."),
        ("📊 Оценка цены",
         "Автоматически сравнивает цену с аналогами в том же городе. "
         "Показывает: «Ниже рынка на X%» / «Выше рынка» / «Цена соответствует рынку»."),
        ("🎁 Реферальная программа",
         "/refer генерирует ссылку t.me/bot?start=ref_ID. "
         "За приглашённого друга: +7 дней подписки. "
         "За каждое опубликованное объявление: +3 дня."),
        ("👨‍💼 Кабинет агента (/cabinet)",
         "Статистика: кол-во объявлений, суммарные просмотры, "
         "запросы на просмотр, средние рейтинги по каждому объявлению."),
    ], col_widths=[55*mm, IW - 55*mm]))
    story.append(sp(14))

    # ──────────────────────────────────────────────────────────────────────────
    # 9. SUBSCRIPTION
    # ──────────────────────────────────────────────────────────────────────────
    story.append(SectionHeader("9. Монетизация и подписка", color=PURPLE))
    story.append(sp(8))
    story.append(body(
        "Тестовый период: бот полностью бесплатен до 15 апреля 2026."
    ))
    story.append(sp(6))
    story.append(cmd_table([
        ("Триал до 15.04.2026", "Полный доступ бесплатно для всех пользователей"),
        ("1 неделя · 19.90 ₪",  "Стандартный план"),
        ("2 недели · 29.90 ₪",  "Хит продаж (⭐)"),
        ("1 месяц · 39.90 ₪",   "Максимальная выгода"),
    ]))
    story.append(sp(14))

    # ──────────────────────────────────────────────────────────────────────────
    # 10. ANALYTICS DASHBOARD
    # ──────────────────────────────────────────────────────────────────────────
    story.append(SectionHeader("10. Аналитика и дашборд", color=TG))
    story.append(sp(8))
    story.append(body(
        "Веб-дашборд доступен по адресу Railway-деплоя. "
        "Обновляется каждые 30 секунд. 5 вкладок:"
    ))
    story.append(sp(6))
    story.append(feature_table([
        ("📊 Обзор",
         "KPI: объявления, пользователи, поиски, просмотры, подписки на поиск, доход. "
         "График активности за 7 дней. Топ городов."),
        ("👥 Пользователи",
         "Общее кол-во, новые сегодня, активные за неделю, "
         "прирост по дням, распределение по языкам."),
        ("🔍 Поиски",
         "Топ городов в поисках, популярные фильтры (аренда, "
         "комнаты, цена, парковка, мамад, лифт)."),
        ("🏠 Объявления",
         "Источники (Telegram-каналы), распределение по городам, "
         "статус каналов."),
        ("💬 Вовлечённость",
         "Просмотры, запросы просмотра, избранное, отзывы, "
         "топ по просмотрам / рейтингу / избранному, "
         "города в подписках, реферальная статистика."),
        ("💰 Доход",
         "Тарифные планы, текущий доход, прогноз после триала "
         "(консервативно / реалистично / оптимистично)."),
    ], col_widths=[45*mm, IW - 45*mm]))
    story.append(sp(14))

    # ──────────────────────────────────────────────────────────────────────────
    # 11. MULTILINGUAL
    # ──────────────────────────────────────────────────────────────────────────
    story.append(SectionHeader("11. Мультиязычность", color=GREEN))
    story.append(sp(8))
    story.append(feature_table([
        ("RU Русский",  "Основной язык интерфейса"),
        ("EN English",  "Полный перевод всех строк"),
        ("HE Hebrew",   "Иврит с поддержкой RTL (справа налево)"),
    ], col_widths=[45*mm, IW - 45*mm]))
    story.append(sp(14))

    # ──────────────────────────────────────────────────────────────────────────
    # 12. TECH STACK
    # ──────────────────────────────────────────────────────────────────────────
    story.append(SectionHeader("12. Техническая архитектура", color=PURPLE))
    story.append(sp(8))
    story.append(feature_table([
        ("Язык",        "Python 3.11.6"),
        ("Фреймворк",   "python-telegram-bot 20.7  (asyncio, ConversationHandler)"),
        ("База данных", "JSON-файл listings_db.json (listings, favorites, subscriptions, reviews, referrals)"),
        ("Аналитика",   "JSON-файл stats.json + HTTP-сервер на порту PORT"),
        ("Дашборд",     "Статический HTML + Chart.js, обслуживается тем же сервером"),
        ("Парсер",      "Telethon (MTProto) — парсинг Telegram-каналов, StringSession"),
        ("Деплой",      "Railway (cloud) — auto-deploy из GitHub main-ветки"),
        ("Фоновые задачи","threading.Thread: парсер каждые 30 мин, "
                          "проверка подписок каждые 30 мин, алерты цен каждый час"),
    ], col_widths=[45*mm, IW - 45*mm]))
    story.append(sp(14))

    # ──────────────────────────────────────────────────────────────────────────
    # 13. DATA MODEL
    # ──────────────────────────────────────────────────────────────────────────
    story.append(SectionHeader("13. Модель данных (listings_db.json)", color=GOLD))
    story.append(sp(8))
    story.append(feature_table([
        ("listings",         "Объявления: id, title, property_type, city, district, neighborhood, rooms, floor, area_sqm, price, deal_type, parking, pool, shelter, elevator, infrastructure, description, contact, photos, date_added, active, views, view_requests, source, user_id"),
        ("favorites",        "user_id → [listing_id, ...]"),
        ("user_listings",    "user_id → [listing_id, ...]"),
        ("subscriptions",    "user_id → [{filters, last_result_ids, created_at}, ...]"),
        ("favorites_prices", "user_id_listing_id → saved_price (для алертов)"),
        ("reviews",          "listing_id → [{user_id, rating, comment, date}, ...]"),
        ("referrals",        "user_id → [referred_user_id, ...]"),
        ("referral_bonuses", "user_id → bonus_days (int)"),
        ("next_id",          "Автоинкремент ID объявлений"),
    ], col_widths=[55*mm, IW - 55*mm]))
    story.append(sp(14))

    # ──────────────────────────────────────────────────────────────────────────
    # 14. ROADMAP
    # ──────────────────────────────────────────────────────────────────────────
    story.append(SectionHeader("14. Дорожная карта", color=TG))
    story.append(sp(8))
    story.append(feature_table([
        ("Q2 2026 · AI-помощник",
         "Пользователь описывает жильё текстом — бот сам выставляет фильтры (Claude API)"),
        ("Q2 2026 · Карты инфраструктуры",
         "Расстояние до метро, школ, больниц (Google Maps / OpenStreetMap API)"),
        ("Q3 2026 · Перевод объявлений",
         "Автоперевод на любой язык через Google Translate API"),
        ("Q3 2026 · Чат арендатор / владелец",
         "Встроенный мессенджер прямо в боте через forwarding"),
        ("Q3 2026 · CRM для агентств",
         "История клиентов, воронка, теги"),
        ("Q4 2026 · Виртуальный тур",
         "Ссылка на 3D-тур (Matterport или аналог)"),
        ("Q4 2026 · Онлайн подписание",
         "Интеграция с DocuSign / HelloSign для договора аренды"),
    ], col_widths=[60*mm, IW - 60*mm]))
    story.append(sp(20))

    # Footer note
    story.append(hr(color=colors.HexColor("#E0E0DA")))
    story.append(Paragraph(
        "FlatFinderIL Bot  |  Март 2026  |  Deployment: Railway  |  @FlatFinderIL_bot",
        ST["center"]
    ))

    doc.build(story)
    print(f"PDF saved: {OUT}")

if __name__ == "__main__":
    build()
