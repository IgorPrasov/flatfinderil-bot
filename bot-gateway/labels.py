def lbl(context, ru, en, he):
    from i18n import get_lang
    lang = get_lang(context)
    if lang == "en": return en
    if lang == "he": return he
    return ru

def confirmed(context, ru, en, he, value):
    label = lbl(context, ru, en, he)
    return f"✅ <b>{label}:</b> {value}"
