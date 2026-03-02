"""Image extraction helper.

Select best representative image URL from scraped article dict.

Priority:
1) Pre-existing scraper-provided image fields (e.g., 'image_url', 'image')
2) HTML <meta property="og:image"> or <meta name="twitter:image">
3) First <img src> in HTML content

Only returns http/https URLs. Returns None if nothing suitable.
"""
from typing import Optional, Dict, Any, Iterable, List, Tuple
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


def _looks_like_site_logo(url: str) -> bool:
    lowered = url.lower()
    bad_markers = (
        "logo",
        "favicon",
        "icon",
        "sprite",
        "avatar",
        "default",
        "placeholder",
        "site-logo",
        "brand",
        "masthead",
        "header",
        "banner",
        "badge",
        "/assets/",
        "/static/",
        "/themes/",
        "gravatar",
        "author",
    )
    return any(marker in lowered for marker in bad_markers)


def _looks_like_generic_image(url: str, article_url: str) -> bool:
    """Check if image looks generic (home page, default, etc.)."""
    url_lower = url.lower()
    article_lower = article_url.lower()
    
    # If image is from a different domain, likely generic CDN image
    try:
        img_domain = urlparse(url).netloc.lower()
        article_domain = urlparse(article_url).netloc.lower()
        # Remove 'www.' for comparison
        img_domain = img_domain.replace("www.", "")
        article_domain = article_domain.replace("www.", "")
        
        # Generic CDN patterns
        generic_cdns = ("cdn.", "static.", "images.", "img.", "media.")
        if any(img_domain.startswith(g) for g in generic_cdns):
            # CDN is OK if path looks article-specific
            if "default" in url_lower or "placeholder" in url_lower:
                return True
    except Exception:
        pass
    
    # Generic image name patterns
    generic_names = (
        "default",
        "placeholder",
        "noimage",
        "fallback",
        "thumb-default",
        "og-image",
        "share",
        "social",
    )
    return any(g in url_lower for g in generic_names)


def _extract_src_from_img(tag: Any) -> Optional[str]:
    # Prefer explicit src
    src = str(tag.get("src") or "").strip()
    if _is_http_url(src):
        return src

    # Common lazy-load attributes
    for attr in ("data-src", "data-original", "data-lazy", "data-srcset", "data-image"):
        val = str(tag.get(attr) or "").strip()
        if not val:
            continue
        if attr.endswith("srcset"):
            best = _best_src_from_srcset(val)
            if best:
                return best
        elif _is_http_url(val):
            return val

    # srcset fallback
    srcset = str(tag.get("srcset") or "").strip()
    return _best_src_from_srcset(srcset)


def _best_src_from_srcset(srcset: str) -> Optional[str]:
    if not srcset:
        return None
    candidates: List[Tuple[int, str]] = []
    for part in srcset.split(","):
        chunk = part.strip()
        if not chunk:
            continue
        bits = chunk.split()
        url = bits[0].strip()
        if not _is_http_url(url):
            continue
        width = 0
        if len(bits) > 1:
            size = bits[1].strip().lower()
            if size.endswith("w"):
                try:
                    width = int(size[:-1])
                except Exception:
                    width = 0
        candidates.append((width, url))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def _get_int_attr(tag: Any, attr: str) -> Optional[int]:
    val = str(tag.get(attr) or "").strip()
    if not val:
        return None
    try:
        return int(float(val))
    except Exception:
        return None


def _iter_image_candidates(soup: BeautifulSoup, article_url: str) -> Iterable[Tuple[str, int]]:
    # Prefer images inside <article> or <main> when present
    article = soup.find("article")
    main = soup.find("main")
    
    # Priority: article > main > body
    if article:
        roots = [article]
    elif main:
        roots = [main]
    else:
        # Fallback: look in body but skip header/footer/nav
        body = soup.find("body")
        if body:
            roots = [body]
        else:
            roots = [soup]

    for root in roots:
        if not root:
            continue
        
        # Skip images in header/footer/nav/aside
        for skip_tag in root.find_all(["header", "footer", "nav", "aside"]):
            skip_tag.decompose()
        
        for img in root.find_all("img"):
            src = _extract_src_from_img(img)
            if not _is_http_url(src):
                continue

            width = _get_int_attr(img, "width")
            height = _get_int_attr(img, "height")
            area = 0
            if width and height:
                area = width * height

            # Skip tracking pixels or tiny images
            if width and height and (width <= 50 or height <= 50 or area < 200 * 200):
                continue

            score = 50
            if article:
                score += 40
            if img.find_parent("figure") is not None:
                score += 30
            if img.get("class") and any("featured" in str(c).lower() or "hero" in str(c).lower() for c in img.get("class", [])):
                score += 25
            if area:
                score += min(int(area / 1500), 50)
            if _looks_like_site_logo(src):
                score -= 50
            if _looks_like_generic_image(src, article_url):
                score -= 40

            yield src, score



def extract_image_candidates(article: Dict[str, Any]) -> List[str]:
    candidates: List[Tuple[str, int]] = []
    article_url = article.get("url", "")

    # 0) Direct image from scraper if present (highest priority)
    for key in ("image_url", "image", "thumbnail", "feature_image"):
        val = str(article.get(key) or "").strip()
        if _is_http_url(val):
            score = 90
            if _looks_like_site_logo(val):
                score -= 40
            candidates.append((val, score))

    # 1) Parse HTML metadata for og:image / twitter:image
    html = (article.get("html") or article.get("summary_html") or "")
    if html:
        try:
            soup = BeautifulSoup(html, "html.parser")

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
                        score = 60
                        if _looks_like_site_logo(content):
                            score -= 40
                        candidates.append((content, score))

            # Collect in-article images
            candidates.extend(list(_iter_image_candidates(soup, article_url)))
        except Exception:
            pass

    if not candidates:
        return []

    # Sort by score and de-duplicate while preserving order
    candidates.sort(key=lambda x: x[1], reverse=True)
    seen: set[str] = set()
    ordered: List[str] = []
    for url, _ in candidates:
        if url in seen:
            continue
        seen.add(url)
        ordered.append(url)
    return ordered


def extract_best_image_url(article: Dict[str, Any]) -> Optional[str]:
    candidates = extract_image_candidates(article)
    return candidates[0] if candidates else None
