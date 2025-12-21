"""
HTML Generator Tool for SafariNewsletter (Ollama Cloud optional).

Objectif:
- Générer un HTML "VeilleCyber-like" STABLE (même thème + même forme)
- À partir d'une newsletter texte au format Markdown simple:
  # titre
  #### Auteur
  date — X min read
  Bonjour...
  #### A la une aujourd'hui:
    * item
  * * *
  ### Titre news [optionnel: (url) ou markdown link]
  #### Points Clés :
    * ...
  #### Description :
    ...
  #### Pourquoi c'est important :
    ...
  * * *
  Footer + liste numérotée

- Conversion déterministe (sans LLM) => rendu constant.
- Cache mémoire par hash.

Note: le client Ollama est conservé (optionnel), mais par défaut on ne l'utilise PAS
pour éviter des variations de style. Si tu veux un fallback LLM, active USE_OLLAMA_HTML=1.
"""

import os
import re
import html
import hashlib
from typing import Dict, List, Tuple, Optional

from ollama import Client
from src.configs.config import settings


_html_cache: Dict[str, str] = {}


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
# Exemple Ghost export: "### Titre†domain" parfois; on supporte aussi "Titre — URL"
BARE_URL_RE = re.compile(r"(https?://\S+)")


def _escape_keep_basic(text: str) -> str:
    # échappe tout, puis ré-injecte les liens markdown
    s = html.escape(text, quote=True)

    # Remettre les markdown links déjà dans le texte original
    # (on refait une passe depuis l'original plutôt que depuis s).
    return s


def _extract_markdown_links(raw: str) -> str:
    """
    Convertit [texte](url) => <a ...>texte</a>
    et détecte aussi les URLs brutes.
    """
    def repl(m: re.Match) -> str:
        label = html.escape(m.group(1))
        url = html.escape(m.group(2))
        return f'<a href="{url}" target="_blank" rel="noopener noreferrer" style="color:#93c5fd;text-decoration:underline;">{label}</a>'

    out = MD_LINK_RE.sub(repl, raw)

    # URLs brutes (si pas déjà dans un href)
    def repl_url(m: re.Match) -> str:
        url = m.group(1)
        esc = html.escape(url)
        return f'<a href="{esc}" target="_blank" rel="noopener noreferrer" style="color:#93c5fd;text-decoration:underline;">{esc}</a>'

    out = BARE_URL_RE.sub(repl_url, out)
    return out


def _normalize_title_line(line: str) -> Tuple[str, Optional[str]]:
    """
    Essaie d'extraire (titre, url) si la ligne contient un lien.
    Supporte:
    - "Titre [source](url)"
    - "Titre (url)"
    - "Titre — url"
    - sinon url None
    """
    raw = line.strip()

    # markdown link
    m = MD_LINK_RE.search(raw)
    if m:
        # on garde raw complet, mais pour la card on veut un titre + url
        return m.group(1).strip(), m.group(2).strip()

    # (url)
    m = re.search(r"^(.*)\((https?://[^\)]+)\)\s*$", raw)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # "— url"
    m = re.search(r"^(.*)\s+—\s+(https?://\S+)\s*$", raw)
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # URL brute dans la ligne
    m = BARE_URL_RE.search(raw)
    if m:
        url = m.group(1).strip()
        title = raw.replace(url, "").strip(" -—")
        title = title if title else url
        return title, url

    return raw, None


# -------------------------
# HTML theme (email/web safe)
# -------------------------
def _wrap_template(body_html: str, page_title: str) -> str:
    # Thème sobre proche d’une newsletter Ghost (structure stable)
    # HTML simple sans cadre pour affichage direct dans le site
    return f"""<div style="font-family:Inter,Segoe UI,Arial,sans-serif;font-size:15px;line-height:1.7;color:#e5e7eb;max-width:100%;">
  {body_html}
</div>"""


def _hr() -> str:
    return '<div style="height:1px;background:#233252;margin:16px 0;"></div>'


def _p(text: str) -> str:
    t = _extract_markdown_links(html.escape(text))
    return f'<p style="margin:0 0 10px 0;color:#e5e7eb;">{t}</p>'


def _meta_line(text: str) -> str:
    t = _extract_markdown_links(html.escape(text))
    return f'<div style="margin:6px 0 14px 0;font-size:13px;color:#a5b4fc;">{t}</div>'


def _h2(text: str) -> str:
    t = _extract_markdown_links(html.escape(text))
    return f'<div style="margin:18px 0 8px 0;font-size:16px;font-weight:900;color:#ffffff;">{t}</div>'


def _h3_link(title: str, url: Optional[str]) -> str:
    safe_title = html.escape(title)
    if url:
        safe_url = html.escape(url)
        return (
            '<div style="margin:18px 0 10px 0;">'
            f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer" '
            'style="font-size:16px;font-weight:900;color:#ffffff;text-decoration:none;">'
            f'{safe_title}</a>'
            '</div>'
        )
    return f'<div style="margin:18px 0 10px 0;font-size:16px;font-weight:900;color:#ffffff;">{safe_title}</div>'


def _label(text: str) -> str:
    # "Points Clés :", "Description :", "Pourquoi c'est important :"
    t = html.escape(text.strip())
    return (
        '<div style="margin:8px 0 6px 0;font-size:13px;font-weight:800;'
        'text-transform:none;color:#93c5fd;">'
        f'{t}</div>'
    )


def _ul(items: List[str]) -> str:
    lis = []
    for it in items:
        lis.append(
            '<li style="margin:0 0 6px 0;color:#e5e7eb;">'
            f'{_extract_markdown_links(html.escape(it))}'
            '</li>'
        )
    return (
        '<ul style="margin:0 0 12px 18px;padding:0;color:#e5e7eb;">'
        + "".join(lis) +
        '</ul>'
    )


def _ol(items: List[str]) -> str:
    lis = []
    for it in items:
        lis.append(
            '<li style="margin:0 0 6px 0;color:#e5e7eb;">'
            f'{_extract_markdown_links(html.escape(it))}'
            '</li>'
        )
    return (
        '<ol style="margin:0 0 12px 18px;padding:0;color:#e5e7eb;">'
        + "".join(lis) +
        '</ol>'
    )


def _card(inner: str) -> str:
    return (
        '<div style="margin:14px 0 0 0;padding:14px 14px 10px 14px;'
        'border:1px solid #233252;border-radius:12px;background:#0c1730;">'
        f'{inner}</div>'
    )


# -------------------------
# Deterministic renderer (VeilleCyber-like)
# -------------------------
def render_veillecyber_html(newsletter_text: str) -> Tuple[str, str]:
    """
    Retourne (page_title, body_html)
    """
    lines = [ln.rstrip() for ln in (newsletter_text or "").splitlines()]

    page_title = "7secure"
    author = None
    date_line = None

    body_parts: List[str] = []

    # State for lists
    pending_ul: List[str] = []
    pending_ol: List[str] = []

    # Story block
    in_story = False
    story_html: List[str] = []

    def flush_lists():
        nonlocal pending_ul, pending_ol, body_parts, story_html, in_story
        if pending_ul:
            html_ul = _ul(pending_ul)
            if in_story:
                story_html.append(html_ul)
            else:
                body_parts.append(html_ul)
            pending_ul = []
        if pending_ol:
            html_ol = _ol(pending_ol)
            if in_story:
                story_html.append(html_ol)
            else:
                body_parts.append(html_ol)
            pending_ol = []

    def flush_story():
        nonlocal in_story, story_html, body_parts
        if in_story:
            flush_lists()
            body_parts.append(_card("".join(story_html)))
            story_html = []
            in_story = False

    for ln in lines:
        if not ln.strip():
            # on garde pas les lignes vides (mise en page via marges)
            continue

        # Separator "* * *"
        if SEP_RE.match(ln):
            flush_lists()
            flush_story()
            body_parts.append(_hr())
            continue

        # H1 "# ..."
        m = H1_RE.match(ln)
        if m:
            flush_lists()
            flush_story()
            page_title = m.group(1).strip()
            # Titre en haut déjà dans template; on peut aussi le rappeler dans body comme Ghost le fait
            body_parts.append(
                f'<div style="font-size:22px;font-weight:900;color:#ffffff;margin:0 0 8px 0;">{html.escape(page_title)}</div>'
            )
            continue

        # H4 "#### ..."
        m = H4_RE.match(ln)
        if m:
            flush_lists()
            # Si c'est "Auteur" en début: Ghost affiche auteur + date en meta
            text = m.group(1).strip()

            # Heuristique: si c'est un nom d'auteur (ex: Maxime Blanc) et pas une section
            if text.lower() not in {
                "a la une aujourd'hui:",
                "à la une aujourd'hui:",
                "points clés :",
                "points cles :",
                "description :",
                "pourquoi c'est important :",
            } and author is None and not in_story and len(text.split()) <= 4:
                author = text
                continue

            # Dans une story, Points/Description/Pourquoi deviennent labels
            lower = text.lower()
            if lower in {"points clés :", "points cles :", "description :", "pourquoi c'est important :"}:
                if not in_story:
                    # si le texte commence direct par Points clés sans titre => on n'ouvre pas de card
                    in_story = True
                story_html.append(_label(text))
            else:
                # section hors story, ex "A la une aujourd'hui:"
                flush_story()
                body_parts.append(_h2(text.replace(":", "")))
            continue

        # H3 "### ..."
        m = H3_RE.match(ln)
        if m:
            flush_lists()
            flush_story()
            in_story = True
            title_line = m.group(1).strip()
            title, url = _normalize_title_line(title_line)
            story_html.append(_h3_link(title, url))
            continue

        # Date line like "19 déc. 2025 — 4 min read"
        if (("min read" in ln) or ("—" in ln and any(ch.isdigit() for ch in ln))) and date_line is None and not in_story:
            date_line = ln.strip()
            continue

        # Bullet "* ..."
        m = BULLET_RE.match(ln)
        if m:
            flush_story() if (not in_story and pending_ol) else None
            pending_ul.append(m.group(1).strip())
            continue

        # Numbered "1. ..."
        m = NUM_RE.match(ln)
        if m:
            pending_ol.append(m.group(2).strip())
            continue

        # Normal paragraph
        flush_lists()

        # meta block (author + date) juste après le titre
        if author and date_line and not in_story:
            body_parts.append(_meta_line(f"{author} — {date_line}"))
            author, date_line = None, None

        if in_story:
            story_html.append(_p(ln))
        else:
            body_parts.append(_p(ln))

    flush_lists()
    flush_story()

    # si meta pas flush (cas rare)
    if author and date_line:
        body_parts.insert(1, _meta_line(f"{author} — {date_line}"))

    body_html = "".join(body_parts).strip()
    return page_title, body_html


# -------------------------
# Main generator
# -------------------------
class HTMLGenerator:
    """
    Génère HTML stable VeilleCyber-like.
    Optionnel: fallback Ollama si USE_OLLAMA_HTML=1 (non recommandé si tu veux stabilité absolue).
    """

    def __init__(self, model: str = "", use_cache: bool = True):
        self.use_cache = use_cache
        self.model = model or _html_model()
        self.client = None

        self.use_ollama = os.getenv("USE_OLLAMA_HTML", "0").strip() == "1"
        if self.use_ollama:
            self.client = _ollama_client()

    def _ollama_to_markdown_like(self, text: str) -> str:
        """
        Fallback: demande au modèle de produire un markdown simple au format attendu,
        sans changer le texte (structure uniquement).
        """
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

            page_title, body_html = render_veillecyber_html(src_text)
            final_html = _wrap_template(body_html=body_html, page_title=page_title)

            if self.use_cache:
                _html_cache[content_hash] = final_html
                print(f"[HTML_GENERATOR] Cached ({content_hash[:8]})")

            return final_html

        except Exception as e:
            print(f"[HTML_GENERATOR] Error: {e}")
            # fallback minimal
            fallback_title = os.getenv("NEWSLETTER_TITLE", "Veille Cyber")
            fallback_body = _p(newsletter_text)
            fallback_html = _wrap_template(fallback_body, fallback_title)
            if self.use_cache:
                _html_cache[content_hash] = fallback_html
            return fallback_html


def generate_newsletter_html(newsletter_text: str) -> str:
    return HTMLGenerator(use_cache=True).generate_html(newsletter_text)
