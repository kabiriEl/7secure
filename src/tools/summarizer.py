# """
# Summarizer tool using Ollama (local LLM).

# This module calls the local Ollama API to produce concise summaries.
# """

# from typing import List
# import requests
# import json

# from src.configs.config import settings

# # ===== OLLAMA CONFIGURATION (ACTIVE) =====
# OLLAMA_CHAT = "http://localhost:11434/api/chat"
# OLLAMA_MODEL = "phi3:mini"


# class Summarizer:
#     """Simple wrapper to call Ollama API and return a short summary string."""

#     def __init__(self) -> None:
#         # Ollama doesn't require API keys, just a running server
#         pass

#     def summarize(self, text: str, max_tokens: int = 200) -> str:
#         """Return a short summary for `text` using Ollama local API.

#         Falls back to smart text truncation if API call fails.
#         """
#         # Safety limits to avoid very large payloads
#         max_input_chars = 4000
#         safe_text = text if len(text) <= max_input_chars else text[:max_input_chars]

#         prompt = (
#             "Resume le texte ci-dessous en cinq phrases maximum. "
#             "Mets en evidence le contexte, les acteurs, l'attaque ou l'actualite, "
#             "les victimes et l'impact. Ne rajoute pas d'information qui n'est pas dans le texte.\n\n"
#             f"Texte :\n{safe_text}\n\nResumé :"
#         )

#         try:
#             # Call Ollama API
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

#             response = requests.post(OLLAMA_CHAT, json=payload)
#             response.raise_for_status()
#             data = response.json()
#             print(f"[SUMMARIZER] Ollama response received")

#             # Extract text from Ollama response
#             if "message" in data:
#                 message = data["message"]
#                 if isinstance(message, dict) and "content" in message:
#                     result = message["content"].strip()
#                     print(f"[SUMMARIZER] Summary generated successfully: {result[:100]}...")
#                     return result

#             print("[SUMMARIZER] No valid response from Ollama")
#             return "Summary unavailable"

#         except requests.exceptions.ConnectionError:
#             print(f"[SUMMARIZER] Ollama connection failed (is it running on {OLLAMA_CHAT}?)")
#             print(f"[SUMMARIZER] Falling back to smart text truncation")
#             # Fallback: return truncated original text with sentence extraction
#             import re
#             sentences = re.split(r'(?<=[.!?])\s+', safe_text)
#             summary = " ".join(sentences[:5])  # First 5 sentences
#             if len(summary) > 500:
#                 summary = summary[:500].rsplit(' ', 1)[0] + "..."
#             return summary if summary else safe_text[:500]

#         except requests.RequestException as exc:
#             print(f"[SUMMARIZER] Ollama API request failed: {exc}")
#             print(f"[SUMMARIZER] Falling back to smart text truncation")
#             # Fallback: return truncated original text with sentence extraction
#             import re
#             sentences = re.split(r'(?<=[.!?])\s+', safe_text)
#             summary = " ".join(sentences[:5])  # First 5 sentences
#             if len(summary) > 500:
#                 summary = summary[:500].rsplit(' ', 1)[0] + "..."
#             return summary if summary else safe_text[:500]

#         except (KeyError, IndexError, ValueError) as exc:
#             print(f"[SUMMARIZER] Error parsing Ollama response: {exc}")
#             print(f"[SUMMARIZER] Falling back to smart text truncation")
#             # Fallback: return truncated original text with sentence extraction
#             import re
#             sentences = re.split(r'(?<=[.!?])\s+', safe_text)
#             summary = " ".join(sentences[:5])  # First 5 sentences
#             if len(summary) > 500:
#                 summary = summary[:500].rsplit(' ', 1)[0] + "..."
#             return summary if summary else safe_text[:500]


# def summarize_articles(articles: list) -> list:
#     """Compatibility wrapper used by the pipeline.

#     Accepts the list of clean article dicts and returns a list of dicts
#     with the same shape but with the 'content' replaced by the summary text.
#     """
#     summarizer = Summarizer()
#     summaries = []
#     for art in articles:
#         title = art.get("title") or art.get("headline") or ""
#         url = art.get("url") or art.get("link") or ""
#         published = art.get("published")
#         content = art.get("content") or art.get("text") or ""

#         if not content:
#             summaries.append({"title": title, "url": url, "published": published, "content": ""})
#             continue

#         try:
#             summary = summarizer.summarize(content, max_tokens=200)
#         except Exception as err:
#             print(f"[SUMMARIZER] summarization failed for {url or title}: {err}")
#             summary = content[:300]

#         summaries.append({"title": title, "url": url, "published": published, "content": summary})

#     return summaries






















# # """Summarization tool using HuggingFace InferenceClient and google/gemma-2b-it.

# # This module exposes summarize_articles(articles) which returns the same
# # structure as clean_articles but with the `content` field replaced by a
# # concise summary generated by the remote model.

# # The implementation keeps things simple: it calls the remote model per-article
# # with a truncated snippet to limit token usage. If the remote call fails we
# # fall back to a short extractive snippet.
# # """

# # from typing import Any, Dict, List
# # import requests
# # import json


# # OLLAMA_API = "http://localhost:11434/api/chat"
# # OLLAMA_MODEL = "llama3"  # Ollama model name for Llama 3; adjust if different locally


# # def _call_ollama(prompt: str, model: str = OLLAMA_MODEL, timeout: int = 200) -> str:
# #     """Call local Ollama chat API and return the text content.

# #     Expects Ollama running locally (default port 11434).
# #     """
# #     payload = {
# #         "model": model,
# #         "messages": [
# #             {"role": "system", "content": "You are a helpful assistant for summarization."},
# #             {"role": "user", "content": prompt},
# #         ],
# #     }
# #     try:
# #         resp = requests.post(OLLAMA_API, json=payload, timeout=timeout)
# #         resp.raise_for_status()
# #         text = resp.text

# #         # Try normal JSON parsing first
# #         data = None
# #         try:
# #             data = resp.json()
# #         except Exception:
# #             # If direct JSON parsing fails, try to extract a JSON object/array substring
# #             try:
# #                 import re
            
# #                 m = re.search(r"\{.*\}", text, flags=re.S)
# #                 if m:
# #                     data = json.loads(m.group(0))
# #                 else:
# #                     m = re.search(r"\[.*\]", text, flags=re.S)
# #                     if m:
# #                         data = json.loads(m.group(0))
# #             except Exception:
# #                 data = None

# #         if isinstance(data, dict):
# #             choices = data.get("choices") or []
# #             if choices:
# #                 message = choices[0].get("message") or {}
# #                 if isinstance(message, dict):
# #                     return message.get("content", "").strip()
# #             return data.get("text", "").strip()

# #         # Fallback: return raw text (useful when Ollama returns plain text)
# #         return text.strip()
# #     except Exception as e:
# #         # Print a short slice of the response if available to aid debugging
# #         try:
# #             snippet = resp.text[:1000]
# #             print(f"[SUMMARIZER][OLLAMA] Error calling Ollama: {e} -- response snippet:\n{snippet}")
# #         except Exception:
# #             print(f"[SUMMARIZER][OLLAMA] Error calling Ollama: {e}")
# #         raise


# # def summarize_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
# #     """Summarize each article using Ollama Llama 3.

# #     Truncates content to 2000 chars before sending to Ollama. On failure, falls
# #     back to a short extractive snippet.
# #     """
# #     if not articles:
# #         print("[SUMMARIZER] Aucun article à résumer.")
# #         return []

# #     summaries: List[Dict[str, Any]] = []

# #     for i, art in enumerate(articles):
# #         title = art.get("title", "")
# #         url = art.get("url", "")
# #         published = art.get("published")
# #         content = art.get("content", "") or ""

# #         if not content:
# #             summaries.append({"title": title, "url": url, "published": published, "content": ""})
# #             print(f"[SUMMARIZER] Article {i+1}/{len(articles)}: {title!r} (pas de contenu)")
# #             continue

# #         snippet = content[:2000]
# #         prompt = (
# #             "Summarize the following cybersecurity article concisely (2-3 sentences).\n\n"
# #             f"Title: {title}\nURL: {url}\n\nContent:\n{snippet}\n\n"
# #             "Return only the summary text. Do not add information not present in the text."
# #         )

# #         try:
# #             summary = _call_ollama(prompt)
# #         except Exception:
# #             summary = content[:300]

# #         summaries.append({"title": title, "url": url, "published": published, "content": summary})
# #         print(f"[SUMMARIZER] Article {i+1}/{len(articles)} résumé: {title!r}")

# #     print(f"[SUMMARIZER] Total résumés: {len(summaries)}")
# #     return summaries