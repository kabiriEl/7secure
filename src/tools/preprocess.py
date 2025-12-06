"""Preprocessing tools for SafariNewsletter.

Transforme les articles bruts (HTML) en articles propres (texte).
"""

import re
from typing import Any, Dict, List

from bs4 import BeautifulSoup


def preprocess_articles(raw_articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Nettoyer le HTML et produire une liste d'articles prêts à être stockés/embeddés.

    Chaque article résultant contient :
    - title
    - url
    - published
    - content (texte propre)
    """
    clean: List[Dict[str, Any]] = []

    for art in raw_articles:
        html = art.get("html", "")
        if not html:
            continue

        content = _extract_text_from_html(html)
        if not content:
            continue

        clean.append(
            {
                "title": art.get("title", ""),
                "url": art.get("url", ""),
                "published": art.get("published"),
                "content": content,
            }
        )

    print(f"[PREPROCESS] Articles nettoyés : {len(clean)}")
    return clean


def _extract_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    texts = []
    for element in soup.find_all(["h1", "h2", "h3", "p", "li"]):
        text = element.get_text(separator=" ", strip=True)
        if text:
            texts.append(text)

    raw_text = "\n\n".join(texts)
    return _normalize_whitespace(raw_text)


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
