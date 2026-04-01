import logging

logger = logging.getLogger(__name__)

try:
    from deep_translator import GoogleTranslator
    _TRANSLATOR_AVAILABLE = True
except ImportError:
    logger.warning("deep_translator not installed — translation disabled, original text will be shown")
    _TRANSLATOR_AVAILABLE = False

# In-memory cache: (text, target_lang) -> translated_text
_cache: dict = {}

# deep-translator uses ISO 639-1 codes; Hebrew is "iw" for Google Translate
LANG_MAP = {
    "ru": "ru",
    "en": "en",
    "he": "iw",
}


def _google_lang(bot_lang: str) -> str:
    return LANG_MAP.get(bot_lang, bot_lang)


def translate_text(text: str, target_lang: str) -> str:
    """Translate text to target_lang. Returns original on failure or if library unavailable."""
    if not text or not text.strip():
        return text
    if not _TRANSLATOR_AVAILABLE:
        return text

    cache_key = (text, target_lang)
    if cache_key in _cache:
        return _cache[cache_key]

    try:
        google_target = _google_lang(target_lang)
        result = GoogleTranslator(source="auto", target=google_target).translate(text)
        _cache[cache_key] = result or text
    except Exception as e:
        logger.warning(f"Translation failed for lang={target_lang}: {e}")
        _cache[cache_key] = text

    return _cache[cache_key]


def translate_listing_fields(listing: dict, target_lang: str) -> dict:
    """Return a copy of the listing with title, description, and neighborhood translated."""
    translated = listing.copy()
    translated["title"] = translate_text(listing.get("title", ""), target_lang)
    translated["description"] = translate_text(listing.get("description", ""), target_lang)
    if listing.get("neighborhood"):
        translated["neighborhood"] = translate_text(listing["neighborhood"], target_lang)
    return translated
