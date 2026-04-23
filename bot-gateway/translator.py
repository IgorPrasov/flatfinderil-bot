"""
translator.py — Автоперевод объявлений через Google Translate (deep-translator).

Стратегия:
  1. Переводы хранятся прямо в объявлении: listing["_translations"][lang]
  2. При добавлении объявления → фоновый поток переводит на все 4 языка
  3. При показе → сначала смотрим в _translations, затем вызываем API
  4. API-кеш дублируется на диск (translations_cache.json) — выживает перезапуск
"""

import json
import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

try:
    from deep_translator import GoogleTranslator
    _TRANSLATOR_AVAILABLE = True
except ImportError:
    logger.warning("deep_translator not installed — translation disabled")
    _TRANSLATOR_AVAILABLE = False

# ── Языковые коды Google Translate ────────────────────────────────────────────
# deep-translator использует ISO 639-1; иврит = "iw" (не "he")
LANG_MAP = {
    "ru": "ru",
    "en": "en",
    "he": "iw",
    "fr": "fr",
}

ALL_LANGS = list(LANG_MAP.keys())   # ["ru", "en", "he", "fr"]

# ── Дисковый кеш ──────────────────────────────────────────────────────────────
_DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
_CACHE_FILE = os.path.join(_DATA_DIR, "translations_cache.json")
_cache_lock = threading.Lock()
_cache: dict[str, str] = {}      # key = "lang:text_hash" → translated


def _load_cache():
    global _cache
    if os.path.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                _cache = json.load(f)
        except Exception:
            _cache = {}


def _save_cache():
    try:
        tmp = _CACHE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False)
        os.replace(tmp, _CACHE_FILE)
    except Exception as e:
        logger.warning(f"Could not save translation cache: {e}")


_load_cache()


def _cache_key(text: str, lang: str) -> str:
    # Use first 200 chars as key prefix (avoid huge keys)
    return f"{lang}:{text[:200]}"


# ── Базовый перевод (с кешем) ─────────────────────────────────────────────────

def translate_text(text: str, target_lang: str) -> str:
    """
    Translate text to target_lang.
    - Checks disk cache first.
    - Falls back to original on error.
    - Rate-limited: 0.3s between calls.
    """
    if not text or not text.strip() or not _TRANSLATOR_AVAILABLE:
        return text

    key = _cache_key(text, target_lang)
    with _cache_lock:
        if key in _cache:
            return _cache[key]

    try:
        google_target = LANG_MAP.get(target_lang, target_lang)
        result = GoogleTranslator(source="auto", target=google_target).translate(text)
        translated = result or text
    except Exception as e:
        logger.warning(f"Translation failed ({target_lang}): {e}")
        translated = text

    with _cache_lock:
        _cache[key] = translated
        # Save every 50 new entries
        if len(_cache) % 50 == 0:
            _save_cache()

    return translated


# ── Перевод объявления ─────────────────────────────────────────────────────────

def translate_listing_fields(listing: dict, target_lang: str) -> dict:
    """
    Return copy of listing with title, description, neighborhood translated.

    Priority:
      1. listing["_translations"][target_lang] — pre-translated (instant)
      2. API call — stored in _translations for next time
    """
    translated = listing.copy()

    # 1. Check pre-stored translations
    stored = listing.get("_translations", {}).get(target_lang)
    if stored:
        if stored.get("title"):
            translated["title"] = stored["title"]
        if stored.get("description"):
            translated["description"] = stored["description"]
        if stored.get("neighborhood"):
            translated["neighborhood"] = stored["neighborhood"]
        return translated

    # 2. API call (and schedule background save)
    changed = False
    for field in ("title", "description", "neighborhood"):
        original = listing.get(field)
        if original and isinstance(original, str) and original.strip():
            result = translate_text(original, target_lang)
            if result and result != original:
                translated[field] = result
                changed = True

    # Store result back into the listing asynchronously
    if changed:
        _schedule_save_translation(listing.get("id"), target_lang, {
            "title":        translated.get("title", ""),
            "description":  translated.get("description", ""),
            "neighborhood": translated.get("neighborhood", ""),
        })

    return translated


# ── Пре-трансляция (фоновый поток) ────────────────────────────────────────────

def pre_translate_listing(listing_id: int, listing: dict):
    """
    Translate listing to all 4 languages in background.
    Saves results into listing["_translations"] via database.update_listing().
    Called automatically by add_listing() for parser-sourced listings.
    """
    translations: dict[str, dict] = listing.get("_translations", {})
    changed = False

    for lang in ALL_LANGS:
        if lang in translations:
            continue   # already done

        lang_trans: dict[str, str] = {}
        for field in ("title", "description", "neighborhood"):
            original = listing.get(field)
            if original and isinstance(original, str) and original.strip():
                result = translate_text(original, lang)
                lang_trans[field] = result
                time.sleep(0.25)   # gentle rate limiting

        if lang_trans:
            translations[lang] = lang_trans
            changed = True

    if changed:
        try:
            import database as db
            db.update_listing(listing_id, {"_translations": translations})
            _save_cache()
            logger.info(f"✅ Pre-translated listing #{listing_id}")
        except Exception as e:
            logger.warning(f"Could not save translations for #{listing_id}: {e}")


def schedule_pre_translate(listing_id: int, listing: dict):
    """Launch pre_translate_listing() in a daemon thread."""
    t = threading.Thread(
        target=pre_translate_listing,
        args=(listing_id, listing),
        daemon=True,
        name=f"translate-{listing_id}",
    )
    t.start()


def _schedule_save_translation(listing_id, lang: str, lang_data: dict):
    """Store a single-language translation result back to the DB asynchronously."""
    if not listing_id:
        return

    def _save():
        try:
            import database as db
            listing = db.get_listing(listing_id)
            if not listing:
                return
            translations = listing.get("_translations", {})
            existing = translations.get(lang, {})
            existing.update({k: v for k, v in lang_data.items() if v})
            translations[lang] = existing
            db.update_listing(listing_id, {"_translations": translations})
        except Exception as e:
            logger.debug(f"_schedule_save_translation error: {e}")

    threading.Thread(target=_save, daemon=True, name=f"save-trans-{listing_id}").start()
