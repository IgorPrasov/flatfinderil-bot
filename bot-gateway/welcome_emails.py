"""
Welcome emails sent upon registration on FlatFinderIL.

Covers:
  • Real estate agent / realtor  (listing_handler calls send_agent_welcome)
  • Private individual           (listing_handler calls send_private_welcome)
  • Movers   (service_handler calls send_service_welcome with svc_type="movers")
  • Packers  (service_handler calls send_service_welcome with svc_type="packers")
  • Cleaning (service_handler calls send_service_welcome with svc_type="cleaning")

Each email is delivered in the language the user chose in the bot (ru / he / en).
Hebrew emails use RTL layout automatically.
"""

import logging
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Base HTML wrapper — responsive, works in Gmail / Outlook / Apple Mail
# ─────────────────────────────────────────────────────────────────────────────

def _wrap(body_html: str, lang: str = "ru", accent: str = "#2563eb") -> str:
    """Wrap content block in a branded HTML email shell."""
    is_rtl   = lang == "he"
    dir_attr = 'dir="rtl"' if is_rtl else 'dir="ltr"'
    align    = "right" if is_rtl else "left"

    return f"""<!DOCTYPE html>
<html lang="{lang}" {dir_attr}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FlatFinderIL</title>
<style>
  body {{ margin:0; padding:0; background:#f4f7fb; font-family:Arial,Helvetica,sans-serif; }}
  .wrap {{ max-width:600px; margin:32px auto; background:#ffffff;
           border-radius:12px; overflow:hidden;
           box-shadow:0 2px 12px rgba(0,0,0,.08); }}
  .header {{ background:{accent}; padding:28px 36px; text-align:center; }}
  .header img {{ height:36px; }}
  .header h1 {{ color:#ffffff; margin:12px 0 0; font-size:22px; letter-spacing:.4px; }}
  .body {{ padding:32px 36px; color:#1e293b; font-size:15px; line-height:1.7;
           text-align:{align}; }}
  .body h2 {{ font-size:20px; margin-top:0; color:#0f172a; }}
  .highlight {{ background:#f0f7ff; border-{align}:4px solid {accent};
                padding:14px 18px; border-radius:6px; margin:20px 0; }}
  .steps {{ background:#f8fafc; border-radius:8px; padding:18px 24px; margin:20px 0; }}
  .steps ol {{ margin:0; padding-inline-start:20px; }}
  .steps li {{ margin-bottom:8px; }}
  .btn {{ display:inline-block; background:{accent}; color:#ffffff !important;
          text-decoration:none; padding:13px 30px; border-radius:8px;
          font-size:15px; font-weight:bold; margin:20px 0; }}
  .divider {{ border:none; border-top:1px solid #e2e8f0; margin:24px 0; }}
  .footer {{ background:#f8fafc; padding:20px 36px; text-align:center;
             color:#64748b; font-size:12px; line-height:1.6; }}
  .footer a {{ color:#2563eb; text-decoration:none; }}
  @media (max-width:600px) {{
    .body, .footer {{ padding:20px; }}
    .header {{ padding:20px; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <div class="header">
    <h1>🏠 FlatFinderIL</h1>
  </div>
  <div class="body">
    {body_html}
  </div>
  <div class="footer">
    <p>
      FlatFinderIL &nbsp;·&nbsp;
      <a href="https://flatfinderil.com">flatfinderil.com</a> &nbsp;·&nbsp;
      <a href="https://t.me/flatfinderil_bot">Telegram Bot</a>
    </p>
  </div>
</div>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Agent / Realtor welcome email
# ─────────────────────────────────────────────────────────────────────────────

def _agent_body(lang: str, name: str, listing_id: int, city: str, price: int,
                deal_label: str, is_agent: bool) -> str:
    greeting = {"ru": "Здравствуйте", "en": "Hello", "he": "שלום"}.get(lang, "Hello")
    name_part = f", <b>{name}</b>" if name else ""

    if lang == "ru":
        role = "Агент" if is_agent else "Арендодатель"
        return f"""
<h2>{'🏢 Объявление опубликовано!' if is_agent else '🏠 Объявление опубликовано!'}</h2>
<p>{greeting}{name_part}!</p>
<p>Ваше объявление успешно размещено на платформе <b>FlatFinderIL</b> и уже появляется в результатах поиска.</p>
<div class="highlight">
  📋 <b>ID объявления:</b> #{listing_id}<br>
  📍 <b>Город:</b> {city}<br>
  💰 <b>Цена:</b> {price:,} ₪ &nbsp;·&nbsp; {deal_label}
</div>
{'<div class="steps"><b>Что дальше?</b><ol><li>Заинтересованные клиенты свяжутся с вами напрямую</li><li>Каждую неделю — отчёт о просмотрах на этот email</li><li>Управляйте объявлениями в разделе <b>📋 Мои объявления</b></li><li>Добавьте ещё объявления — это бесплатно во время триального периода</li></ol></div>' if is_agent else '<div class="steps"><b>Что дальше?</b><ol><li>Пользователи уже видят ваше объявление в поиске по всему Израилю</li><li>Как только кто-то захочет связаться — вы получите уведомление в Telegram</li><li>Управляйте объявлением в разделе <b>📋 Мои объявления</b></li></ol></div>'}
<a href="https://t.me/flatfinderil_bot" class="btn">Открыть бот →</a>
<hr class="divider">
<p style="color:#64748b;font-size:13px;">Если у вас есть вопросы — просто напишите нам в Telegram. Удачных сделок! 🤝</p>
"""
    elif lang == "en":
        return f"""
<h2>{'🏢 Listing Published!' if is_agent else '🏠 Listing Published!'}</h2>
<p>{greeting}{name_part}!</p>
<p>Your listing is now live on <b>FlatFinderIL</b> and appearing in search results.</p>
<div class="highlight">
  📋 <b>Listing ID:</b> #{listing_id}<br>
  📍 <b>City:</b> {city}<br>
  💰 <b>Price:</b> ₪{price:,} &nbsp;·&nbsp; {deal_label}
</div>
{'<div class="steps"><b>What\'s next?</b><ol><li>Interested clients will contact you directly</li><li>Every week you\'ll receive a views report to this email</li><li>Manage your listings in <b>📋 My Listings</b></li><li>Add more listings — free during the trial period</li></ol></div>' if is_agent else '<div class="steps"><b>What\'s next?</b><ol><li>Users across Israel can already find your listing</li><li>You\'ll get a Telegram notification when someone wants to contact you</li><li>Manage your listing under <b>📋 My Listings</b></li></ol></div>'}
<a href="https://t.me/flatfinderil_bot" class="btn">Open Bot →</a>
<hr class="divider">
<p style="color:#64748b;font-size:13px;">Questions? Just message us in Telegram. Wishing you a successful deal! 🤝</p>
"""
    else:  # he
        return f"""
<h2>{'🏢 המודעה פורסמה!' if is_agent else '🏠 המודעה פורסמה!'}</h2>
<p>{greeting}{name_part}!</p>
<p>המודעה שלך פעילה ב-<b>FlatFinderIL</b> ומופיעה כבר בתוצאות החיפוש.</p>
<div class="highlight">
  📋 <b>מספר מודעה:</b> #{listing_id}<br>
  📍 <b>עיר:</b> {city}<br>
  💰 <b>מחיר:</b> ₪{price:,} &nbsp;·&nbsp; {deal_label}
</div>
{'<div class="steps"><b>מה הלאה?</b><ol><li>לקוחות מתעניינים יפנו אליך ישירות</li><li>כל שבוע תקבל/י דוח על צפיות לאימייל הזה</li><li>נהל/י את המודעות תחת <b>📋 המודעות שלי</b></li><li>הוסף/י מודעות נוספות — בחינם בתקופת הניסיון</li></ol></div>' if is_agent else '<div class="steps"><b>מה הלאה?</b><ol><li>משתמשים ברחבי ישראל כבר יכולים למצוא את המודעה שלך</li><li>תקבל/י התראה בטלגרם כשמישהו ירצה ליצור קשר</li><li>נהל/י את המודעה תחת <b>📋 המודעות שלי</b></li></ol></div>'}
<a href="https://t.me/flatfinderil_bot" class="btn">פתיחת הבוט ←</a>
<hr class="divider">
<p style="color:#64748b;font-size:13px;">שאלות? פשוט כתבו לנו בטלגרם. בהצלחה בעסקה! 🤝</p>
"""


def send_agent_welcome(user_id: int, lang: str, name: str, email: str,
                       listing_id: int, city: str, price: int,
                       deal_label: str, is_agent: bool = False) -> bool:
    """Send welcome email after agent/owner publishes first listing."""
    if not email:
        return False
    try:
        from email_reporter import _send_email_simple
        subjects = {
            "ru": f"🏠 Объявление #{listing_id} опубликовано — FlatFinderIL",
            "en": f"🏠 Listing #{listing_id} is live — FlatFinderIL",
            "he": f"🏠 המודעה #{listing_id} פורסמה — FlatFinderIL",
        }
        body = _agent_body(lang, name, listing_id, city, price, deal_label, is_agent)
        html = _wrap(body, lang, accent="#2563eb")
        ok = _send_email_simple(email, subjects.get(lang, subjects["en"]), html)
        if ok:
            logger.info(f"[WELCOME] Agent email sent user={user_id} lang={lang}")
        return ok
    except Exception as e:
        logger.error(f"[WELCOME] Agent email failed user={user_id}: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Service provider welcome emails (movers / packers / cleaning)
# ─────────────────────────────────────────────────────────────────────────────

_SERVICE_CONTENT = {

    # ── Movers / הובלות / Перевозчики ──────────────────────────────────────
    "movers": {
        "accent": "#0ea5e9",
        "subjects": {
            "ru": "🚛 Вы зарегистрированы как перевозчик — FlatFinderIL",
            "he": "🚛 נרשמת כחברת הובלות — FlatFinderIL",
            "en": "🚛 You're registered as a moving company — FlatFinderIL",
        },
        "bodies": {
            "ru": lambda name: f"""
<h2>🚛 Добро пожаловать в FlatFinderIL!</h2>
<p>Здравствуйте{',' + ' <b>' + name + '</b>' if name else ''}!</p>
<p>Ваша компания по перевозкам успешно зарегистрирована на платформе <b>FlatFinderIL</b> —
   ведущем Telegram-боте для поиска жилья в Израиле.</p>
<div class="highlight">
  🏠 Тысячи людей каждый месяц переезжают через нашу платформу.<br>
  Теперь они видят ваши услуги прямо в момент поиска квартиры.
</div>
<div class="steps">
  <b>Как это работает:</b>
  <ol>
    <li>Пользователь находит квартиру и открывает раздел <b>🔧 Услуги</b></li>
    <li>Видит вашу компанию — название, регион, телефон</li>
    <li>Оставляет заявку прямо в боте — вы получаете уведомление</li>
    <li>Еженедельный отчёт о просмотрах вашей карточки — на этот email</li>
  </ol>
</div>
<p><b>Советы для быстрого старта:</b></p>
<ul>
  <li>Отвечайте на заявки быстро — это повышает рейтинг</li>
  <li>Укажите диапазон цен — клиенты ценят прозрачность</li>
  <li>Работаете в нескольких городах? Сообщите нам — расширим охват</li>
</ul>
<a href="https://t.me/flatfinderil_bot" class="btn">Открыть бот →</a>
<hr class="divider">
<p style="color:#64748b;font-size:13px;">Вопросы? Напишите нам в Telegram. Желаем много заявок! 🤝</p>
""",
            "he": lambda name: f"""
<h2>🚛 ברוכים הבאים ל-FlatFinderIL!</h2>
<p>שלום{',' + ' <b>' + name + '</b>' if name else ''}!</p>
<p>חברת ההובלות שלך נרשמה בהצלחה בפלטפורמה <b>FlatFinderIL</b> —
   בוט הטלגרם המוביל לחיפוש דירות בישראל.</p>
<div class="highlight">
  🏠 אלפי אנשים עוברים דירה בכל חודש דרך הפלטפורמה שלנו.<br>
  עכשיו הם רואים את השירות שלך בדיוק ברגע שהם מחפשים דירה.
</div>
<div class="steps">
  <b>איך זה עובד:</b>
  <ol>
    <li>משתמש מוצא דירה ופותח את סעיף <b>🔧 שירותים</b></li>
    <li>רואה את חברתך — שם, אזור, טלפון</li>
    <li>משאיר פנייה ישירות בבוט — אתה מקבל התראה</li>
    <li>דוח שבועי על צפיות בפרופיל שלך — לאימייל הזה</li>
  </ol>
</div>
<p><b>טיפים להתחלה מהירה:</b></p>
<ul>
  <li>הגב לפניות מהר — זה מעלה את הדירוג שלך</li>
  <li>ציין טווח מחירים — לקוחות מעריכים שקיפות</li>
  <li>עובד בכמה ערים? ספר לנו — נרחיב את הטווח</li>
</ul>
<a href="https://t.me/flatfinderil_bot" class="btn">פתיחת הבוט ←</a>
<hr class="divider">
<p style="color:#64748b;font-size:13px;">שאלות? כתבו לנו בטלגרם. בהצלחה! 🤝</p>
""",
            "en": lambda name: f"""
<h2>🚛 Welcome to FlatFinderIL!</h2>
<p>Hello{',' + ' <b>' + name + '</b>' if name else ''}!</p>
<p>Your moving company is now registered on <b>FlatFinderIL</b> —
   Israel's leading Telegram bot for apartment hunting.</p>
<div class="highlight">
  🏠 Thousands of people move every month through our platform.<br>
  Now they see your service exactly when they find a new apartment.
</div>
<div class="steps">
  <b>How it works:</b>
  <ol>
    <li>A user finds an apartment and opens the <b>🔧 Services</b> section</li>
    <li>They see your company — name, region, phone</li>
    <li>They submit a request directly in the bot — you get notified</li>
    <li>Weekly profile views report sent to this email</li>
  </ol>
</div>
<p><b>Quick-start tips:</b></p>
<ul>
  <li>Reply to requests quickly — it boosts your ranking</li>
  <li>Include a price range — clients appreciate transparency</li>
  <li>Serve multiple cities? Let us know — we'll expand your coverage</li>
</ul>
<a href="https://t.me/flatfinderil_bot" class="btn">Open Bot →</a>
<hr class="divider">
<p style="color:#64748b;font-size:13px;">Questions? Message us in Telegram. Wishing you many clients! 🤝</p>
""",
        },
    },

    # ── Packers / אריזה / Упаковщики ───────────────────────────────────────
    "packers": {
        "accent": "#8b5cf6",
        "subjects": {
            "ru": "📦 Вы зарегистрированы как упаковщик — FlatFinderIL",
            "he": "📦 נרשמת כחברת אריזה — FlatFinderIL",
            "en": "📦 You're registered as a packing service — FlatFinderIL",
        },
        "bodies": {
            "ru": lambda name: f"""
<h2>📦 Добро пожаловать в FlatFinderIL!</h2>
<p>Здравствуйте{',' + ' <b>' + name + '</b>' if name else ''}!</p>
<p>Ваш сервис упаковки успешно зарегистрирован на платформе <b>FlatFinderIL</b>.</p>
<div class="highlight">
  📦 Переезд без упаковки — невозможен. Теперь ваши услуги видят
  именно те, кому они нужны прямо сейчас.
</div>
<div class="steps">
  <b>Как это работает:</b>
  <ol>
    <li>Пользователь находит квартиру и открывает раздел <b>🔧 Услуги</b></li>
    <li>Видит ваш сервис упаковки — описание, регион, контакты</li>
    <li>Оставляет заявку — вы получаете уведомление в Telegram</li>
    <li>Еженедельный отчёт о просмотрах — на этот email</li>
  </ol>
</div>
<p><b>Совет:</b> укажите в профиле какие материалы вы используете (коробки, плёнка, пузырчатая бумага) —
это повышает доверие клиентов.</p>
<a href="https://t.me/flatfinderil_bot" class="btn">Открыть бот →</a>
<hr class="divider">
<p style="color:#64748b;font-size:13px;">Вопросы? Напишите нам в Telegram. Желаем успехов! 📦</p>
""",
            "he": lambda name: f"""
<h2>📦 ברוכים הבאים ל-FlatFinderIL!</h2>
<p>שלום{',' + ' <b>' + name + '</b>' if name else ''}!</p>
<p>שירות האריזה שלך נרשם בהצלחה בפלטפורמה <b>FlatFinderIL</b>.</p>
<div class="highlight">
  📦 מעבר דירה בלי אריזה — בלתי אפשרי. עכשיו השירות שלך נראה
  בדיוק לאלו שצריכים אותו עכשיו.
</div>
<div class="steps">
  <b>איך זה עובד:</b>
  <ol>
    <li>משתמש מוצא דירה ופותח את סעיף <b>🔧 שירותים</b></li>
    <li>רואה את שירות האריזה שלך — תיאור, אזור, פרטי קשר</li>
    <li>משאיר פנייה — אתה מקבל התראה בטלגרם</li>
    <li>דוח שבועי על צפיות — לאימייל הזה</li>
  </ol>
</div>
<p><b>טיפ:</b> ציין בפרופיל אילו חומרים אתה משתמש (קרטונים, ניילון, נייר בועות) —
זה מגביר את אמון הלקוחות.</p>
<a href="https://t.me/flatfinderil_bot" class="btn">פתיחת הבוט ←</a>
<hr class="divider">
<p style="color:#64748b;font-size:13px;">שאלות? כתבו לנו בטלגרם. בהצלחה! 📦</p>
""",
            "en": lambda name: f"""
<h2>📦 Welcome to FlatFinderIL!</h2>
<p>Hello{',' + ' <b>' + name + '</b>' if name else ''}!</p>
<p>Your packing service is now registered on <b>FlatFinderIL</b>.</p>
<div class="highlight">
  📦 No move is complete without packing. Now your service is visible
  to exactly the people who need it right now.
</div>
<div class="steps">
  <b>How it works:</b>
  <ol>
    <li>A user finds an apartment and opens the <b>🔧 Services</b> section</li>
    <li>They see your packing service — description, region, contacts</li>
    <li>They submit a request — you get notified in Telegram</li>
    <li>Weekly views report sent to this email</li>
  </ol>
</div>
<p><b>Tip:</b> List the materials you use (boxes, wrap, bubble paper) in your profile
— it builds client trust.</p>
<a href="https://t.me/flatfinderil_bot" class="btn">Open Bot →</a>
<hr class="divider">
<p style="color:#64748b;font-size:13px;">Questions? Message us in Telegram. Best of luck! 📦</p>
""",
        },
    },

    # ── Cleaning / ניקיון / Уборка ───────────────────────────────────────────
    "cleaning": {
        "accent": "#10b981",
        "subjects": {
            "ru": "🧹 Вы зарегистрированы как клининг — FlatFinderIL",
            "he": "🧹 נרשמת כחברת ניקיון — FlatFinderIL",
            "en": "🧹 You're registered as a cleaning service — FlatFinderIL",
        },
        "bodies": {
            "ru": lambda name: f"""
<h2>🧹 Добро пожаловать в FlatFinderIL!</h2>
<p>Здравствуйте{',' + ' <b>' + name + '</b>' if name else ''}!</p>
<p>Ваш клининговый сервис успешно зарегистрирован на платформе <b>FlatFinderIL</b>.</p>
<div class="highlight">
  🧹 Каждый, кто въезжает в новую квартиру или выезжает из старой,
  нуждается в уборке. Ваши услуги появляются именно в этот момент.
</div>
<div class="steps">
  <b>Как это работает:</b>
  <ol>
    <li>Пользователь находит квартиру и открывает раздел <b>🔧 Услуги</b></li>
    <li>Видит ваш клининг — описание, регион, контакты, цены</li>
    <li>Оставляет заявку прямо в боте — вы получаете уведомление</li>
    <li>Еженедельный отчёт о просмотрах вашей карточки — на этот email</li>
  </ol>
</div>
<p><b>Советы для роста:</b></p>
<ul>
  <li>Укажите типы уборки: генеральная, после ремонта, сдача квартиры</li>
  <li>Добавьте диапазон цен — клиенты выбирают быстрее</li>
  <li>Работаете по нескольким городам? Напишите нам — расширим регион</li>
</ul>
<a href="https://t.me/flatfinderil_bot" class="btn">Открыть бот →</a>
<hr class="divider">
<p style="color:#64748b;font-size:13px;">Вопросы? Напишите нам в Telegram. Желаем много клиентов! 🧹</p>
""",
            "he": lambda name: f"""
<h2>🧹 ברוכים הבאים ל-FlatFinderIL!</h2>
<p>שלום{',' + ' <b>' + name + '</b>' if name else ''}!</p>
<p>חברת הניקיון שלך נרשמה בהצלחה בפלטפורמה <b>FlatFinderIL</b>.</p>
<div class="highlight">
  🧹 כל מי שנכנס לדירה חדשה או עוזב דירה ישנה צריך ניקיון.
  השירות שלך מופיע בדיוק ברגע הזה.
</div>
<div class="steps">
  <b>איך זה עובד:</b>
  <ol>
    <li>משתמש מוצא דירה ופותח את סעיף <b>🔧 שירותים</b></li>
    <li>רואה את חברת הניקיון שלך — תיאור, אזור, פרטי קשר</li>
    <li>משאיר פנייה ישירות בבוט — אתה מקבל התראה</li>
    <li>דוח שבועי על צפיות — לאימייל הזה</li>
  </ol>
</div>
<p><b>טיפים לצמיחה:</b></p>
<ul>
  <li>ציין סוגי ניקיון: כללי, לאחר שיפוץ, לפני מסירת דירה</li>
  <li>הוסף טווח מחירים — לקוחות בוחרים מהר יותר</li>
  <li>עובד בכמה ערים? ספר לנו — נרחיב את האזור</li>
</ul>
<a href="https://t.me/flatfinderil_bot" class="btn">פתיחת הבוט ←</a>
<hr class="divider">
<p style="color:#64748b;font-size:13px;">שאלות? כתבו לנו בטלגרם. בהצלחה! 🧹</p>
""",
            "en": lambda name: f"""
<h2>🧹 Welcome to FlatFinderIL!</h2>
<p>Hello{',' + ' <b>' + name + '</b>' if name else ''}!</p>
<p>Your cleaning service is now registered on <b>FlatFinderIL</b>.</p>
<div class="highlight">
  🧹 Everyone moving in or out of an apartment needs cleaning.
  Your service appears exactly at that moment.
</div>
<div class="steps">
  <b>How it works:</b>
  <ol>
    <li>A user finds an apartment and opens the <b>🔧 Services</b> section</li>
    <li>They see your cleaning service — description, region, contacts</li>
    <li>They submit a request directly in the bot — you get notified</li>
    <li>Weekly profile views report sent to this email</li>
  </ol>
</div>
<p><b>Growth tips:</b></p>
<ul>
  <li>List cleaning types: deep clean, post-renovation, end-of-tenancy</li>
  <li>Add a price range — clients decide faster</li>
  <li>Serve multiple cities? Tell us — we'll expand your region</li>
</ul>
<a href="https://t.me/flatfinderil_bot" class="btn">Open Bot →</a>
<hr class="divider">
<p style="color:#64748b;font-size:13px;">Questions? Message us in Telegram. Wishing you many clients! 🧹</p>
""",
        },
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Private individual welcome email (non-agent listing owner)
# ─────────────────────────────────────────────────────────────────────────────

def _private_body(lang: str, name: str, listing_id: int, city: str,
                  price: int, deal_label: str) -> str:
    greeting = {"ru": "Здравствуйте", "en": "Hello", "he": "שלום"}.get(lang, "Hello")
    name_part = f", <b>{name}</b>" if name else ""

    if lang == "ru":
        return f"""
<h2>🏠 Ваше объявление опубликовано!</h2>
<p>{greeting}{name_part}!</p>
<p>Отличная новость — ваше объявление уже видно тысячам пользователей <b>FlatFinderIL</b> в Израиле.</p>
<div class="highlight">
  📋 <b>ID объявления:</b> #{listing_id}<br>
  📍 <b>Город:</b> {city}<br>
  💰 <b>Цена:</b> {price:,} ₪ &nbsp;·&nbsp; {deal_label}
</div>
<div class="steps">
  <b>Что происходит дальше:</b>
  <ol>
    <li>Люди ищут жильё в вашем городе и видят ваше объявление</li>
    <li>Когда кто-то хочет связаться — вы получаете уведомление в Telegram</li>
    <li>Управляйте объявлением в разделе <b>📋 Мои объявления</b></li>
  </ol>
</div>
<p><b>Советы для быстрой сдачи/продажи:</b></p>
<ul>
  <li>Добавьте фотографии — объявления с фото просматривают в 5 раз чаще</li>
  <li>Укажите точный адрес или район — это помогает в поиске</li>
  <li>Отвечайте на запросы быстро — первые минуты решают всё</li>
</ul>
<a href="https://t.me/flatfinderil_bot" class="btn">Открыть бот →</a>
<hr class="divider">
<p style="color:#64748b;font-size:13px;">Удачи в поиске! Если нужна помощь — напишите нам в Telegram. 🤝</p>
"""
    elif lang == "he":
        return f"""
<h2>🏠 המודעה שלך פורסמה!</h2>
<p>{greeting}{name_part}!</p>
<p>חדשות מעולות — המודעה שלך כבר נראית לאלפי משתמשים של <b>FlatFinderIL</b> בישראל.</p>
<div class="highlight">
  📋 <b>מספר מודעה:</b> #{listing_id}<br>
  📍 <b>עיר:</b> {city}<br>
  💰 <b>מחיר:</b> ₪{price:,} &nbsp;·&nbsp; {deal_label}
</div>
<div class="steps">
  <b>מה קורה עכשיו:</b>
  <ol>
    <li>אנשים מחפשים דיור בעיר שלך ורואים את המודעה שלך</li>
    <li>כשמישהו רוצה ליצור קשר — תקבל/י התראה בטלגרם</li>
    <li>נהל/י את המודעה תחת <b>📋 המודעות שלי</b></li>
  </ol>
</div>
<p><b>טיפים להשכרה/מכירה מהירה:</b></p>
<ul>
  <li>הוסף/י תמונות — מודעות עם תמונות נצפות פי 5 יותר</li>
  <li>ציין/י כתובת מדויקת או שכונה — זה עוזר בחיפוש</li>
  <li>הגב/י לפניות מהר — הדקות הראשונות קובעות הכל</li>
</ul>
<a href="https://t.me/flatfinderil_bot" class="btn">פתיחת הבוט ←</a>
<hr class="divider">
<p style="color:#64748b;font-size:13px;">בהצלחה! אם צריך עזרה — כתוב/י לנו בטלגרם. 🤝</p>
"""
    else:  # en
        return f"""
<h2>🏠 Your Listing Is Live!</h2>
<p>{greeting}{name_part}!</p>
<p>Great news — your listing is already visible to thousands of <b>FlatFinderIL</b> users across Israel.</p>
<div class="highlight">
  📋 <b>Listing ID:</b> #{listing_id}<br>
  📍 <b>City:</b> {city}<br>
  💰 <b>Price:</b> ₪{price:,} &nbsp;·&nbsp; {deal_label}
</div>
<div class="steps">
  <b>What happens next:</b>
  <ol>
    <li>People searching for housing in your city will see your listing</li>
    <li>When someone wants to contact you — you'll get a Telegram notification</li>
    <li>Manage your listing under <b>📋 My Listings</b></li>
  </ol>
</div>
<p><b>Tips for a quick deal:</b></p>
<ul>
  <li>Add photos — listings with photos get 5× more views</li>
  <li>Include the exact address or neighborhood — it helps in search</li>
  <li>Respond to enquiries fast — the first minutes matter most</li>
</ul>
<a href="https://t.me/flatfinderil_bot" class="btn">Open Bot →</a>
<hr class="divider">
<p style="color:#64748b;font-size:13px;">Good luck! If you need help — just message us in Telegram. 🤝</p>
"""


def send_private_welcome(user_id: int, lang: str, name: str, email: str,
                         listing_id: int, city: str, price: int,
                         deal_label: str) -> bool:
    """Send welcome email to a private individual after publishing a listing."""
    if not email:
        return False
    try:
        from email_reporter import _send_email_simple
        subjects = {
            "ru": f"🏠 Объявление #{listing_id} опубликовано — FlatFinderIL",
            "en": f"🏠 Your listing #{listing_id} is live — FlatFinderIL",
            "he": f"🏠 המודעה #{listing_id} פורסמה — FlatFinderIL",
        }
        effective_lang = lang if lang in ("ru", "he", "en") else "ru"
        body = _private_body(effective_lang, name, listing_id, city, price, deal_label)
        html = _wrap(body, effective_lang, accent="#f59e0b")
        ok = _send_email_simple(email, subjects.get(effective_lang, subjects["en"]), html)
        if ok:
            logger.info(f"[WELCOME] Private email sent user={user_id} lang={effective_lang}")
        return ok
    except Exception as e:
        logger.error(f"[WELCOME] Private email failed user={user_id}: {e}")
        return False


def send_service_welcome(user_id: int, svc_type: str, lang: str,
                         name: str, email: str) -> bool:
    """
    Send a welcome email to a newly registered service provider.

    svc_type: "movers" | "packers" | "cleaning"
    lang:     "ru" | "he" | "en"
    """
    if not email:
        logger.debug(f"[WELCOME] No email for service user={user_id}, skipping")
        return False

    content = _SERVICE_CONTENT.get(svc_type)
    if not content:
        logger.warning(f"[WELCOME] Unknown svc_type={svc_type!r}")
        return False

    # Fall back to Russian if language not translated
    effective_lang = lang if lang in ("ru", "he", "en") else "ru"

    subject  = content["subjects"].get(effective_lang, content["subjects"]["en"])
    body_fn  = content["bodies"].get(effective_lang, content["bodies"]["en"])
    body_html = body_fn(name)
    html     = _wrap(body_html, effective_lang, accent=content["accent"])

    try:
        from email_reporter import _send_email_simple
        ok = _send_email_simple(email, subject, html)
        if ok:
            logger.info(f"[WELCOME] Service email sent user={user_id} type={svc_type} lang={effective_lang}")
        else:
            logger.warning(f"[WELCOME] Service email failed user={user_id} type={svc_type}")
        return ok
    except Exception as e:
        logger.error(f"[WELCOME] Service email exception user={user_id}: {e}")
        return False
