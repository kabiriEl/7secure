"""
LangGraph workflow for end-to-end daily pipeline.

Étapes :
1. scrape      -> raw_articles
2. filter      -> filtered_articles
3. preprocess  -> clean_articles
4. embed       -> met à jour vector store
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
from src.tools.image_extractor import extract_best_image_url
from src.tools.ghost_media import download_image, upload_image_to_ghost
from src.tools.collection_publisher import publish_stories_as_collection_posts


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
    # images index built from filtered articles: url -> ghost image url
    images_index: Dict[str, str]

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
    Déduit un titre et un extrait à partir du texte brut de la newsletter.
    Heuristique simple :
    - titre = première ligne non vide nettoyée
    - extrait = premières phrases/paragraphes non vides hors listes/titres
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

        # headlines = json_data.get("headlines") or []
        headlines = ""
        stories = json_data.get("stories") or []
        # intro = _clean_line_for_meta(str(json_data.get("intro") or json_data.get("introduction") or ""))

        # On ne met pas l'intro en excerpt pour éviter l'affichage en doublon sous le titre Ghost
        excerpt = ""


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

        return {"title": final_title, "excerpt": excerpt}

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

    final_title = title or "Newsletter"
    return {"title": final_title, "excerpt": excerpt}


def _create_draft_post(
    ghost_base: str,
    token: str,
    post_data: Dict[str, Any],
) -> tuple[str, str]:
    """
    Étape 1: Créer un post en DRAFT via Ghost Admin API.
    Retourne: (post_id, updated_at)
    """
    url = f"{ghost_base}/ghost/api/admin/posts/?source=html"
    headers = {
        "Authorization": f"Ghost {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    draft_data = {
        "title": post_data["title"],
        "html": post_data["html"],
        "status": "draft",  # ✅ Créer en DRAFT, pas en PUBLISHED
        "email_only": post_data.get("email_only", False),
        "tags": post_data.get("tags", []),
    }
    
    # Ajouter les champs optionnels s'ils existent
    if "custom_excerpt" in post_data and post_data["custom_excerpt"]:
        draft_data["custom_excerpt"] = post_data["custom_excerpt"]
    if "feature_image" in post_data and post_data["feature_image"]:
        draft_data["feature_image"] = post_data["feature_image"]

    payload = {"posts": [draft_data]}

    resp = requests.post(url, json=payload, headers=headers, timeout=60)
    if resp.status_code >= 300:
        raise RuntimeError(
            f"[GHOST] Draft creation failed ({resp.status_code}): {resp.text[:1000]}"
        )

    data = resp.json()
    post = (data.get("posts") or [{}])[0]
    post_id = str(post.get("id", ""))
    updated_at = str(post.get("updated_at", ""))

    if not post_id or not updated_at:
        raise RuntimeError(
            f"[GHOST] Draft creation response missing id or updated_at: {data}"
        )

    print(f"[GHOST] ✅ Created draft post id={post_id} updated_at={updated_at}")
    return post_id, updated_at


def _publish_post_and_send_email(
    ghost_base: str,
    token: str,
    post_id: str,
    updated_at: str,
    email_only: bool,
    newsletter_slug: str,
) -> Dict[str, Any]:
    """
    Étape 2: Publier le post et déclencher l'envoi email via le query param ?newsletter=<slug>.
    IMPORTANT: Ghost exige updated_at lors d'un PUT pour éviter les conflits (409).
    Le paramètre ?newsletter=<slug> déclenche l'envoi aux abonnés.
    """
    url = f"{ghost_base}/ghost/api/admin/posts/{post_id}/?source=html&newsletter={newsletter_slug}"
    headers = {
        "Authorization": f"Ghost {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    publish_data = {
        "posts": [{
            "id": post_id,
            "updated_at": updated_at,  # ✅ OBLIGATOIRE pour eviter 409 Conflict
            "status": "published",      # ✅ Passer de draft à published
            "email_only": email_only,
        }]
    }

    resp = requests.put(url, json=publish_data, headers=headers, timeout=60)
    if resp.status_code >= 300:
        raise RuntimeError(
            f"[GHOST] Publish & email send failed ({resp.status_code}): {resp.text[:1000]}"
        )

    data = resp.json()
    post = (data.get("posts") or [{}])[0]
    
    print(f"[GHOST] ✅ Published post id={post_id} with ?newsletter={newsletter_slug}")
    print(f"[GHOST] ✅ Email send triggered to newsletter '{newsletter_slug}' subscribers")
    
    # Vérifier la réponse pour confirmation d'email
    email_info = post.get("email", {})
    if email_info:
        email_status = email_info.get("status", "unknown")
        print(f"[GHOST] Email status: {email_status}")
    
    return post


def publish_post_to_ghost(state: PipelineState) -> PipelineState:
    """
    Publie la newsletter via la méthode officielle Ghost en 2 étapes:
    1) Créer le post en DRAFT
    2) Publier avec PUT + ?newsletter=<slug> pour déclencher l'email
    
    ✅ Site publication: email_only=False
    ✅ Email envoyé: via ?newsletter=<slug> dans le PUT
    """
    ghost_base = _require_env("GHOST_ADMIN_API_URL").rstrip("/")
    admin_key = _require_env("GHOST_ADMIN_API_KEY")
    newsletter_slug = _require_env("GHOST_NEWSLETTER_SLUG")

    html = state.get("newsletter_html") or ""
    if not html.strip():
        raise RuntimeError("newsletter_html is empty: cannot publish to Ghost")

    # Parse RAG JSON answer
    rag_answer = state.get("rag_answer", "") or ""
    title = ""
    excerpt = ""
    feature_image = None
    
    try:
        rag_data = json.loads(rag_answer)
        if isinstance(rag_data, dict):
            title = (rag_data.get("title") or "").strip()
            excerpt = (rag_data.get("intro") or "").strip()
            if len(excerpt) > 280:
                excerpt = excerpt[:277].rsplit(" ", 1)[0]
            if "stories" in rag_data and isinstance(rag_data["stories"], list):
                for story in rag_data["stories"]:
                    if isinstance(story, dict) and not feature_image and "image_url" in story:
                        feature_image = story["image_url"]
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[GHOST] Warning: Could not parse RAG JSON, using fallback: {e}")
        meta = _extract_post_metadata(rag_answer)
        title = meta.get("title") or ""
        excerpt = meta.get("excerpt") or ""
        # No tags for newsletter
    
    if not feature_image:
        images_index = state.get("images_index", {}) or {}
        if images_index:
            feature_image = next(iter(images_index.values()), None)
    
    if not title:
        title = "Cybersecurity Newsletter"

    excerpt = ""  # Avoid duplicate display
    
    token = _build_ghost_admin_jwt(admin_key)

    post_data = {
        "title": title,
        "custom_excerpt": excerpt,
        "html": html,
        "email_only": False,  # ✅ Visible sur le site
    }
    
    if feature_image:
        post_data["feature_image"] = feature_image
        print(f"[GHOST] Adding feature_image: {feature_image}")

    # ÉTAPE 1: Créer en DRAFT
    post_id, updated_at = _create_draft_post(ghost_base, token, post_data)

    # ÉTAPE 2: Publier + Déclencher email via ?newsletter=<slug>
    published_post = _publish_post_and_send_email(
        ghost_base, token, post_id, updated_at, False, newsletter_slug
    )

    state["ghost_post_id"] = post_id
    state["ghost_post_url"] = str(published_post.get("url", "")) or str(published_post.get("canonical_url", ""))

    return state


def _collection_node(state: PipelineState) -> PipelineState:
    """Wrapper pour publish_stories_as_collection_posts."""
    rag_answer = state.get("rag_answer", "") or ""
    images_index = state.get("images_index", {}) or {}
    
    result = publish_stories_as_collection_posts(rag_answer, images_index)
    
    state["collection_posts_count"] = result.get("collection_posts_count", 0)
    state["collection_posts_failed"] = result.get("collection_posts_failed", 0)
    
    return state



def build_pipeline_app():
    graph = StateGraph(PipelineState)

    # Nodes
    graph.add_node("scrape", lambda s: {"raw_articles": scrape_sources(max_items_per_feed=2)})
    graph.add_node("filter", lambda s: {"filtered_articles": filter_articles(s.get("raw_articles", []))})
    def _preprocess_node(state: PipelineState) -> PipelineState:
        clean = preprocess_articles(state.get("filtered_articles", []))
        if len(clean) < 10:
            raise RuntimeError(
                f"Not enough clean articles to generate 10-story newsletter (got {len(clean)})."
            )
        return {"clean_articles": clean}

    graph.add_node("preprocess", _preprocess_node)
    # Build image index from filtered articles (HTML available)
    def _images_node(state: PipelineState) -> PipelineState:
        filtered = state.get("filtered_articles", []) or []
        images_index: Dict[str, str] = {}
        seen_sources: set[str] = set()

        for art in filtered:
            try:
                url = (art.get("url") or "").strip()
                if not url:
                    continue
                # Deduplicate by source URL per run
                if url in seen_sources:
                    continue
                seen_sources.add(url)

                # Try to pick best image candidate from article metadata/html
                candidate = extract_best_image_url(art)
                if not candidate:
                    continue

                # Download + validation
                dl = download_image(candidate)
                if not dl:
                    # Logged inside helper; skip silently here
                    continue
                image_bytes, filename, content_type = dl

                # Upload to Ghost Admin images endpoint
                ghost_url = upload_image_to_ghost(image_bytes, filename, content_type)
                if ghost_url:
                    images_index[url] = ghost_url
            except Exception as e:
                # Keep pipeline resilient; log and continue
                print(f"[IMAGES] skip for article: {e}")

        return {"images_index": images_index}

    graph.add_node("images", _images_node)
    graph.add_node("embed", lambda s: upsert_embeddings(s.get("clean_articles", [])) or {})
    graph.add_node("rag", lambda s: {"rag_answer": answer_with_rag(s.get("question", ""))})
    # Enrich RAG JSON stories with Ghost image URLs if available
    def _html_node(state: PipelineState) -> PipelineState:
        raw = state.get("rag_answer", "") or ""
        images_index = state.get("images_index", {}) or {}
        enriched_text = raw
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                stories = data.get("stories")
                if isinstance(stories, list):
                    for st in stories:
                        if not isinstance(st, dict):
                            continue
                        src_url = (st.get("url") or st.get("source") or "").strip()
                        if src_url and src_url in images_index:
                            st["image_url"] = images_index[src_url]
                enriched_text = json.dumps(data, ensure_ascii=False)
        except Exception as e:
            print(f"[HTML] Could not enrich with images: {e}")

        return {"newsletter_html": generate_newsletter_html(enriched_text)}

    graph.add_node("html", _html_node)
    graph.add_node("ghost", publish_post_to_ghost)
    graph.add_node("collection", _collection_node)

    
    graph.set_entry_point("scrape")
    graph.add_edge("scrape", "filter")
    graph.add_edge("filter", "preprocess")
    graph.add_edge("preprocess", "images")
    graph.add_edge("preprocess", "embed")
    graph.add_edge("embed", "rag")
    graph.add_edge("rag", "html")
    graph.add_edge("html", "ghost")
    graph.add_edge("ghost", "collection")
    graph.add_edge("collection", END)



    return graph.compile()


















































