"""
Overpass API (OpenStreetMap) helper for finding infrastructure POIs near a location.
Results are cached in poi_cache.json to avoid repeated API calls.
"""
import json
import os
import ssl
import urllib.request
import urllib.parse
import logging

# macOS / Railway SSL fix
_SSL_CTX = ssl._create_unverified_context()

logger = logging.getLogger(__name__)

# Map bot infrastructure keys → OSM tags
INFRA_OSM = {
    "mall": [
        ('shop', 'mall'),
        ('shop', 'supermarket'),
        ('amenity', 'marketplace'),
    ],
    "school": [
        ('amenity', 'school'),
    ],
    "kindergarten": [
        ('amenity', 'kindergarten'),
    ],
    "park": [
        ('leisure', 'park'),
        ('leisure', 'garden'),
    ],
    "gym": [
        ('leisure', 'fitness_centre'),
        ('leisure', 'sports_centre'),
        ('leisure', 'stadium'),
    ],
    "hospital": [
        ('amenity', 'hospital'),
        ('amenity', 'clinic'),
    ],
    "beach": [
        ('natural', 'beach'),
    ],
    "transport": [
        ('amenity', 'bus_station'),
        ('railway', 'station'),
        ('railway', 'halt'),
        ('highway', 'bus_stop'),
    ],
    "restaurant": [
        ('amenity', 'restaurant'),
        ('amenity', 'cafe'),
        ('amenity', 'food_court'),
    ],
    "synagogue": [
        ('amenity', 'place_of_worship'),
    ],
}

_DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
_CACHE_FILE = os.path.join(_DATA_DIR, "poi_cache.json")
_CACHE_TTL_DAYS = 30  # refresh cache after 30 days


def _load_cache() -> dict:
    try:
        if os.path.exists(_CACHE_FILE):
            with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_cache(cache: dict):
    try:
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    except Exception:
        pass


def get_pois(lat: float, lng: float, infra_type: str, radius: int = 3000) -> list:
    """
    Return list of (lat, lng) for POIs of given infrastructure type
    within `radius` meters of (lat, lng).
    Results are cached per city-grid-cell and infra type.
    """
    tags = INFRA_OSM.get(infra_type, [])
    if not tags:
        return []

    # Cache key: round to 2 decimal places (~1 km grid)
    cache_key = f"{round(lat, 2)},{round(lng, 2)},{infra_type},{radius}"
    cache = _load_cache()
    if cache_key in cache:
        return [tuple(p) for p in cache[cache_key]]

    # Build Overpass QL query
    parts = []
    for k, v in tags:
        if infra_type == "synagogue":
            # special case: filter by religion=jewish
            parts.append(f'node["amenity"="place_of_worship"]["religion"="jewish"](around:{radius},{lat},{lng});')
            parts.append(f'way["amenity"="place_of_worship"]["religion"="jewish"](around:{radius},{lat},{lng});')
        else:
            parts.append(f'node["{k}"="{v}"](around:{radius},{lat},{lng});')
            parts.append(f'way["{k}"="{v}"](around:{radius},{lat},{lng});')

    # Deduplicate
    parts = list(dict.fromkeys(parts))

    query = f"[out:json][timeout:15];({''.join(parts)});out center;"

    try:
        data = urllib.parse.urlencode({"data": query}).encode("utf-8")
        req = urllib.request.Request(
            "https://overpass-api.de/api/interpreter",
            data=data,
            method="POST",
            headers={"User-Agent": "FlatFinderIL-Bot/1.0"},
        )
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            result = json.loads(resp.read())

        pois = []
        for el in result.get("elements", []):
            if el.get("type") == "node":
                pois.append((el["lat"], el["lon"]))
            elif el.get("type") == "way" and "center" in el:
                pois.append((el["center"]["lat"], el["center"]["lon"]))

        cache[cache_key] = pois
        _save_cache(cache)
        logger.info(f"Overpass: {len(pois)} POIs for {infra_type} near ({lat:.2f},{lng:.2f})")
        return pois

    except Exception as e:
        logger.warning(f"Overpass API error for {infra_type}: {e}")
        return []


def nearest_distance(listing_lat: float, listing_lng: float,
                     city_lat: float, city_lng: float,
                     infra_types: list) -> float:
    """
    Return distance in meters from listing to nearest POI of any infra type.
    Falls back to a large number if no POIs found.
    """
    from geocoding import haversine
    min_dist = float("inf")
    for itype in infra_types:
        pois = get_pois(city_lat, city_lng, itype, radius=5000)
        for plat, plng in pois:
            d = haversine(listing_lat, listing_lng, plat, plng)
            if d < min_dist:
                min_dist = d
    return min_dist
