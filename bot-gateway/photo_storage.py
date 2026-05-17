"""
Cloudflare R2 photo storage for parsed listings.

Required env vars:
  R2_ACCOUNT_ID        — Cloudflare account ID
  R2_ACCESS_KEY_ID     — R2 API token access key
  R2_SECRET_ACCESS_KEY — R2 API token secret
  R2_BUCKET            — bucket name (default: flatfinderil-photos)
  R2_PUBLIC_URL        — public base URL, e.g. https://pub-xxx.r2.dev
"""
import os
import hashlib
import logging
import requests

logger = logging.getLogger(__name__)

R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY = os.environ.get("R2_ACCESS_KEY_ID", "")
R2_SECRET_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET     = os.environ.get("R2_BUCKET", "flatfinderil-photos")
R2_PUBLIC_URL = os.environ.get("R2_PUBLIC_URL", "").rstrip("/")

_client = None
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def is_enabled() -> bool:
    return bool(R2_ACCOUNT_ID and R2_ACCESS_KEY and R2_SECRET_KEY and R2_PUBLIC_URL)


def _get_client():
    global _client
    if _client is None:
        import boto3
        from botocore.config import Config
        _client = boto3.client(
            "s3",
            endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=R2_ACCESS_KEY,
            aws_secret_access_key=R2_SECRET_KEY,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )
    return _client


def _object_key(url: str, folder: str) -> str:
    h = hashlib.md5(url.encode()).hexdigest()
    raw_ext = url.split("?")[0].rsplit(".", 1)[-1].lower()
    ext = raw_ext if raw_ext in ("jpg", "jpeg", "png", "webp", "gif") else "jpg"
    return f"{folder}/{h}.{ext}"


def upload_from_url(image_url: str, folder: str = "misc") -> str:
    """Download image from URL and upload to R2.
    Returns R2 public URL on success, empty string on failure.
    """
    if not is_enabled():
        return ""
    try:
        client = _get_client()
        key = _object_key(image_url, folder)

        # Dedup: if already uploaded, return existing URL
        try:
            client.head_object(Bucket=R2_BUCKET, Key=key)
            return f"{R2_PUBLIC_URL}/{key}"
        except Exception:
            pass

        resp = requests.get(image_url, timeout=15, headers=_HEADERS)
        if resp.status_code != 200 or len(resp.content) < 2000:
            return ""

        content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
        client.put_object(Bucket=R2_BUCKET, Key=key, Body=resp.content, ContentType=content_type)
        return f"{R2_PUBLIC_URL}/{key}"

    except Exception as e:
        logger.warning(f"[R2] upload_from_url failed {image_url}: {e}")
        return ""


def upload_bytes(data: bytes, name: str, content_type: str = "image/jpeg",
                 folder: str = "misc") -> str:
    """Upload raw bytes to R2. Returns public URL."""
    if not is_enabled():
        return ""
    try:
        h = hashlib.md5(data).hexdigest()
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else "jpg"
        key = f"{folder}/{h}.{ext}"
        _get_client().put_object(Bucket=R2_BUCKET, Key=key, Body=data, ContentType=content_type)
        return f"{R2_PUBLIC_URL}/{key}"
    except Exception as e:
        logger.warning(f"[R2] upload_bytes failed: {e}")
        return ""


def upload_photos(urls: list, folder: str = "misc", max_photos: int = 5) -> list:
    """Upload a list of image URLs to R2. Returns list of R2 public URLs (skips failures)."""
    result = []
    for url in urls[:max_photos]:
        r2_url = upload_from_url(url, folder)
        if r2_url:
            result.append(r2_url)
    return result
