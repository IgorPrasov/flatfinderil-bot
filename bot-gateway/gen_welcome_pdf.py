#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

OUTPUT = "/Users/alinatsarenko/projects/flatfinderil-bot/FlatFinderIL_Welcome_Messages.pdf"
SUPP = "/System/Library/Fonts/Supplemental/"
pdfmetrics.registerFont(TTFont("MF",  SUPP+"Arial.ttf"))
pdfmetrics.registerFont(TTFont("MFB", SUPP+"Arial Bold.ttf"))
F, FB = "MF", "MFB"

BLUE   = colors.HexColor("#2AABEE")
DARK   = colors.HexColor("#1a1a2e")
GREEN  = colors.HexColor("#27AE60")
ORANGE = colors.HexColor("#EF9F27")
LGRAY  = colors.HexColor("#F5F7FA")
MGRAY  = colors.HexColor("#E2E8F0")
WHITE  = colors.white
TEXT   = colors.HexColor("#333333")

def ps(name, **kw):
    d = dict(fontName=F, fontSize=10, textColor=TEXT, leading=15)
    d.update(kw)
    return ParagraphStyle(name, **d)

W, H = A4

def P(text, **kw):
    return Paragraph(str(text), ps("x", **kw))

def badge(text, bg, fg=WHITE):
    t = Table([[P(text, fontName=FB, fontSize=9, textColor=fg, alignment=TA_CENTER, leading=12)]],
              colWidths=[5*cm], rowHeights=[0.6*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),bg),
        ("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
    ]))
    return t

def msg_block(title_badge, badge_color, lines, rtl=False):
    """One message block: badge + message bubble."""
    W2 = W - 4*cm
    align = TA_RIGHT if rtl else TA_LEFT
    # Build content paragraphs
    content = []
    for line in lines:
        if line == "---":
            content.append(Spacer(1, 5))
        elif line.startswith("**") and line.endswith("**"):
            content.append(P(line[2:-2], fontName=FB, fontSize=10.5, textColor=DARK, leading=15, alignment=align))
        elif line.startswith("•"):
            indent = 20 if not rtl else 0
            content.append(P(line, fontName=F, fontSize=10, textColor=TEXT, leading=14,
                              leftIndent=indent, alignment=align))
        else:
            content.append(P(line, fontName=F, fontSize=10, textColor=TEXT, leading=15, alignment=align))
        content.append(Spacer(1, 3))

    # Wrap in bubble table
    rows = [[c] for c in content]
    inner = Table(rows, colWidths=[W2 - 2.2*cm])
    inner.setStyle(TableStyle([
        ("FONTNAME",(0,0),(-1,-1),F),
        ("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),
        ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0),
    ]))
    bubble = Table([[inner]], colWidths=[W2 - 0.4*cm])
    bubble.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),LGRAY),
        ("BOX",(0,0),(-1,-1),0.8,MGRAY),
        ("LEFTPADDING",(0,0),(-1,-1),14),("RIGHTPADDING",(0,0),(-1,-1),14),
        ("TOPPADDING",(0,0),(-1,-1),12),("BOTTOMPADDING",(0,0),(-1,-1),12),
        ("FONTNAME",(0,0),(-1,-1),F),
    ]))
    return [badge(title_badge, badge_color), Spacer(1,6), bubble, Spacer(1,14)]

def section_divider(title):
    W2 = W - 4*cm
    t = Table([[P(title, fontName=FB, fontSize=11, textColor=WHITE, alignment=TA_CENTER, leading=14)]],
              colWidths=[W2])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),DARK),
        ("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8),
        ("FONTNAME",(0,0),(-1,-1),FB),
    ]))
    return [Spacer(1,10), t, Spacer(1,12)]

def on_page(canvas, doc):
    canvas.saveState()
    if doc.page > 1:
        canvas.setStrokeColor(BLUE); canvas.setLineWidth(0.5)
        canvas.line(2*cm, H-1.5*cm, W-2*cm, H-1.5*cm)
        canvas.setFont(FB,8); canvas.setFillColor(BLUE)
        canvas.drawString(2*cm, H-1.2*cm, "FlatFinderIL")
        canvas.setFont(F,8); canvas.setFillColor(colors.HexColor("#888"))
        canvas.drawRightString(W-2*cm, H-1.2*cm, "Приветственные сообщения · Welcome Messages")
        canvas.setStrokeColor(MGRAY)
        canvas.line(2*cm, 1.5*cm, W-2*cm, 1.5*cm)
        canvas.setFont(F,8); canvas.setFillColor(colors.HexColor("#888"))
        canvas.drawString(2*cm, 1.0*cm, "FlatFinderIL © 2026")
        canvas.drawRightString(W-2*cm, 1.0*cm, f"Стр. {doc.page}")
    canvas.restoreState()

doc = SimpleDocTemplate(OUTPUT, pagesize=A4,
    leftMargin=2*cm, rightMargin=2*cm, topMargin=2.2*cm, bottomMargin=2.2*cm,
    title="FlatFinderIL — Welcome Messages")

story = []
W2 = W - 4*cm

# ── COVER ──────────────────────────────────────────────────────────────────
story.append(Spacer(1, 1.5*cm))
cov = Table([[P("🏠  FlatFinderIL", fontName=FB, fontSize=28, textColor=WHITE,
                alignment=TA_CENTER, leading=34)]],
            colWidths=[W2])
cov.setStyle(TableStyle([
    ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#1a1a2e")),
    ("TOPPADDING",(0,0),(-1,-1),22),("BOTTOMPADDING",(0,0),(-1,-1),22),
    ("FONTNAME",(0,0),(-1,-1),FB),
]))
story.append(cov)

sub = Table([[P("Приветственные сообщения при публикации объявлений",
               fontName=F, fontSize=13, textColor=colors.HexColor("#444"),
               alignment=TA_CENTER, leading=18)]],
            colWidths=[W2])
sub.setStyle(TableStyle([
    ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#EBF5FB")),
    ("TOPPADDING",(0,0),(-1,-1),12),("BOTTOMPADDING",(0,0),(-1,-1),12),
    ("FONTNAME",(0,0),(-1,-1),F),
]))
story.append(sub)
story.append(Spacer(1,0.5*cm))

info = Table([
    [P("Тип сообщений:", fontName=FB, fontSize=10, textColor=WHITE),
     P("Агент · Частное лицо · Поставщик услуг", fontName=F, fontSize=10, textColor=TEXT)],
    [P("Языки:", fontName=FB, fontSize=10, textColor=WHITE),
     P("Русский (RU) · English (EN) · Hebrew / עברית (HE)", fontName=F, fontSize=10, textColor=TEXT)],
    [P("Всего шаблонов:", fontName=FB, fontSize=10, textColor=WHITE),
     P("9 (3 типа × 3 языка)", fontName=F, fontSize=10, textColor=TEXT)],
    [P("Канал доставки:", fontName=FB, fontSize=10, textColor=WHITE),
     P("Telegram + Email (Resend API)", fontName=F, fontSize=10, textColor=TEXT)],
], colWidths=[4*cm, W2-4*cm])
info.setStyle(TableStyle([
    ("BACKGROUND",(0,0),(0,-1),DARK),("BACKGROUND",(1,0),(1,-1),LGRAY),
    ("FONTNAME",(0,0),(-1,-1),F),
    ("GRID",(0,0),(-1,-1),0.3,MGRAY),
    ("LEFTPADDING",(0,0),(-1,-1),10),("TOPPADDING",(0,0),(-1,-1),7),
    ("BOTTOMPADDING",(0,0),(-1,-1),7),
]))
story.append(info)
story.append(Spacer(1, 1*cm))

# legend
leg_data = [
    [badge("🏢  Агент (риэлтор)", BLUE),
     badge("👤  Частное лицо", GREEN),
     badge("🚚  Услуги", ORANGE)],
    [P("Профессиональный агент\nпо недвижимости", fontName=F, fontSize=9,
       textColor=colors.HexColor("#555"), alignment=TA_CENTER, leading=13),
     P("Собственник,\nпродаёт без посредников", fontName=F, fontSize=9,
       textColor=colors.HexColor("#555"), alignment=TA_CENTER, leading=13),
     P("Перевозчики,\nупаковщики и др.", fontName=F, fontSize=9,
       textColor=colors.HexColor("#555"), alignment=TA_CENTER, leading=13)],
]
leg = Table(leg_data, colWidths=[W2/3]*3)
leg.setStyle(TableStyle([
    ("FONTNAME",(0,0),(-1,-1),F),
    ("ALIGN",(0,0),(-1,-1),"CENTER"),
    ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
    ("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8),
    ("GRID",(0,0),(-1,-1),0.3,MGRAY),
    ("BACKGROUND",(0,0),(-1,-1),LGRAY),
]))
story.append(leg)

# ══════════════════════════════════════════════════════
# SECTION 1 — AGENT
# ══════════════════════════════════════════════════════
story += section_divider("РАЗДЕЛ 1  ·  🏢 АГЕНТ (РИЭЛТОР)  ·  3 языка")

story += msg_block("🏢  Агент — Русский (RU)", BLUE, [
    "🏢  FlatFinderIL — Объявление опубликовано!",
    "---",
    "Здравствуйте, Иван! Ваше объявление уже доступно для поиска тысячам пользователей.",
    "---",
    "📋 ID: #1042",
    "📍 Тель-Авив  ·  Аренда  ·  5 500 ₪",
    "---",
    "**Что дальше?**",
    "• Раз в неделю вы получите отчёт о просмотрах на email",
    "• Заинтересованные покупатели свяжутся с вами напрямую",
    "• Управляйте объявлением в разделе 📋 Мои объявления",
    "---",
    "Желаем успешной сделки! 🤝",
])

story += msg_block("🏢  Agent — English (EN)", BLUE, [
    "🏢  FlatFinderIL — Listing Published!",
    "---",
    "Hello, Ivan! Your listing is now live and searchable by thousands of users.",
    "---",
    "📋 ID: #1042",
    "📍 Tel Aviv  ·  Rent  ·  5,500 ₪",
    "---",
    "**What's next?**",
    "• You'll receive a weekly views report to your email",
    "• Interested buyers will contact you directly",
    "• Manage your listing in 📋 My Listings",
    "---",
    "Wishing you a successful deal! 🤝",
])

story += msg_block("🏢  סוכן — עברית (HE)", BLUE, [
    "🏢  FlatFinderIL — המודעה פורסמה!",
    "---",
    "שלום, איבן! המודעה שלך פעילה ומאות משתמשים יכולים למצוא אותה.",
    "---",
    "📋 מזהה: #1042",
    "📍 תל אביב  ·  שכירות  ·  5,500 ₪",
    "---",
    "**מה הלאה?**",
    "• תקבל/י דוח שבועי על צפיות לאימייל שלך",
    "• קונים מתעניינים יפנו אליך ישירות",
    "• נהל/י את המודעה תחת 📋 המודעות שלי",
    "---",
    "בהצלחה בעסקה! 🤝",
], rtl=True)

# ══════════════════════════════════════════════════════
# SECTION 2 — PRIVATE
# ══════════════════════════════════════════════════════
story += section_divider("РАЗДЕЛ 2  ·  👤 ЧАСТНОЕ ЛИЦО  ·  3 языка")

story += msg_block("👤  Частное лицо — Русский (RU)", GREEN, [
    "🏠  FlatFinderIL — Объявление опубликовано!",
    "---",
    "Привет, Михаил! Ваше объявление успешно размещено!",
    "---",
    "📋 ID: #1042",
    "📍 Тель-Авив  ·  Аренда  ·  5 500 ₪",
    "---",
    "Пользователи уже находят его в поиске. Как только кто-то захочет связаться — мы пришлём вам уведомление.",
    "---",
    "Управляйте объявлением через 📋 Мои объявления.",
    "---",
    "Удачи! 🙌",
])

story += msg_block("👤  Private — English (EN)", GREEN, [
    "🏠  FlatFinderIL — Listing Published!",
    "---",
    "Hi, Michael! Your listing is now live!",
    "---",
    "📋 ID: #1042",
    "📍 Tel Aviv  ·  Rent  ·  5,500 ₪",
    "---",
    "Users can already find your listing in search. We'll notify you as soon as someone wants to get in touch.",
    "---",
    "Manage your listing under 📋 My Listings.",
    "---",
    "Good luck! 🙌",
])

story += msg_block("👤  פרטי — עברית (HE)", GREEN, [
    "🏠  FlatFinderIL — המודעה פורסמה!",
    "---",
    "היי, מיכאל! המודעה שלך עלתה לאוויר!",
    "---",
    "📋 מזהה: #1042",
    "📍 תל אביב  ·  שכירות  ·  5,500 ₪",
    "---",
    "משתמשים כבר יכולים למצוא את המודעה שלך. נשלח לך התראה כשמישהו ירצה ליצור קשר.",
    "---",
    "נהל/י את המודעה תחת 📋 המודעות שלי.",
    "---",
    "!בהצלחה 🙌",
], rtl=True)

# ══════════════════════════════════════════════════════
# SECTION 3 — SERVICES
# ══════════════════════════════════════════════════════
story += section_divider("РАЗДЕЛ 3  ·  🚚 УСЛУГИ (ПЕРЕВОЗЧИКИ / УПАКОВЩИКИ)  ·  3 языка")

story += msg_block("🚚  Услуги — Русский (RU)", ORANGE, [
    "🚚  FlatFinderIL — Услуга опубликована!",
    "---",
    "Здравствуйте, ООО Переезд! Ваша услуга успешно размещена на платформе.",
    "---",
    "📋 Категория: Перевозчики",
    "---",
    "Клиенты уже могут найти вас через раздел 🔧 Услуги. Каждую неделю вы будете получать отчёт о просмотрах.",
    "---",
    "Желаем много заявок! 💼",
])

story += msg_block("🚚  Services — English (EN)", ORANGE, [
    "🚚  FlatFinderIL — Service Published!",
    "---",
    "Hello, Moving Pro! Your service is now live on the platform.",
    "---",
    "📋 Category: Movers",
    "---",
    "Clients can already find you through the 🔧 Services section. You will receive a weekly views report.",
    "---",
    "Wishing you many clients! 💼",
])

story += msg_block("🚚  שירותים — עברית (HE)", ORANGE, [
    "🚚  FlatFinderIL — השירות פורסם!",
    "---",
    "שלום, Moving Pro! השירות שלך פעיל בפלטפורמה.",
    "---",
    "📋 קטגוריה: הובלות",
    "---",
    "לקוחות כבר יכולים למצוא אותך בסעיף 🔧 שירותים. כל שבוע תקבל/י דוח על צפיות.",
    "---",
    "!בהצלחה עם הלקוחות 💼",
], rtl=True)

# Footer
story.append(Spacer(1, 0.5*cm))
ft = Table([[P("FlatFinderIL © 2026  ·  9 шаблонов сообщений  ·  RU / EN / HE",
               fontName=F, fontSize=9, textColor=colors.HexColor("#aaa"), alignment=TA_CENTER)]],
           colWidths=[W2])
ft.setStyle(TableStyle([
    ("BACKGROUND",(0,0),(-1,-1),LGRAY),
    ("TOPPADDING",(0,0),(-1,-1),10),("BOTTOMPADDING",(0,0),(-1,-1),10),
    ("FONTNAME",(0,0),(-1,-1),F),
]))
story.append(ft)

doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
size = os.path.getsize(OUTPUT)
print(f"PDF: {OUTPUT}  ({size//1024} KB)")
