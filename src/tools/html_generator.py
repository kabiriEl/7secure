"""
HTML Generator Tool for SafariNewsletter (Ollama Cloud only, official client).

- Convertit une newsletter texte en HTML email compatible
- Cache mémoire par hash pour éviter les appels redondants
"""

import os
import hashlib
from typing import Dict

from ollama import Client
from src.configs.config import settings


_html_cache: Dict[str, str] = {}


def _hash_content(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ollama_client() -> Client:
    if not settings.OLLAMA_API_KEY:
        raise RuntimeError("OLLAMA_API_KEY manquant (Ollama Cloud requis)")

    # Doc officielle: host="https://ollama.com" + Bearer token :contentReference[oaicite:4]{index=4}
    return Client(
        host="https://ollama.com",
        headers={"Authorization": "Bearer " + settings.OLLAMA_API_KEY},
    )


def _html_model() -> str:
    # modèle HTML séparé si voulu
    return os.getenv("OLLAMA_HTML_MODEL") or getattr(settings, "OLLAMA_MODEL", "gpt-oss:20b-cloud")


class HTMLGenerator:
    """Transforme une newsletter texte en HTML email via Ollama Cloud."""

    def __init__(self, model: str = "", use_cache: bool = True):
        self.model = model or _html_model()
        self.use_cache = use_cache
        self.client = _ollama_client()

    def generate_html(self, newsletter_text: str) -> str:
        if not newsletter_text:
            return ""

        content_hash = _hash_content(newsletter_text)

        if self.use_cache and content_hash in _html_cache:
            print(f"[HTML_GENERATOR] Cache hit ({content_hash[:8]})")
            return _html_cache[content_hash]

        prompt = f"""Tu es un expert en design d'e-mails HTML.

OBJECTIF:
Convertir la newsletter ci-dessous en un HTML propre, lisible, responsive
et compatible Gmail/Outlook/mobile.

CONTRAINTES STRICTES:
- NE PAS modifier le texte
- NE RIEN ajouter
- NE RIEN supprimer
- NE PAS résumer
- Ajouter UNIQUEMENT la structure HTML + style inline (pas de <style> global)
- Structure:
  - header (titre)
  - sections avec <h2>, <p>, <ul><li>
  - footer

NEWSLETTER:
----------------------------
{newsletter_text}
----------------------------

Retourne UNIQUEMENT le HTML final.
"""

        try:
            resp = self.client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You convert newsletters into clean, email-safe HTML with inline CSS only."},
                    {"role": "user", "content": prompt},
                ],
                stream=False,
            )

            html = (resp.get("message", {}) or {}).get("content", "")
            html = (html or "").strip()

            if not html:
                print("[HTML_GENERATOR] Réponse vide, fallback texte brut.")
                html = newsletter_text

            if self.use_cache:
                _html_cache[content_hash] = html
                print(f"[HTML_GENERATOR] Cached ({content_hash[:8]})")

            return html

        except Exception as e:
            print(f"[HTML_GENERATOR] Ollama Cloud error: {e}")
            if self.use_cache:
                _html_cache[content_hash] = newsletter_text
            return newsletter_text


def html_from_newsletter(newsletter_text: str) -> str:
    return HTMLGenerator(use_cache=True).generate_html(newsletter_text)


def generate_newsletter_html(newsletter_text: str) -> str:
    return html_from_newsletter(newsletter_text)


def clear_html_cache() -> None:
    _html_cache.clear()
    print("[HTML_GENERATOR] Cache cleared")





















# """
# HTML Generator Tool for SafariNewsletter.

# Ce module prend une newsletter texte (déjà générée par rag.py) et demande
# au LLM Ollama local de produire un HTML complet, responsive et compatible
# avec les clients e-mail.

# Inclut un système de mise en cache en mémoire pour éviter les appels
# redondants au LLM pour la même newsletter.
# """

# import requests
# import json
# import hashlib
# from typing import Optional, Dict
# from src.configs.config import settings

# # ===== OLLAMA CONFIGURATION =====
# OLLAMA_CHAT = "http://localhost:11434/api/chat"
# OLLAMA_MODEL = "phi3:mini"

# # Global cache for generated HTML (in-memory)
# _html_cache: Dict[str, str] = {}


# def _hash_content(text: str) -> str:
#     """Compute SHA256 hash of text to use as cache key."""
#     return hashlib.sha256(text.encode("utf-8")).hexdigest()


# class HTMLGenerator:
#     """Transforme une newsletter texte en HTML professionnel via Google Gemini.

#     Utilise l'API Google Gemini Flash 2.5. Le générateur essaie plusieurs
#     stratégies pour extraire le HTML produit : JSON complet, lignes JSON
#     délimitées, ou fallback sur le texte brut.

#     Inclut une mise en cache en mémoire basée sur le hash du contenu.
#     """

#     def __init__(self, model: str = OLLAMA_MODEL, use_cache: bool = True):
#         self.model = model
#         self.use_cache = use_cache
        

#     def generate_html(self, newsletter_text: str) -> str:
#         """Demande au modèle de convertir le texte de la newsletter en HTML.

#         Retourne la chaîne HTML générée. Utilise le cache si disponible.
#         """
#         # Check cache first
#         if self.use_cache:
#             content_hash = _hash_content(newsletter_text)
#             if content_hash in _html_cache:
#                 print(f"[HTML_GENERATOR] Cache hit for hash {content_hash[:8]}...")
#                 return _html_cache[content_hash]
        
#         prompt = f"""Tu es un assistant expert en design d'e-mail HTML.

# Transforme la newsletter suivante en un HTML propre, responsive et professionnel.
# Utilise uniquement du style inline compatible Gmail, Outlook et clients mobiles.
# Structure demandée : header, introduction, sections avec <h2>/<p>, footer.

# NE CHANGE PAS LE CONTENU, ne rajoute aucune information.

# Newsletter à convertir :
# ---------------------------
# {newsletter_text}
# ---------------------------

# Retourne UNIQUEMENT le HTML final."""

#         # ===== OLLAMA CALL =====
#         try:
#             payload = {
#                 "model": OLLAMA_MODEL,
#                 "messages": [
#                     {
#                         "role": "user",
#                         "content": prompt
#                     }
#                 ],
#                 "stream": False,
#             }

#             resp = requests.post(OLLAMA_CHAT, json=payload)
#             resp.raise_for_status()
#             data = resp.json()

#             # Extract HTML from Ollama response
#             if "message" in data:
#                 message = data["message"]
#                 if isinstance(message, dict) and "content" in message:
#                     result = message["content"].strip()
#                     # Cache before returning
#                     if self.use_cache:
#                         content_hash = _hash_content(newsletter_text)
#                         _html_cache[content_hash] = result
#                         print(f"[HTML_GENERATOR] Cached HTML with hash {content_hash[:8]}...")
#                     return result

#             # No valid response
#             print("[HTML_GENERATOR] No valid response from Ollama, returning original text")
#             result = newsletter_text
#             if self.use_cache:
#                 content_hash = _hash_content(newsletter_text)
#                 _html_cache[content_hash] = result
#             return result

#         except requests.exceptions.ConnectionError:
#             print(f"[HTML_GENERATOR] Ollama connection failed (is it running on {OLLAMA_CHAT}?), returning original text")
#             result = newsletter_text
#             if self.use_cache:
#                 content_hash = _hash_content(newsletter_text)
#                 _html_cache[content_hash] = result
#             return result

#         except requests.exceptions.Timeout:
#             print("[HTML_GENERATOR] Ollama request timeout, returning original text")
#             result = newsletter_text
#             if self.use_cache:
#                 content_hash = _hash_content(newsletter_text)
#                 _html_cache[content_hash] = result
#             return result

#         except Exception as e:
#             print(f"[HTML_GENERATOR] Ollama API request failed: {e}, returning original text")
#             result = newsletter_text
#             if self.use_cache:
#                 content_hash = _hash_content(newsletter_text)
#                 _html_cache[content_hash] = result
#             return result


# # Backwards-compatible wrapper used by the workflow
# def html_from_newsletter(newsletter_text: str) -> str:
#     generator = HTMLGenerator(use_cache=True)
#     return generator.generate_html(newsletter_text)


# # Compatibility: some modules expect `generate_newsletter_html`
# def generate_newsletter_html(newsletter_text: str) -> str:
#     return html_from_newsletter(newsletter_text)


# def clear_html_cache() -> None:
#     """Clear the HTML cache. Useful for testing or manual reset."""
#     global _html_cache
#     _html_cache.clear()
#     print("[HTML_GENERATOR] Cache cleared")
#     print("[HTML_GENERATOR] Cache cleared")


# # ===== COMMENTED OLLAMA IMPLEMENTATION (KEPT FOR FUTURE REFERENCE) =====
# # """
# # def generate_html_with_ollama(newsletter_text: str) -> str:
# #     payload = {
# #         "model": "phi3:mini",
# #         "messages": [
# #             {"role": "system", "content": "You convert text newsletters into clean, responsive HTML emails."},
# #             {"role": "user", "content": prompt},
# #         ],
# #         "temperature": 0.1,
# #         "max_tokens": 1200,
# #     }
# #
# #     resp = requests.post(OLLAMA_CHAT, json=payload)
# #     raw = resp.content.decode("utf-8", errors="replace")
# #
# #     # Try parse whole body as JSON
# #     try:
# #         data = json.loads(raw)
# #         choices = data.get("choices") or []
# #         if choices:
# #             msg = choices[0].get("message") or {}
# #             if isinstance(msg, dict) and msg.get("content"):
# #                 return msg.get("content").strip()
# #     except Exception:
# #         pass
# # """
