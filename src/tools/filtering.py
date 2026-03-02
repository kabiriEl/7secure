"""Filtering tool for SafariNewsletter.

Étape intermédiaire entre :
scraping → filtering → preprocessing.

Objectifs :
- dédupliquer les articles
- prioriser les articles pour la sélection pré-RAG
- appliquer des règles de diversité (source, catégorie si présente)
- sélectionner jusqu'à TARGET_COUNT articles

"""

import re
from typing import Dict, List, Any
from collections import defaultdict
from difflib import SequenceMatcher


# Compat API: keep category keys for existing imports/usages
CATEGORIES = {
    "AI Security & Threats": [],
    "Threat Intelligence": [],
    "Malware & Ransomware": [],
    "Vulnerabilities & Exploits": [],
    "Cloud & SaaS Security": [],
    "Identity & Access Management": [],
    "SOC & Automation": [],
    "Data Protection & Privacy": [],
    "Security Culture & Human Factors": [],
    "Compliance & Regulation": [],
    "Data Breaches": [],
}

# Selection targets / limits
TARGET_COUNT = 20
MAX_PER_DOMAIN_PRIMARY = 1
MAX_PER_CATEGORY_PRIMARY = 3


def is_similar(a: str, b: str, threshold: float = 0.80) -> bool:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() >= threshold


def deduplicate(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    unique = []
    seen_urls = set()
    for art in articles:
        url = (art.get("url") or "").strip()
        if url and url in seen_urls:
            continue

        title = art.get("title") or ""
        if not any(is_similar(title, u.get("title") or "") for u in unique):
            unique.append(art)
            if url:
                seen_urls.add(url)
    return unique


def select_top_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    final = []
    selected_urls = set()
    source_count = defaultdict(int)
    category_count = defaultdict(int)

    # Trier par priorité → score → trending
    articles_sorted = sorted(
        articles,
        key=lambda x: (x.get("priority", 0), x.get("score", 0), x.get("trending", 0)),
        reverse=True,
    )

    for art in articles_sorted:
        url = (art.get("url") or "").strip()
        if url and url in selected_urls:
            continue

        domain = "unknown"
        if art.get("url"):
            try:
                domain = re.sub(r"^www\.", "", art["url"].split("/")[2])
            except Exception:
                domain = "unknown"

        cat = (art.get("category") or "").strip()

        if source_count[domain] >= MAX_PER_DOMAIN_PRIMARY:
            continue
        if cat and category_count[cat] >= MAX_PER_CATEGORY_PRIMARY:
            continue
        if len(final) >= TARGET_COUNT:
            break

        final.append(art)
        if url:
            selected_urls.add(url)
        source_count[domain] += 1
        if cat:
            category_count[cat] += 1

    # Relax limits to reach target while keeping unique URLs
    if len(final) < TARGET_COUNT:
        for art in articles_sorted:
            if len(final) >= TARGET_COUNT:
                break
            url = (art.get("url") or "").strip()
            if url and url in selected_urls:
                continue
            final.append(art)
            if url:
                selected_urls.add(url)

    if len(final) < TARGET_COUNT:
        print(f"[FILTER] Warning: only {len(final)}/{TARGET_COUNT} unique articles available after filtering.")

    return final


def filter_articles(raw_articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filtre complet avant preprocessing (sans catégorisation LLM pré-RAG)."""

    # 1) Déduplication
    raw_articles = deduplicate(raw_articles)

    # 2) Préparation scoring pré-RAG (sans catégorisation)
    enriched = []
    title_count = defaultdict(int)
    for art in raw_articles:
        title = art.get("title") or ""
        title_count[title] += 1

        # No category assigned pre-RAG; classification happens post-RAG only.
        art["category"] = ""
        art["secondary_categories"] = []
        art["subtopics"] = []
        art["classification_flags"] = {}
        art["priority_level"] = "medium"

        # Lightweight pre-RAG ranking
        art["score"] = 1
        art["priority"] = 0
        art["trending"] = title_count[title]
        enriched.append(art)

    # 3) Sélection finale
    final = select_top_articles(enriched)

    print(f"[FILTER] Articles filtrés : {len(final)}")
    return final
