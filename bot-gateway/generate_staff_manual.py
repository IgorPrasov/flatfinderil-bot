#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FlatFinderIL — Staff Training Manual PDF Generator"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

OUTPUT = "/Users/alinatsarenko/projects/flatfinderil-bot/FlatFinderIL_Staff_Manual.pdf"

# ── Colors ────────────────────────────────────────────────────────────────────
BLUE   = colors.HexColor("#2AABEE")
DARK   = colors.HexColor("#1a1a2e")
GREEN  = colors.HexColor("#27AE60")
ORANGE = colors.HexColor("#EF9F27")
RED    = colors.HexColor("#E74C3C")
LIGHT  = colors.HexColor("#F0F8FF")
LGRAY  = colors.HexColor("#F5F5F5")
MGRAY  = colors.HexColor("#E0E0E0")
WHITE  = colors.white
TEXT   = colors.HexColor("#2C3E50")

# ── Font registration ──────────────────────────────────────────────────────────
def _reg(name, paths):
    for p in paths:
        if os.path.exists(p):
            try:
                pdfmetrics.registerFont(TTFont(name, p))
                return True
            except Exception:
                pass
    return False

SUPP = "/System/Library/Fonts/Supplemental/"
_reg("MF",  [SUPP+"Arial.ttf",      SUPP+"Verdana.ttf",      SUPP+"Trebuchet MS.ttf"])
_reg("MFB", [SUPP+"Arial Bold.ttf", SUPP+"Verdana Bold.ttf", SUPP+"Trebuchet MS Bold.ttf"])
F  = "MF"
FB = "MFB"

# ── Paragraph styles ──────────────────────────────────────────────────────────
def ps(name, **kw):
    defaults = dict(fontName=F, fontSize=10, textColor=TEXT, leading=14)
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)

ST = {
    "h_title":   ps("h_title",  fontName=FB, fontSize=30, textColor=WHITE, alignment=TA_CENTER, leading=36),
    "h_sub":     ps("h_sub",    fontName=F,  fontSize=13, textColor=colors.HexColor("#CCE8FA"), alignment=TA_CENTER),
    "ch_label":  ps("ch_label", fontName=FB, fontSize=10, textColor=colors.HexColor("#AAD4F5")),
    "ch_title":  ps("ch_title", fontName=FB, fontSize=22, textColor=WHITE, leading=28),
    "section":   ps("section",  fontName=FB, fontSize=14, textColor=BLUE, spaceBefore=14, spaceAfter=5),
    "sub":       ps("sub",      fontName=FB, fontSize=11, textColor=DARK, spaceBefore=8, spaceAfter=3),
    "body":      ps("body",     fontName=F,  fontSize=10, textColor=TEXT, leading=15, spaceAfter=5, alignment=TA_JUSTIFY),
    "bullet":    ps("bullet",   fontName=F,  fontSize=10, textColor=TEXT, leading=14, spaceAfter=3, leftIndent=14),
    "note":      ps("note",     fontName=F,  fontSize=9,  textColor=colors.HexColor("#444"), leading=13),
    "toc1":      ps("toc1",     fontName=FB, fontSize=11, textColor=DARK, spaceBefore=6, spaceAfter=1),
    "toc2":      ps("toc2",     fontName=F,  fontSize=10, textColor=TEXT, leftIndent=14, spaceAfter=1),
    "th":        ps("th",       fontName=FB, fontSize=9,  textColor=WHITE, alignment=TA_CENTER, leading=12),
    "td":        ps("td",       fontName=F,  fontSize=9,  textColor=TEXT,  leading=12),
    "tdb":       ps("tdb",      fontName=FB, fontSize=9,  textColor=TEXT,  leading=12),
    "td_c":      ps("td_c",     fontName=F,  fontSize=9,  textColor=TEXT,  leading=12, alignment=TA_CENTER),
    "step_n":    ps("step_n",   fontName=FB, fontSize=17, textColor=BLUE, alignment=TA_CENTER, leading=20),
    "cover_inf": ps("cover_inf",fontName=F,  fontSize=10, textColor=TEXT, leading=14),
    "cover_infb":ps("cover_infb",fontName=FB,fontSize=10, textColor=WHITE, leading=14),
    "end":       ps("end",      fontName=F,  fontSize=9,  textColor=colors.HexColor("#555"), alignment=TA_CENTER, leading=14),
    "hdr":       ps("hdr",      fontName=FB, fontSize=8,  textColor=BLUE),
    "ftr":       ps("ftr",      fontName=F,  fontSize=8,  textColor=colors.HexColor("#888")),
}

# ── Shortcut: Paragraph with style ───────────────────────────────────────────
def P(text, style="td"):
    return Paragraph(str(text), ST[style])

def on_page(canvas, doc):
    W, H = A4
    canvas.saveState()
    if doc.page > 1:
        canvas.setStrokeColor(BLUE); canvas.setLineWidth(0.5)
        canvas.line(2*cm, H-1.5*cm, W-2*cm, H-1.5*cm)
        canvas.setFont(FB, 8); canvas.setFillColor(BLUE)
        canvas.drawString(2*cm, H-1.2*cm, "FlatFinderIL")
        canvas.setFont(F, 8); canvas.setFillColor(colors.HexColor("#888"))
        canvas.drawRightString(W-2*cm, H-1.2*cm, "Учебное пособие для персонала")
        canvas.setStrokeColor(MGRAY)
        canvas.line(2*cm, 1.5*cm, W-2*cm, 1.5*cm)
        canvas.setFont(F, 8); canvas.setFillColor(colors.HexColor("#888"))
        canvas.drawString(2*cm, 1.0*cm, "FlatFinderIL © 2026  |  Конфиденциально")
        canvas.drawRightString(W-2*cm, 1.0*cm, f"Стр. {doc.page}")
    canvas.restoreState()

# ── Generic table style ────────────────────────────────────────────────────────
BASE_TBL = [
    ("FONTNAME",      (0,0),(-1,-1), F),
    ("FONTSIZE",      (0,0),(-1,-1), 9),
    ("GRID",          (0,0),(-1,-1), 0.3, MGRAY),
    ("LEFTPADDING",   (0,0),(-1,-1), 7),
    ("RIGHTPADDING",  (0,0),(-1,-1), 7),
    ("TOPPADDING",    (0,0),(-1,-1), 5),
    ("BOTTOMPADDING", (0,0),(-1,-1), 5),
    ("VALIGN",        (0,0),(-1,-1), "TOP"),
]
HEADER_ROW = [
    ("BACKGROUND",  (0,0),(-1,0), DARK),
    ("FONTNAME",    (0,0),(-1,0), FB),
    ("TEXTCOLOR",   (0,0),(-1,0), WHITE),
]
ALT_ROWS = [("ROWBACKGROUNDS",(0,1),(-1,-1),[WHITE, LGRAY])]

def make_tbl(data, col_w, extra=None):
    style = BASE_TBL + HEADER_ROW + ALT_ROWS + (extra or [])
    t = Table(data, colWidths=col_w)
    t.setStyle(TableStyle(style))
    return [t, Spacer(1,6)]

# ── Builders ───────────────────────────────────────────────────────────────────
def chapter_block(num, title, subtitle=""):
    W, _ = A4
    rows = [[P(f"РАЗДЕЛ {num}", "ch_label")],
            [P(title,           "ch_title")]]
    if subtitle:
        rows.append([P(subtitle, "h_sub")])
    t = Table(rows, colWidths=[W-4*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), DARK),
        ("FONTNAME",     (0,0),(-1,-1), F),
        ("LEFTPADDING",  (0,0),(-1,-1), 20),
        ("TOPPADDING",   (0,0),(0,0),   12),
        ("BOTTOMPADDING",(0,-1),(-1,-1),14),
        ("TOPPADDING",   (0,1),(-1,-1), 2),
    ]))
    return [t, Spacer(1,0.5*cm)]

def section(title, icon=""):
    txt = f"{icon}  {title}" if icon else title
    return [Paragraph(txt, ST["section"]),
            HRFlowable(width="100%", thickness=0.5, color=BLUE, spaceAfter=4)]

def sub(title):
    return [Paragraph(title, ST["sub"])]

def body(text):
    return [Paragraph(text, ST["body"])]

def bullets(items):
    return [Paragraph(f"▸  {i}", ST["bullet"]) for i in items]

def note(text, kind="info"):
    ic   = {"info":"ℹ","warn":"⚠","tip":"💡","ok":"✅"}.get(kind,"ℹ")
    bg   = {"info":LIGHT,"warn":colors.HexColor("#FEF9E7"),
            "tip":colors.HexColor("#EAFAF1"),"ok":colors.HexColor("#EAFAF1")}.get(kind,LIGHT)
    bord = {"info":BLUE,"warn":ORANGE,"tip":GREEN,"ok":GREEN}.get(kind,BLUE)
    W, _ = A4
    t = Table([[P(f"{ic}  {text}", "note")]], colWidths=[W-4*cm])
    t.setStyle(TableStyle([
        ("FONTNAME",     (0,0),(-1,-1), F),
        ("BACKGROUND",   (0,0),(-1,-1), bg),
        ("BOX",          (0,0),(-1,-1), 1.2, bord),
        ("LEFTPADDING",  (0,0),(-1,-1), 10),
        ("RIGHTPADDING", (0,0),(-1,-1), 10),
        ("TOPPADDING",   (0,0),(-1,-1), 6),
        ("BOTTOMPADDING",(0,0),(-1,-1), 6),
    ]))
    return [t, Spacer(1,4)]

def kv_table(rows):
    W, _ = A4
    data = [[P(k,"tdb"), P(v,"td")] for k,v in rows]
    t = Table(data, colWidths=[5.5*cm, W-4*cm-5.5*cm])
    t.setStyle(TableStyle(BASE_TBL + ALT_ROWS + [
        ("FONTNAME",   (0,0),(0,-1), FB),
        ("BACKGROUND", (0,0),(0,-1), colors.HexColor("#2C3E50")),
        ("TEXTCOLOR",  (0,0),(0,-1), WHITE),
    ]))
    return [t, Spacer(1,6)]

def generic_table(headers, rows, col_w, bold_col0=False):
    h_row = [P(h, "th") for h in headers]
    data_rows = []
    for row in rows:
        data_rows.append([P(str(c), "tdb" if (i==0 and bold_col0) else "td")
                          for i, c in enumerate(row)])
    extra = []
    if bold_col0:
        extra = [("BACKGROUND", (0,1),(0,-1), colors.HexColor("#EBF5FB")),
                 ("FONTNAME",   (0,1),(0,-1), FB)]
    return make_tbl([h_row]+data_rows, col_w, extra)

def step_table(steps):
    W, _ = A4
    data = []
    for i,(t,d) in enumerate(steps,1):
        data.append([P(str(i),"step_n"),
                     P(f"<b>{t}</b><br/>{d}", "td")])
    tbl = Table(data, colWidths=[1.2*cm, W-4*cm-1.2*cm])
    tbl.setStyle(TableStyle(BASE_TBL + [
        ("LINEBELOW",   (0,0),(-1,-2), 0.3, MGRAY),
        ("BACKGROUND",  (0,0),(-1,-1), LGRAY),
        ("VALIGN",      (0,0),(-1,-1), "TOP"),
    ]))
    return [tbl, Spacer(1,6)]

# ══════════════════════════════════════════════════════════════════════════════
def build_pdf():
    W, H = A4
    doc = SimpleDocTemplate(OUTPUT, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2.2*cm, bottomMargin=2.2*cm,
        title="FlatFinderIL — Учебное пособие для персонала")
    story = []

    # ── COVER ────────────────────────────────────────────────────────────────
    story.append(Spacer(1,2*cm))
    logo = Table([[Paragraph("FF", ps("L", fontName=FB, fontSize=52, textColor=WHITE, alignment=TA_CENTER))]],
                 colWidths=[3.5*cm], rowHeights=[3.5*cm])
    logo.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),BLUE),
                               ("FONTNAME",(0,0),(-1,-1),FB),
                               ("ALIGN",(0,0),(-1,-1),"CENTER"),
                               ("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    story.append(Table([[logo]], colWidths=[W-4*cm]))
    story.append(Spacer(1,0.5*cm))
    story.append(Paragraph("FlatFinderIL", ps("ct", fontName=FB, fontSize=34, textColor=BLUE, alignment=TA_CENTER, leading=40)))
    story.append(Spacer(1,0.2*cm))
    story.append(Paragraph("Учебное пособие для персонала", ps("cs", fontName=F, fontSize=16, textColor=DARK, alignment=TA_CENTER)))
    story.append(Spacer(1,0.2*cm))
    story.append(Paragraph("Телеграм-бот по недвижимости Израиля", ps("cd", fontName=F, fontSize=11, textColor=colors.HexColor("#555"), alignment=TA_CENTER)))
    story.append(Spacer(1,1.5*cm))

    cov = Table(
        [[P("Версия:", "cover_infb"),  P("1.0  |  Март 2026", "cover_inf")],
         [P("Языки:", "cover_infb"),   P("Русский / English / Hebrew", "cover_inf")],
         [P("Платформа:", "cover_infb"),P("Telegram Bot + Dashboard + Back-office", "cover_inf")],
         [P("Деплой:", "cover_infb"),  P("Railway (cloud)", "cover_inf")]],
        colWidths=[3.5*cm, W-4*cm-3.5*cm])
    cov.setStyle(TableStyle([
        ("FONTNAME",     (0,0),(-1,-1), F),
        ("BACKGROUND",   (0,0),(0,-1),  colors.HexColor("#2C3E50")),
        ("TEXTCOLOR",    (0,0),(0,-1),  WHITE),
        ("BACKGROUND",   (1,0),(1,-1),  LGRAY),
        ("GRID",         (0,0),(-1,-1), 0.3, MGRAY),
        ("LEFTPADDING",  (0,0),(-1,-1), 10),
        ("TOPPADDING",   (0,0),(-1,-1), 7),
        ("BOTTOMPADDING",(0,0),(-1,-1), 7),
    ]))
    story.append(cov)
    story.append(Spacer(1,1*cm))
    conf = Table([[Paragraph("КОНФИДЕНЦИАЛЬНО — Только для внутреннего использования персоналом FlatFinderIL",
                     ps("c2", fontName=FB, fontSize=9, textColor=colors.HexColor("#7B241C"), alignment=TA_CENTER))]],
                 colWidths=[W-4*cm])
    conf.setStyle(TableStyle([("FONTNAME",(0,0),(-1,-1),FB),
                               ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#FDEDEC")),
                               ("BOX",(0,0),(-1,-1),1,RED),
                               ("TOPPADDING",(0,0),(-1,-1),7),
                               ("BOTTOMPADDING",(0,0),(-1,-1),7)]))
    story.append(conf)
    story.append(PageBreak())

    # ── TOC ──────────────────────────────────────────────────────────────────
    story.append(Paragraph("Содержание", ps("tt", fontName=FB, fontSize=20, textColor=DARK, spaceAfter=14)))
    story.append(HRFlowable(width="100%", thickness=2, color=BLUE, spaceAfter=12))
    toc = [
        ("1","ВВЕДЕНИЕ",[("1.1","Описание системы"),("1.2","Архитектура"),("1.3","Роли и обязанности")]),
        ("2","TELEGRAM-БОТ",[("2.1","Запуск и главное меню"),("2.2","Поиск недвижимости (10 шагов)"),
                             ("2.3","Добавление объявления"),("2.4","Избранное"),
                             ("2.5","Подписки и кабинет агента"),("2.6","Многоязычность"),
                             ("2.7","Уведомления")]),
        ("3","АНАЛИТИЧЕСКИЙ ДАШБОРД",[("3.1","Доступ и навигация"),("3.2","Главный экран — KPI"),
                                       ("3.3","Объявления"),("3.4","Пользователи"),
                                       ("3.5","Агенты vs Частные лица"),("3.6","Подписки"),
                                       ("3.7","Email-рассылка"),("3.8","Фильтрация по дате")]),
        ("4","BACK-OFFICE",[("4.1","Вход и безопасность"),("4.2","Объявления"),
                            ("4.3","Пользователи"),("4.4","Услуги"),
                            ("4.5","CRM"),("4.6","Email"),("4.7","Боковая панель")]),
        ("5","ПАРСИНГ И БАЗА ДАННЫХ",[("5.1","Источники"),("5.2","Расписание"),
                                       ("5.3","Хранение данных"),("5.4","Дедупликация")]),
        ("6","EMAIL-ОТЧЁТЫ",[("6.1","Агенты"),("6.2","Перевозчики / упаковщики"),("6.3","Шаблоны")]),
        ("7","FAQ И РЕШЕНИЕ ПРОБЛЕМ",[("7.1","Бот не отвечает"),("7.2","Объявления не показываются"),
                                       ("7.3","Дашборд"),("7.4","Email")]),
        ("8","БЫСТРЫЙ СПРАВОЧНИК",[("8.1","Команды бота"),("8.2","URL-адреса"),("8.3","Env переменные")]),
    ]
    for num, title, secs in toc:
        story.append(P(f"{num}.  {title}", "toc1"))
        for sn, st2 in secs:
            story.append(P(f"    {sn}  {st2}", "toc2"))
        story.append(Spacer(1,3))
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # CHAPTER 1
    # ══════════════════════════════════════════════════════════════════════════
    story += chapter_block("1","ВВЕДЕНИЕ","Общее описание платформы FlatFinderIL")
    story += section("1.1  Общее описание системы","🏠")
    story += body("FlatFinderIL — многофункциональная платформа для поиска и публикации объявлений о недвижимости в Израиле. Система состоит из трёх компонентов:")
    story += bullets(["Telegram-бот (@FlatFinderIL) — основной канал взаимодействия с пользователями",
                      "Аналитический дашборд — веб-интерфейс статистики",
                      "Back-office — защищённая админ-панель для администраторов"])
    story += body("Платформа поддерживает аренду и покупку, жилую и коммерческую недвижимость, три языка: русский, английский и иврит.")

    story += section("1.2  Архитектура","⚙️")
    story += kv_table([
        ("Язык",         "Python 3.11.6"),
        ("Фреймворк",    "python-telegram-bot v20.7 (ConversationHandler)"),
        ("База данных",  "JSON-файл listings_db.json на volume /data"),
        ("Email",        "Resend API (HTTP — Railway блокирует SMTP)"),
        ("Парсинг",      "Веб-скрапинг Telegram-каналов + Telethon API"),
        ("Деплой",       "Railway cloud — один публичный порт"),
    ])

    story += section("1.3  Роли и обязанности","👥")
    story += generic_table(
        ["Роль","Функции"],
        [["Администратор",    "Полный доступ к back-office, дашборду, управление объявлениями и пользователями"],
         ["Агент (риэлтор)",  "Публикует объявления, получает email-отчёты, имеет личный кабинет, CSV-загрузка"],
         ["Частное лицо",     "Публикует объявления, базовый доступ к поиску"],
         ["Пользователь",     "Поиск недвижимости, избранное, подписки на поиск"],
         ["Поставщик услуг",  "Перевозчики/упаковщики — регистрация в разделе услуг, еженедельные отчёты"]],
        [4*cm, W-4*cm-4*cm], bold_col0=True)
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # CHAPTER 2 — БОТ
    # ══════════════════════════════════════════════════════════════════════════
    story += chapter_block("2","TELEGRAM-БОТ","Полное руководство по функциям бота")

    story += section("2.1  Запуск и главное меню","🚀")
    story += body("Пользователь открывает чат с @FlatFinderIL и нажимает START или /start. Бот показывает главное меню с 12 инлайн-кнопками.")
    story += note("После первого запуска система запоминает язык пользователя. Изменить язык — кнопка 🌐 в меню.","info")
    story += generic_table(
        ["Кнопка","callback_data","Назначение"],
        [["🔍 Поиск",       "search",          "Запуск 10-шагового поиска недвижимости"],
         ["❤️ Избранное",    "favorites",       "Список сохранённых объявлений"],
         ["🏢 Коммерческая", "commercial",      "Поиск коммерческой недвижимости"],
         ["🔧 Услуги",       "services",        "Перевозчики, упаковщики, услуги"],
         ["📋 Мои объявл.",  "my_listings",     "Список объявлений пользователя"],
         ["➕ Добавить",     "add_listing",     "Добавление нового объявления"],
         ["🏠 Все объявл.", "all_listings",     "Все активные объявления"],
         ["❓ Помощь",       "help",            "Справка и контакты"],
         ["💎 Подписка",     "subscription",    "Тарифы и активация подписки"],
         ["📊 Мои подписки", "my_subscriptions","История и статус подписок"],
         ["👤 Кабинет",      "cabinet",         "Личный кабинет агента"],
         ["🌐 Язык",         "choose_lang",     "Смена языка интерфейса"]],
        [3.5*cm, 3.5*cm, W-4*cm-7*cm])

    story += section("2.2  Поиск недвижимости (10 шагов)","🔍")
    story += body("Поиск — пошаговый диалог (ConversationHandler). Каждый шаг показывает инлайн-кнопки. На любом шаге доступна кнопка Назад.")
    story += step_table([
        ("Шаг 1: Тип сделки",         "Аренда / Покупка"),
        ("Шаг 2: Тип недвижимости",    "Квартира, Дом, Вилла, Пентхаус, Студия, Дуплекс, Таунхаус, Земля, Гараж, Склад"),
        ("Шаг 3: Район",               "Тель-Авив, Иерусалим, Хайфа, Север, Юг, Центр и др."),
        ("Шаг 4: Город",               "Список городов выбранного района. Можно пропустить."),
        ("Шаг 5: Мин. комнат",         "От 1 до 6+ комнат. Кнопка 'Любое' пропускает фильтр."),
        ("Шаг 6: Макс. комнат",        "Верхняя граница по количеству комнат."),
        ("Шаг 7: Мин. цена (₪)",       "Нижняя граница цены. Диапазоны для аренды и покупки разные."),
        ("Шаг 8: Макс. цена (₪)",      "Верхняя граница цены. Кнопка 'Без ограничений'."),
        ("Шаг 9: Парковка",            "Есть / Нет / Не важно."),
        ("Шаг 10: Бассейн → Результаты","Есть / Нет / Не важно. После — показ карточек объявлений."),
    ])
    story += note("Если ничего не найдено — бот предлагает расширить критерии или сохранить поиск как подписку.","tip")

    story += section("2.3  Добавление объявления","➕")
    story += body("Добавление — многошаговый диалог. Первый шаг — тип продавца (ВАЖНО для аналитики и функциональных отличий).")
    story += sub("Шаг 0: Тип продавца")
    story += bullets(["🏢 Агент (риэлтор) — доступ к CSV-загрузке, кабинету агента, еженедельным отчётам",
                      "👤 Частное лицо — базовый доступ"])
    story += note("Значок [🏢 Агент] или [👤 Частное лицо] отображается на каждой карточке в поиске.","info")
    story += generic_table(
        ["#","Шаг","Описание"],
        [[str(i),t,d] for i,(t,d) in enumerate([
            ("Тип сделки",        "Аренда или Продажа"),
            ("Тип продавца",      "Агент / Частное лицо"),
            ("Тип недвижимости",  "Квартира, Дом, Вилла и т.д."),
            ("Район",             "Выбор из списка районов"),
            ("Город",             "Выбор из городов района"),
            ("Район города",      "Ввод вручную: напр. Флорентин"),
            ("Адрес",             "Улица и номер — автоматически создаётся ссылка на Google Maps"),
            ("Кол-во комнат",     "Число или выбор из кнопок"),
            ("Этаж",              "Номер этажа"),
            ("Площадь (кв.м)",    "Площадь квартиры"),
            ("Цена (₪)",          "Цена в шекелях"),
            ("Парковка",          "Есть / Нет"),
            ("Бассейн",           "Есть / Нет"),
            ("Укрытие (мамад)",   "Есть / Нет"),
            ("Лифт",              "Есть / Нет"),
            ("Инфраструктура",    "Школы, сады, транспорт и т.д."),
            ("Описание",          "Свободный текст"),
            ("Имя владельца",     "ФИО для контакта"),
            ("Телефон",           "Номер телефона"),
            ("Контакт Telegram",  "@ или номер"),
            ("Подтверждение",     "Превью + кнопки Опубликовать / Редактировать"),
        ],1)],
        [0.8*cm, 4.5*cm, W-4*cm-5.3*cm])
    story += note("После публикации пользователь получает приветственное сообщение в Telegram. Агенты с email — также письмо через Resend API.","ok")

    story += section("2.4  Избранное и управление объявлениями","❤️")
    story += body("Кнопка ❤️ под карточкой добавляет объявление в избранное. Доступ — кнопка главного меню.")
    story += sub("Управление своими объявлениями:")
    story += bullets(["Просмотр всех опубликованных объявлений",
                      "Деактивация / повторная активация",
                      "Удаление объявления",
                      "Редактирование отдельных полей"])

    story += section("2.5  Подписка и кабинет агента","💎")
    story += generic_table(
        ["Тариф","Цена","Период","Описание"],
        [["Тестовый",   "Бесплатно","До 15.04.2026","Полный доступ ко всем функциям"],
         ["Недельный",  "19.90 ₪",  "7 дней",       "Все функции поиска и публикации"],
         ["2-недельный","29.90 ₪",  "14 дней",      "Расширенный доступ"],
         ["Месячный",   "39.90 ₪",  "30 дней",      "Полный месячный доступ"]],
        [3.5*cm, 3*cm, 3*cm, W-4*cm-9.5*cm])
    story += sub("Кабинет агента включает:")
    story += bullets(["Статистика объявлений (всего / активных / просмотры)",
                      "График активности за 7 и 30 дней",
                      "Реферальная программа (личная ссылка)",
                      "Управление email для отчётов",
                      "CSV-загрузка нескольких объявлений (только агенты)"])

    story += section("2.6  Многоязычность","🌐")
    story += generic_table(
        ["Код","Язык","Направление","Особенности"],
        [["ru","Русский",          "Слева направо","Язык по умолчанию"],
         ["en","English",          "Слева направо","Стандартный английский"],
         ["he","Hebrew / Иврит",   "Справа налево (RTL)","Специальное RTL-форматирование"]],
        [1.5*cm, 3.5*cm, 4*cm, W-4*cm-9*cm])

    story += section("2.7  Уведомления","📨")
    story += bullets(["Приветственное сообщение в Telegram — после публикации объявления на языке пользователя",
                      "Приветственный email — если агент указал email (через Resend API)",
                      "Уведомление об окончании подписки — за 3 дня",
                      "Уведомление о просмотрах — агенту о новых просмотрах",
                      "Уведомление об устаревших объявлениях — после 30 дней"])
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # CHAPTER 3 — DASHBOARD
    # ══════════════════════════════════════════════════════════════════════════
    story += chapter_block("3","АНАЛИТИЧЕСКИЙ ДАШБОРД","Руководство по веб-интерфейсу аналитики")

    story += section("3.1  Доступ и навигация","🌐")
    story += kv_table([
        ("URL дашборда",   "https://flatfinderil-bot-production.up.railway.app/"),
        ("Back-office",    "https://flatfinderil-bot-production.up.railway.app/backoffice"),
        ("API аналитики",  "https://flatfinderil-bot-production.up.railway.app/analytics"),
        ("Авторизация",    "Дашборд открыт публично. Back-office — по паролю."),
        ("Кнопка входа",   "⚙️ Back-office — правый верхний угол дашборда"),
        ("Обновление",     "Автоматически каждые 30 сек. Кнопка ↻ — принудительное обновление."),
    ])

    story += section("3.2  Главный экран — KPI","📊")
    story += body("На главном экране — ключевые показатели в виде карточек. Данные берутся из /analytics endpoint.")
    story += bullets(["👥 Пользователи — общее число и уникальные за период",
                      "🔍 Поиски — количество запросов за выбранный период",
                      "🏠 Объявления — общее число и число из Telegram",
                      "💎 Подписки — активные подписки и расчётный доход",
                      "📧 Email-подписчики — агенты с настроенной почтой",
                      "💬 Конверсия — отношение просмотров к результатам поиска"])

    story += section("3.3  Вкладка Объявления","🏠")
    story += bullets(["Распределение по городам (горизонтальный bar-chart)",
                      "Источники парсинга (каналы @telegram с числом объявлений)",
                      "Пользовательские объявления (таблица с контактами)",
                      "График добавления по дням",
                      "Список активных каналов-источников"])

    story += section("3.4  Вкладка Пользователи / Кабинеты","👥")
    story += bullets(["Список агентов с числом объявлений и статусом подписки",
                      "Топ-агенты по числу объявлений и просмотрам",
                      "Последняя активность",
                      "Реферальная статистика — число приглашённых"])

    story += section("3.5  Вкладка Агент / Частные лица","🏢")
    story += bullets(["KPI: число объявлений от агентов и частных лиц",
                      "Средняя цена аренды и покупки по каждому сегменту",
                      "Топ-города для каждого типа",
                      "Последние объявления с типом продавца"])

    story += section("3.6  Подписки и монетизация","💎")
    story += bullets(["Число активных подписок по тарифам",
                      "Ожидаемый месячный доход (MRR)",
                      "Статус тестового периода",
                      "График активаций по дням"])
    story += note("Подписки хранятся в памяти. При перезапуске сбрасываются. Рекомендуется добавить постоянное хранение в listings_db.json.","warn")

    story += section("3.7  Вкладка Email-рассылка","📧")
    story += bullets(["Агенты с настроенным email",
                      "Перевозчики и упаковщики с email",
                      "Язык письма (ru / en / he)",
                      "Дата следующей рассылки (каждое воскресенье 10:00)",
                      "Число просмотров за период"])

    story += section("3.8  Фильтрация по дате","📅")
    story += body("Панель фильтров в верхней части дашборда — все KPI и графики пересчитываются.")
    story += bullets(["Сегодня — данные за текущий день",
                      "7 дней — последняя неделя",
                      "30 дней — последний месяц",
                      "Произвольный период — поля 'с' и 'по' с выбором даты"])
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # CHAPTER 4 — BACK-OFFICE
    # ══════════════════════════════════════════════════════════════════════════
    story += chapter_block("4","BACK-OFFICE (АДМИН-ПАНЕЛЬ)","Руководство администратора")

    story += section("4.1  Вход и безопасность","🔐")
    story += kv_table([
        ("URL",          "https://flatfinderil-bot-production.up.railway.app/backoffice"),
        ("Вход",         "⚙️ Back-office — правый верхний угол дашборда"),
        ("Пароль",       "FlatFinderIL2026  (переменная BACKOFFICE_PASSWORD в Railway)"),
        ("Сессия",       "Cookie bo_session, действует 24 часа"),
        ("Выход",        "Кнопка Выйти в боковой панели back-office"),
    ])
    story += note("При компрометации пароля — измените BACKOFFICE_PASSWORD в Railway Variables и перезапустите сервис.","warn")

    story += section("4.2  Управление объявлениями","🏠")
    story += body("Полный список всех объявлений (включая неактивные) с фильтрацией и поиском.")
    story += bullets(["Фильтры: город, тип сделки, тип недвижимости, статус (активное/неактивное)",
                      "Текстовый поиск по заголовку и описанию",
                      "Клик на строку — открывает боковую панель с деталями"])
    story += sub("Детальная панель объявления:")
    story += bullets(["Все поля: тип, город, район, адрес, этаж, площадь, цена",
                      "Контакт продавца — кликабельный номер tel:",
                      "Ссылка на Google Maps (если указан адрес)",
                      "Тип продавца: 🏢 Агент или 👤 Частное лицо",
                      "Дата добавления и число просмотров",
                      "Кнопки: Деактивировать / Удалить (необратимо)"])

    story += section("4.3  Управление пользователями","👥")
    story += bullets(["ID и @username пользователя Telegram",
                      "Язык интерфейса, статус агента",
                      "Email, телефон агента",
                      "Число добавленных объявлений",
                      "Дата первого/последнего обращения"])
    story += sub("Детальная панель пользователя:")
    story += bullets(["Профиль агента с контактами",
                      "Список всех объявлений пользователя",
                      "Статистика просмотров и реферальные данные"])

    story += section("4.4  Поставщики услуг","🔧")
    story += generic_table(
        ["Поле","Описание"],
        [["Название",     "Компания или имя поставщика"],
         ["Тип услуги",   "Перевозчики (movers) / Упаковщики (packers) / Другие"],
         ["Телефон",      "Кликабельный tel: для прямого звонка"],
         ["Email",        "Ссылка mailto:"],
         ["Telegram",     "@ контакт"],
         ["Регион",       "Город/регион работы"],
         ["Статус",       "Активный / Неактивный"]],
        [3.5*cm, W-4*cm-3.5*cm])

    story += section("4.5  CRM — контакты и сделки","📋")
    story += body("Инструмент для ведения контактов и отслеживания сделок (доступен только через back-office).")
    story += bullets(["Список контактов: имя, телефон, email",
                      "Статус: новый / в работе / закрыта / отказ",
                      "История взаимодействий",
                      "Привязка контакта к объявлению",
                      "Воронка продаж"])

    story += section("4.6  Email-подписчики","📧")
    story += bullets(["Агенты с email: имя, адрес, язык, дата следующей рассылки",
                      "Поставщики услуг с email",
                      "Кнопка Отправить сейчас — ручной запуск для конкретного пользователя",
                      "Кнопка Разослать всем — ручной запуск еженедельной рассылки",
                      "Статус последней отправки (OK / Ошибка)"])

    story += section("4.7  Боковая детальная панель","↗️")
    story += body("Slide-in панель справа открывается при клике на любую строку таблицы — без перехода на новую страницу.")
    story += bullets(["Плавная анимация появления справа",
                      "Закрытие по клику на крестик или вне панели",
                      "Телефон — ссылка tel: для быстрого звонка",
                      "Email — ссылка mailto:",
                      "Google Maps — ссылка для адресов объявлений"])
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # CHAPTER 5 — ПАРСИНГ
    # ══════════════════════════════════════════════════════════════════════════
    story += chapter_block("5","ПАРСИНГ И БАЗА ДАННЫХ","Автоматический сбор объявлений")

    story += section("5.1  Источники данных","📡")
    story += generic_table(
        ["Канал","Описание"],
        [["@israel_rent",          "Аренда по Израилю (общий)"],
         ["@tlvapartments",        "Тель-Авив — аренда и продажа"],
         ["@israelrealestate",     "Недвижимость Израиля"],
         ["@israel_apartments",    "Квартиры по всему Израилю"],
         ["@izrailnedvizimosti",   "Недвижимость на русском"],
         ["@isra_home_arenda",     "Аренда квартир"],
         ["@nagariyaapartments",   "Нагария — аренда и продажа"],
         ["@ashdod_rent",          "Ашдод — аренда"],
         ["@happy_home_ashkelon",  "Ашкелон — недвижимость"],
         ["@haifa_arenda",         "Хайфа — аренда"],
         ["@israel_home",          "Дома в Израиле"]],
        [5*cm, W-4*cm-5*cm])

    story += section("5.2  Расписание парсинга","⏰")
    story += kv_table([
        ("Первый запуск",    "Глубокий парсинг: limit=500 на канал (~15-20 мин)"),
        ("Регулярный цикл",  "Каждые 30 минут: limit=50 на канал (~2 мин)"),
        ("Метод",            "Веб-скрапинг https://t.me/s/CHANNEL (без авторизации)"),
        ("Резервный метод",  "Telethon API (если указан SESSION_STRING)"),
        ("Прирост",          "~130-150 новых объявлений за первые сутки"),
    ])

    story += section("5.3  Хранение данных","💾")
    story += kv_table([
        ("Файл БД",       "/data/listings_db.json (Railway volume)"),
        ("DATA_DIR",      "Переменная окружения DATA_DIR=/data"),
        ("Volume",        "flatfinderil-bot-volume (Railway persistent disk)"),
        ("Резерв",        "listings_db.json в репозитории (25 базовых объявлений для старта)"),
        ("Структура",     "listings{}, favorites{}, user_listings{}, subscriptions{}, next_id"),
    ])
    story += note("Volume /data сохраняется при перезапусках и деплоях. Данные НЕ теряются при обновлении кода.","ok")

    story += section("5.4  Дедупликация","🔄")
    story += bullets(["По URL источника (source_url) — если URL совпадает, пропускается",
                      "По заголовку (первые 100 символов) — для постов без URL",
                      "url_exists() — проверка перед каждым сохранением",
                      "_dedup_listings() — запускается при старте сервиса"])
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # CHAPTER 6 — EMAIL
    # ══════════════════════════════════════════════════════════════════════════
    story += chapter_block("6","EMAIL-ОТЧЁТЫ","Автоматическая рассылка для агентов и поставщиков")

    story += section("6.1  Отчёты для агентов","📊")
    story += body("Каждое воскресенье в 10:00 (Израильское время) всем агентам с email отправляется персональный отчёт.")
    story += sub("Содержание отчёта:")
    story += bullets(["Количество активных объявлений агента",
                      "Просмотры за прошедшую неделю",
                      "Самое популярное объявление",
                      "Статус подписки",
                      "Рекомендации (если объявления устарели)"])
    story += kv_table([
        ("Провайдер",   "Resend API (re_RU9HGMoS_...)"),
        ("FROM",        "onboarding@resend.dev"),
        ("Расписание",  "Каждое воскресенье в 10:00 IL (UTC+3)"),
        ("Тест",        "Команда /testemail в боте — отправляет себе тестовый отчёт"),
    ])

    story += section("6.2  Отчёты для перевозчиков / упаковщиков","🚚")
    story += bullets(["То же расписание (воскресенье 10:00)",
                      "Статистика просмотров их страницы услуг",
                      "Язык письма = язык регистрации в боте"])

    story += section("6.3  Шаблоны и язык","✉️")
    story += bullets(["ru — письмо полностью на русском",
                      "en — письмо на английском",
                      "he — письмо на иврите (RTL-форматирование)"])
    story += note("Если Resend недоступен — ошибка логируется, бот продолжает работу нормально.","info")
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # CHAPTER 7 — FAQ
    # ══════════════════════════════════════════════════════════════════════════
    story += chapter_block("7","FAQ И РЕШЕНИЕ ПРОБЛЕМ","Диагностика типичных ситуаций")

    story += section("7.1  Бот не отвечает","🤖")
    story += generic_table(
        ["Симптом","Причина","Решение"],
        [["Нет ответа на /start",  "Сервис упал на Railway",     "Открыть Railway → проверить deployment. Если FAILED — смотреть логи."],
         ["Зависает на шаге поиска","Конфликт ConversationHandler","Написать /start для сброса состояния"],
         ["Один язык не работает", "Нет перевода в i18n.py",     "Добавить ключ в i18n.py → деплой"],
         ["BOT_TOKEN недействителен","Токен отозван",             "Создать новый токен через @BotFather → обновить BOT_TOKEN в Railway"]],
        [3.5*cm, 4.5*cm, W-4*cm-8*cm])

    story += section("7.2  Объявления не показываются","🏠")
    story += bullets(["Проверить /analytics — поле listings.total. Если 0 — парсер не работает",
                      "Проверить логи Railway на ошибки парсинга",
                      "Убедиться, что объявления активные (active: true)",
                      "Проверить фильтры поиска — возможно слишком строгие критерии"])

    story += section("7.3  Дашборд не обновляется","📊")
    story += bullets(["Нажать кнопку ↻ для принудительного обновления",
                      "Проверить URL /analytics в браузере — должен вернуть JSON",
                      "404 на /analytics — сервис не запущен, проверить Railway",
                      "Очистить кэш браузера (Ctrl+Shift+R)"])

    story += section("7.4  Письма не приходят","📧")
    story += bullets(["Проверить логи Railway на ошибки Resend API",
                      "Убедиться, что RESEND_API_KEY установлен правильно",
                      "Тест: команда /testemail в боте",
                      "Resend бесплатный план: FROM = onboarding@resend.dev",
                      "Проверить папку СПАМ у получателя"])
    story.append(PageBreak())

    # ══════════════════════════════════════════════════════════════════════════
    # CHAPTER 8 — СПРАВОЧНИК
    # ══════════════════════════════════════════════════════════════════════════
    story += chapter_block("8","БЫСТРЫЙ СПРАВОЧНИК","Команды, URL-адреса и переменные")

    story += section("8.1  Команды бота","⌨️")
    story += kv_table([
        ("/start",      "Главное меню. Сбрасывает незавершённые диалоги."),
        ("/search",     "Прямой запуск поиска недвижимости"),
        ("/add",        "Прямой запуск добавления объявления"),
        ("/listings",   "Список своих объявлений"),
        ("/help",       "Справка и контакты поддержки"),
        ("/cabinet",    "Открыть кабинет агента"),
        ("/refer",      "Реферальная программа — получить ссылку"),
        ("/testemail",  "Отправить тестовый email-отчёт (для агентов)"),
        ("/cancel",     "Отменить текущий диалог"),
    ])

    story += section("8.2  URL-адреса сервисов","🌐")
    story += kv_table([
        ("Дашборд",         "https://flatfinderil-bot-production.up.railway.app/"),
        ("API аналитики",   "https://flatfinderil-bot-production.up.railway.app/analytics"),
        ("Back-office",     "https://flatfinderil-bot-production.up.railway.app/backoffice"),
        ("Telegram-бот",    "https://t.me/FlatFinderIL"),
        ("Railway проект",  "https://railway.app → проект exemplary-nurturing"),
        ("Resend дашборд",  "https://resend.com/emails"),
    ])

    story += section("8.3  Переменные окружения Railway","⚙️")
    story += generic_table(
        ["Переменная","Описание","Обязательна"],
        [["BOT_TOKEN",          "Telegram Bot API token от @BotFather",                "Да"],
         ["DATA_DIR",           "/data — путь к persistent volume",                    "Да"],
         ["PORT",               "Порт веб-сервера (дашборд + back-office)",            "Да"],
         ["BACKOFFICE_PASSWORD","Пароль для back-office (по умолч. FlatFinderIL2026)", "Да"],
         ["RESEND_API_KEY",     "API ключ Resend для email-рассылок",                  "Для email"],
         ["SESSION_STRING",     "Telethon session для авторизованного парсинга",       "Нет"]],
        [5*cm, 9*cm, 2*cm])

    story.append(Spacer(1,1*cm))
    W2, _ = A4
    end = Table([[P("FlatFinderIL — Учебное пособие для персонала v1.0  |  Март 2026\n"
                    "По вопросам обновления документа обращайтесь к администратору системы.", "end")]],
                colWidths=[W2-4*cm])
    end.setStyle(TableStyle([
        ("FONTNAME",     (0,0),(-1,-1), F),
        ("BACKGROUND",   (0,0),(-1,-1), LGRAY),
        ("BOX",          (0,0),(-1,-1), 0.5, MGRAY),
        ("TOPPADDING",   (0,0),(-1,-1), 10),
        ("BOTTOMPADDING",(0,0),(-1,-1), 10),
        ("LEFTPADDING",  (0,0),(-1,-1), 14),
    ]))
    story.append(end)

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    size = os.path.getsize(OUTPUT)
    print(f"PDF создан: {OUTPUT}")
    print(f"Страниц и размер проверяются отдельно. Размер файла: {size//1024} KB")

if __name__ == "__main__":
    build_pdf()
