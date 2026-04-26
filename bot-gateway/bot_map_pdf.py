"""
Generate FlatFinderIL Bot Map PDF.
Call generate() -> bytes
Call generate_safe() -> (bytes, mime_type, filename) — never raises; falls back
to a minimal stdlib-only PDF if reportlab is unavailable or crashes.
"""
import io
import logging
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

BLUE      = colors.HexColor("#2AABEE")
DARK      = colors.HexColor("#1a1a2e")
MID       = colors.HexColor("#2d3561")
LIGHT_BG  = colors.HexColor("#f0f8ff")
GRAY      = colors.HexColor("#666666")
GREEN     = colors.HexColor("#4CAF50")
ORANGE    = colors.HexColor("#FF9800")
RED_C     = colors.HexColor("#e74c3c")
WHITE     = colors.white
LIGHT_GRAY= colors.HexColor("#f5f5f5")
TEAL      = colors.HexColor("#009688")
PURPLE    = colors.HexColor("#9c27b0")


def S(name, **kw):
    return ParagraphStyle(name, **kw)


def generate() -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm
    )

    W = A4[0] - 3*cm

    h1 = S("H1", fontSize=22, textColor=WHITE, spaceAfter=4, alignment=TA_CENTER,
            fontName="Helvetica-Bold")
    h2 = S("H2", fontSize=14, textColor=WHITE, spaceAfter=2, fontName="Helvetica-Bold")
    h3 = S("H3", fontSize=11, textColor=DARK, spaceAfter=2, fontName="Helvetica-Bold",
            spaceBefore=6)
    body = S("Body", fontSize=9, textColor=DARK, spaceAfter=3, leading=13)
    small= S("Small", fontSize=8, textColor=GRAY, spaceAfter=2, leading=11)
    bullet=S("Bullet", fontSize=9, textColor=DARK, spaceAfter=2, leading=12,
              leftIndent=12, bulletIndent=0)
    center=S("Center", fontSize=9, textColor=GRAY, alignment=TA_CENTER)
    tag_s=S("Tag", fontSize=8, textColor=WHITE, alignment=TA_CENTER,
             fontName="Helvetica-Bold")

    story = []

    # --- COVER ---
    def cover_table():
        data = [[Paragraph("[HOME] FlatFinderIL Bot", h1)],
                [Paragraph("Polnaya karta funktsiy i arkhitektury", S("sub", fontSize=13,
                  textColor=colors.HexColor("#cce8ff"), alignment=TA_CENTER, spaceAfter=2))],
                [Paragraph("Versiya 1.0 · Aprel 2026", S("ver", fontSize=10,
                  textColor=colors.HexColor("#aaccee"), alignment=TA_CENTER))],
               ]
        t = Table(data, colWidths=[W])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), DARK),
            ("TOPPADDING",  (0,0), (-1,-1), 18),
            ("BOTTOMPADDING",(0,0),(-1,-1), 18),
            ("LEFTPADDING", (0,0), (-1,-1), 20),
            ("RIGHTPADDING",(0,0), (-1,-1), 20),
        ]))
        return t

    story.append(cover_table())
    story.append(Spacer(1, 0.4*cm))

    # --- Stats bar ---
    def stat_card(label, value, bg):
        inner = Table([[Paragraph(value, S("sv", fontSize=13, fontName="Helvetica-Bold",
                                   textColor=WHITE, alignment=TA_CENTER))],
                       [Paragraph(label, S("sl", fontSize=8, textColor=colors.HexColor("#ccddee"),
                                   alignment=TA_CENTER))],
                      ], colWidths=[W/5 - 0.3*cm])
        inner.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,-1), bg),
            ("TOPPADDING",(0,0),(-1,-1), 8),
            ("BOTTOMPADDING",(0,0),(-1,-1), 8),
        ]))
        return inner

    stats = Table([[
        stat_card("Shagov poiska", "10", MID),
        stat_card("Gorodov", "23", TEAL),
        stat_card("Tarifov", "4", colors.HexColor("#e67e22")),
        stat_card("Yazykov", "3", PURPLE),
        stat_card("Funktsiy", "20+", colors.HexColor("#27ae60")),
    ]], colWidths=[W/5]*5, hAlign="CENTER")
    stats.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),3),("RIGHTPADDING",(0,0),(-1,-1),3)]))
    story.append(stats)
    story.append(Spacer(1, 0.4*cm))

    # --- Section header helper ---
    def section(title, color=BLUE):
        t = Table([[Paragraph(title, h2)]], colWidths=[W])
        t.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,-1), color),
            ("TOPPADDING",(0,0),(-1,-1), 7),
            ("BOTTOMPADDING",(0,0),(-1,-1), 7),
            ("LEFTPADDING",(0,0),(-1,-1), 12),
        ]))
        return t

    def row_table(rows, col_widths, header=None, alt=True):
        data = []
        if header:
            data.append([Paragraph(h, S("th", fontSize=9, fontName="Helvetica-Bold",
                        textColor=WHITE)) for h in header])
        for row in rows:
            data.append([Paragraph(str(c), body) if isinstance(c, str) else c for c in row])
        t = Table(data, colWidths=col_widths)
        style = [
            ("GRID",(0,0),(-1,-1), 0.5, colors.HexColor("#dddddd")),
            ("TOPPADDING",(0,0),(-1,-1), 5),
            ("BOTTOMPADDING",(0,0),(-1,-1), 5),
            ("LEFTPADDING",(0,0),(-1,-1), 7),
            ("VALIGN",(0,0),(-1,-1),"TOP"),
        ]
        if header:
            style += [("BACKGROUND",(0,0),(-1,0), MID),
                      ("TEXTCOLOR",(0,0),(-1,0), WHITE)]
        if alt:
            for i in range(1 if header else 0, len(data), 2):
                style.append(("BACKGROUND",(0,i),(-1,i), LIGHT_BG))
        t.setStyle(TableStyle(style))
        return t

    def bullets(items):
        return [Paragraph(f"<bullet>&bull;</bullet> {item}", bullet) for item in items]

    # 1. COMMANDS
    story.append(section("1. Komandy bota"))
    story.append(Spacer(1, 0.2*cm))
    cmds = [
        ["/start",    "Glavnoye menyu, privetstviye, vybor yazyka"],
        ["/search",   "Nachat' poisk nedvizhimosti (10-shagovyy filtr)"],
        ["/add",      "Dobavit' ob'yavleniye (18+ shagov)"],
        ["/listings", "Moi ob'yavleniya — lichnyy kabinet"],
        ["/cabinet",  "Panel' agenta"],
        ["/refer",    "Referalnaya programma — podelit'sya ssylkoy"],
        ["/help",     "Pomoshch' i spisok komand"],
        ["/testemail","(Admin) Otpravit' testovyy email-otchyot"],
        ["/testpay",  "(Admin) Simulyatsiya uspeshnogo platezha"],
    ]
    story.append(row_table(cmds, [3.5*cm, W-3.5*cm],
                 header=["Komanda", "Opisaniye"]))
    story.append(Spacer(1, 0.3*cm))

    # 2. SEARCH FLOW
    story.append(section("2. Potok poiska nedvizhimosti (10 shagov)", MID))
    story.append(Spacer(1, 0.2*cm))
    search_steps = [
        ["1",  "Tip sdelki",          "Kupit' / Snyat' / Subrarenda"],
        ["2",  "Tip ob'yekta",        "Kvartira, dom, villa, pentkhaus, studiya, dupleks (multi-vybor)"],
        ["3",  "Rayon",               "Tel'-Aviv, Iyerusalim, Khayfa, Sheron, Tsentr, Yug / Ves' Izrail'"],
        ["4",  "Gorod",               "23 goroda (multi-vybor) / Lyuboy gorod"],
        ["5",  "Komnat (minimum)",    "1 / 1.5 / 2 / 2.5 / 3 / 3.5 / 4 / 4.5 / 5 / 5+"],
        ["6",  "Komnat (maksimum)",   "Tot zhe diapazon / Bez ogranicheniy"],
        ["7",  "Tsena (minimum)",     "Arenda: 0-10 000 ILS/mes | Pokupka: 0-5 mln ILS"],
        ["8",  "Tsena (maksimum)",    "Arenda: do 15 000+ ILS/mes | Pokupka: do 10 mln+ ILS"],
        ["9",  "Parkovka",            "Net / 1 / 2 / 3+ / Lyubaya"],
        ["10", "Basseyn",             "Da / Lyuboy (tol'ko dlya domov i vill)"],
    ]
    story.append(row_table(search_steps, [1*cm, 3.5*cm, W-4.5*cm],
                 header=["No.", "Shag", "Varianty"]))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("Dopolnitel'nyye fil'try:", h3))
    extras = [
        "Ubezhishche (Mamad / Miklat / Net / Lyuboye)",
        "Lift (Da / Lyuboy)",
        "Infrastruktura: Detsad, Shkola, TTs, Park, Sportzal, Bol'nitsa, Plyazh, Transport, Restoran, Sinagoga, Basseyn",
        "Tol'ko s foto"
    ]
    story.extend(bullets(extras))
    story.append(Spacer(1, 0.15*cm))

    story.append(Paragraph("Deystviya v rezul'tatakh:", h3))
    actions = [
        "V izbrannoye | Kontakty prodavtsa | Google Maps",
        "Zaprosit' prosmotr | Ostavit' otzyv | Ya arendoval/kupil",
        "Podpisat'sya na poisk | Novyy poisk | Glavnoye menyu",
    ]
    story.extend(bullets(actions))
    story.append(Spacer(1, 0.3*cm))

    # 3. ADD LISTING
    story.append(section("3. Dobavleniye ob'yavleniya (18+ shagov)", TEAL))
    story.append(Spacer(1, 0.2*cm))
    listing_steps = [
        ["1-2",  "Tip prodavtsa + Tip sdelki", "Chastnoye litso / Agent → Kupit' / Snyat'"],
        ["3-5",  "Ob'yekt + Rayon + Gorod",    "Tip nedvizhimosti, rayon iz 6, gorod iz 23"],
        ["6",    "Adres/Rayon",                "Tekstovyy vvod"],
        ["7-9",  "Komnaty + Etazh + Ploshchad'","Komnat: 1-5+, Etazh: podval/1-21+/pentkhaus, m2"],
        ["10",   "Tsena (ILS)",                "Chislovoy vvod"],
        ["11-14","Udobstva",                   "Parkovka, Basseyn, Ubezhishche, Lift"],
        ["15",   "Infrastruktura",             "Multi-vybor (11 variantov)"],
        ["16",   "Opisaniye",                  "Proizvol'nyy tekst"],
        ["17-18","Khozyan + Telefon",          "Imya, nomer telefona"],
        ["19",   "Sposob svyazi",              "Telegram / WhatsApp / Telefon / Email"],
        ["20",   "Foto",                       "Zagruzka neskol'kikh foto (optsional'no)"],
        ["21",   "Podtverzhdeniye i publikatsiya","Predprosmotr → Opublikovat' / Otmenit'"],
    ]
    story.append(row_table(listing_steps, [1.5*cm, 3.5*cm, W-5*cm],
                 header=["Shag", "Pole", "Detali"]))
    story.append(Spacer(1, 0.3*cm))

    # 4. OTHER FLOWS
    story.append(section("4. Dopolnitel'nyye funktsii", colors.HexColor("#e67e22")))
    story.append(Spacer(1, 0.2*cm))

    gap = 0.3*cm
    half2 = (W - gap) / 2

    def mini_section(title, items, bg=LIGHT_BG):
        col_w = (W - 0.3*cm) / 2
        rows = [[Paragraph(title, S("ms_h", fontSize=10, fontName="Helvetica-Bold",
                    textColor=WHITE))]]
        for item in items:
            rows.append([Paragraph(f"• {item}", small)])
        t = Table(rows, colWidths=[col_w])
        t.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0), MID),
            ("BACKGROUND",(0,1),(-1,-1), bg),
            ("TOPPADDING",(0,0),(-1,-1), 5),
            ("BOTTOMPADDING",(0,0),(-1,-1), 4),
            ("LEFTPADDING",(0,0),(-1,-1), 8),
            ("GRID",(0,0),(-1,-1), 0.3, colors.HexColor("#cccccc")),
        ]))
        return t

    commercial = mini_section("Kommercheskaya nedvizhimost'", [
        "5-shagovyy poisk (Tip → Gorod → Tsena)",
        "Tipy: Ofis, Riteyl, Sklad, Restoran, Studiya, Parkovka",
        "Arenda ot 3 000 ILS / Pokupka ot 500 000 ILS",
    ])

    services = mini_section("Marketpleys uslug", [
        "Pereezd / Upakovka / Uborka",
        "Poisk po regionu: Sever / Tsentr / Yug",
        "Dobavleniye svoey uslugi (9 shagov)",
        "Prosmotr provayderov s kontaktami",
    ])

    crm = mini_section("CRM kontakty", [
        "Tipy: Agenty, Gruzchiki, Upakovshchiki, Uborshchiki",
        "Dobavleniye s imyenem, telefonom, regionom",
        "Statusy sdelok: Novyy / V rabote / Gotovo / Otmeneno",
    ])

    favorites = mini_section("Izbrannoye", [
        "Sokhraneniye ob'yavleniy",
        "Uvedomleniya o snizhenii tseny",
        "Navigatsiya po izbrannomu",
        "Bystryy dostup iz menyu",
    ])

    row1 = Table([[commercial, services]], colWidths=[half2, half2])
    row1.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),
                               ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0)]))
    row2 = Table([[crm, favorites]], colWidths=[half2, half2])
    row2.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),
                               ("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0)]))

    story.append(row1)
    story.append(Spacer(1, 0.25*cm))
    story.append(row2)
    story.append(Spacer(1, 0.3*cm))

    # 5. SUBSCRIPTIONS
    story.append(section("5. Podpiski i monetizatsiya", colors.HexColor("#27ae60")))
    story.append(Spacer(1, 0.2*cm))

    trial_t = Table([[
        Paragraph("Testovyy period", S("tp", fontSize=11, fontName="Helvetica-Bold",
                   textColor=WHITE)),
        Paragraph("Besplatnyy dostup ko vsem funktsiyam do 15 maya 2026",
                   S("td", fontSize=10, textColor=WHITE)),
    ]], colWidths=[5*cm, W-5*cm])
    trial_t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1), colors.HexColor("#27ae60")),
        ("TOPPADDING",(0,0),(-1,-1), 10),
        ("BOTTOMPADDING",(0,0),(-1,-1), 10),
        ("LEFTPADDING",(0,0),(-1,-1), 12),
    ]))
    story.append(trial_t)
    story.append(Spacer(1, 0.2*cm))

    plans = [
        ["Nedelya",       "19.90 ILS",  "7 dney",   "Bezlimitnyy poisk + razmeshcheniye ob'yavleniy"],
        ["2 nedeli",      "29.90 ILS",  "14 dney",  "Bezlimitnyy poisk + razmeshcheniye ob'yavleniy"],
        ["Mesyats",       "39.90 ILS",  "30 dney",  "Bezlimitnyy poisk + razmeshcheniye ob'yavleniy"],
        ["Poisk-erty",    "39.90 ILS",  "30 dney",  "Uvedomleniya o novykh ob'yavleniyakh po fil'tram"],
    ]
    story.append(row_table(plans, [3*cm, 2.5*cm, 2.5*cm, W-8*cm],
                 header=["Tarif", "Tsena", "Srok", "Vklyucheno"]))
    story.append(Spacer(1, 0.15*cm))
    story.append(Paragraph("Posle okonchaniya triala:", h3))
    story.extend(bullets([
        "Ogranicheniye: 3 poiska v sessiyu",
        "Nel'zya dobavlyat' ob'yavleniya",
        "Prosmotr publichnykh ob'yavleniy dostupen",
        "Referalnyy bonus: +7 dney za kazhdogo privlechyonnogo pol'zovatelya",
        "Bonus za zakrytiye sdelki: +3 dnya",
    ]))
    story.append(Spacer(1, 0.3*cm))

    # 6. PAYMENTS
    story.append(section("6. Platezhna sistema", colors.HexColor("#e67e22")))
    story.append(Spacer(1, 0.2*cm))

    pay_flow = [
        ["1", "Pol'zovatel' vybirayet tarif",         "Knopki v menyu podpiski"],
        ["2", "Bot otpravlyayet invoice",              "Telegram sendInvoice (ILS)"],
        ["3", "Pol'zovatel' vvodit kartu",             "Forma oplaty platezhnoogo provaydere"],
        ["4", "Telegram otpravlyayet pre_checkout",    "Bot provervayet payload, otvechayet ok=True"],
        ["5", "Provayider spisyvayet den'gi",          "Charge cherez Smart Glocal LIVE"],
        ["6", "Bot poluchayet successful_payment",     "Aktiviruyet podpisku"],
        ["7", "Kvitantsiya na email",                  "HTML-pis'mo cherez Resend API"],
    ]
    story.append(row_table(pay_flow, [0.8*cm, 5.5*cm, W-6.3*cm],
                 header=["No.", "Shag", "Detali"]))
    story.append(Spacer(1, 0.15*cm))

    providers_data = [
        ["Smart Glocal TEST", "Bankovskiye karty (ILS)", "Podklyuchyon", "Problema s test-kartami"],
        ["Smart Glocal LIVE", "Bankovskiye karty (ILS)", "Ozhidaniye verifikatsii (5 dney)", "Zapushchen protsess"],
        ["CryptoPay",         "USDT/TON/BTC/ETH",        "Podklyuchyon (testnet)", "Polling cherez @CryptoBot API"],
        ["PayPal",            "Fiat / karty",            "Ne podklyuchyon",  "Trebuyet otdel'noy razrabotki"],
    ]
    story.append(row_table(providers_data, [3.5*cm, 3.5*cm, 3.5*cm, W-10.5*cm],
                 header=["Provayider", "Tip", "Status", "Primechaniye"]))
    story.append(Spacer(1, 0.3*cm))

    # 7. NOTIFICATIONS
    story.append(section("7. Uvedomleniya (fonovyye zadachi)", PURPLE))
    story.append(Spacer(1, 0.2*cm))
    notif = [
        ["Novyye ob'yavl. po fil'tram",  "Kazhdyye 30 min", "Uvedomlyayet podpischikov o novykh sovpadeniyakh"],
        ["Snizheniye tseny v izbrannom", "Kazhdyy chas",    "Otslezh. tseny, uvedomlyayet o snizhenii"],
        ["Napominaniye o starykh ob'yav.","Raz v den'",     "Ob'yavl. 30+ dney s zaprosami — napomn. zakryt'"],
        ["Ezhenedel'nyy email-otchyot",  "Voskresen'ye",    "Otchyot agentam: prosmotry, zaprosy, reyting"],
        ["CryptoPay pollinq",            "Kazhdyye 60 sek", "Proverka oplachenykh kripto-invoysov"],
    ]
    story.append(row_table(notif, [4.5*cm, 3*cm, W-7.5*cm],
                 header=["Tip", "Period", "Opisaniye"]))
    story.append(Spacer(1, 0.3*cm))

    # 8. MULTILINGUAL
    story.append(section("8. Mnogooyazychnost' i goroda", colors.HexColor("#00796b")))
    story.append(Spacer(1, 0.2*cm))

    lang_table = Table([
        [Paragraph("Russkiy", body), Paragraph("English", body), Paragraph("Ivrit (RTL)", body)],
        [Paragraph("Vse knopki, soobshcheniya,\nuvedomleniya", small),
         Paragraph("All buttons, messages,\nnotifications", small),
         Paragraph("All UI elements\n(right-to-left)", small)],
    ], colWidths=[W/3]*3)
    lang_table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0), MID),
        ("TEXTCOLOR",(0,0),(-1,0), WHITE),
        ("BACKGROUND",(0,1),(-1,-1), LIGHT_BG),
        ("ALIGN",(0,0),(-1,-1),"CENTER"),
        ("TOPPADDING",(0,0),(-1,-1), 7),
        ("BOTTOMPADDING",(0,0),(-1,-1), 7),
        ("GRID",(0,0),(-1,-1), 0.5, colors.HexColor("#dddddd")),
    ]))
    story.append(lang_table)
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("23 podderzhivayemykh goroda:", h3))
    cities = ("Tel'-Aviv, Iyerusalim, Khayfa, Rishon-le-Tsion, Petakh-Tikva, Ashdod, "
              "Netaniya, Beer-Sheva, Bney-Brak, Kholon, Ramat-Gan, Rekovot, Ashkelon, "
              "Bat-Yam, Kfar-Saba, Khadera, Eylat, Gertsiya, Raanana, Lod, Nes-Tsiona, "
              "Or-Yekhuda, Modiyin")
    story.append(Paragraph(cities, small))
    story.append(Spacer(1, 0.3*cm))

    # 9. ANALYTICS & ADMIN
    story.append(section("9. Analitika i administrirovaniye", DARK))
    story.append(Spacer(1, 0.2*cm))

    analytics_rows = [
        ["Pol'zovateli",   "Data registratsii, yazyk, imya, username, aktivnost'"],
        ["Poiski",         "Vse fil'try: tip sdelki, tip ob'yekta, gorod, komnaty, tsena, infrastruktura"],
        ["Podpiski",       "Aktivatsii po tarifu, konversiya triala, platezhnyye logi"],
        ["Ob'yavleniya",   "Kol-vo, po gorodam/rayonam, prosmotry, zaprosy, sdelki"],
        ["Platezhi",       "Istoriya platezhey: data, vremya, pol'zovatel', tarif, summa, tip oplaty"],
    ]
    story.append(row_table(analytics_rows, [3.5*cm, W-3.5*cm],
                 header=["Chto otslezhivayetsya", "Detali"]))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("Dashboard (admin panel):", h3))
    dash = [
        "URL: flatfinderil-bot-production.up.railway.app (zashchishchyon parolem)",
        "Vkladki: Obzor, Poiski, Ob'yavleniya, Pol'zovateli, Platezhi",
        "Grafiki: Chart.js — aktivnost', poiski, podpiski, platezhi",
        "API: GET /analytics?from=DATE&to=DATE → JSON",
        "Skachat' PDF: knopka 'Skachat' karta bota (PDF)' na dashborde",
    ]
    story.extend(bullets(dash))
    story.append(Spacer(1, 0.3*cm))

    # 10. ARCHITECTURE
    story.append(section("10. Tekhnicheskaya arkhitektura", colors.HexColor("#37474f")))
    story.append(Spacer(1, 0.2*cm))

    arch = [
        ["Yazyk",          "Python 3.11.6"],
        ["Freymvork",      "python-telegram-bot 20.7 (async)"],
        ["Baza dannykh",   "JSON-fayly: listings_db.json, stats.json"],
        ["Deply",          "Railway (cloud) — avtodeploy iz GitHub"],
        ["Email",          "Resend API — HTML-kvitantsii"],
        ["Porty",          "8080 — Analytics API | 3000 — Dashboard"],
        ["Parsery",        "Yad2, Telegram-kanaly, Facebook (otdel'nyye skripty)"],
        ["Uvedomleniya",   "asyncio fonovyye zadachi + threading"],
        ["Kripto-platezhi", "CryptoPay API (@CryptoBot) — USDT/TON/BTC/ETH"],
    ]
    story.append(row_table(arch, [3.5*cm, W-3.5*cm]))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("Klyuchevyye fayly:", h3))
    files = [
        "bot.py — tochka vkhoda, registratsiya vsekh handlers",
        "handlers.py — glavnoye menyu, platezhi, podpiski, inline-knopki",
        "search_handler.py — 10-shagovyy ConversationHandler poiska",
        "listing_handler.py — 18+-shagovyy ConversationHandler ob'yavleniy",
        "subscription.py — logika tarifov, triala, aktivatsii",
        "analytics.py — treking sobytiy, payments_log",
        "cryptopay.py — integratsiya s CryptoPay API",
        "dashboard.html — SPA dashbord (Chart.js)",
        "notifications.py — fonovyye zadachi uvedomleniy",
    ]
    story.extend(bullets(files))
    story.append(Spacer(1, 0.3*cm))

    # FOOTER
    story.append(HRFlowable(width=W, thickness=1, color=colors.HexColor("#dddddd")))
    story.append(Spacer(1, 0.2*cm))
    footer_t = Table([[
        Paragraph("FlatFinderIL Bot · Karta funktsiy v1.0",
                   S("fl", fontSize=9, textColor=GRAY)),
        Paragraph("Aprel 2026 · Python + Telegram Bot API",
                   S("fr", fontSize=9, textColor=GRAY, alignment=TA_CENTER)),
        Paragraph("CryptoPay enabled · Smart Glocal LIVE pending",
                   S("frr", fontSize=9, textColor=colors.HexColor("#e67e22"),
                     alignment=TA_CENTER)),
    ]], colWidths=[W/3]*3)
    footer_t.setStyle(TableStyle([("TOPPADDING",(0,0),(-1,-1),3)]))
    story.append(footer_t)

    doc.build(story)
    return buf.getvalue()


# --- Fallback (stdlib-only) PDF generator ----------------------------------

_FALLBACK_LINES = [
    "FlatFinderIL Bot - Karta funktsiy",
    "",
    "Versiya 1.0  ·  Aprel 2026",
    "",
    "Telegram bot dlya poiska i razmeshcheniya",
    "nedvizhimosti v Izraile.",
    "",
    "Klyuchevye funktsii:",
    "  - Poisk arendy i pokupki s mnogoshagovym filtrom",
    "  - Razmeshchenie ob'yavleniy s fotografiyami",
    "  - Izbrannoe i istoriya prosmotrov",
    "  - Mnogoyazychnyy interfeys (RU / EN / HE / FR)",
    "  - Tarify, trial, podpiski (Stars + CryptoPay)",
    "  - Analitika i administrativnaya panel'",
    "",
    "Polnaya versiya etogo dokumenta vremenno",
    "nedostupna - generator otrisovki ne smog",
    "sobrat' polnyy PDF. Etot fallback soderzhit",
    "kratkoye opisanie. Poprobuyte pozzhe ili",
    "obratites' v podderzhku.",
    "",
    "Telegram: @FlatFinderIL_Bot",
]


def _build_minimal_pdf(lines):
    """Build a tiny but valid 1-page PDF using only the standard library.

    Used as a fallback when reportlab is not importable or raises.
    """
    # Escape PDF special chars and force latin-1 (ASCII-safe) encoding.
    def esc(s):
        return (s.replace("\\", "\\\\")
                 .replace("(", "\\(")
                 .replace(")", "\\)"))

    content_ops = ["BT", "/F1 12 Tf", "14 TL", "50 770 Td"]
    for ln in lines:
        content_ops.append(f"({esc(ln)}) Tj T*")
    content_ops.append("ET")
    content_stream = ("\n".join(content_ops)).encode("latin-1", "replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R "
        b"/Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 612 792] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content_stream)).encode() + b" >>\n"
        b"stream\n" + content_stream + b"\nendstream",
    ]

    out = bytearray()
    out += b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode()
        out += obj
        out += b"\nendobj\n"

    xref_offset = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n").encode()

    return bytes(out)


def generate_safe():
    """Always-succeed wrapper around generate().

    Returns (bytes, mime_type, filename). On reportlab failure (ImportError,
    runtime error, missing fonts, etc.) returns a minimal stdlib-built PDF
    with a textual summary so callers can always serve a downloadable file.
    """
    log = logging.getLogger(__name__)
    try:
        data = generate()
        if not data or len(data) < 100:
            raise RuntimeError("generate() returned empty/too-small payload")
        return data, "application/pdf", "FlatFinderIL_Bot_Map.pdf"
    except Exception as e:
        log.warning("[bot_map_pdf] reportlab path failed (%s); using fallback", e)
        try:
            data = _build_minimal_pdf(_FALLBACK_LINES)
            return data, "application/pdf", "FlatFinderIL_Bot_Map_fallback.pdf"
        except Exception as e2:
            log.error("[bot_map_pdf] fallback PDF builder also failed: %s", e2)
            text = "\n".join(_FALLBACK_LINES).encode("utf-8")
            return text, "text/plain; charset=utf-8", "FlatFinderIL_Bot_Map.txt"
