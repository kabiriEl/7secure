"""Newsletter formatting tool for SafariNewsletter."""

from typing import Dict


def build_newsletter_from_rag(rag_answer: str) -> Dict:
    """Transforme le texte brut en structure de newsletter.

    Ici on fait simple : une seule section avec tout le texte.
    Plus tard, tu pourras re-appeler le LLM pour découper en sections.
    """
    newsletter = {
        "subject": "Newsletter quotidienne – Veille cybersécurité",
        "sections": [
            {
                "title": "Résumé du jour",
                "content": rag_answer,
            }
        ],
    }
    return newsletter
