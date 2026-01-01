"""
LangGraph workflow for end-to-end daily pipeline.

Étapes :
1. scrape      -> raw_articles
2. filter      -> filtered_articles
3. preprocess  -> clean_articles
4. embed       -> met à jour Mongo + vector store
5. rag         -> rag_answer (texte brut)
6. html        -> newsletter_html (HTML)
7. ghost       -> publie direct en Published + Email-only (pas de draft)
"""

from __future__ import annotations

import os
import re
import json
import time
from typing import Any, Dict, List, Optional, TypedDict

import requests
import jwt  # PyJWT

from langgraph.graph import StateGraph, END

from src.tools.scraper import scrape_sources
from src.tools.preprocess import preprocess_articles
from src.tools.embedding import upsert_embeddings
from src.tools.rag import answer_with_rag
from src.tools.html_generator import generate_newsletter_html
from src.tools.filtering import filter_articles


# Tags autorisés (catégories de cybersécurité)
ALLOWED_TAGS = [
    "AI Security & Threats",
    "Threat Intelligence",
    "Malware & Ransomware",
    "Vulnerabilities & Exploits",
    "Cloud & SaaS Security",
    "IAM",
    "SOC & Automation",
    "Data Protection & Privacy",
    "Human Factors",
    "Compliance & Regulation",
    "Data Breaches",
]


class PipelineState(TypedDict, total=False):
    # inputs
    question: str

    # outputs of steps
    raw_articles: List[Dict[str, Any]]
    filtered_articles: List[Dict[str, Any]]
    clean_articles: List[Dict[str, Any]]

    rag_answer: str
    newsletter_html: str

    # ghost result
    ghost_post_id: str
    ghost_post_url: str


def _require_env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val


def _build_ghost_admin_jwt(admin_api_key: str) -> str:
    """
    Ghost Admin API key format: "<id>:<secret>"
    JWT header kid = id
    JWT secret = secret (hex) -> bytes
    """
    try:
        key_id, key_secret = admin_api_key.split(":", 1)
    except ValueError as e:
        raise RuntimeError("GHOST_ADMIN_API_KEY must be in format '<id>:<secret>'") from e

    iat = int(time.time())
    header = {"alg": "HS256", "typ": "JWT", "kid": key_id}
    payload = {
        "iat": iat,
        "exp": iat + 5 * 60,  # 5 minutes
        "aud": "/admin/",
    }

    secret_bytes = bytes.fromhex(key_secret)
    token = jwt.encode(payload, secret_bytes, algorithm="HS256", headers=header)
    # pyjwt may return bytes in old versions
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def _clean_line_for_meta(line: str) -> str:
    """Nettoie une ligne pour l'utiliser comme titre/extrait/tag."""
    cleaned = re.sub(r"^[#>*\-\s]+", "", line or "")
    cleaned = re.sub(r"^\d+\.\s+", "", cleaned)
    cleaned = re.sub(r"[*`_]+", "", cleaned)
    return cleaned.strip(" -–—•\t")


def _shorten(text: str, limit: int = 140) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    trimmed = text[: limit - 1].rstrip()
    return trimmed + "…"


def _extract_emojis(text: str) -> List[str]:
    # Capture a broad emoji range (no static palette)
    return re.findall(r"[\U0001F300-\U0001FAFF\U00002600-\U000026FF\U00002700-\U000027BF]", text or "")


def _extract_post_metadata(newsletter_text: str) -> Dict[str, Any]:
    """
    Déduit un titre, un extrait et des tags à partir du texte brut de la newsletter.
    Heuristique simple :
    - titre = première ligne non vide nettoyée
    - extrait = premières phrases/paragraphes non vides hors listes/titres
    - tags = titres de sections (###) puis bullet points
    """
    json_data: Dict[str, Any] = {}
    stripped = (newsletter_text or "").strip()
    if stripped.startswith(("{", "[")):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                json_data = parsed
        except Exception:
            json_data = {}

    if json_data:
        raw_ai_title = str(json_data.get("title") or "")
        ai_title = _clean_line_for_meta(raw_ai_title)

        headlines = json_data.get("headlines") or []
        stories = json_data.get("stories") or []
        intro = _clean_line_for_meta(str(json_data.get("intro") or json_data.get("introduction") or ""))

        # On ne met pas l'intro en excerpt pour éviter l'affichage en doublon sous le titre Ghost
        excerpt = ""

        tag_candidates: List[str] = []
        if isinstance(headlines, list):
            tag_candidates.extend([_clean_line_for_meta(str(h)) for h in headlines])
        if isinstance(stories, list):
            for st in stories:
                if not isinstance(st, dict):
                    continue
                if st.get("title"):
                    tag_candidates.append(_clean_line_for_meta(str(st.get("title"))))
                kp = st.get("key_points") or []
                if isinstance(kp, list):
                    tag_candidates.extend([_clean_line_for_meta(str(p)) for p in kp])

        tags: List[str] = []
        seen = set()
        for cand in tag_candidates:
            tag = cand[:40].strip(" .,;:-")
            key = tag.lower()
            if not tag or key in seen:
                continue
            # Ne garder que les tags qui matchent les catégories autorisées
            matched = False
            for allowed in ALLOWED_TAGS:
                if allowed.lower() in key or key in allowed.lower():
                    if allowed not in tags:
                        tags.append(allowed)
                        seen.add(allowed.lower())
                        matched = True
                        break
            if not matched:
                # Vérifier correspondance partielle (ex: "ransomware" → "Malware & Ransomware")
                for allowed in ALLOWED_TAGS:
                    allowed_words = set(allowed.lower().split())
                    cand_words = set(key.split())
                    if allowed_words & cand_words:
                        if allowed not in tags:
                            tags.append(allowed)
                            seen.add(allowed.lower())
                            break
            if len(tags) >= 6:
                break

        # Construit un titre sophistiqué en combinant les sous-titres (headlines) et les emojis déjà présents
        headline_segments: List[str] = []
        for h in headlines:
            cleaned = _clean_line_for_meta(str(h))
            if not cleaned:
                continue
            emo = (_extract_emojis(str(h)) or [None])[0]
            segment = f"{emo} {_shorten(cleaned, 120)}" if emo else _shorten(cleaned, 120)
            headline_segments.append(segment.strip())
            if len(headline_segments) >= 3:
                break

        combined = " | ".join([s for s in headline_segments if s])
        lead_emoji = (_extract_emojis(raw_ai_title) or [None])[0]

        parts = []
        if lead_emoji:
            parts.append(lead_emoji)
        if combined:
            parts.append(combined)
        elif ai_title:
            parts.append(ai_title)

        final_title = " ".join(parts).strip() or ai_title or "Newsletter"

        if final_title.count(".") > 1:
            final_title = ".".join(final_title.split(".")[:2]).strip().rstrip(".")
        if len(final_title) > 200:
            final_title = final_title[:197].rsplit(" ", 1)[0]

        return {"title": final_title, "excerpt": excerpt, "tags": tags}

    # Fallback heuristique texte
    lines = [ln.strip() for ln in (newsletter_text or "").splitlines()]

    title = ""
    for ln in lines:
        candidate = _clean_line_for_meta(ln)
        if candidate:
            title = candidate
            break

    excerpt_parts: List[str] = []
    for ln in lines:
        raw = ln.strip()
        cleaned = _clean_line_for_meta(raw)
        if not cleaned or cleaned == title:
            continue
        if raw.startswith(("#", "*", "-")):
            continue
        excerpt_parts.append(cleaned)
        if len(" ".join(excerpt_parts)) >= 260:
            break

    excerpt = " ".join(excerpt_parts).strip()
    if len(excerpt) > 280:
        excerpt = excerpt[:277].rsplit(" ", 1)[0]

    tag_candidates: List[str] = []
    for ln in lines:
        raw = ln.strip()
        cand = ""
        if raw.startswith("###"):
            cand = _clean_line_for_meta(raw[3:])
        elif raw.startswith(("*", "-", "•")):
            cand = _clean_line_for_meta(raw)
        if cand:
            tag_candidates.append(cand)
        if len(tag_candidates) >= 12:
            break

    tags: List[str] = []
    seen = set()
    for cand in tag_candidates:
        tag = cand[:40].strip(" .,;:-")
        key = tag.lower()
        if not tag or key in seen:
            continue
        # Ne garder que les tags qui matchent les catégories autorisées
        matched = False
        for allowed in ALLOWED_TAGS:
            if allowed.lower() in key or key in allowed.lower():
                if allowed not in tags:
                    tags.append(allowed)
                    seen.add(allowed.lower())
                    matched = True
                    break
        if not matched:
            # Vérifier correspondance partielle
            for allowed in ALLOWED_TAGS:
                allowed_words = set(allowed.lower().split())
                cand_words = set(key.split())
                if allowed_words & cand_words:
                    if allowed not in tags:
                        tags.append(allowed)
                        seen.add(allowed.lower())
                        break
        if len(tags) >= 6:
            break

    final_title = title or "Newsletter"
    return {"title": final_title, "excerpt": excerpt, "tags": tags}


def publish_post_to_ghost(state: PipelineState) -> PipelineState:
    """
    Publie la newsletter HTML directement:
    - status='published' (=> Published posts)
    - email_only=True (=> Email-only posts)
    - via URL: POST /ghost/api/admin/posts/?newsletter=<newsletter_slug>
    """
    ghost_base = _require_env("GHOST_ADMIN_API_URL").rstrip("/")
    admin_key = _require_env("GHOST_ADMIN_API_KEY")
    newsletter_slug = _require_env("GHOST_NEWSLETTER_SLUG")

    html = state.get("newsletter_html") or ""
    if not html.strip():
        raise RuntimeError("newsletter_html is empty: cannot publish to Ghost")

    meta = _extract_post_metadata(state.get("rag_answer", ""))

    # TOUJOURS utiliser le titre généré par l'IA (pas de fallback statique)
    title = meta.get("title") 
    excerpt = meta.get("excerpt") 

    tags_csv = os.getenv("GHOST_POST_TAGS")
    if tags_csv:
        tags = [{"name": t.strip()} for t in tags_csv.split(",") if t.strip()]
    else:
        inferred_tags = meta.get("tags") or []
        tags = [{"name": t} for t in inferred_tags] if inferred_tags else [{"name": "VeilleCyber"}, {"name": "Newsletter"}]

    token = _build_ghost_admin_jwt(admin_key)

    # IMPORTANT:
    # - "source=html" aide Ghost à accepter du HTML brut.
    # - "newsletter=<slug>" : associe à la newsletter (et permet l’email)
    url = f"{ghost_base}/ghost/api/admin/posts/?source=html&newsletter={newsletter_slug}"

    headers = {
        "Authorization": f"Ghost {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {
        "posts": [
            {
                "title": title,
                "custom_excerpt": excerpt,
                "html": html,
                "status": "published",     # ✅ pas de draft
                "email_only": False,        # ✅ Email-only posts
                "tags": tags,
            }
        ]
    }

    resp = requests.post(url, json=payload, headers=headers, timeout=60)
    if resp.status_code >= 300:
        raise RuntimeError(
            f"Ghost publish failed ({resp.status_code}): {resp.text[:1000]}"
        )

    data = resp.json()
    post = (data.get("posts") or [{}])[0]
    state["ghost_post_id"] = str(post.get("id", ""))
    state["ghost_post_url"] = str(post.get("url", "")) or str(post.get("canonical_url", ""))

    return state


def build_pipeline_app():
    graph = StateGraph(PipelineState)

    # Nodes
    graph.add_node("scrape", lambda s: {"raw_articles": scrape_sources()})
    graph.add_node("filter", lambda s: {"filtered_articles": filter_articles(s.get("raw_articles", []))})
    graph.add_node("preprocess", lambda s: {"clean_articles": preprocess_articles(s.get("filtered_articles", []))})
    graph.add_node("embed", lambda s: upsert_embeddings(s.get("clean_articles", [])) or {})
    graph.add_node("rag", lambda s: {"rag_answer": answer_with_rag(s.get("question", ""))})
    graph.add_node("html", lambda s: {"newsletter_html": generate_newsletter_html(s.get("rag_answer", ""))})
    graph.add_node("ghost", publish_post_to_ghost)

    # Edges
    graph.set_entry_point("scrape")
    graph.add_edge("scrape", "filter")
    graph.add_edge("filter", "preprocess")
    graph.add_edge("preprocess", "embed")
    graph.add_edge("embed", "rag")
    graph.add_edge("rag", "html")
    graph.add_edge("html", "ghost")

    graph.add_edge("ghost", END)



    return graph.compile()


















































