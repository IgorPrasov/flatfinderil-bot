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

RSS_SOURCES = [
    {
        "name": "Times of Israel",
        "url": "https://www.timesofisrael.com/topic/real-estate/feed/",
        "lang": "en",
        "category_hint": None,
    },
    {
        "name": "Times of Israel",
        "url": "https://www.timesofisrael.com/feed/",
        "lang": "en",
        "category_hint": None,
    },
    {
        "name": "Globes",
        "url": "https://www.globes.co.il/webservice/rss/rssfeeder.asmx/FeederNode?iID=1124",
        "lang": "he",
        "category_hint": None,
    },
    {
        "name": "Calcalist",
        "url": "https://www.calcalist.co.il/rss/mador/5.xml",
        "lang": "he",
        "category_hint": None,
    },
    {
        "name": "Ynet",
        "url": "https://www.ynet.co.il/Integration/StoryRss3082.xml",
        "lang": "he",
        "category_hint": None,
    },
    {
        "name": "Bank of Israel",
        "url": "https://www.boi.org.il/en/newsandpublications/pressreleases/rss/",
        "lang": "en",
        "category_hint": "mortgage",
    },
    {
        "name": "Jerusalem Post",
        "url": "https://www.jpost.com/rss/rssfeedsrealestate.aspx",
        "lang": "en",
        "category_hint": None,
    },
]

# ── Keyword tables ─────────────────────────────────────────────────────────────

_RELEVANT_KW = [
    # Hebrew
    "דירה", "דיור", 'נדל"ן', "נדל", "בית", "שכירות", "מכירה", "קנייה",
    "בנייה", "משכנתא", "ריבית", "בנק", "קבלן", "שכונה", "מגדל",
    "פרויקט", "מחיר", "שוק הנדל", "התחדשות",
    # English
    "real estate", "apartment", "housing", "property", "rent", "mortgage",
    "interest rate", "bank", "construction", "developer", "neighborhood",
    "homebuyer", "home price", "affordable housing",
]

_CATEGORY_KW = {
    "mortgage": [
        "משכנתא", "ריבית", "פריים", "הלוואה", "בנק ישראל", "בנק",
        "מימון", "ריבית הבנק",
        "mortgage", "interest rate", "prime rate", "loan", "bank of israel",
        "bank", "financing", "boi", "rate cut", "rate hike",
    ],
    "program": [
        "מחיר למשתכן", "מחיר לדירה", "דיור בר השגה", "לוטריה", "פיס",
        "סיוע בשכר דירה", "דיור ציבורי", "משרד הבינוי", "תוכנית דיור",
        "זכאות", "ממשלה",
        "affordable", "lottery", "subsidy", "government program",
        "ministry of housing", "social housing", "mechir lamishtaken",
        "first-time buyer",
    ],
    "project": [
        "פרויקט", "בנייה", "קבלן", "התחדשות עירונית", "פינוי בינוי",
        'תמ"א', "תמ״א", "מגדל", "שכונה חדשה", "תכנית בנייה",
        "project", "construction", "developer", "urban renewal",
        "tower", "new neighborhood", "new development", "pinui binui",
    ],
}


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _classify(text: str) -> str:
    t = text.lower()
    for cat, kws in _CATEGORY_KW.items():
        if any(kw.lower() in t for kw in kws):
            return cat
    return "news"


def _is_relevant(text: str) -> bool:
    t = text.lower()
    return any(kw.lower() in t for kw in _RELEVANT_KW)


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


def _fetch_source(source: dict) -> list:
    try:
        resp = requests.get(
            source["url"], timeout=12,
            headers={"User-Agent": "FlatFinderIL/1.0 (+https://flatfinderil.com)"},
        )
        resp.raise_for_status()

        # Try fixing encoding for Hebrew
        content = resp.content
        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            # Try stripping BOM / bad chars
            content = content.lstrip(b"\xef\xbb\xbf")
            root = ET.fromstring(content)

        items = []
        for item in root.findall(".//item"):
            title   = _strip_html(item.findtext("title") or "")
            desc    = _strip_html(item.findtext("description") or "")[:400]
            link    = (item.findtext("link") or "").strip()
            pub     = item.findtext("pubDate") or ""

            combined = f"{title} {desc}"
            if not _is_relevant(combined):
                continue

            cat = source.get("category_hint") or _classify(combined)

            items.append({
                "category": cat,
                "title":    title,
                "body":     desc,
                "date":     _parse_date(pub),
                "source":   source["name"],
                "url":      link,
                "lang":     source["lang"],
            })

        logger.info(f"[NEWS] {source['name']} ({source['url'][:40]}…): {len(items)} items")
        return items

    except Exception as e:
        logger.warning(f"[NEWS] {source['name']} failed: {e}")
        return []


def fetch_all_news() -> dict:
    all_items = []
    for src in RSS_SOURCES:
        all_items.extend(_fetch_source(src))

    # Sort newest first
    all_items.sort(key=lambda x: x.get("date", ""), reverse=True)

    # Deduplicate by first 60 chars of title
    seen, deduped = set(), []
    for item in all_items:
        key = item["title"][:60].lower()
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    deduped = deduped[:60]  # keep top 60

    ticker = [item["title"] for item in deduped[:10] if item["title"]]

    result = {
        "updated": datetime.now().isoformat(),
        "ticker":  ticker,
        "total":   len(deduped),
        "items":   deduped,
    }

    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"[NEWS] Cache saved: {len(deduped)} items")
    except Exception as e:
        logger.warning(f"[NEWS] Cache write error: {e}")

    return result


def get_news(category: str = None, lang: str = None, limit: int = 20) -> dict:
    """Return cached news (refreshes if stale > REFRESH_INTERVAL min)."""
    cached = None
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            updated = datetime.fromisoformat(cached.get("updated", "2000-01-01"))
            if datetime.now() - updated > timedelta(minutes=REFRESH_INTERVAL):
                cached = None  # stale
    except Exception:
        cached = None

    if cached is None:
        cached = fetch_all_news()

    items = cached.get("items", [])

    if category:
        items = [i for i in items if i.get("category") == category]
    if lang:
        items = [i for i in items if i.get("lang") == lang]

    return {
        "updated": cached.get("updated"),
        "ticker":  cached.get("ticker", []),
        "total":   len(items),
        "items":   items[:limit],
    }


def start_news_refresh_loop():
    """Start background thread that refreshes news every REFRESH_INTERVAL min."""
    def _loop():
        # Initial fetch after 5s (let bot fully start first)
        time.sleep(5)
        while True:
            try:
                fetch_all_news()
            except Exception as e:
                logger.error(f"[NEWS] Refresh loop error: {e}")
            time.sleep(REFRESH_INTERVAL * 60)

    t = threading.Thread(target=_loop, daemon=True, name="news-refresh")
    t.start()
    logger.info("[NEWS] Refresh loop started")
