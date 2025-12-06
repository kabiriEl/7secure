"""Summarization tool: regroupe les articles en lots et résume chaque lot via le LLM.

Le LLM doit retourner un JSON contenant une liste d'objets avec les champs
title, url et summary. Cette approche réduit fortement le nombre d'appels
réseau quand la source de données est large.
"""

from typing import Any, Dict, List
import json

from src.tools.rag_llm import get_llm


def _chunk(iterable: List[Any], size: int) -> List[List[Any]]:
    return [iterable[i: i + size] for i in range(0, len(iterable), size)]


def summarize_articles(articles: List[Dict[str, Any]], max_sentences: int = 3, batch_size: int = 20) -> List[Dict[str, Any]]:
    """Produit un résumé pour chaque article en traitant les articles par lots.

    - batch_size : nombre d'articles par appel LLM (éviter appels unitaires)
    - max_sentences : longueur approximative des résumés

    Retourne une liste d'articles au même format que `clean_articles` mais avec
    `content` contenant le résumé.
    """
    if not articles:
        print("[SUMMARIZER] Aucun article à résumer.")
        return []

    llm = get_llm()
    summaries: List[Dict[str, Any]] = []

    batches = _chunk(articles, batch_size)
    for b_index, batch in enumerate(batches):
        # Construire prompt unique contenant plusieurs articles
        prompt_parts = [
            "Tu es un assistant qui résume des articles de cybersécurité.",
            "Pour chaque article fourni, fournis un petit résumé en respectant les consignes :",
            f"- Résumé concis en {max_sentences} phrases maximum par article.",
            "- Met en avant incidents, vulnérabilités et tendances importantes.",
            "- N'invente pas d'informations.",
            "- Réponds en français si le texte source est en français.",
            "La sortie DOIT être un JSON valide : une liste d'objets {\"title\", \"url\", \"summary\"}.",
            "Début des articles:\n",
        ]

        for idx, art in enumerate(batch):
            title = art.get("title", "")
            url = art.get("url", "")
            content = art.get("content", "")
            prompt_parts.append(f"---ARTICLE-{idx+1}---")
            prompt_parts.append(f"TITLE: {title}")
            prompt_parts.append(f"URL: {url}")
            # Limiter la longueur insérée pour éviter prompts trop grands
            snippet = content[:8000]
            prompt_parts.append(f"CONTENT: {snippet}")

        prompt = "\n".join(prompt_parts)

        try:
            raw = llm.invoke(prompt)
        except Exception as e:
            print(f"[SUMMARIZER] Erreur LLM pour le batch {b_index+1}/{len(batches)}: {e}")
            # fallback : copier les contenus originaux en guise de résumé
            for art in batch:
                summaries.append({
                    "title": art.get("title", ""),
                    "url": art.get("url", ""),
                    "published": art.get("published"),
                    "content": art.get("content", ""),
                })
            continue

        # Tenter de parser le JSON renvoyé
        parsed = None
        try:
            parsed = json.loads(raw)
        except Exception:
            # Si ce n'est pas un JSON strict, essayer d'extraire la première occurrence JSON
            try:
                start = raw.find("[")
                end = raw.rfind("]")
                if start != -1 and end != -1 and end > start:
                    parsed = json.loads(raw[start: end + 1])
            except Exception:
                parsed = None

        if not parsed or not isinstance(parsed, list):
            print(f"[SUMMARIZER] Réponse LLM non-JSON pour batch {b_index+1}, utilisation du fallback")
            for art in batch:
                summaries.append({
                    "title": art.get("title", ""),
                    "url": art.get("url", ""),
                    "published": art.get("published"),
                    "content": art.get("content", ""),
                })
            continue

        # Mapper les résumés retournés sur les articles du batch (par ordre)
        for i, item in enumerate(parsed):
            try:
                title = item.get("title") or batch[i].get("title", "")
                url = item.get("url") or batch[i].get("url", "")
                summary_text = item.get("summary") or item.get("content") or ""
            except Exception:
                # Défaut si la taille ne correspond pas
                art = batch[i] if i < len(batch) else {}
                title = art.get("title", "")
                url = art.get("url", "")
                summary_text = art.get("content", "")

            summaries.append({
                "title": title,
                "url": url,
                "published": batch[i].get("published"),
                "content": summary_text,
            })

        print(f"[SUMMARIZER] Batch {b_index+1}/{len(batches)} traité, {len(parsed)} résumés reçus")

    print(f"[SUMMARIZER] Total résumés: {len(summaries)}")
    return summaries