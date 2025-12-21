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
    context_text = ""  #  évite NameError en fallback

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
    - format :  greetings with date, without saying "INTRODUCTION".
    

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

        #  Pour du Cloud, utilise idéalement un modèle *-cloud* (ex: gpt-oss:120b-cloud). :contentReference[oaicite:3]{index=3}
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





























