"""
RAG + Newsletter generator using Ollama CLOUD only (official Python client).

- Charge Chroma
- Récupère top-k chunks
- Génère une newsletter via Ollama Cloud (Client host="https://ollama.com")
"""

import json
from typing import List, Dict, Any
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
def _ensure_newsletter_json(raw: str) -> Dict[str, Any]:
    """Parse JSON and validate complete structure.
    
    Ensures every story has ALL required fields:
    - title, url, category, key_points, description, why_it_matters
    """
    try:
        data = json.loads(raw)
    except Exception as e:
        print(f"[RAG] JSON parse error: {e}")
        return {}
    
    if not isinstance(data, dict):
        print(f"[RAG] Response is not a dict: {type(data)}")
        return {}
    
    # Validate and fix stories array
    stories = data.get("stories", [])
    if not isinstance(stories, list):
        print(f"[RAG] 'stories' is not a list: {type(stories)}")
        return {}
    
    # Required fields per story
    REQUIRED_STORY_FIELDS = {"title", "url", "category", "key_points", "description", "why_it_matters"}
    
    for idx, story in enumerate(stories):
        if not isinstance(story, dict):
            print(f"[RAG] Story {idx} is not a dict, skipping")
            continue
        
        missing_fields = REQUIRED_STORY_FIELDS - set(story.keys())
        if missing_fields:
            print(f"[RAG] Story {idx} missing fields: {missing_fields}")
            # Mark as incomplete
            story['_incomplete'] = True
    
    # Filter out incomplete stories
    valid_stories = [s for s in stories if not s.get('_incomplete')]
    
    if not valid_stories:
        print(f"[RAG] No valid stories in response (had {len(stories)}, valid {len(valid_stories)})")
        return {}
    
    data["stories"] = valid_stories
    print(f"[RAG] Validation complete: {len(valid_stories)} valid stories from {len(stories)} total")
    
    return data


def generate_newsletter(question: str, user_prompt: str = "", k: int = 5) -> str:
    """Generate newsletter from RAG results.
    
    Args:
        question: Query for vector retrieval (legacy parameter, may be deprecated)
        user_prompt: User message to send to the model (from API)
        k: Number of documents to retrieve
    """
    context_text = ""  # évite NameError en fallback

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

    context_text = "\n\n".join(context_blocks) if context_blocks else "(No content retrieved.)"

    # 3) System message (schema + rules)
    system_message = f"""You are a senior cybersecurity analyst. Produce ONLY valid JSON for a DAILY CYBERSECURITY & AI THREAT INTELLIGENCE NEWSLETTER.

RULES (hard):
- Output must be a single JSON object, nothing else, no markdown, no prose outside JSON.
- No greetings in the content except inside the intro field.
- No signature, no storytelling, no personal opinions.
- Stay factual; no fabrication. If data is missing, omit the field.
- Use English for all content. NEVER use French or any other language.

JSON SCHEMA (keys):
{{
    "title": "string",
    "intro": "string",
    "headlines": ["string", ...],
    "stories": [
        {{
            "title": "string",
            "url": "string optional",
            "category": "string (MUST be one of: AI Security & Threats, Threat Intelligence, Malware & Ransomware, Vulnerabilities & Exploits, Cloud & SaaS Security, IAM, SOC & Automation, Data Protection & Privacy, Human Factors, Compliance & Regulation, Data Breaches)",
            "key_points": ["string", ...],
            "description": "string",
            "why_it_matters": "string"
        }}
    ],
    "closing": "string"
}}

CONTENT REQUIREMENTS:
- OBLIGATORY 6 stories minimum .
- title: 1–2 factual lines combining 2–3 major topics, can use emojis.
- intro: 1–2 sentences with date/greeting.
- headlines: 4–6 concise bullets.
- stories: 6-7 items. Each story MUST include:
  * category: EXACTLY one of these categories: AI Security & Threats, Threat Intelligence, Malware & Ransomware, Vulnerabilities & Exploits, Cloud & SaaS Security, IAM, SOC & Automation, Data Protection & Privacy, Human Factors, Compliance & Regulation, Data Breaches
  * key_points: 3–5 bullets
  * description: 1 paragraph
  * why_it_matters: 1 paragraph
  * url: optional
- closing: short closing line.

Return ONLY the JSON object per schema, no trailing text."""

    # 4) User message (question + context)
    final_user_prompt = f"""{user_prompt}

PROVIDED CONTEXT:
{context_text}

Return ONLY the JSON object, no trailing text."""

    # 5) Ollama Cloud call
    try:
        client = _ollama_client()
        model = settings.OLLAMA_MODEL

        resp = client.chat(
            model=model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": final_user_prompt},
            ],
            stream=False,
        )

        text = (resp.get("message", {}) or {}).get("content", "")
        text = (text or "").strip()

        if not text:
            print("[RAG] Empty response from model, fallback.")
            return f"Newsletter Summary\n\n{context_text}"

        print(f"[RAG] Model response received ({len(text)} chars), parsing JSON...")
        data = _ensure_newsletter_json(text)
        if not data:
            print(f"[RAG] Invalid JSON response, returning raw text. First 200 chars: {text[:200]}")
            return text

        stories = data.get('stories', [])
        print(f"[RAG] ✓ JSON VALIDATED - {len(stories)} complete articles with all required fields")
        return json.dumps(data, ensure_ascii=False)

    except Exception as e:
        print(f"[RAG] Ollama Cloud error: {e}")
        return f"Newsletter Summary\n\n{context_text}"


def answer_with_rag(question: str, user_prompt: str = "") -> str:
    """Generate newsletter answer.
    
    Args:
        question: Vector store query (legacy)
        user_prompt: User message from API
    """
    return generate_newsletter(question, user_prompt=user_prompt)





























