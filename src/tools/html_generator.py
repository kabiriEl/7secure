"""
HTML Generator Tool for SafariNewsletter.

Ce module prend une newsletter texte (déjà générée par rag.py) et demande
au LLM local (Ollama) de produire un HTML complet, responsive et compatible
avec les clients e-mail. Le code est résilient aux réponses streamées
(newline-delimited JSON) et renvoie le HTML final tel quel.

Inclut un système de mise en cache en mémoire pour éviter les appels
redondants au LLM pour la même newsletter.
"""

import requests
import json
import hashlib
from typing import Optional, Dict

OLLAMA_CHAT = "http://localhost:11434/api/chat"
MODEL_NAME = "phi3:mini"

# Global cache for generated HTML (in-memory)
_html_cache: Dict[str, str] = {}


def _hash_content(text: str) -> str:
    """Compute SHA256 hash of text to use as cache key."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class HTMLGenerator:
    """Transforme une newsletter texte en HTML professionnel via un LLM local.

    Utilise l'endpoint `/api/chat` d'Ollama. Le générateur essaie plusieurs
    stratégies pour extraire le HTML produit : JSON complet, lignes JSON
    délimitées (stream), ou fallback sur le texte brut.

    Inclut une mise en cache en mémoire basée sur le hash du contenu.
    """

    def __init__(self, model: str = MODEL_NAME, timeout: Optional[int] = 120, use_cache: bool = True):
        self.model = model
        self.timeout = timeout
        self.use_cache = use_cache
        

    def generate_html(self, newsletter_text: str) -> str:
        """Demande au modèle de convertir le texte de la newsletter en HTML.

        Retourne la chaîne HTML générée. Utilise le cache si disponible.
        """
        # Check cache first
        if self.use_cache:
            content_hash = _hash_content(newsletter_text)
            if content_hash in _html_cache:
                print(f"[HTML_GENERATOR] Cache hit for hash {content_hash[:8]}...")
                return _html_cache[content_hash]
        
        prompt = f"""
Tu es un assistant expert en design d'e-mail HTML.

Transforme la newsletter suivante en un HTML propre, responsive et professionnel.
Utilise uniquement du style inline compatible Gmail, Outlook et clients mobiles.
Structure demandée : header, introduction, sections avec <h2>/<p>, footer.

NE CHANGE PAS LE CONTENU, ne rajoute aucune information.

Newsletter à convertir :
---------------------------
{newsletter_text}
---------------------------

Retourne UNIQUEMENT le HTML final.
"""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You convert text newsletters into clean, responsive HTML emails."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 1200,
        }

        resp = requests.post(OLLAMA_CHAT, json=payload)

        # Read once and try multiple parsing strategies
        raw = resp.content.decode("utf-8", errors="replace")

        # 1) Try parse whole body as JSON
        try:
            data = json.loads(raw)
            # Ollama chat shape: {'choices': [{'message': {'content': '...'}}]}
            choices = data.get("choices") or []
            if choices:
                msg = choices[0].get("message") or {}
                if isinstance(msg, dict) and msg.get("content"):
                    result = msg.get("content").strip()
                    # Cache before returning
                    if self.use_cache:
                        content_hash = _hash_content(newsletter_text)
                        _html_cache[content_hash] = result
                        print(f"[HTML_GENERATOR] Cached HTML with hash {content_hash[:8]}...")
                    return result
            if isinstance(data, dict) and data.get("message"):
                m = data.get("message")
                if isinstance(m, dict) and m.get("content"):
                    result = m.get("content").strip()
                    # Cache before returning
                    if self.use_cache:
                        content_hash = _hash_content(newsletter_text)
                        _html_cache[content_hash] = result
                        print(f"[HTML_GENERATOR] Cached HTML with hash {content_hash[:8]}...")
                    return result
        except Exception:
            pass

        # 2) Try newline-delimited JSON
        parts = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            choices = obj.get("choices") or []
            if choices:
                f = choices[0]
                msg = f.get("message") or {}
                if isinstance(msg, dict) and msg.get("content"):
                    parts.append(msg.get("content"))
            elif isinstance(obj, dict) and obj.get("message"):
                m = obj.get("message") or {}
                if isinstance(m, dict) and m.get("content"):
                    parts.append(m.get("content"))

        if parts:
            result = "".join(parts).strip()
            # Cache the result
            if self.use_cache:
                content_hash = _hash_content(newsletter_text)
                _html_cache[content_hash] = result
                print(f"[HTML_GENERATOR] Cached HTML with hash {content_hash[:8]}...")
            return result

        # 3) Fallback: return raw text (assume it's the HTML)
        result = raw.strip()
        # Cache the fallback result too
        if self.use_cache:
            content_hash = _hash_content(newsletter_text)
            _html_cache[content_hash] = result
            print(f"[HTML_GENERATOR] Cached fallback HTML with hash {content_hash[:8]}...")
        return result


# Backwards-compatible wrapper used by the workflow
def html_from_newsletter(newsletter_text: str) -> str:
    generator = HTMLGenerator(use_cache=True)
    return generator.generate_html(newsletter_text)


# Compatibility: some modules expect `generate_newsletter_html`
def generate_newsletter_html(newsletter_text: str) -> str:
    return html_from_newsletter(newsletter_text)


def clear_html_cache() -> None:
    """Clear the HTML cache. Useful for testing or manual reset."""
    global _html_cache
    _html_cache.clear()
    print("[HTML_GENERATOR] Cache cleared")
