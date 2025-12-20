"""
RAG + Newsletter generator using Ollama CLOUD only (official Python client).

- Charge Chroma
- Récupère top-k chunks
- Génère une newsletter via Ollama Cloud (Client host="https://ollama.com")
"""

from typing import List
from ollama import Client

from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

from src.configs.config import settings


# =========================
# Vector store
# =========================
def _load_vectorstore() -> Chroma:
    embeddings = HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL_NAME)
    return Chroma(
        persist_directory=settings.VECTORSTORE_DIR,
        embedding_function=embeddings,
    )


# =========================
# Ollama Cloud (official)
# =========================
def _ollama_client() -> Client:
    if not settings.OLLAMA_API_KEY:
        raise RuntimeError("OLLAMA_API_KEY manquant (Ollama Cloud requis)")

    # Doc officielle: host="https://ollama.com" + Bearer token :contentReference[oaicite:2]{index=2}
    return Client(
        host="https://ollama.com",
        headers={"Authorization": "Bearer " + settings.OLLAMA_API_KEY},
    )


# =========================
# RAG pipeline
# =========================
def generate_newsletter(question: str, k: int = 5) -> str:
    context_text = ""  # ✅ évite NameError en fallback

    # 1) Retrieve
    vectorstore = _load_vectorstore()
    retriever = vectorstore.as_retriever(search_kwargs={"k": k})

    try:
        docs: List = (
            retriever.invoke(question)
            if hasattr(retriever, "invoke")
            else retriever.get_relevant_documents(question)
        )
    except Exception as e:
        print(f"[RAG] Retriever error: {e}")
        docs = []

    # 2) Build context
    context_blocks = []
    for i, doc in enumerate(docs, start=1):
        content = getattr(doc, "page_content", "") or ""
        meta = getattr(doc, "metadata", {}) or {}

        title = (meta.get("title") or "").strip()
        source = (meta.get("url") or meta.get("source") or "").strip()

        if not content:
            continue

        header = " - ".join([x for x in [title, source] if x])
        block = f"[{i}] {header}\n{content}" if header else f"[{i}] {content}"
        context_blocks.append(block)

    context_text = "\n\n".join(context_blocks) if context_blocks else "(Aucun contenu récupéré.)"

    # 3) Prompt final
    prompt = f"""
You are a senior cybersecurity analyst and the author of a DAILY CYBERSECURITY & AI
THREAT INTELLIGENCE NEWSLETTER, in a professional format, strictly inspired by veillecyber.fr.

=====================
ABSOLUTE RULE
=====================
What you produce:
- IS NOT an editorial letter
- IS NOT a message addressed to subscribers
- IS NOT a single article
- IS a structured, multi-event cybersecurity intelligence report

=====================
STRICT PROHIBITIONS
=====================
- No greetings
- No signature
- No storytelling
- No personal opinions
- No fabrication or assumptions

=====================
MANDATORY STRUCTURE
=====================

GLOBAL TITLE :
    - size : 1–2 factual lines 
    - exemple : "Ministère de l'Intérieur fuite données 🇫🇷, Cisco faille 0-day , GRU cible énergie"
    - format : combine 2–3 major topics of the day in a factual, informative style and use emojis where relevant. without saying "GLOBAL TITLE".

INTRODUCTION :
    - size : 1-2 sentences 
    - exemple : "Hello and welcome to the edition of Friday, "mounth" th!"
    - format : just greetings with date, without saying "INTRODUCTION".

TODAY’S HEADLINES (maximum 4–6 bullet points)

Minimum of 5 to 6 major topics.

Then, for each major topic:
[TITLE]
Key points: 3–5 bullet points
Description: 1 paragraph
Why it matters: 1 paragraph

Closing expression, for example (have a good day, see you tomorrow, etc.).

=====================
PROVIDED CONTEXT
=====================
{context_text}

=====================
EXPECTED OUTPUT
=====================
Complete, structured, factual newsletter.
"""


    # 4) Ollama Cloud call (official client)
    try:
        client = _ollama_client()

        # ⚠️ Pour du Cloud, utilise idéalement un modèle *-cloud* (ex: gpt-oss:120b-cloud). :contentReference[oaicite:3]{index=3}
        model = settings.OLLAMA_MODEL

        resp = client.chat(
            model=model,
            messages=[
                {"role": "system", "content": "Rédige une newsletter cybersécurité factuelle, structurée, détaillée."},
                {"role": "user", "content": prompt},
            ],
            stream=False,
        )

        text = (resp.get("message", {}) or {}).get("content", "")
        text = (text or "").strip()

        if not text:
            print("[RAG] Réponse vide du modèle, fallback.")
            return f"Newsletter — Synthèse rapide\n\n{context_text}"

        return text

    except Exception as e:
        print(f"[RAG] Ollama Cloud error: {e}")
        return f"Newsletter — Synthèse rapide\n\n{context_text}"


def answer_with_rag(question: str) -> str:
    return generate_newsletter(question)































# """
# RAG + Newsletter generator using local Ollama (Llama 3).

# Ce module :
# 1. Charge le vector store Chroma construit auparavant.
# 2. Récupère les documents les plus pertinents via le retriever.
# 3. Utilise uniquement le contenu déjà nettoyé (pas de nouvelle summarisation ici).
# 4. Génère une newsletter concise via l'API Ollama locale.
# """

# from typing import List
# import json
# import requests
# from langchain_community.vectorstores import Chroma
# from langchain_community.embeddings import HuggingFaceEmbeddings
# from src.configs.config import settings

# # ===== OLLAMA CONFIGURATION =====
# OLLAMA_CHAT = "http://localhost:11434/api/chat"
# OLLAMA_MODEL = "llama3:latest"


# def _load_vectorstore() -> Chroma:
#     """Charge le vector store Chroma depuis le dossier configuré."""
#     embeddings = HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL_NAME)
#     return Chroma(
#         persist_directory=settings.VECTORSTORE_DIR,
#         embedding_function=embeddings,
#     )


# def generate_newsletter(question: str, k: int = 5) -> str:
#     """Génère une newsletter à partir d'une question ouverte et des articles indexés.

#     Args:
#         question: la thématique ou question posée par l'utilisateur.
#         k: nombre de documents à récupérer (top k).

#     Returns:
#         Texte de la newsletter (français de préférence si les sources le sont).
#     """

#     vectorstore = _load_vectorstore()
#     retriever = vectorstore.as_retriever(search_kwargs={"k": k})

#     # Nouvelle logique compatible avec les versions récentes de LangChain
#     try:
#         if hasattr(retriever, "invoke"):
#             # API moderne
#             docs: List = retriever.invoke(question)
#         else:
#             # Ancienne API (au cas où)
#             docs = retriever.get_relevant_documents(question)
#     except Exception as exc:
#         print(f"[RAG] retriever failed: {exc}. Falling back to similarity_search")
#         try:
#             docs = vectorstore.similarity_search(question, k=k)
#         except Exception as exc2:
#             print(f"[RAG] vectorstore.similarity_search also failed: {exc2}")
#             docs = []

#     # 2) Récupérer le contenu nettoyé depuis le vector store
#     # Les documents dans le vector store doivent contenir le texte nettoyé dans 'page_content'
#     # IMPORTANT : Ne pas effectuer de nouvelle summarisation ici — utiliser tel quel.
#     clean_texts = []
#     for i, doc in enumerate(docs, start=1):
#         # support both Document-like objects and dicts
#         if isinstance(doc, dict):
#             content_text = doc.get("page_content") or doc.get("html") or ""
#             meta = doc.get("metadata") or {}
#         else:
#             content_text = getattr(doc, "page_content", "") or ""
#             meta = getattr(doc, "metadata", {}) or {}

#         source = meta.get("url") or meta.get("source") or ""
#         title = meta.get("title") or meta.get("headline") or ""

#         if content_text:
#             header = f"{title} - {source}" if (title or source) else ""
#             if header:
#                 entry = f"[{i}] {header}\n{content_text}"
#             else:
#                 entry = f"[{i}] {content_text}"
#             clean_texts.append(entry)
#         else:
#             print(f"[RAG] warning: doc #{i} has empty page_content")
#             clean_texts.append(f"[{i}] (Document vide)")

#     # Contexte final pour le modèle — contenus nettoyés
#     context_text = "\n\n".join(clean_texts)

#     # 3) Construire le prompt pour la newsletter finale
#     prompt = f"""
# Tu es un analyste senior en cybersécurité et le rédacteur d’une NEWSLETTER DE VEILLE
# cybersécurité quotidienne, au format professionnel, strictement inspiré de veillecyber.fr.

# =====================
# RÈGLE ABSOLUE
# =====================
# Ce que tu produis :
# - N’EST PAS une lettre éditoriale
# - N’EST PAS un message adressé à un abonné
# - N’EST PAS un article unique
# - EST une veille cybersécurité structurée multi-événements

# =====================
# INTERDICTIONS STRICTES
# =====================
# - Aucune salutation (Bonjour, Dear reader, etc.)
# - Aucune signature ou message personnel
# - Aucun appel à répondre, commenter ou partager
# - Aucune phrase marketing ou émotionnelle
# - Aucun storytelling
# - Aucune opinion personnelle
# - Aucune invention ou extrapolation
# - Aucun contenu hors cybersécurité

# =====================
# OBJECTIF ÉDITORIAL
# =====================
# Fournir une veille cybersécurité quotidienne :
# - claire
# - factuelle
# - détaillée
# - actionnable

# Public cible :
# RSSI, analystes SOC, équipes IT, ingénieurs sécurité.

# =====================
# LONGUEUR & DENSITÉ
# =====================
# - Newsletter détaillée et riche
# - Viser 1200 à 2000 mots si les sources le permettent
# - Chaque sujet majeur doit être développé en profondeur
# - Pas de remplissage artificiel

# =====================
# STRUCTURE OBLIGATOIRE (NON NÉGOCIABLE)
# =====================

# TITRE PRINCIPAL
# - Un titre éditorial synthétique combinant 2 à 3 sujets majeurs de la journée
# - Style factuel et informatif (ex : correctifs, alertes, vulnérabilités)

# INTRODUCTION
# - 4 à 6 phrases
# - Présenter le contexte global de la journée
# - Mentionner brièvement les grands thèmes abordés

# À LA UNE AUJOURD’HUI
# - Liste à puces
# - 4 à 6 points maximum
# - Une phrase courte par point
# - Résumer les sujets clés de la newsletter

# =====================
# ARTICLES DE VEILLE (FORMAT OBLIGATOIRE)
# =====================

# Pour CHAQUE sujet important, utiliser STRICTEMENT la structure suivante :

# [TITRE DE L’ARTICLE]

# Points clés :
# - 3 à 5 puces factuelles
# - Informations essentielles uniquement
# - Pas de phrases vagues

# Description :
# - 1 à 2 paragraphes
# - Contexte technique ou opérationnel
# - Ce qui s’est passé, comment, sur quoi

# Pourquoi c’est important :
# - 1 paragraphe clair
# - Impact réel pour les organisations
# - Risque, exposition ou enjeu sécurité

# =====================
# CATÉGORIES À COUVRIR
# =====================
# - Vulnérabilités & CVE
# - Incidents & attaques
# - Campagnes malveillantes
# - Alertes éditeurs / agences (Microsoft, NCSC, CISA, etc.)
# - Tendances & rapports stratégiques

# =====================
# RÈGLES DE RÉDACTION
# =====================
# - Ton neutre et professionnel
# - Style journalistique de veille
# - Paragraphes courts
# - Vocabulaire précis
# - Pas de jargon inutile
# - Prioriser les faits et l’impact

# =====================
# CONTEXTE FOURNI
# =====================
# Les contenus suivants sont des SOURCES BRUTES NETTOYÉES.
# Tu dois les ANALYSER, STRUCTURER et PRIORISER.
# Ne pas les reformuler comme un article unique.

# {context_text}

# =====================
# SORTIE ATTENDUE
# =====================
# - Une newsletter complète de veille cybersécurité
# - Strict respect de la structure imposée
# - Aucun contenu hors format
# """





#     # ===== OLLAMA CALL =====
#     try:
#         payload = {
#             "model": OLLAMA_MODEL,
#             # Add a system message to reinforce length and style, then the user prompt
#             "messages": [
#                 {"role": "system", "content": "Génère une newsletter détaillée et structurée; vise ~800-1200 mots si possible, développe chaque point."},
#                 {"role": "user", "content": prompt}
#             ],
#             # Encourage longer outputs; Ollama may accept max_tokens / max_output_tokens
#             "max_tokens": 1500,
#             "temperature": 0.2,
#             "stream": False,
#         }

#         resp = requests.post(OLLAMA_CHAT, json=payload)
#         resp.raise_for_status()
#         data = resp.json()
        
#         print(f"[RAG] Ollama response received")

#         # Extract text from Ollama response
#         if "message" in data:
#             message = data["message"]
#             if isinstance(message, dict) and "content" in message:
#                 result = message["content"].strip()
#                 print(f"[RAG] Newsletter generated successfully: {result[:200]}...")
#                 return result

#         print("[RAG] No valid response from Ollama")
#         # Fallback: return context as newsletter
#         return f"Newsletter — Synthèse rapide pour : {question}\n\n{context_text}"

#     except requests.exceptions.ConnectionError as conn_err:
#         print(f"[RAG] Ollama connection failed (is it running on {OLLAMA_CHAT}?): {conn_err}")
#         # Fallback: return structured newsletter from summaries
#         return f"Newsletter — Synthèse rapide pour : {question}\n\n{context_text}"

#     except requests.exceptions.Timeout as rte:
#         print(f"[RAG] Ollama API timeout: {rte}. Returning summaries as fallback.")
#         return f"Newsletter — Synthèse rapide pour : {question}\n\n{context_text}"

#     except Exception as e:
#         try:
#             snippet = resp.text[:1000] if resp is not None else ""
#             print(f"[RAG] Ollama API request failed: {e} -- response snippet:\n{snippet}")
#         except Exception:
#             print(f"[RAG] Ollama API request failed: {e}")
#         # Fallback: return context as newsletter
#         return f"Newsletter — Synthèse rapide pour : {question}\n\n{context_text}"


# def answer_with_rag(question: str) -> str:
#     """Backward-compatible wrapper used by the pipeline.

#     Delegates to generate_newsletter and returns the generated text.
#     """
#     return generate_newsletter(question)
























