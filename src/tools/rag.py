"""
RAG + Newsletter generator using local Ollama (Llama 3).

Ce module :
1. Charge le vector store Chroma construit auparavant.
2. Récupère les documents les plus pertinents via le retriever.
3. Résume chaque document avec Summarizer.
4. Génère une newsletter concise via l’API Ollama locale.
"""

from typing import List

import requests
import json
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from src.configs.config import settings
from src.tools.summarizer import Summarizer

# Ollama chat endpoint
OLLAMA_CHAT = "http://localhost:11434/api/chat"
MODEL_NAME = "phi3:mini"


def _load_vectorstore() -> Chroma:
    """Charge le vector store Chroma depuis le dossier configuré."""
    embeddings = HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL_NAME)
    return Chroma(
        persist_directory=settings.VECTORSTORE_DIR,
        embedding_function=embeddings,
    )


def generate_newsletter(question: str, k: int = 5) -> str:
    """Génère une newsletter à partir d'une question ouverte et des articles indexés.

    Args:
        question: la thématique ou question posée par l'utilisateur.
        k: nombre de documents à récupérer (top k).

    Returns:
        Texte de la newsletter (français de préférence si les sources le sont).
    """

    vectorstore = _load_vectorstore()
    retriever = vectorstore.as_retriever(search_kwargs={"k": k})

    # Nouvelle logique compatible avec les versions récentes de LangChain
    try:
        if hasattr(retriever, "invoke"):
            # API moderne
            docs: List = retriever.invoke(question)
        else:
            # Ancienne API (au cas où)
            docs = retriever.get_relevant_documents(question)
    except Exception as exc:
        print(f"[RAG] retriever failed: {exc}. Falling back to similarity_search")
        try:
            docs = vectorstore.similarity_search(question, k=k)
        except Exception as exc2:
            print(f"[RAG] vectorstore.similarity_search also failed: {exc2}")
            docs = []


    # 2) Résumer chaque document (contenu du champ page_content)
    summarizer = Summarizer()
    summaries = []
    for i, doc in enumerate(docs, start=1):
        # support both Document-like objects and dicts
        if isinstance(doc, dict):
            article_text = doc.get("page_content") or doc.get("html") or ""
        else:
            article_text = getattr(doc, "page_content", "") or ""

        try:
            summary = summarizer.summarize(article_text, max_tokens=200)
            summaries.append(f"[{i}] {summary}")
        except Exception as err:
            print(f"[RAG] summarizer failed for doc #{i}: {err}")
            summaries.append(f"[{i}] {article_text[:300]}")

    # Contexte final pour le modèle Llama 3
    context_text = "\n\n".join(summaries)

    # 3) Construire le prompt pour la newsletter finale
    prompt = (
        "Tu es le rédacteur d'une newsletter de veille cybersécurité. "
        "À partir des résumés ci-dessous, écris une newsletter concise. "
        "Fournis une introduction (2 phrases max) et structure le reste en sections avec titre et contenu. "
        "N'invente pas d'informations et reste professionnel.\n\n"
        f"Question : {question}\n\n"
        f"Résumés :\n{context_text}\n\n"
        "Newsletter :"
    )

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "You are an assistant that writes a short structured newsletter from provided snippets."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 300,
    }

    resp = None
    try:
        resp = requests.post(OLLAMA_CHAT, json=payload)
        resp.raise_for_status()

        # Read full body once
        raw = resp.content.decode("utf-8", errors="replace")
        print(f"[RAG] Raw Ollama response (first 500 chars):\n{raw[:500]}\n---")

        # 1) Try parse entire body as JSON
        try:
            data = json.loads(raw)
            choices = data.get("choices") or []
            if choices:
                first = choices[0]
                message = first.get("message") or {}
                if isinstance(message, dict) and message.get("content"):
                    return message.get("content").strip()
                if first.get("text"):
                    return first.get("text").strip()
            if isinstance(data, dict) and data.get("response"):
                return (data.get("response") or "").strip()
        except Exception as e:
            print(f"[RAG] JSON parse attempt 1 failed: {e}")

        # 2) Newline-delimited JSON objects
        parts = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception as pe:
                print(f"[RAG] Could not parse line as JSON: {pe} -- line[:120]={line[:120]}")
                continue
            choices = obj.get("choices") or []
            if choices:
                f = choices[0]
                msg = f.get("message") or {}
                if isinstance(msg, dict) and msg.get("content"):
                    parts.append(msg.get("content"))
            elif isinstance(obj, dict) and obj.get("message"):
                msg = obj.get("message") or {}
                if isinstance(msg, dict) and msg.get("content"):
                    parts.append(msg.get("content"))

        if parts:
            result = "".join(parts).strip()
            print(f"[RAG] Newline JSON parse succeeded: {result[:200]}")
            return result

        # 3) Nested JSON substring fallback
        try:
            import re

            m = re.search(r"\{.*\}", raw, flags=re.S)
            if m:
                maybe = json.loads(m.group(0))
                choices = maybe.get("choices") or []
                if choices:
                    m0 = choices[0].get("message") or {}
                    if isinstance(m0, dict) and m0.get("content"):
                        return m0.get("content").strip()
        except Exception as ex:
            print(f"[RAG] Nested JSON extraction failed: {ex}")

        print(f"[RAG] All parsing failed, returning raw text: {raw[:200]}")
        return raw.strip()
    except requests.exceptions.ReadTimeout as rte:
        print(f"[RAG] Ollama read timeout: {rte}. Returning summaries as fallback.")
        return "Ollama generation timed out. Returning summaries:\n\n" + context_text
    except Exception as e:
        try:
            snippet = resp.text[:1000] if resp is not None else ""
            print(f"[RAG] Ollama request failed: {e} -- response snippet:\n{snippet}")
        except Exception:
            print(f"[RAG] Ollama request failed: {e}")
        raise


def answer_with_rag(question: str) -> str:
    """Backward-compatible wrapper used by the pipeline.

    Delegates to generate_newsletter and returns the generated text.
    """
    return generate_newsletter(question)


























# """RAG tool for SafariNewsletter.

# Utilise :
# - le vector store Chroma comme retriever,
# - Llama 3 via HuggingFaceEndpoint comme générateur.
# """

# from typing import List

# from langchain_community.vectorstores import Chroma
# from langchain_core.prompts import ChatPromptTemplate
# from langchain_core.runnables import RunnableParallel, RunnablePassthrough
# from langchain_core.output_parsers import StrOutputParser

# from src.configs.config import settings
# from src.tools.embedding import get_embeddings
# import requests
# import json


# # Ollama local settings for RAG generation (LLama 3)
# OLLAMA_API = "http://localhost:11434/api/chat"
# OLLAMA_MODEL = "llama3"


# def _call_ollama(prompt: str, model: str = OLLAMA_MODEL, timeout: int = 200) -> str:
#     payload = {
#         "model": model,
#         "messages": [
#             {"role": "system", "content": "You are an assistant specialized in writing structured newsletters from contextual summaries."},
#             {"role": "user", "content": prompt},
#         ],
#     }
#     try:
#         resp = requests.post(OLLAMA_API, json=payload, timeout=timeout)
#         resp.raise_for_status()
#         text = resp.text

#         # Try normal JSON parsing first
#         data = None
#         try:
#             data = resp.json()
#         except Exception:
#             # If direct JSON parsing fails, try to extract JSON substring
#             try:
#                 import re

#                 m = re.search(r"\{.*\}", text, flags=re.S)
#                 if m:
#                     data = json.loads(m.group(0))
#                 else:
#                     m = re.search(r"\[.*\]", text, flags=re.S)
#                     if m:
#                         data = json.loads(m.group(0))
#             except Exception:
#                 data = None

#         if isinstance(data, dict):
#             choices = data.get("choices") or []
#             if choices:
#                 message = choices[0].get("message") or {}
#                 if isinstance(message, dict):
#                     return message.get("content", "").strip()
#             return data.get("text", "").strip()

#         # Fallback: return raw text when Ollama responded with plain text
#         return text.strip()
#     except Exception as e:
#         try:
#             snippet = resp.text[:1000]
#             print(f"[RAG][OLLAMA] Error calling Ollama: {e} -- response snippet:\n{snippet}")
#         except Exception:
#             print(f"[RAG][OLLAMA] Error calling Ollama: {e}")
#         raise


# def _load_vectorstore() -> Chroma:
#     embeddings = get_embeddings()
#     vs = Chroma(
#         persist_directory=settings.VECTORSTORE_DIR,
#         embedding_function=embeddings,
#     )
#     return vs


# def _format_docs(docs) -> str:
#     parts: List[str] = []
#     for i, d in enumerate(docs):
#         meta = d.metadata or {}
#         title = meta.get("title", "")
#         url = meta.get("url", "")
#         parts.append(
#             f"[{i+1}] {title}\nURL: {url}\n\n{d.page_content}\n"
#         )
#     return "\n\n".join(parts)


# def answer_with_rag(question: str) -> str:
#     """RAG complet : question + contexte résumé -> réponse texte.

#     Utilise les résumés stockés dans le vector store (produits par le summarizer).
#     Le prompt demande une newsletter structurée avec 5 sections minimum,
#     sources cliquables et explications concises.
    
#     question: ex. "Génère une newsletter quotidienne résumant les actualités cyber..."
#     """
#     vectorstore = _load_vectorstore()
#     # Récupérer les k=5 résumés les plus pertinents (smaller context = clearer output)
#     retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

#     # Récupérer les documents pertinents
#     try:
#         docs = retriever.get_relevant_documents(question)
#     except Exception as e:
#         # Some retriever implementations may not behave uniformly across
#         # langchain versions. Fall back to a direct vectorstore similarity
#         # search (Chroma provides similarity_search) which is more stable.
#         print(f"[RAG] retriever.get_relevant_documents failed: {e}. Falling back to vectorstore.similarity_search")
#         try:
#             docs = vectorstore.similarity_search(question, k=5)
#         except Exception as e2:
#             print(f"[RAG] vectorstore.similarity_search also failed: {e2}")
#             docs = []

#     context_text = _format_docs(docs)

#     template = """TASK: Generate a professional, structured cybersecurity newsletter from the summaries below.

# RULES:
# 1. Use ONLY information from the provided summaries
# 2. Do NOT invent details not in the context
# 3. Format with clear section headers using ##
# 4. Each section: title, brief description, source URL
# 5. Write in plain English or French (match source language)
# 6. Keep descriptions to 2-3 sentences each
# 7. Include 3-5 main news items
# 8. Add an introduction (1 sentence) and conclusion (1 sentence)

# SUMMARIES TO PROCESS:
# {context}

# OUTPUT FORMAT EXAMPLE:
# ## Introduction
# Brief intro (1 sentence)

# ## Section 1: [Title]
# Description here.
# Source: [URL]

# ## Section 2: [Title]
# Description here.
# Source: [URL]

# ## Conclusion
# Brief summary (1 sentence)

# NOW GENERATE THE NEWSLETTER:
# """

#     prompt = template.format(question=question, context=context_text)

#     try:
#         # Appel local à Ollama pour la génération finale
#         result = _call_ollama(prompt)
#         # Clean up the response: strip extra whitespace, ensure section breaks
#         result = _clean_newsletter_output(result)
#         return result
#     except Exception as e:
#         print(f"[RAG] Ollama generation failed: {e}")
#         # En dernier recours, retourner le contexte brut pour inspection
#         return context_text


# def _clean_newsletter_output(text: str) -> str:
#     """Clean up Ollama response: remove junk, ensure structure, fix formatting."""
#     import re
    
#     # Remove common junk (extra model instructions, warnings, etc.)
#     text = re.sub(r"^(NOTE:|WARNING:|ASSISTANT:|HUMAN:|Here's the newsletter:).*?\n", "", text, flags=re.MULTILINE | re.IGNORECASE)
    
#     # Ensure double line breaks between sections (## headers)
#     text = re.sub(r"\n(##[^#])", r"\n\n\1", text)
    
#     # Remove excessive blank lines (more than 2 in a row)
#     text = re.sub(r"\n{3,}", "\n\n", text)
    
#     # Trim leading/trailing whitespace
#     text = text.strip()
    
#     return text
