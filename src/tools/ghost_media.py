"""Ghost media helper: download & upload images safely.

Functions:
- download_image(url) -> (bytes, filename, content_type) | None
- upload_image_to_ghost(image_bytes, filename, content_type) -> str | None

Constraints:
- Accept only jpg/png/webp; size <= GHOST_MAX_IMAGE_MB (default 4 MB)
- Use requests.Session with retries, timeouts, headers; follow redirects
- Validate scheme (http/https only) and content-type
- Deduplicate within run using URL and content hash caches
- Ghost credentials from env: GHOST_URL, GHOST_ADMIN_API_KEY
"""
import os
import re
import time
import hashlib
from typing import Optional, Tuple
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import jwt

# Module-level caches (same run)
_URL_CACHE: dict[str, str] = {}
_HASH_CACHE: dict[str, str] = {}

_ALLOWED_CT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

_DEFAULT_MAX_MB = float(os.getenv("GHOST_MAX_IMAGE_MB", "4") or 4)
_MAX_BYTES = int(_DEFAULT_MAX_MB * 1024 * 1024)
_TIMEOUT = int(os.getenv("GHOST_IMAGE_UPLOAD_TIMEOUT", "20") or 20)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/110.0 Safari/537.36"
)


def _requests_session() -> requests.Session:
    sess = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST"),
    )
    adapter = HTTPAdapter(max_retries=retries)
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    return sess


def _is_http(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


def _safe_filename_from_url(url: str, fallback_ext: str) -> str:
    try:
        p = urlparse(url)
        name = os.path.basename(p.path) or "image"
        # strip query
        name = re.sub(r"\?.*$", "", name)
        # remove dangerous chars
        name = re.sub(r"[^A-Za-z0-9._-]", "-", name)
        # enforce extension
        if not os.path.splitext(name)[1]:
            name += fallback_ext
        # clamp length
        return name[:120]
    except Exception:
        return f"image{fallback_ext}"


def download_image(url: str) -> Optional[Tuple[bytes, str, str]]:
    url = (url or "").strip()
    if not _is_http(url):
        print(f"[IMG] skipped invalid scheme: {url}")
        return None

    # URL cache hit
    cached = _URL_CACHE.get(url)
    if cached:
        print(f"[IMG] skipped (already uploaded): {url}")
        # We don't have bytes here, but upload step will read from HASH cache when present
        # Return None to indicate no need to re-download; pipeline will rely on URL cache in upload
        return None

    sess = _requests_session()
    headers = {"User-Agent": _USER_AGENT, "Accept": "image/*"}
    try:
        resp = sess.get(url, headers=headers, timeout=_TIMEOUT, allow_redirects=True, stream=True)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[IMG] download failed: {url} -> {e}")
        return None

    ct = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
    if ct not in _ALLOWED_CT:
        print(f"[IMG] skipped content-type {ct} for {url}")
        return None

    # Check length limit
    clen = resp.headers.get("Content-Length")
    if clen:
        try:
            if int(clen) > _MAX_BYTES:
                print(f"[IMG] skipped over size ({clen} bytes) {url}")
                return None
        except Exception:
            pass

    # Read up to max bytes
    buf = bytearray()
    for chunk in resp.iter_content(chunk_size=64 * 1024):
        if chunk:
            buf.extend(chunk)
            if len(buf) > _MAX_BYTES:
                print(f"[IMG] skipped (stream over size) {url}")
                return None
    data = bytes(buf)

    # Dedup by content hash
    h = hashlib.sha256(data).hexdigest()
    if h in _HASH_CACHE:
        _URL_CACHE[url] = _HASH_CACHE[h]
        print(f"[IMG] dedup by content hash for {url}")
        # Return bytes anyway to allow optional re-upload if needed

    filename = _safe_filename_from_url(url, _ALLOWED_CT[ct])
    return data, filename, ct


def _make_admin_jwt(admin_api_key: str) -> str:
    try:
        kid, secret_hex = admin_api_key.split(":", 1)
    except ValueError:
        raise RuntimeError("GHOST_ADMIN_API_KEY must be 'id:secret'")
    secret = bytes.fromhex(secret_hex)
    now = int(time.time())
    token = jwt.encode({"iat": now, "exp": now + 300, "aud": "/admin/"}, secret, algorithm="HS256", headers={"kid": kid})
    return token.decode("utf-8") if isinstance(token, bytes) else token


def upload_image_to_ghost(image_bytes: bytes, filename: str, content_type: str) -> Optional[str]:
    # Dedup by content hash
    h = hashlib.sha256(image_bytes).hexdigest()
    if h in _HASH_CACHE:
        url = _HASH_CACHE[h]
        print(f"[IMG] uploaded (cache hit): {url}")
        return url

    ghost_url = (os.getenv("GHOST_URL", "") or "").rstrip("/")
    admin_key = os.getenv("GHOST_ADMIN_API_KEY", "")
    if not ghost_url or not admin_key:
        print("[IMG] missing GHOST_URL or GHOST_ADMIN_API_KEY")
        return None

    token = _make_admin_jwt(admin_key)
    api = f"{ghost_url}/ghost/api/admin/images/upload/"

    files = {
        "file": (filename, image_bytes, content_type),
    }
    headers = {
        "Authorization": f"Ghost {token}",
        "Accept": "application/json",
        # Do NOT set Content-Type; requests will set multipart boundary
        "User-Agent": _USER_AGENT,
    }

    try:
        resp = requests.post(api, headers=headers, files=files, timeout=_TIMEOUT)
    except requests.RequestException as e:
        print(f"[IMG] upload failed: {e}")
        return None

    if resp.status_code >= 300:
        print(f"[IMG] upload error {resp.status_code}: {resp.text[:300]}")
        return None

    try:
        data = resp.json()
    except Exception:
        print(f"[IMG] upload bad JSON: {resp.text[:300]}")
        return None

    # Ghost may return {"images":[{"url":"..."}]} or {"url":"..."}
    ghost_image_url: Optional[str] = None
    if isinstance(data, dict):
        if "images" in data and isinstance(data["images"], list) and data["images"]:
            ghost_image_url = (data["images"][0] or {}).get("url")
        elif "url" in data:
            ghost_image_url = data.get("url")
    ghost_image_url = (ghost_image_url or "").strip()
    if not ghost_image_url:
        print(f"[IMG] upload response missing url: {data}")
        return None

    # Update caches
    _HASH_CACHE[h] = ghost_image_url
    print(f"[IMG] uploaded: {ghost_image_url}")
    return ghost_image_url
