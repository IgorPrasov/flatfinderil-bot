from i18n import get_lang, get_property_type_name, get_district_name, get_infra_name, t
from translator import translate_listing_fields

def _price_str(price: int, deal_type: str, lang: str) -> str:
    if deal_type == "rent":
        unit = {"ru": "₪/мес", "en": "₪/mo", "he": "₪/חודש"}.get(lang, "₪/мес")
        return f"{price:,} {unit}".replace(",", " ")
    else:
        if price >= 1_000_000:
            mln = {"ru": "млн ₪", "en": "M ₪", "he": "מיל' ₪"}.get(lang, "млн ₪")
            return f"{price / 1_000_000:.1f} {mln}"
        return f"{price:,} ₪".replace(",", " ")

def format_listing_card(listing: dict, ctx=None, index: int = None, total: int = None) -> str:
    lang = get_lang(ctx) if ctx else "ru"
    listing = translate_listing_fields(listing, lang)
    prop_type = get_property_type_name(listing["property_type"], lang)
    deal_emoji = "🔑" if listing["deal_type"] == "rent" else "🏷"
    deal_label = {"ru":"Аренда","en":"Rent","he":"שכירות"}.get(lang) if listing["deal_type"]=="rent" else {"ru":"Продажа","en":"Sale","he":"מכירה"}.get(lang)
    price_str = _price_str(listing["price"], listing["deal_type"], lang)
    pool_str = {"ru":"🏊 Есть бассейн","en":"🏊 Pool available","he":"🏊 יש בריכה"}.get(lang) if listing.get("pool") else {"ru":"🚫 Без бассейна","en":"🚫 No pool","he":"🚫 אין בריכה"}.get(lang)
    parking = listing.get("parking", 0)
    if parking == 0:
        park_str = {"ru":"❌ Без парковки","en":"❌ No parking","he":"❌ ללא חניה"}.get(lang)
    elif parking == 1:
        park_str = {"ru":"🚗 1 место","en":"🚗 1 space","he":"🚗 מקום 1"}.get(lang)
    elif parking == 2:
        park_str = {"ru":"🚗🚗 2 места","en":"🚗🚗 2 spaces","he":"🚗🚗 2 מקומות"}.get(lang)
    else:
        park_str = {"ru":f"🚗 {parking} места","en":f"🚗 {parking} spaces","he":f"🚗 {parking} מקומות"}.get(lang)
    infra_list = listing.get("infrastructure", [])
    infra_str = ""
    if infra_list:
        infra_items = [get_infra_name(k, lang) for k in infra_list[:5]]
        infra_label = {"ru":"Инфраструктура","en":"Infrastructure","he":"תשתיות"}.get(lang)
        infra_str = f"\n🏙 <b>{infra_label}:</b> " + " · ".join(infra_items)
    district_key = listing.get("district")
    district_name = get_district_name(district_key, lang) if district_key else ""
    header = ""
    if index is not None and total is not None:
        card_word = {"ru":"Объявление","en":"Listing","he":"מודעה"}.get(lang)
        of_word = {"ru":"из","en":"of","he":"מתוך"}.get(lang)
        header = f"📋 <i>{card_word} {index+1} {of_word} {total}</i>\n\n"
    photo = listing.get("photos", ["🏠"])[0]
    sqm_label = {"ru":"кв.м","en":"sq.m","he":'מ"ר'}.get(lang, "sq.m")
    city_label = {"ru":"Город","en":"City","he":"עיר"}.get(lang)
    hood_label = {"ru":"Район","en":"Area","he":"אזור"}.get(lang)
    rooms_label = {"ru":"Комнат","en":"Rooms","he":"חדרים"}.get(lang)
    floor_label = {"ru":"Этаж","en":"Floor","he":"קומה"}.get(lang)
    area_label = {"ru":"Площадь","en":"Area","he":"שטח"}.get(lang)
    added_label = {"ru":"Добавлено","en":"Added","he":"נוסף"}.get(lang)
    return (
        f"{header}{photo} <b>{listing['title']}</b>\n\n"
        f"{deal_emoji} <b>{deal_label}</b>  |  {prop_type}\n"
        f"💰 <b>{price_str}</b>\n\n"
        f"📍 <b>{city_label}:</b> {listing['city']}{f' ({district_name})' if district_name else ''}\n"
        f"🏘 <b>{hood_label}:</b> {listing.get('neighborhood','—')}\n"
        f"🚪 <b>{rooms_label}:</b> {listing['rooms']}  |  🏗 <b>{floor_label}:</b> {listing['floor']}\n"
        f"📐 <b>{area_label}:</b> {listing.get('area_sqm','—')} {sqm_label}\n\n"
        f"{pool_str}\n{park_str}{infra_str}\n\n"
        f"📝 {listing['description']}\n\n"
        f"📅 <i>{added_label}: {listing.get('date_added','—')}</i>"
    )

def format_search_summary(filters: dict, ctx) -> str:
    lang = get_lang(ctx)
    def _tr(key, **kw): return t(key, ctx, **kw)
    lines = [_tr("summary_title")]
    deal = filters.get("deal_type")
    if deal:
        lines.append(_tr("sum_deal", val=_tr("deal_rent") if deal=="rent" else _tr("deal_buy")))
    if filters.get("property_types"):
        lines.append(_tr("sum_ptype", val=", ".join([get_property_type_name(p,lang) for p in filters["property_types"]])))
    if filters.get("district"):
        lines.append(_tr("sum_district", val=get_district_name(filters["district"],lang)))
    if filters.get("city"):
        lines.append(_tr("sum_city", val=filters["city"]))
    rooms_min = filters.get("rooms_min")
    rooms_max = filters.get("rooms_max")
    if rooms_min and rooms_max:
        lines.append(_tr("sum_rooms", val=f"{rooms_min} – {rooms_max}"))
    elif rooms_min:
        lines.append(_tr("sum_rooms", val=_tr("sum_rooms_from", v=rooms_min)))
    elif rooms_max:
        lines.append(_tr("sum_rooms", val=_tr("sum_rooms_to", v=rooms_max)))
    deal_type = filters.get("deal_type","rent")
    price_min = filters.get("price_min")
    price_max = filters.get("price_max")
    def _fmt(v): return _price_str(v, deal_type, lang)
    if price_min and price_max:
        lines.append(_tr("sum_price", val=f"{_fmt(price_min)} – {_fmt(price_max)}"))
    elif price_min:
        lines.append(_tr("sum_price", val=_tr("sum_price_from", v=_fmt(price_min))))
    elif price_max:
        lines.append(_tr("sum_price", val=_tr("sum_price_to", v=_fmt(price_max))))
    parking = filters.get("parking_min")
    if parking is not None:
        lines.append(_tr("sum_parking_any") if parking==0 else _tr("sum_parking", n=parking))
    if filters.get("pool"):
        lines.append(_tr("sum_pool"))
    elevator = filters.get("elevator")
    if elevator == "yes":
        lines.append(_tr("sum_elevator", val={"ru":"Есть","en":"Yes","he":"יש"}.get(lang,"Yes")))
    if filters.get("infrastructure"):
        lines.append(_tr("sum_infra", val=", ".join([get_infra_name(k,lang) for k in filters["infrastructure"]])))
    if filters.get("with_photos"):
        lines.append(_tr("sum_with_photos"))
    if len(lines)==1: lines.append(_tr("sum_all"))
    return "\n".join(lines)

def format_welcome(name: str, ctx) -> str:
    return t("welcome", ctx, name=name)
