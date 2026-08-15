"""
news_fetcher.py — RSS news fetcher for FlatFinderIL
Fetches real estate, social housing and banking news from Israeli media.
Caches to news_cache.json, auto-refreshes every REFRESH_INTERVAL minutes.
"""

import os
import re
import json
import time
import logging
import threading
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

import requests

logger = logging.getLogger(__name__)

_DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
CACHE_FILE = os.path.join(_DATA_DIR, "news_cache.json")
REFRESH_INTERVAL = 60  # minutes between auto-refresh

# ── RSS Sources ────────────────────────────────────────────────────────────────
# Each entry: name, url, lang (he/en), optional category_hint (forces category)

RSS_SOURCES = [
    # Google News — Hebrew real estate (נדל"ן ישראל)
    {
        "name": "Google News נדל\"ן",
        "url": "https://news.google.com/rss/search?q=%D7%A0%D7%93%D7%9C%22%D7%9F+%D7%99%D7%A9%D7%A8%D7%90%D7%9C&hl=he&gl=IL&ceid=IL:iw",
        "lang": "he",
        "category_hint": None,
        "force_relevant": True,
    },
    # Google News — Hebrew mortgage (משכנתא)
    {
        "name": "Google News משכנתא",
        "url": "https://news.google.com/rss/search?q=%D7%9E%D7%A9%D7%9B%D7%A0%D7%AA%D7%90+%D7%99%D7%A9%D7%A8%D7%90%D7%9C&hl=he&gl=IL&ceid=IL:iw",
        "lang": "he",
        "category_hint": "mortgage",
        "force_relevant": True,
    },
    # Google News — Hebrew apartments/rent (דירות שכירות)
    {
        "name": "Google News דירות",
        "url": "https://news.google.com/rss/search?q=%D7%93%D7%99%D7%A8%D7%95%D7%AA+%D7%A9%D7%9B%D7%99%D7%A8%D7%95%D7%AA+%D7%99%D7%A9%D7%A8%D7%90%D7%9C&hl=he&gl=IL&ceid=IL:iw",
        "lang": "he",
        "category_hint": None,
        "force_relevant": True,
    },
    # Google News — English real estate Israel
    {
        "name": "Google News Real Estate",
        "url": "https://news.google.com/rss/search?q=real+estate+israel&hl=en-IL&gl=IL&ceid=IL:en",
        "lang": "en",
        "category_hint": None,
        "force_relevant": True,
    },
    # Times of Israel — main feed (filter for RE topics)
    {
        "name": "Times of Israel",
        "url": "https://www.timesofisrael.com/feed/",
        "lang": "en",
        "category_hint": None,
        "force_relevant": False,
    },
    # Ynet — main news feed (filter for RE topics)
    {
        "name": "Ynet",
        "url": "https://www.ynet.co.il/Integration/StoryRss1854.xml",
        "lang": "he",
        "category_hint": None,
        "force_relevant": False,
    },
    # Walla economy feed (filter for RE topics)
    {
        "name": "Walla כלכלה",
        "url": "https://rss.walla.co.il/feed/9",
        "lang": "he",
        "category_hint": None,
        "force_relevant": False,
    },
    # Google News — developers / new construction projects (nationwide)
    {
        "name": "Google News יזמים/פרויקטים",
        "url": "https://news.google.com/rss/search?q=%D7%99%D7%96%D7%9D+%D7%A0%D7%93%D7%9C%22%D7%9F+%D7%A4%D7%A8%D7%95%D7%99%D7%A7%D7%98+%D7%91%D7%A0%D7%99%D7%99%D7%94&hl=he&gl=IL&ceid=IL:iw",
        "lang": "he",
        "category_hint": "developer",
        "force_relevant": True,
    },
    # Google News — construction specifically in Judea and Samaria
    {
        "name": "Google News יהודה ושומרון",
        "url": "https://news.google.com/rss/search?q=%D7%91%D7%A0%D7%99%D7%99%D7%94+%D7%99%D7%94%D7%95%D7%93%D7%94+%D7%95%D7%A9%D7%95%D7%9E%D7%A8%D7%95%D7%9F&hl=he&gl=IL&ceid=IL:iw",
        "lang": "he",
        "category_hint": "developer",
        "force_relevant": True,
        "region_hint": "judea_samaria",
    },
    # Arutz Sheva / Channel 7 — Hebrew general feed, strong Judea & Samaria coverage
    {
        "name": "ערוץ 7 (Arutz Sheva)",
        "url": "https://www.inn.co.il/Rss.aspx",
        "lang": "he",
        "category_hint": None,
        "force_relevant": False,
    },
]

# ── Relevance keywords (whole-phrase matching, not substring) ──────────────────
# Used ONLY for feeds that are not dedicated real-estate feeds (force_relevant=False)

_RELEVANT_PHRASES = [
    # Hebrew — specific enough to avoid false positives
    "נדל\"ן", "נדל'ן", "דירה", "דירות", "שכירות", "בנייה", "משכנתא",
    "ריבית הפריים", "מחיר למשתכן", "דיור בר השגה", "פינוי בינוי",
    "התחדשות עירונית", "קבלן", "שכונה", "פרויקט נדל",
    # Hebrew — developer-specific (real-estate terms only, NOT bare region/political terms —
    # those go in _JUDEA_SAMARIA_PHRASES for tagging only, to avoid matching unrelated
    # political/security news about the same region)
    "יזם נדל", "יזמי נדל", "יחידות דיור", "היתרי בנייה", "היתר בנייה",
    # English — specific phrases
    "real estate", "apartment", "housing market", "home price", "property price",
    "mortgage rate", "interest rate", "homebuyer", "affordable housing",
    "construction project", "new development", "rental market",
]

# ── Judea & Samaria region detection (tags items regardless of source) ─────────
_JUDEA_SAMARIA_PHRASES = [
    "יהודה ושומרון", "יו\"ש", "התיישבות", "מתנחלים", "מאחז",
    "אריאל", "מעלה אדומים", "ביתר עילית", "מודיעין עילית", "אפרת",
    "קריית ארבע", "אלון מורה", "עפרה", "כפר אדומים", "גוש עציון",
    "judea and samaria", "west bank", "settlement", "yesha",
]

# ── Classification keywords ────────────────────────────────────────────────────

_CATEGORY_KW = {
    "mortgage": [
        # Hebrew
        "משכנתא", "ריבית", "ריבית הפריים", "הלוואת דיור", "בנק ישראל",
        "מימון", "החזר חודשי",
        # English
        "mortgage", "interest rate", "prime rate", "housing loan",
        "bank of israel", "boi rate", "rate cut", "rate hike", "refinanc",
        "monthly payment",
    ],
    "program": [
        # Hebrew
        "מחיר למשתכן", "מחיר לדירה", "דיור בר השגה", "לוטריה", "הגרלה",
        "סיוע בשכר דירה", "דיור ציבורי", "משרד הבינוי", "תוכנית דיור",
        "זכאות", "הנחה לדיור", "דיור מסובסד",
        # English
        "affordable housing", "lottery", "housing subsidy", "government program",
        "ministry of housing", "social housing", "mechir lamishtaken",
        "first-time buyer", "first-time homebuyer",
    ],
    "project": [
        # Hebrew
        "פרויקט", "בנייה חדשה", "פינוי בינוי", "התחדשות עירונית",
        "תמ\"א 38", "תמ״א", "מגדל", "שכונה חדשה", "תכנית בנייה", "קבלן",
        "יחידות דיור",
        # English
        "construction project", "new development", "urban renewal",
        "new tower", "new neighborhood", "developer", "pinui binui",
        "building permit", "housing units",
    ],
}


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _is_relevant(text: str) -> bool:
    """Check if text is real-estate related using phrase matching."""
    t = text.lower()
    return any(phrase.lower() in t for phrase in _RELEVANT_PHRASES)


def _classify(text: str) -> str:
    """Return category: mortgage | program | project | news"""
    t = text.lower()
    # Check in priority order
    for cat in ("mortgage", "program", "project"):
        if any(kw.lower() in t for kw in _CATEGORY_KW[cat]):
            return cat
    return "news"


def _is_judea_samaria(text: str) -> bool:
    """Detect whether an item is about Judea & Samaria, regardless of source."""
    t = text.lower()
    return any(phrase.lower() in t for phrase in _JUDEA_SAMARIA_PHRASES)


def _parse_date(raw: str) -> str:
    if not raw:
        return datetime.now().strftime("%Y-%m-%d")
    try:
        return parsedate_to_datetime(raw).strftime("%Y-%m-%d")
    except Exception:
        pass
    try:
        return raw[:10]
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def _extract_link(item_el) -> str:
    """Extract link from RSS item element (handles various formats)."""
    # Standard RSS 2.0 <link>
    link = (item_el.findtext("link") or "").strip()
    if link and link.startswith("http"):
        return link

    # Some feeds put link in <guid isPermaLink="true">
    guid = item_el.find("guid")
    if guid is not None:
        is_perm = guid.get("isPermaLink", "true").lower()
        gtext = (guid.text or "").strip()
        if is_perm != "false" and gtext.startswith("http"):
            return gtext

    # Atom <link href="...">
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    atom_link = item_el.find("atom:link", ns)
    if atom_link is not None:
        href = atom_link.get("href", "")
        if href.startswith("http"):
            return href

    return ""


def _fetch_source(source: dict) -> list:
    try:
        resp = requests.get(
            source["url"], timeout=15,
            headers={"User-Agent": "Mozilla/5.0 FlatFinderIL/1.0 (+https://flatfinderil.com)"},
        )
        resp.raise_for_status()

        content = resp.content.lstrip(b"\xef\xbb\xbf")  # strip BOM
        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            # Try removing problematic XML declarations
            content_str = content.decode("utf-8", errors="replace")
            content_str = re.sub(r"<\?xml[^?]*\?>", "", content_str)
            root = ET.fromstring(content_str.encode("utf-8"))

        force_relevant = source.get("force_relevant", False)
        items = []

        for item_el in root.findall(".//item"):
            title = _strip_html(item_el.findtext("title") or "")
            desc  = _strip_html(item_el.findtext("description") or "")[:500]
            link  = _extract_link(item_el)
            pub   = item_el.findtext("pubDate") or ""

            if not title:
                continue

            combined = f"{title} {desc}"

            # Skip if not relevant (only for non-dedicated feeds)
            if not force_relevant and not _is_relevant(combined):
                continue

            # For dedicated feeds, still skip obvious non-RE content
            # by checking the title doesn't contain very specific exclusion terms
            # (e.g. pure politics with no real estate angle)
            if force_relevant and not _is_relevant(combined):
                # Still try — dedicated feeds may have RE news phrased differently
                pass  # accept all from dedicated feeds

            cat = source.get("category_hint") or _classify(combined)
            region = source.get("region_hint") or ("judea_samaria" if _is_judea_samaria(combined) else None)

            items.append({
                "category": cat,
                "title":    title,
                "body":     desc,
                "date":     _parse_date(pub),
                "source":   source["name"],
                "url":      link,
                "lang":     source["lang"],
                "region":   region,
            })

        logger.info(f"[NEWS] {source['name']}: {len(items)} items from {source['url'][:60]}")
        return items

    except Exception as e:
        logger.warning(f"[NEWS] {source['name']} ({source['url'][:50]}) failed: {e}")
        return []


def fetch_all_news() -> dict:
    all_items = []
    for src in RSS_SOURCES:
        all_items.extend(_fetch_source(src))

    # Sort newest first
    all_items.sort(key=lambda x: x.get("date", ""), reverse=True)

    # Deduplicate by first 60 chars of title (case-insensitive)
    seen, deduped = set(), []
    for item in all_items:
        key = item["title"][:60].lower()
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    deduped = deduped[:60]

    # Build ticker from top items that have titles
    ticker = [item["title"] for item in deduped[:12] if item["title"]]

    result = {
        "updated": datetime.now().isoformat(),
        "ticker":  ticker,
        "total":   len(deduped),
        "items":   deduped,
    }

    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"[NEWS] Cache saved: {len(deduped)} items total")
    except Exception as e:
        logger.warning(f"[NEWS] Cache write error: {e}")

    return result


def get_news(category: str = None, lang: str = None, region: str = None, limit: int = 20) -> dict:
    """Return cached news, refreshing if stale > REFRESH_INTERVAL min."""
    cached = None
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            updated = datetime.fromisoformat(cached.get("updated", "2000-01-01"))
            if datetime.now() - updated > timedelta(minutes=REFRESH_INTERVAL):
                cached = None  # stale — refetch
    except Exception:
        cached = None

    if cached is None:
        cached = fetch_all_news()

    items = cached.get("items", [])
    if category:
        items = [i for i in items if i.get("category") == category]
    if lang:
        items = [i for i in items if i.get("lang") == lang]
    if region:
        items = [i for i in items if i.get("region") == region]

    return {
        "updated": cached.get("updated"),
        "ticker":  cached.get("ticker", []),
        "total":   len(items),
        "items":   items[:limit],
    }


def start_news_refresh_loop():
    """Start background thread that refreshes news every REFRESH_INTERVAL min."""
    def _loop():
        time.sleep(5)  # let bot fully start first
        while True:
            try:
                fetch_all_news()
            except Exception as e:
                logger.error(f"[NEWS] Refresh loop error: {e}")
            time.sleep(REFRESH_INTERVAL * 60)

    t = threading.Thread(target=_loop, daemon=True, name="news-refresh")
    t.start()
    logger.info("[NEWS] Refresh loop started")
