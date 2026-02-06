"""Image extraction helper.

Select best representative image URL from scraped article dict.

Priority:
1) Pre-existing scraper-provided image fields (e.g., 'image_url', 'image')
2) HTML <meta property="og:image"> or <meta name="twitter:image">
3) First <img src> in HTML content

Only returns http/https URLs. Returns None if nothing suitable.
"""
from typing import Optional, Dict, Any
from urllib.parse import urlparse

from bs4 import BeautifulSoup


def _is_http_url(url: Optional[str]) -> bool:
    if not url:
        return False
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def extract_best_image_url(article: Dict[str, Any]) -> Optional[str]:
    # 0) Direct image from scraper if present
    for key in ("image_url", "image", "thumbnail", "feature_image"):
        val = str(article.get(key) or "").strip()
        if _is_http_url(val):
            return val

    # 1) Parse HTML metadata for og:image / twitter:image
    html = (article.get("html") or article.get("summary_html") or "")
    url = str(article.get("url") or "")
    if html:
        try:
            soup = BeautifulSoup(html, "html.parser")
            # Meta candidates
            meta_props = [
                ("property", "og:image"),
                ("name", "og:image"),
                ("property", "og:image:url"),
                ("name", "twitter:image"),
                ("property", "twitter:image"),
                ("name", "twitter:image:src"),
            ]
            for attr, value in meta_props:
                tag = soup.find("meta", attrs={attr: value})
                if tag:
                    content = str(tag.get("content") or "").strip()
                    if _is_http_url(content):
                        return content

            # First <img> in article
            img = soup.find("img")
            if img:
                src = str(img.get("src") or "").strip()
                if _is_http_url(src):
                    return src
        except Exception:
            # If parsing fails, continue
            pass

    # Fallback: None
    return None
