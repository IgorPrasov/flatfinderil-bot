"""
analytics_server.py — HTTP API сервер аналитики FlatFinderIL.

Endpoints:
  GET  /analytics?from=&to=       → полная аналитика (JSON)
  GET  /api/news?lang=&cat=&n=    → новости недвижимости (JSON)
  GET  /api/price-stats?city=&deal=&days= → статистика цен (JSON)
  GET  /api/daily-digest?city=&lang= → данные для утренней сводки (JSON)
  GET  /api/datagov?city=&rooms=&days= → сделки из data.gov.il (JSON)
  GET  /rss.xml?lang=&cat=        → RSS-лента новостей недвижимости
  POST /admin/cleanup-spam        → очистить спам из БД

Запуск:
  python3 analytics_server.py
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json, sys, os, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PORT = int(os.environ.get("ANALYTICS_PORT", os.environ.get("PORT", 8765)))


# ── RSS XML генератор ─────────────────────────────────────────────────────────

def _build_rss(items: list[dict], lang: str = "he", category: str = None) -> str:
    """Генерировать RSS 2.0 XML из списка новостей."""
    import html as _html
    from datetime import datetime

    lang_labels = {
        "ru": ("Новости недвижимости Израиля", "Актуальные новости рынка недвижимости"),
        "en": ("Israel Real Estate News",      "Latest real estate news from Israel"),
        "he": ("חדשות נדל\"ן ישראל",          "חדשות שוק הנדל\"ן הישראלי"),
        "fr": ("Actualités immobilières Israël","Dernières nouvelles de l'immobilier en Israël"),
    }
    title, desc = lang_labels.get(lang, lang_labels["en"])

    pub_date = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")

    items_xml = []
    for item in items[:40]:
        item_title = _html.escape(item.get("title", ""))
        item_desc  = _html.escape(item.get("body",  "")[:300])
        item_link  = _html.escape(item.get("url",   ""))
        item_date  = item.get("date", "")
        item_cat   = item.get("category", "news")
        item_src   = item.get("source", "")

        # Convert YYYY-MM-DD to RFC 2822
        try:
            from datetime import datetime as _dt
            d = _dt.strptime(item_date, "%Y-%m-%d")
            item_date_rss = d.strftime("%a, %d %b %Y 09:00:00 +0300")
        except Exception:
            item_date_rss = pub_date

        items_xml.append(f"""    <item>
      <title>{item_title}</title>
      <description>{item_desc}</description>
      <link>{item_link}</link>
      <pubDate>{item_date_rss}</pubDate>
      <category>{item_cat}</category>
      <source url="{item_link}">{_html.escape(item_src)}</source>
      <guid isPermaLink="false">{item_link}</guid>
    </item>""")

    items_str = "\n".join(items_xml)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{_html.escape(title)}</title>
    <description>{_html.escape(desc)}</description>
    <link>https://flatfinderil.com</link>
    <language>{lang}</language>
    <lastBuildDate>{pub_date}</lastBuildDate>
    <atom:link href="https://flatfinderil-bot-production.up.railway.app/rss.xml" rel="self" type="application/rss+xml"/>
    <image>
      <url>https://flatfinderil.com/logo.png</url>
      <title>{_html.escape(title)}</title>
      <link>https://flatfinderil.com</link>
    </image>
{items_str}
  </channel>
</rss>"""


# ── Вспомогательные функции ───────────────────────────────────────────────────

def _json_response(handler, data: dict, status: int = 200):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Content-Length", len(body))
    handler.end_headers()
    handler.wfile.write(body)


def _xml_response(handler, xml: str, status: int = 200):
    body = xml.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/rss+xml; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Content-Length", len(body))
    handler.end_headers()
    handler.wfile.write(body)


def _qs(parsed_url, key: str, default=None):
    """Безопасно получить первый query-param."""
    vals = parse_qs(parsed_url.query).get(key)
    return vals[0] if vals else default


# ── Request handler ───────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip("/") or "/"

        try:
            # ── /analytics ────────────────────────────────────────────────────
            if path in ("/analytics", "/"):
                from analytics import get_analytics
                date_from = _qs(parsed, "from")
                date_to   = _qs(parsed, "to")
                data = get_analytics(date_from=date_from, date_to=date_to)
                _json_response(self, data)

            # ── /api/news ─────────────────────────────────────────────────────
            elif path == "/api/news":
                from news_fetcher import get_news
                lang  = _qs(parsed, "lang")
                cat   = _qs(parsed, "cat")
                limit = int(_qs(parsed, "n") or 20)
                data  = get_news(category=cat, lang=lang, limit=limit)
                _json_response(self, data)

            # ── /rss.xml ──────────────────────────────────────────────────────
            elif path == "/rss.xml":
                from news_fetcher import get_news
                lang  = _qs(parsed, "lang", "he")
                cat   = _qs(parsed, "cat")
                news  = get_news(category=cat, lang=lang, limit=40)
                xml   = _build_rss(news.get("items", []), lang=lang, category=cat)
                _xml_response(self, xml)

            # ── /api/price-stats ──────────────────────────────────────────────
            elif path == "/api/price-stats":
                city  = _qs(parsed, "city")
                deal  = _qs(parsed, "deal", "rent")
                days  = int(_qs(parsed, "days") or 30)
                data  = _get_price_stats(city=city, deal_type=deal, days=days)
                _json_response(self, data)

            # ── /api/daily-digest ─────────────────────────────────────────────
            elif path == "/api/daily-digest":
                from morning_digest import get_daily_stats, build_digest_text
                city = _qs(parsed, "city")
                lang = _qs(parsed, "lang", "ru")
                stats = get_daily_stats(city=city)
                text  = build_digest_text(city=city, lang=lang, include_datagov=False)
                _json_response(self, {"stats": stats, "text": text, "lang": lang})

            # ── /api/datagov ──────────────────────────────────────────────────
            elif path == "/api/datagov":
                from datagov_api import get_market_overview, get_recent_deals
                city  = _qs(parsed, "city", "Нетания")
                rooms = _qs(parsed, "rooms")
                days  = int(_qs(parsed, "days") or 90)
                if rooms:
                    data = get_recent_deals(city_ru=city, rooms=int(rooms), last_days=days)
                else:
                    data = get_market_overview(city_ru=city, last_days=days)
                _json_response(self, data)

            # ── /api/backoffice-stats ─────────────────────────────────────────
            elif path == "/api/backoffice-stats":
                data = _get_backoffice_daily_stats()
                _json_response(self, data)

            # ── /api/miniapp/* ────────────────────────────────────────────────
            elif path.startswith("/api/miniapp/"):
                from mini_app_api import route as miniapp_route
                params = parse_qs(parsed.query)
                headers = dict(self.headers)
                result, status = miniapp_route("GET", path, params, {}, headers)
                _json_response(self, result, status)

            else:
                _json_response(self, {"error": "Not found"}, 404)

        except Exception as e:
            _json_response(self, {"error": str(e)}, 500)

    def do_POST(self):
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip("/")

        content_len = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_len) if content_len > 0 else b"{}"
        try:
            body = json.loads(raw_body)
        except Exception:
            body = {}

        try:
            if path == "/admin/cleanup-spam":
                result = _cleanup_spam_listings()
                _json_response(self, result)

            # ── POST /api/miniapp/* ──────────────────────────────────────────
            elif path.startswith("/api/miniapp/"):
                from mini_app_api import route as miniapp_route
                params = parse_qs(urlparse(self.path).query)
                headers = dict(self.headers)
                result, status = miniapp_route("POST", path, params, body, headers)
                _json_response(self, result, status)

            else:
                _json_response(self, {"error": "Not found"}, 404)
        except Exception as e:
            _json_response(self, {"error": str(e)}, 500)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Telegram-Init-Data")
        self.end_headers()

    def log_message(self, fmt, *args):
        pass   # Отключаем стандартные access logs


# ── Вспомогательные функции данных ───────────────────────────────────────────

def _get_price_stats(city: str = None, deal_type: str = "rent", days: int = 30) -> dict:
    """Агрегация цен из собственной БД (для графиков на сайте)."""
    import statistics as _st
    from datetime import date, timedelta
    from collections import defaultdict
    import database as db

    data     = db._load()
    listings = list(data.get("listings", {}).values())
    cutoff   = (date.today() - timedelta(days=days)).isoformat()
    today    = date.today().isoformat()

    def _match(l):
        if not l.get("active"):
            return False
        if l.get("deal_type") != deal_type:
            return False
        if city and l.get("city", "").lower() != city.lower():
            return False
        if l.get("date_added", "") < cutoff:
            return False
        return True

    filtered = [l for l in listings if _match(l)]
    prices   = [l["price"] for l in filtered if (l.get("price") or 0) > 0]

    # По дням
    daily: dict[str, list] = defaultdict(list)
    for l in filtered:
        d = l.get("date_added", "")
        p = l.get("price") or 0
        if d and p > 0:
            daily[d].append(p)

    daily_series = []
    for i in range(days):
        d = (date.today() - timedelta(days=days - i - 1)).isoformat()
        ps = daily.get(d, [])
        daily_series.append({
            "date":   d,
            "avg":    round(_st.mean(ps)) if ps else None,
            "count":  len(ps),
        })

    # По городам
    city_data: dict[str, list] = defaultdict(list)
    for l in filtered:
        c = l.get("city")
        p = l.get("price") or 0
        if c and p > 0:
            city_data[c].append(p)

    by_city = sorted(
        [{"city": c, "avg": round(_st.mean(ps)), "count": len(ps)}
         for c, ps in city_data.items() if ps],
        key=lambda x: x["count"], reverse=True
    )[:15]

    # По источнику
    src_data: dict[str, list] = defaultdict(list)
    for l in filtered:
        src = l.get("source", "manual")
        p   = l.get("price") or 0
        if p > 0:
            src_data[src].append(p)

    return {
        "city":      city or "all",
        "deal_type": deal_type,
        "days":      days,
        "total":     len(filtered),
        "overall": {
            "avg":    round(_st.mean(prices))   if prices else 0,
            "median": round(_st.median(prices)) if prices else 0,
            "min":    min(prices)               if prices else 0,
            "max":    max(prices)               if prices else 0,
            "count":  len(prices),
        },
        "daily_series": daily_series,
        "by_city":      by_city,
        "by_source": {
            src: {"avg": round(_st.mean(ps)), "count": len(ps)}
            for src, ps in src_data.items() if ps
        },
    }


def _get_backoffice_daily_stats() -> dict:
    """Дневная статистика для бэк-офиса: новые частники по городам."""
    from datetime import date, timedelta
    from collections import defaultdict
    import database as db

    data     = db._load()
    listings = list(data.get("listings", {}).values())
    today    = date.today().isoformat()
    yday     = (date.today() - timedelta(days=1)).isoformat()

    def _count(filter_fn):
        return sum(1 for l in listings if filter_fn(l))

    def _by_city(filter_fn):
        counter: dict[str, int] = defaultdict(int)
        for l in listings:
            if filter_fn(l):
                city = l.get("city", "—")
                counter[city] += 1
        return dict(sorted(counter.items(), key=lambda x: x[1], reverse=True))

    is_new     = lambda l: l.get("date_added", "") == today
    is_private = lambda l: l.get("poster_type") in ("private", "unknown")
    is_active  = lambda l: bool(l.get("active"))

    return {
        "date": today,
        "new_today": {
            "total":   _count(lambda l: is_new(l)),
            "private": _count(lambda l: is_new(l) and is_private(l)),
            "agent":   _count(lambda l: is_new(l) and l.get("poster_type") == "agent"),
            "by_city": _by_city(lambda l: is_new(l) and is_private(l)),
        },
        "new_yesterday": {
            "total":   _count(lambda l: l.get("date_added", "") == yday),
            "private": _count(lambda l: l.get("date_added", "") == yday and is_private(l)),
        },
        "active_total": _count(is_active),
        "active_private": _count(lambda l: is_active(l) and is_private(l)),
        "blacklisted": _count(lambda l: l.get("poster_type") == "blacklist"),
    }


def _cleanup_spam_listings() -> dict:
    import database as db
    from telegram_parser import is_ad_or_spam
    data = db._load()
    removed = []
    for lid, listing in list(data["listings"].items()):
        if listing.get("source") not in ("telegram", "facebook"):
            continue
        text = (listing.get("description") or "") + " " + (listing.get("title") or "")
        if is_ad_or_spam(text):
            removed.append(lid)
    for lid in removed:
        del data["listings"][lid]
        for uid in data.get("user_listings", {}):
            if lid in data["user_listings"][uid]:
                data["user_listings"][uid].remove(lid)
    db._save(data)
    return {"removed": len(removed), "ids": removed[:50]}


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"✅ Analytics API on :{PORT}")
    print(f"   GET  /analytics")
    print(f"   GET  /api/news?lang=he&cat=mortgage")
    print(f"   GET  /rss.xml?lang=he")
    print(f"   GET  /api/price-stats?city=Нетания&deal=rent&days=30")
    print(f"   GET  /api/daily-digest?city=Нетания&lang=ru")
    print(f"   GET  /api/datagov?city=Нетания&days=90")
    print(f"   GET  /api/backoffice-stats")
    print(f"   POST /admin/cleanup-spam")
    server.serve_forever()
