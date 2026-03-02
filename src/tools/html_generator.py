"""
HTML Generator Tool for SafariNewsletter (Ollama Cloud optional).

Objectif:
- Générer un HTML "VeilleCyber-like" STABLE (même thème + même forme)
- À partir d'une newsletter texte au format Markdown simple
- Conversion déterministe (sans LLM) => rendu constant.
- Cache mémoire par hash.
"""

import os
import re
import html
import json
import hashlib
from typing import Dict, List, Tuple, Optional, Any

from ollama import Client
from src.configs.config import settings


_html_cache: Dict[str, str] = {}


def _try_parse_newsletter_json(text: str) -> Dict[str, Any]:
    stripped = (text or "").strip()
    if not stripped:
        print("[HTML_GENERATOR] JSON parse: Empty text")
        return {}
    if stripped[0] not in "[{":
        print(f"[HTML_GENERATOR] JSON parse: Text does not start with '[' or '{{', got: {stripped[:50]}")
        return {}
    try:
        data = json.loads(stripped)
        print(f"[HTML_GENERATOR] JSON parse: SUCCESS - parsed {type(data)} with {len(data) if isinstance(data, dict) else '?'} keys")
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"[HTML_GENERATOR] JSON parse: FAILED - {e}")
        return {}


# -------------------------
# Cache + client (optionnel)
# -------------------------
def _hash_content(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ollama_client() -> Client:
    if not settings.OLLAMA_API_KEY:
        raise RuntimeError("OLLAMA_API_KEY manquant (Ollama Cloud requis)")
    return Client(
        host="https://ollama.com",
        headers={"Authorization": "Bearer " + settings.OLLAMA_API_KEY},
    )


def _html_model() -> str:
    return (
        os.getenv("OLLAMA_HTML_MODEL")
        or getattr(settings, "OLLAMA_HTML_MODEL", "")
        or getattr(settings, "OLLAMA_MODEL", "gpt-oss:20b-cloud")
    )


def clear_html_cache() -> None:
    _html_cache.clear()
    print("[HTML_GENERATOR] Cache cleared")


# -------------------------
# Parsing helpers
# -------------------------
SEP_RE = re.compile(r"^\s*\*\s*\*\s*\*\s*$")
H1_RE = re.compile(r"^\s*#\s+(.*)\s*$")
H3_RE = re.compile(r"^\s*###\s+(.*)\s*$")
H4_RE = re.compile(r"^\s*####\s+(.*)\s*$")
BULLET_RE = re.compile(r"^\s*\*\s+(.*)\s*$")
NUM_RE = re.compile(r"^\s*(\d+)\.\s+(.*)\s*$")

MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\)]+)\)")
BARE_URL_RE = re.compile(r"(https?://\S+)")


_TAG_RE = re.compile(
    r"\[\s*(title|titre|subtitle|sous[-\s]?titre|heading|header)\s*\]\s*",
    flags=re.IGNORECASE,
)


def _clean_markdown_formatting(text: str) -> str:
    """
    Supprime les caractères de formatage Markdown + tags type [TITLE]
    """
    # Supprimer TOUTES les étoiles (**, *, etc.)
    text = re.sub(r"\*+", "", text)

    # Supprimer les underscores de formatage
    text = re.sub(r"__+", "", text)
    text = re.sub(r"_", "", text)

    # Supprimer les tags [TITLE] / [TITRE] / etc.
    text = _TAG_RE.sub("", text)

    # Retire les marqueurs de titre en début de ligne (#, ##, ###, etc.)
    text = re.sub(r"^\s*#+\s*", "", text)

    # Retire les # restants hors URL
    text = re.sub(r"(?!https?://[^\s]*)#", "", text)

    # Supprimer les backticks
    text = re.sub(r"`+", "", text)

    return text.strip()


def _extract_markdown_links(raw: str) -> str:
    """
    Convertit [texte](url) => <a ...>texte</a>
    et détecte aussi les URLs brutes.
    Escape HTML seulement pour les éléments dangereux.
    """
    # Escape minimal pour sécurité
    safe_text = raw.replace('<', '&lt;').replace('>', '&gt;')
    
    def repl(m: re.Match) -> str:
        label = m.group(1).replace('<', '&lt;').replace('>', '&gt;')
        url = html.escape(m.group(2))
        return (
            f'<a href="{url}" target="_blank" rel="noopener noreferrer" '
            f'style="color:#93c5fd;text-decoration:underline;">{label}</a>'
        )

    out = MD_LINK_RE.sub(repl, safe_text)

    # URLs brutes (si pas déjà dans un href)
    def repl_url(m: re.Match) -> str:
        url = m.group(1)
        esc = html.escape(url)
        return (
            f'<a href="{esc}" target="_blank" rel="noopener noreferrer" '
            f'style="color:#93c5fd;text-decoration:underline;">{esc}</a>'
        )

    out = BARE_URL_RE.sub(repl_url, out)
    return out


def _normalize_title_line(line: str) -> Tuple[str, Optional[str]]:
    """
    Essaie d'extraire (titre, url) si la ligne contient un lien.
    """
    raw = line.strip()

    # markdown link
    m = MD_LINK_RE.search(raw)
    if m:
        return _clean_markdown_formatting(m.group(1).strip()), m.group(2).strip()

    # (url)
    m = re.search(r"^(.*)\((https?://[^\)]+)\)\s*$", raw)
    if m:
        return _clean_markdown_formatting(m.group(1).strip()), m.group(2).strip()

    # "— url"
    m = re.search(r"^(.*)\s+—\s+(https?://\S+)\s*$", raw)
    if m:
        return _clean_markdown_formatting(m.group(1).strip()), m.group(2).strip()

    # URL brute dans la ligne
    m = BARE_URL_RE.search(raw)
    if m:
        url = m.group(1).strip()
        title = raw.replace(url, "").strip(" -—")
        title = _clean_markdown_formatting(title) if title else url
        return title, url

    return _clean_markdown_formatting(raw), None


def _final_cleanup_html(html_text: str) -> str:
    cleaned = re.sub(r"\*+", "", html_text)
    return cleaned


# -------------------------
# HTML theme
# -------------------------
def _wrap_template(body_html: str, page_title: str) -> str:
    return f"""<div style="font-family:'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;font-size:15px;font-weight:400;line-height:1.7;color:#e5e7eb;max-width:100%;background-color:#0a0a0a;">
  <style>
    body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0a0a0a; }}
    p {{ font-weight: 400; }}
    strong {{ font-weight: 500; }}
    h2 {{ font-weight: 500; }}
    h3 {{ font-weight: 500; }}
  </style>
  {body_html}
</div>"""


def _hr() -> str:
    # Divider "bande" très visible + fallback couleur (si gradient ignoré)
    return """
<div style="margin:28px 0;">
  <div style="
    height:14px;
    width:100%;
    display:block;
    border-radius:999px;
    background-color:#1f2937; /* fallback visible */
    border:1px solid rgba(148,163,184,0.35);
    box-shadow: 0 10px 18px rgba(0,0,0,0.25), 0 0 18px rgba(34,211,238,0.18);
    background-image:
      linear-gradient(90deg,
        rgba(15,23,42,0) 0%,
        rgba(34,211,238,0.55) 25%,
        rgba(59,130,246,0.35) 50%,
        rgba(34,211,238,0.55) 75%,
        rgba(15,23,42,0) 100%
      );
  ">&nbsp;</div>
</div>
"""


def _p(text: str) -> str:
    cleaned = _clean_markdown_formatting(text)
    t = _extract_markdown_links(cleaned)
    return f'<p style="margin:4px 0 14px 0;color:#e5e7eb;line-height:1.6;font-family:\'Inter\', sans-serif;font-weight:400;">{t}</p>'


def _meta_line(text: str) -> str:
    cleaned = _clean_markdown_formatting(text)
    t = _extract_markdown_links(cleaned)
    return f'<div style="margin:6px 0 16px 0;font-size:13px;color:#a5b4fc;font-family:\'Inter\', sans-serif;font-weight:400;">{t}</div>'


def _h2(text: str) -> str:
    # Sous-titres PLUS GRANDS + couleur différente
    cleaned = _clean_markdown_formatting(text)
    t = _extract_markdown_links(cleaned)
    return (
        '<div style="margin:26px 0 12px 0;'
        'font-size:22px;font-weight:500;letter-spacing:0.2px;'
        'color:#f472b6;font-family:\'Inter\', sans-serif;">'
        f'{t}</div>'
    )


def _h3_link(title: str, url: Optional[str]) -> str:
    clean_title = _clean_markdown_formatting(title)
    safe_title = html.escape(clean_title)
    if url:
        safe_url = html.escape(url)
        return (
            '<div style="margin:26px 0 18px 0;">'
            f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer" '
            'style="font-size:22px;font-weight:700;color:#FFFFFF;text-decoration:none;display:block;line-height:1.3;font-family:\'Inter\', sans-serif;"'
            f'>{safe_title}</a>'
            '</div>'
        )
    return (
        '<div style="margin:26px 0 18px 0;font-size:22px;font-weight:700;color:#FFFFFF;line-height:1.3;font-family:\'Inter\', sans-serif;">'
        f'{safe_title}</div>'
    )


def _img_vignette(src_url: str, alt_text: str) -> str:
    if not src_url:
        return ""
    safe_src = html.escape(src_url)
    safe_alt = html.escape(alt_text or "")
    # 140px wide vignette, rounded corners
    return (
        '<div style="margin:10px 0 14px 0;">'
        f'<img src="{safe_src}" alt="{safe_alt}" '
        'style="width:140px;height:auto;border-radius:8px;display:block;"/>'
        '</div>'
    )


def _label(text: str) -> str:
    cleaned = _clean_markdown_formatting(text.strip())
    t = html.escape(cleaned) if cleaned else ""
    return (
        '<div style="margin:16px 0 10px 0;font-size:13px;font-weight:500;'
        'text-transform:none;color:#93c5fd;font-family:\'Inter\', sans-serif;">'
        f'{t}</div>'
    )






def _spacer(margin_px: int = 8) -> str:
    """
    Spacer with content to avoid being stripped by email clients; keeps subtitle separated.
    """
    m = max(int(margin_px), 0)
    return f'<div style="margin:{m}px 0;line-height:0;font-size:0;">&nbsp;</div>'


def _line_break() -> str:
    """Explicit line break to survive aggressive sanitizers."""
    return '<br style="line-height:1.2;" />'


def _ul(items: List[str]) -> str:
    lis = []
    for it in items:
        cleaned = _clean_markdown_formatting(it)
        lis.append(
            '<li style="margin:0 0 6px 0;color:#e5e7eb;font-family:\'Inter\', sans-serif;font-weight:400;">'
            f'{_extract_markdown_links(cleaned)}'
            '</li>'
        )
    return (
        '<ul style="margin:4px 0 14px 18px;padding:0;color:#e5e7eb;line-height:1.5;font-family:\'Inter\', sans-serif;font-weight:400;">'
        + "".join(lis) +
        '</ul>'
    )


def _ol(items: List[str]) -> str:
    lis = []
    for it in items:
        cleaned = _clean_markdown_formatting(it)
        lis.append(
            '<li style="margin:0 0 6px 0;color:#e5e7eb;font-family:\'Inter\', sans-serif;font-weight:400;">'
            f'{_extract_markdown_links(cleaned)}'
            '</li>'
        )
    return (
        '<ol style="margin:0 0 12px 18px;padding:0;color:#e5e7eb;font-family:\'Inter\', sans-serif;font-weight:400;">'
        + "".join(lis) +
        '</ol>'
    )


# -------------------------
# JSON renderer
# -------------------------
def render_newsletter_json(data: Dict[str, Any]) -> Tuple[str, str]:
    page_title = _clean_markdown_formatting(str(data.get("title", "") or "7secure")) or "7secure"

    body_parts: List[str] = []
    
    # Track intro to avoid duplication
    intro_text = ""
    intro = data.get("intro") or data.get("introduction")
    if intro:
        intro_text = str(intro).strip().lower()
        body_parts.append(_p(str(intro)))

    headlines = data.get("headlines")
    if isinstance(headlines, list) and headlines:
        body_parts.append(_h2("Today's headlines"))
        # Filter out headlines that match intro to avoid duplication
        filtered_headlines = []
        for h in headlines:
            h_str = str(h).strip()
            if h_str and h_str.lower() != intro_text:
                filtered_headlines.append(h_str)
        if filtered_headlines:
            body_parts.append(_ul(filtered_headlines))

    # Track images already displayed to avoid duplication
    displayed_images: set[str] = set()

    stories = data.get("stories") or data.get("items") or []
    if isinstance(stories, list):
        print(f"[HTML_GENERATOR] Processing {len(stories)} stories")
        for idx, story in enumerate(stories):
            print(f"[HTML_GENERATOR] Story {idx+1}: {story.get('title', '(no title)')[:50]}")
            if not isinstance(story, dict):
                print(f"[HTML_GENERATOR] Story {idx+1} is not a dict, skipping")
                continue
            st_title = story.get("title") or ""
            st_url = story.get("url") or story.get("source")
            if st_title:
                print(f"[HTML_GENERATOR] Adding story {idx+1} title with URL: {st_url}")
                body_parts.append(_h3_link(str(st_title), str(st_url) if st_url else None))

            # Optional vignette image from pipeline enrichment (display only once per newsletter)
            img_url = story.get("image_url")
            if isinstance(img_url, str) and img_url.strip():
                img_url_clean = img_url.strip()
                if img_url_clean not in displayed_images:
                    body_parts.append(_img_vignette(img_url_clean, str(st_title or "")))
                    displayed_images.add(img_url_clean)
                else:
                    print(f"[HTML_GENERATOR] Story {idx+1}: skipped duplicate image {img_url_clean[:50]}")

            key_points = story.get("key_points") or story.get("keypoints") or story.get("points")
            if isinstance(key_points, list) and key_points:
                print(f"[HTML_GENERATOR] Story {idx+1}: Adding {len(key_points)} key points")
                body_parts.append('<br style="line-height:1.5;" />')
                body_parts.append('<br style="line-height:1.5;" />')
                body_parts.append(_label("Key Points:"))
                body_parts.append(_ul([str(p) for p in key_points if str(p).strip()]))

            desc = story.get("description") or story.get("summary")
            if desc:
                body_parts.append(_label("Description:"))
                body_parts.append(_p(str(desc)))

            wim = story.get("why_it_matters") or story.get("impact") or story.get("so_what")
            if wim:
                body_parts.append(_label("Why It Matters:"))
                body_parts.append(_p(str(wim)))

            # if idx < len(stories) - 1:
            #     body_parts.append(_hr())
            if idx > 0:
                body_parts.append(_hr())


    closing = data.get("closing") or data.get("outro") or data.get("conclusion")
    if closing:
        body_parts.append(_p(str(closing)))

    body_html = "".join(body_parts).strip()
    body_html = _final_cleanup_html(body_html)
    return page_title, body_html


# -------------------------
# Deterministic renderer
# -------------------------
def render_veillecyber_html(newsletter_text: str) -> Tuple[str, str]:
    lines = [ln.rstrip() for ln in (newsletter_text or "").splitlines()]

    page_title = "7secure"
    author = None
    date_line = None

    body_parts: List[str] = []
    pending_ul: List[str] = []
    pending_ol: List[str] = []
    in_story = False
    last_plain_line: Optional[str] = None
    last_plain_index: Optional[int] = None

    # Fix duplication: track intro and title
    seen_intro = False
    seen_intro_text = ""
    removed_title_line = False

    def flush_lists():
        nonlocal pending_ul, pending_ol, body_parts
        if pending_ul:
            body_parts.append(_ul(pending_ul))
            pending_ul = []
        if pending_ol:
            body_parts.append(_ol(pending_ol))
            pending_ol = []

    for ln in lines:
        if not ln.strip():
            continue

        cleaned_line = _clean_markdown_formatting(ln)

        # Remove duplicate intro (like "Hello, here's...")
        if not seen_intro and cleaned_line.lower().startswith("hello"):
            seen_intro = True
            seen_intro_text = cleaned_line.strip().lower()
            body_parts.append(_p(cleaned_line))
            continue
        if seen_intro and cleaned_line.strip().lower() == seen_intro_text:
            continue

        # Remove duplicate title line
        if page_title and cleaned_line.lower() == page_title.lower():
            if not removed_title_line:
                removed_title_line = True
                continue

        if SEP_RE.match(ln):
            flush_lists()
            in_story = False
            last_plain_line = None
            last_plain_index = None
            body_parts.append(_hr())
            continue

        m = H1_RE.match(ln)
        if m:
            flush_lists()
            in_story = False
            last_plain_line = None
            last_plain_index = None
            raw_title = m.group(1).strip()
            page_title = _clean_markdown_formatting(raw_title)
            continue

        lower_clean = cleaned_line.lower()
        if lower_clean in {"key points:", "description:", "why it matters:"}:
            flush_lists()
            in_story = True
            if last_plain_line is not None and last_plain_index is not None:
                title_txt, title_url = _normalize_title_line(last_plain_line)
                body_parts[last_plain_index] = _h3_link(title_txt, title_url)
            last_plain_line = None
            last_plain_index = None
            body_parts.append(_line_break())
            body_parts.append(_label(ln.strip()))
            continue

        m = H4_RE.match(ln)
        if m:
            flush_lists()
            text = m.group(1).strip()

            lower = text.lower()
            if lower in {
                "key points:", "description:", "why it matters:"
            }:
                in_story = True
                if last_plain_line is not None and last_plain_index is not None:
                    title_txt, title_url = _normalize_title_line(last_plain_line)
                    body_parts[last_plain_index] = _h3_link(title_txt, title_url)
                last_plain_line = None
                last_plain_index = None
                body_parts.append(_line_break())
                body_parts.append(_label(text))
            else:
                in_story = False
                last_plain_line = None
                last_plain_index = None
                body_parts.append(_h2(text.replace(":", "")))
            continue

        m = H3_RE.match(ln)
        if m:
            flush_lists()
            in_story = True
            last_plain_line = None
            last_plain_index = None
            title_line = m.group(1).strip()
            title, url = _normalize_title_line(title_line)
            body_parts.append(_h3_link(title, url))
            body_parts.append(_line_break())
            body_parts.append(_spacer())  # Espace après le sous-titre
            continue

        if ("min read" in ln) or ("—" in ln and any(ch.isdigit() for ch in ln)):
            if date_line is None and not in_story:
                date_line = ln.strip()
                continue

        m = BULLET_RE.match(ln)
        if m:
            if pending_ol:
                flush_lists()
            pending_ul.append(m.group(1).strip())
            continue

        m = NUM_RE.match(ln)
        if m:
            pending_ol.append(m.group(2).strip())
            continue

        flush_lists()

        if author and date_line and not in_story:
            body_parts.append(_meta_line(f"{author} — {date_line}"))
            author, date_line = None, None

        body_parts.append(_p(ln))
        last_plain_line = ln
        last_plain_index = len(body_parts) - 1

    flush_lists()

    if author and date_line:
        body_parts.insert(1, _meta_line(f"{author} — {date_line}"))

    body_html = "".join(body_parts).strip()
    body_html = _final_cleanup_html(body_html)
    return page_title, body_html

# -------------------------
# Main generator
# -------------------------
class HTMLGenerator:
    def __init__(self, model: str = "", use_cache: bool = True):
        self.use_cache = use_cache
        self.model = model or _html_model()
        self.client = None

        self.use_ollama = os.getenv("USE_OLLAMA_HTML", "0").strip() == "1"
        if self.use_ollama:
            self.client = _ollama_client()

    def _ollama_to_markdown_like(self, text: str) -> str:
        if not self.client:
            return text

        system = (
            "You ONLY format the input into a simple markdown structure similar to a Ghost newsletter. "
            "STRICT: do not rewrite, do not summarize, do not add, do not remove. "
            "Use: #, ###, ####, bullet lists '* ', numbered lists '1.' and separators '* * *'. "
            "Return ONLY the markdown."
        )
        user = f"""Reformat the following newsletter into this structure:

# <main title>
#### <author if present>
<date line if present>
<intro paragraph(s)>
#### A la une aujourd'hui:
* ...
* ...
* * *
### <story title> (include source link if present)
#### Points Clés :
* ...
#### Description :
<paragraphs>
#### Pourquoi c'est important :
<paragraphs>
* * *
(repeat stories)
<footer paragraphs + numbered list if present>

INPUT:
{text}
"""
        resp = self.client.chat(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            stream=False,
        )
        md = (resp.get("message", {}) or {}).get("content", "") or ""
        return md.strip() or text

    def generate_html(self, newsletter_text: str) -> str:
        if not newsletter_text:
            return ""

        content_hash = _hash_content(newsletter_text)
        if self.use_cache and content_hash in _html_cache:
            print(f"[HTML_GENERATOR] Cache hit ({content_hash[:8]})")
            return _html_cache[content_hash]

        try:
            src_text = newsletter_text
            if self.use_ollama:
                src_text = self._ollama_to_markdown_like(newsletter_text)

            data = _try_parse_newsletter_json(src_text)
            if data:
                page_title, body_html = render_newsletter_json(data)
            else:
                page_title, body_html = render_veillecyber_html(src_text)

            final_html = _wrap_template(body_html=body_html, page_title=page_title)
            final_html = _final_cleanup_html(final_html)

            if self.use_cache:
                _html_cache[content_hash] = final_html
                print(f"[HTML_GENERATOR] Cached ({content_hash[:8]})")

            return final_html

        except Exception as e:
            print(f"[HTML_GENERATOR] Error: {e}")
            fallback_title = os.getenv("NEWSLETTER_TITLE", "Veille Cyber")
            fallback_body = _p(newsletter_text)
            fallback_html = _wrap_template(fallback_body, fallback_title)
            fallback_html = _final_cleanup_html(fallback_html)
            if self.use_cache:
                _html_cache[content_hash] = fallback_html
            return fallback_html


def generate_newsletter_html(newsletter_text: str) -> str:
    return HTMLGenerator(use_cache=True).generate_html(newsletter_text)


def _split_sentences(text: str) -> List[str]:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return []
    return re.split(r"(?<=[\.!\?])\s+", cleaned)


def build_email_summary_html(newsletter_text: str, max_sentences: int = 3) -> str:
    """
    Build a short HTML summary for email from existing content only.
    Prefers JSON intro/headlines; falls back to first 2-4 sentences of raw text.
    """
    data = _try_parse_newsletter_json(newsletter_text)
    parts: List[str] = []

    if data:
        intro = data.get("intro") or data.get("introduction")
        if intro:
            parts.append(_p(str(intro)))

        headlines = data.get("headlines")
        if isinstance(headlines, list) and headlines:
            trimmed = [str(h) for h in headlines[:4] if str(h).strip()]
            if trimmed:
                parts.append(_ul(trimmed))

        # If still empty, fallback to first story description
        if not parts:
            stories = data.get("stories") or []
            if isinstance(stories, list) and stories:
                first = stories[0] if isinstance(stories[0], dict) else {}
                desc = (first.get("description") or "").strip()
                if desc:
                    parts.append(_p(desc))

    if not parts:
        cleaned_text = _clean_markdown_formatting(newsletter_text or "")
        sentences = [s for s in _split_sentences(cleaned_text) if s]
        if not sentences:
            return _p("Daily cybersecurity briefing available.")

        count = max(2, min(max_sentences, len(sentences)))
        for s in sentences[:count]:
            parts.append(_p(s))

    return "\n".join(parts)


def build_ghost_html_with_public_preview(summary_html: str, full_html: str) -> str:
    """
    Build HTML that uses Ghost's Public Preview card.
    Everything before the card is sent by email, content after stays on site.
    """
    preview_begin = "<!--kg-card-begin: public-preview-->"
    preview_end = "<!--kg-card-end: public-preview-->"
    summary = (summary_html or "").strip()
    full = (full_html or "").strip()
    return "\n\n".join(
        [
            summary,
            preview_begin,
            preview_end,
            full,
        ]
    ).strip()























# """
# HTML Generator Tool for SafariNewsletter (Ollama Cloud optional).

# Objectif:
# - Générer un HTML "VeilleCyber-like" STABLE (même thème + même forme)
# - À partir d'une newsletter texte au format Markdown simple
# - Conversion déterministe (sans LLM) => rendu constant.
# - Cache mémoire par hash.
# """

# import os
# import re
# import html
# import json
# import hashlib
# from typing import Dict, List, Tuple, Optional, Any

# from ollama import Client
# from src.configs.config import settings


# _html_cache: Dict[str, str] = {}


# def _try_parse_newsletter_json(text: str) -> Dict[str, Any]:
#     stripped = (text or "").strip()
#     if not stripped:
#         print("[HTML_GENERATOR] JSON parse: Empty text")
#         return {}
#     if stripped[0] not in "[{":
#         print(f"[HTML_GENERATOR] JSON parse: Text does not start with '[' or '{{', got: {stripped[:50]}")
#         return {}
#     try:
#         data = json.loads(stripped)
#         print(f"[HTML_GENERATOR] JSON parse: SUCCESS - parsed {type(data)} with {len(data) if isinstance(data, dict) else '?'} keys")
#         return data if isinstance(data, dict) else {}
#     except Exception as e:
#         print(f"[HTML_GENERATOR] JSON parse: FAILED - {e}")
#         return {}


# # -------------------------
# # Cache + client (optionnel)
# # -------------------------
# def _hash_content(text: str) -> str:
#     return hashlib.sha256(text.encode("utf-8")).hexdigest()


# def _ollama_client() -> Client:
#     if not settings.OLLAMA_API_KEY:
#         raise RuntimeError("OLLAMA_API_KEY manquant (Ollama Cloud requis)")
#     return Client(
#         host="https://ollama.com",
#         headers={"Authorization": "Bearer " + settings.OLLAMA_API_KEY},
#     )


# def _html_model() -> str:
#     return (
#         os.getenv("OLLAMA_HTML_MODEL")
#         or getattr(settings, "OLLAMA_HTML_MODEL", "")
#         or getattr(settings, "OLLAMA_MODEL", "gpt-oss:20b-cloud")
#     )


# def clear_html_cache() -> None:
#     _html_cache.clear()
#     print("[HTML_GENERATOR] Cache cleared")


# # -------------------------
# # Parsing helpers
# # -------------------------
# SEP_RE = re.compile(r"^\s*\*\s*\*\s*\*\s*$")
# H1_RE = re.compile(r"^\s*#\s+(.*)\s*$")
# H3_RE = re.compile(r"^\s*###\s+(.*)\s*$")
# H4_RE = re.compile(r"^\s*####\s+(.*)\s*$")
# BULLET_RE = re.compile(r"^\s*\*\s+(.*)\s*$")
# NUM_RE = re.compile(r"^\s*(\d+)\.\s+(.*)\s*$")

# MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\)]+)\)")
# BARE_URL_RE = re.compile(r"(https?://\S+)")


# _TAG_RE = re.compile(
#     r"\[\s*(title|titre|subtitle|sous[-\s]?titre|heading|header)\s*\]\s*",
#     flags=re.IGNORECASE,
# )


# def _clean_markdown_formatting(text: str) -> str:
#     """
#     Supprime les caractères de formatage Markdown + tags type [TITLE]
#     """
#     # Supprimer TOUTES les étoiles (**, *, etc.)
#     text = re.sub(r"\*+", "", text)

#     # Supprimer les underscores de formatage
#     text = re.sub(r"__+", "", text)
#     text = re.sub(r"_", "", text)

#     # Supprimer les tags [TITLE] / [TITRE] / etc.
#     text = _TAG_RE.sub("", text)

#     # Retire les marqueurs de titre en début de ligne (#, ##, ###, etc.)
#     text = re.sub(r"^\s*#+\s*", "", text)

#     # Retire les # restants hors URL
#     text = re.sub(r"(?!https?://[^\s]*)#", "", text)

#     # Supprimer les backticks
#     text = re.sub(r"`+", "", text)

#     return text.strip()


# def _extract_markdown_links(raw: str) -> str:
#     """
#     Convertit [texte](url) => <a ...>texte</a>
#     et détecte aussi les URLs brutes.
#     Escape HTML seulement pour les éléments dangereux.
#     """
#     # Escape minimal pour sécurité
#     safe_text = raw.replace('<', '&lt;').replace('>', '&gt;')
    
#     def repl(m: re.Match) -> str:
#         label = m.group(1).replace('<', '&lt;').replace('>', '&gt;')
#         url = html.escape(m.group(2))
#         return (
#             f'<a href="{url}" target="_blank" rel="noopener noreferrer" '
#             f'style="color:#93c5fd;text-decoration:underline;">{label}</a>'
#         )

#     out = MD_LINK_RE.sub(repl, safe_text)

#     # URLs brutes (si pas déjà dans un href)
#     def repl_url(m: re.Match) -> str:
#         url = m.group(1)
#         esc = html.escape(url)
#         return (
#             f'<a href="{esc}" target="_blank" rel="noopener noreferrer" '
#             f'style="color:#93c5fd;text-decoration:underline;">{esc}</a>'
#         )

#     out = BARE_URL_RE.sub(repl_url, out)
#     return out


# def _normalize_title_line(line: str) -> Tuple[str, Optional[str]]:
#     """
#     Essaie d'extraire (titre, url) si la ligne contient un lien.
#     """
#     raw = line.strip()

#     # markdown link
#     m = MD_LINK_RE.search(raw)
#     if m:
#         return _clean_markdown_formatting(m.group(1).strip()), m.group(2).strip()

#     # (url)
#     m = re.search(r"^(.*)\((https?://[^\)]+)\)\s*$", raw)
#     if m:
#         return _clean_markdown_formatting(m.group(1).strip()), m.group(2).strip()

#     # "— url"
#     m = re.search(r"^(.*)\s+—\s+(https?://\S+)\s*$", raw)
#     if m:
#         return _clean_markdown_formatting(m.group(1).strip()), m.group(2).strip()

#     # URL brute dans la ligne
#     m = BARE_URL_RE.search(raw)
#     if m:
#         url = m.group(1).strip()
#         title = raw.replace(url, "").strip(" -—")
#         title = _clean_markdown_formatting(title) if title else url
#         return title, url

#     return _clean_markdown_formatting(raw), None


# def _final_cleanup_html(html_text: str) -> str:
#     cleaned = re.sub(r"\*+", "", html_text)
#     return cleaned


# # -------------------------
# # HTML theme
# # -------------------------
# def _wrap_template(body_html: str, page_title: str) -> str:
#     return f"""<div style="font-family:Inter,Segoe UI,Arial,sans-serif;font-size:15px;line-height:1.7;color:#e5e7eb;max-width:100%;">
#   {body_html}
# </div>"""


# def _hr() -> str:
#     return '<div style="height:1px;background:#233252;margin:20px 0;"></div>'


# def _p(text: str) -> str:
#     cleaned = _clean_markdown_formatting(text)
#     t = _extract_markdown_links(cleaned)
#     return f'<p style="margin:4px 0 14px 0;color:#e5e7eb;line-height:1.6;">{t}</p>'


# def _meta_line(text: str) -> str:
#     cleaned = _clean_markdown_formatting(text)
#     t = _extract_markdown_links(cleaned)
#     return f'<div style="margin:6px 0 16px 0;font-size:13px;color:#a5b4fc;">{t}</div>'


# def _h2(text: str) -> str:
#     # Sous-titres PLUS GRANDS + couleur différente
#     cleaned = _clean_markdown_formatting(text)
#     t = _extract_markdown_links(cleaned)
#     return (
#         '<div style="margin:26px 0 12px 0;'
#         'font-size:22px;font-weight:950;letter-spacing:0.2px;'
#         'color:#f472b6;">'
#         f'{t}</div>'
#     )


# def _h3_link(title: str, url: Optional[str]) -> str:
#     clean_title = _clean_markdown_formatting(title)
#     safe_title = html.escape(clean_title)
#     if url:
#         safe_url = html.escape(url)
#         return (
#             '<div style="margin:26px 0 18px 0;">'
#             f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer" '
#             'style="font-size:20px;font-weight:900;color:#ef4444;text-decoration:none;display:block;line-height:1.3;"'
#             f'>{safe_title}</a>'
#             '</div>'
#         )
#     return (
#         '<div style="margin:26px 0 18px 0;font-size:20px;font-weight:900;color:#ef4444;line-height:1.3;">'
#         f'{safe_title}</div>'
#     )


# def _img_vignette(src_url: str, alt_text: str) -> str:
#     if not src_url:
#         return ""
#     safe_src = html.escape(src_url)
#     safe_alt = html.escape(alt_text or "")
#     # 140px wide vignette, rounded corners
#     return (
#         '<div style="margin:10px 0 14px 0;">'
#         f'<img src="{safe_src}" alt="{safe_alt}" '
#         'style="width:140px;height:auto;border-radius:8px;display:block;"/>'
#         '</div>'
#     )


# def _label(text: str) -> str:
#     cleaned = _clean_markdown_formatting(text.strip())
#     t = html.escape(cleaned) if cleaned else ""
#     return (
#         '<div style="margin:16px 0 10px 0;font-size:13px;font-weight:800;'
#         'text-transform:none;color:#93c5fd;">'
#         f'{t}</div>'
#     )






# def _spacer(margin_px: int = 8) -> str:
#     """
#     Spacer with content to avoid being stripped by email clients; keeps subtitle separated.
#     """
#     m = max(int(margin_px), 0)
#     return f'<div style="margin:{m}px 0;line-height:0;font-size:0;">&nbsp;</div>'


# def _line_break() -> str:
#     """Explicit line break to survive aggressive sanitizers."""
#     return '<br style="line-height:1.2;" />'


# def _ul(items: List[str]) -> str:
#     lis = []
#     for it in items:
#         cleaned = _clean_markdown_formatting(it)
#         lis.append(
#             '<li style="margin:0 0 6px 0;color:#e5e7eb;">'
#             f'{_extract_markdown_links(cleaned)}'
#             '</li>'
#         )
#     return (
#         '<ul style="margin:4px 0 14px 18px;padding:0;color:#e5e7eb;line-height:1.5;">'
#         + "".join(lis) +
#         '</ul>'
#     )


# def _ol(items: List[str]) -> str:
#     lis = []
#     for it in items:
#         cleaned = _clean_markdown_formatting(it)
#         lis.append(
#             '<li style="margin:0 0 6px 0;color:#e5e7eb;">'
#             f'{_extract_markdown_links(cleaned)}'
#             '</li>'
#         )
#     return (
#         '<ol style="margin:0 0 12px 18px;padding:0;color:#e5e7eb;">'
#         + "".join(lis) +
#         '</ol>'
#     )


# # -------------------------
# # JSON renderer
# # -------------------------
# def render_newsletter_json(data: Dict[str, Any]) -> Tuple[str, str]:
#     page_title = _clean_markdown_formatting(str(data.get("title", "") or "7secure")) or "7secure"

#     body_parts: List[str] = []
    
#     # Track intro to avoid duplication
#     intro_text = ""
#     intro = data.get("intro") or data.get("introduction")
#     if intro:
#         intro_text = str(intro).strip().lower()
#         body_parts.append(_p(str(intro)))

#     headlines = data.get("headlines")
#     if isinstance(headlines, list) and headlines:
#         body_parts.append(_h2("Today's headlines"))
#         # Filter out headlines that match intro to avoid duplication
#         filtered_headlines = []
#         for h in headlines:
#             h_str = str(h).strip()
#             if h_str and h_str.lower() != intro_text:
#                 filtered_headlines.append(h_str)
#         if filtered_headlines:
#             body_parts.append(_ul(filtered_headlines))

#     # Track images already displayed to avoid duplication
#     displayed_images: set[str] = set()

#     stories = data.get("stories") or data.get("items") or []
#     if isinstance(stories, list):
#         print(f"[HTML_GENERATOR] Processing {len(stories)} stories")
#         for idx, story in enumerate(stories):
#             print(f"[HTML_GENERATOR] Story {idx+1}: {story.get('title', '(no title)')[:50]}")
#             if not isinstance(story, dict):
#                 print(f"[HTML_GENERATOR] Story {idx+1} is not a dict, skipping")
#                 continue
#             st_title = story.get("title") or ""
#             st_url = story.get("url") or story.get("source")
#             if st_title:
#                 print(f"[HTML_GENERATOR] Adding story {idx+1} title with URL: {st_url}")
#                 body_parts.append(_h3_link(str(st_title), str(st_url) if st_url else None))

#             # Optional vignette image from pipeline enrichment (display only once per newsletter)
#             img_url = story.get("image_url")
#             if isinstance(img_url, str) and img_url.strip():
#                 img_url_clean = img_url.strip()
#                 if img_url_clean not in displayed_images:
#                     body_parts.append(_img_vignette(img_url_clean, str(st_title or "")))
#                     displayed_images.add(img_url_clean)
#                 else:
#                     print(f"[HTML_GENERATOR] Story {idx+1}: skipped duplicate image {img_url_clean[:50]}")

#             key_points = story.get("key_points") or story.get("keypoints") or story.get("points")
#             if isinstance(key_points, list) and key_points:
#                 print(f"[HTML_GENERATOR] Story {idx+1}: Adding {len(key_points)} key points")
#                 body_parts.append('<br style="line-height:1.5;" />')
#                 body_parts.append('<br style="line-height:1.5;" />')
#                 body_parts.append(_label("Key Points:"))
#                 body_parts.append(_ul([str(p) for p in key_points if str(p).strip()]))

#             desc = story.get("description") or story.get("summary")
#             if desc:
#                 body_parts.append(_label("Description:"))
#                 body_parts.append(_p(str(desc)))

#             wim = story.get("why_it_matters") or story.get("impact") or story.get("so_what")
#             if wim:
#                 body_parts.append(_label("Why It Matters:"))
#                 body_parts.append(_p(str(wim)))

#             if idx < len(stories) - 1:
#                 body_parts.append(_hr())

#     closing = data.get("closing") or data.get("outro") or data.get("conclusion")
#     if closing:
#         body_parts.append(_p(str(closing)))

#     body_html = "".join(body_parts).strip()
#     body_html = _final_cleanup_html(body_html)
#     return page_title, body_html


# # -------------------------
# # Deterministic renderer
# # -------------------------
# def render_veillecyber_html(newsletter_text: str) -> Tuple[str, str]:
#     lines = [ln.rstrip() for ln in (newsletter_text or "").splitlines()]

#     page_title = "7secure"
#     author = None
#     date_line = None

#     body_parts: List[str] = []
#     pending_ul: List[str] = []
#     pending_ol: List[str] = []
#     in_story = False
#     last_plain_line: Optional[str] = None
#     last_plain_index: Optional[int] = None

#     # Fix duplication: track intro and title
#     seen_intro = False
#     seen_intro_text = ""
#     removed_title_line = False

#     def flush_lists():
#         nonlocal pending_ul, pending_ol, body_parts
#         if pending_ul:
#             body_parts.append(_ul(pending_ul))
#             pending_ul = []
#         if pending_ol:
#             body_parts.append(_ol(pending_ol))
#             pending_ol = []

#     for ln in lines:
#         if not ln.strip():
#             continue

#         cleaned_line = _clean_markdown_formatting(ln)

#         # Remove duplicate intro (like "Hello, here's...")
#         if not seen_intro and cleaned_line.lower().startswith("hello"):
#             seen_intro = True
#             seen_intro_text = cleaned_line.strip().lower()
#             body_parts.append(_p(cleaned_line))
#             continue
#         if seen_intro and cleaned_line.strip().lower() == seen_intro_text:
#             continue

#         # Remove duplicate title line
#         if page_title and cleaned_line.lower() == page_title.lower():
#             if not removed_title_line:
#                 removed_title_line = True
#                 continue

#         if SEP_RE.match(ln):
#             flush_lists()
#             in_story = False
#             last_plain_line = None
#             last_plain_index = None
#             body_parts.append(_hr())
#             continue

#         m = H1_RE.match(ln)
#         if m:
#             flush_lists()
#             in_story = False
#             last_plain_line = None
#             last_plain_index = None
#             raw_title = m.group(1).strip()
#             page_title = _clean_markdown_formatting(raw_title)
#             continue

#         lower_clean = cleaned_line.lower()
#         if lower_clean in {"key points:", "description:", "why it matters:"}:
#             flush_lists()
#             in_story = True
#             if last_plain_line is not None and last_plain_index is not None:
#                 title_txt, title_url = _normalize_title_line(last_plain_line)
#                 body_parts[last_plain_index] = _h3_link(title_txt, title_url)
#             last_plain_line = None
#             last_plain_index = None
#             body_parts.append(_line_break())
#             body_parts.append(_label(ln.strip()))
#             continue

#         m = H4_RE.match(ln)
#         if m:
#             flush_lists()
#             text = m.group(1).strip()

#             lower = text.lower()
#             if lower in {
#                 "key points:", "description:", "why it matters:"
#             }:
#                 in_story = True
#                 if last_plain_line is not None and last_plain_index is not None:
#                     title_txt, title_url = _normalize_title_line(last_plain_line)
#                     body_parts[last_plain_index] = _h3_link(title_txt, title_url)
#                 last_plain_line = None
#                 last_plain_index = None
#                 body_parts.append(_line_break())
#                 body_parts.append(_label(text))
#             else:
#                 in_story = False
#                 last_plain_line = None
#                 last_plain_index = None
#                 body_parts.append(_h2(text.replace(":", "")))
#             continue

#         m = H3_RE.match(ln)
#         if m:
#             flush_lists()
#             in_story = True
#             last_plain_line = None
#             last_plain_index = None
#             title_line = m.group(1).strip()
#             title, url = _normalize_title_line(title_line)
#             body_parts.append(_h3_link(title, url))
#             body_parts.append(_line_break())
#             body_parts.append(_spacer())  # Espace après le sous-titre
#             continue

#         if ("min read" in ln) or ("—" in ln and any(ch.isdigit() for ch in ln)):
#             if date_line is None and not in_story:
#                 date_line = ln.strip()
#                 continue

#         m = BULLET_RE.match(ln)
#         if m:
#             if pending_ol:
#                 flush_lists()
#             pending_ul.append(m.group(1).strip())
#             continue

#         m = NUM_RE.match(ln)
#         if m:
#             pending_ol.append(m.group(2).strip())
#             continue

#         flush_lists()

#         if author and date_line and not in_story:
#             body_parts.append(_meta_line(f"{author} — {date_line}"))
#             author, date_line = None, None

#         body_parts.append(_p(ln))
#         last_plain_line = ln
#         last_plain_index = len(body_parts) - 1

#     flush_lists()

#     if author and date_line:
#         body_parts.insert(1, _meta_line(f"{author} — {date_line}"))

#     body_html = "".join(body_parts).strip()
#     body_html = _final_cleanup_html(body_html)
#     return page_title, body_html

# # -------------------------
# # Main generator
# # -------------------------
# class HTMLGenerator:
#     def __init__(self, model: str = "", use_cache: bool = True):
#         self.use_cache = use_cache
#         self.model = model or _html_model()
#         self.client = None

#         self.use_ollama = os.getenv("USE_OLLAMA_HTML", "0").strip() == "1"
#         if self.use_ollama:
#             self.client = _ollama_client()

#     def _ollama_to_markdown_like(self, text: str) -> str:
#         if not self.client:
#             return text

#         system = (
#             "You ONLY format the input into a simple markdown structure similar to a Ghost newsletter. "
#             "STRICT: do not rewrite, do not summarize, do not add, do not remove. "
#             "Use: #, ###, ####, bullet lists '* ', numbered lists '1.' and separators '* * *'. "
#             "Return ONLY the markdown."
#         )
#         user = f"""Reformat the following newsletter into this structure:

# # <main title>
# #### <author if present>
# <date line if present>
# <intro paragraph(s)>
# #### A la une aujourd'hui:
# * ...
# * ...
# * * *
# ### <story title> (include source link if present)
# #### Points Clés :
# * ...
# #### Description :
# <paragraphs>
# #### Pourquoi c'est important :
# <paragraphs>
# * * *
# (repeat stories)
# <footer paragraphs + numbered list if present>

# INPUT:
# {text}
# """
#         resp = self.client.chat(
#             model=self.model,
#             messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
#             stream=False,
#         )
#         md = (resp.get("message", {}) or {}).get("content", "") or ""
#         return md.strip() or text

#     def generate_html(self, newsletter_text: str) -> str:
#         if not newsletter_text:
#             return ""

#         content_hash = _hash_content(newsletter_text)
#         if self.use_cache and content_hash in _html_cache:
#             print(f"[HTML_GENERATOR] Cache hit ({content_hash[:8]})")
#             return _html_cache[content_hash]

#         try:
#             src_text = newsletter_text
#             if self.use_ollama:
#                 src_text = self._ollama_to_markdown_like(newsletter_text)

#             data = _try_parse_newsletter_json(src_text)
#             if data:
#                 page_title, body_html = render_newsletter_json(data)
#             else:
#                 page_title, body_html = render_veillecyber_html(src_text)

#             final_html = _wrap_template(body_html=body_html, page_title=page_title)
#             final_html = _final_cleanup_html(final_html)

#             if self.use_cache:
#                 _html_cache[content_hash] = final_html
#                 print(f"[HTML_GENERATOR] Cached ({content_hash[:8]})")

#             return final_html

#         except Exception as e:
#             print(f"[HTML_GENERATOR] Error: {e}")
#             fallback_title = os.getenv("NEWSLETTER_TITLE", "Veille Cyber")
#             fallback_body = _p(newsletter_text)
#             fallback_html = _wrap_template(fallback_body, fallback_title)
#             fallback_html = _final_cleanup_html(fallback_html)
#             if self.use_cache:
#                 _html_cache[content_hash] = fallback_html
#             return fallback_html


# def generate_newsletter_html(newsletter_text: str) -> str:
#     return HTMLGenerator(use_cache=True).generate_html(newsletter_text)
