"""
One-time deduplication script for listings_db.json.
Removes text-duplicate listings, keeping the best version (with R2 photo).
Safe to run while bot is stopped or between cycles.
"""
import json, os, re, sys

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "listings_db.json")

def fingerprint(text: str) -> str:
    t = re.sub(r'\s+', '', text.lower())
    t = re.sub(r'[^\wЀ-ӿא-ת]', '', t)
    return t[:200]

def score(listing: dict) -> int:
    """Higher = better: prefer R2 photos, then any photo, then more recent."""
    photos = listing.get("photos", [])
    s = 0
    if any("r2.dev" in p for p in photos): s += 100
    if any(p.startswith("http") for p in photos): s += 10
    date = listing.get("date_added", "")
    s += len(date)  # longer date string = more recent format
    return s

with open(DB_FILE) as f:
    data = json.load(f)

listings = data["listings"]
print(f"Before: {len(listings)} listings")

seen_urls: dict[str, str] = {}   # url -> lid
seen_fps:  dict[str, str] = {}   # fingerprint -> lid
to_remove = []
fingerprints: dict[str, bool] = {}

for lid, l in listings.items():
    url = l.get("source_url", "").strip()
    desc = l.get("description", "")
    source = l.get("source", "")

    # URL dedup
    if url:
        if url in seen_urls:
            prev_lid = seen_urls[url]
            if score(l) > score(listings[prev_lid]):
                to_remove.append(prev_lid)
                seen_urls[url] = lid
            else:
                to_remove.append(lid)
            continue
        seen_urls[url] = lid

    # Text fingerprint dedup (only for parser listings)
    if desc and source in ("facebook", "telegram"):
        fp = fingerprint(desc)
        if fp in seen_fps:
            prev_lid = seen_fps[fp]
            if score(l) > score(listings[prev_lid]):
                to_remove.append(prev_lid)
                seen_fps[fp] = lid
            else:
                to_remove.append(lid)
            continue
        seen_fps[fp] = lid

for lid in set(to_remove):
    if lid in listings:
        del listings[lid]

# Build fingerprint index for future dedup
data["listing_fingerprints"] = {}
for l in listings.values():
    desc = l.get("description", "")
    if desc and l.get("source") in ("facebook", "telegram"):
        fp = fingerprint(desc)
        data["listing_fingerprints"][fp] = True

print(f"After:  {len(listings)} listings")
print(f"Removed: {len(set(to_remove))} duplicates")
print(f"Fingerprints indexed: {len(data['listing_fingerprints'])}")

tmp = DB_FILE + ".tmp"
with open(tmp, "w") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
os.replace(tmp, DB_FILE)
print("Done. Database updated.")
