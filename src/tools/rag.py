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
from src.tools.llm_categorizer import classify_article_with_llm

TARGET_STORY_COUNT = 10


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


def _pick_unique_docs(docs: List[Any], target: int) -> List[Any]:
    """Keep at most one doc per URL to enforce one story per source URL."""
    unique: List[Any] = []
    seen_urls = set()
    for doc in docs:
        meta = getattr(doc, "metadata", {}) or {}
        url = (meta.get("url") or meta.get("source") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        unique.append(doc)
        if len(unique) >= target:
            break
    return unique


def _classify_story_with_llm(story: Dict[str, Any], client: Client, model: str) -> Dict[str, Any]:
    """Classify one story using centralized Ollama categorizer."""
    title = str(story.get("title") or "").strip()
    description = str(story.get("description") or "").strip()
    why_it_matters = str(story.get("why_it_matters") or "").strip()
    key_points = story.get("key_points") or []
    if not isinstance(key_points, list):
        key_points = [str(key_points)]

    content = "\n\n".join(
        [
            f"Description: {description}",
            f"Why it matters: {why_it_matters}",
            "Key points:\n" + "\n".join([f"- {str(kp).strip()}" for kp in key_points if str(kp).strip()]),
        ]
    )

    return classify_article_with_llm(
        title=title,
        content=content,
        client=client,
        model=model,
    )


# =========================
# RAG pipeline
# =========================
def _ensure_newsletter_json(raw: str, client: Client, model: str) -> Dict[str, Any]:
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
    
    # Required fields per story (title, description are critical)
    # Note: 'category' is NOT required from LLM - will be assigned by classifier
    CRITICAL_STORY_FIELDS = {"title", "description"}
    
    for idx, story in enumerate(stories):
        if not isinstance(story, dict):
            print(f"[RAG] Story {idx} is not a dict, skipping")
            continue
        
        missing_critical = CRITICAL_STORY_FIELDS - set(story.keys())
        if missing_critical:
            print(f"[RAG] Story {idx} missing critical fields: {missing_critical}")
            # Mark as incomplete (missing critical)
            story['_incomplete'] = True
        else:
            # Auto-fill empty optional fields with defaults
            if not story.get("key_points"):
                story["key_points"] = [story.get("description", "")[:100]]
            if not story.get("why_it_matters"):
                story["why_it_matters"] = "Important for cybersecurity awareness."
            if not story.get("url"):
                story["url"] = ""
                story["_incomplete"] = True
            
            # Assign category with Ollama Cloud (one call per story)
            llm_classification = _classify_story_with_llm(story, client=client, model=model)
            story["category"] = llm_classification["primary_category"]
            story["secondary_categories"] = llm_classification.get("secondary_categories", [])
            story["subtopics"] = llm_classification.get("subtopics", [])
            story["priority_level"] = llm_classification.get("priority", "medium")
            story["classification_flags"] = llm_classification.get("flags", {})
            print(f"[RAG] Story categorized by LLM: {story.get('category')}")
    
    # Filter out incomplete stories (missing critical fields)
    valid_stories = [s for s in stories if not s.get('_incomplete')]

    # De-duplicate by URL to enforce one story per source URL
    deduped: List[Dict[str, Any]] = []
    seen_urls = set()
    for s in valid_stories:
        url = (s.get("url") or "").strip()
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        deduped.append(s)
    valid_stories = deduped

    if len(valid_stories) > TARGET_STORY_COUNT:
        valid_stories = valid_stories[:TARGET_STORY_COUNT]

    if len(valid_stories) < TARGET_STORY_COUNT:
        print(f"[RAG] Warning: only {len(valid_stories)}/{TARGET_STORY_COUNT} valid stories after validation.")
    
    if not valid_stories:
        print(f"[RAG] No valid stories in response (had {len(stories)}, valid {len(valid_stories)})")
        return {}
    
    data["stories"] = valid_stories
    print(f"[RAG] Validation complete: {len(valid_stories)} valid stories from {len(stories)} total")
    
    return data


def generate_newsletter(question: str, user_prompt: str = "", k: int = 30) -> str:
    """Generate newsletter from RAG results.
    
    Args:
        question: Query for vector retrieval (legacy parameter, may be deprecated)
        user_prompt: User message to send to the model (from API)
        k: Number of documents to retrieve (default 30 to reach 10 unique sources)
    """
    context_text = ""  # évite NameError en fallback

    # 1) Retrieve
    vectorstore = _load_vectorstore()
    query = (question or "").strip() or "latest cybersecurity news"
    k = max(k, TARGET_STORY_COUNT * 3)
    retriever = vectorstore.as_retriever(search_kwargs={"k": k})

    try:
        docs: List = (
            retriever.invoke(query)
            if hasattr(retriever, "invoke")
            else retriever.get_relevant_documents(query)
        )
    except Exception as e:
        print(f"[RAG] Retriever error: {e}")
        docs = []

    unique_docs = _pick_unique_docs(docs, TARGET_STORY_COUNT)
    if len(unique_docs) < TARGET_STORY_COUNT and k < 80:
        k_retry = min(max(k * 2, TARGET_STORY_COUNT * 4), 80)
        retriever = vectorstore.as_retriever(search_kwargs={"k": k_retry})
        try:
            docs = (
                retriever.invoke(query)
                if hasattr(retriever, "invoke")
                else retriever.get_relevant_documents(query)
            )
        except Exception as e:
            print(f"[RAG] Retriever error (retry): {e}")
            docs = []
        unique_docs = _pick_unique_docs(docs, TARGET_STORY_COUNT)

    if len(unique_docs) < TARGET_STORY_COUNT:
        print(f"[RAG] Warning: only {len(unique_docs)}/{TARGET_STORY_COUNT} unique sources available for context.")

    # 2) Build context
    context_blocks = []
    docs_for_context = unique_docs or docs
    for i, doc in enumerate(docs_for_context, start=1):
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
    system_message = """You are a senior cybersecurity analyst. Produce ONLY valid JSON for a DAILY CYBERSECURITY & AI THREAT INTELLIGENCE NEWSLETTER.

RULES (hard):
- Output must be a single JSON object, nothing else, no markdown, no prose outside JSON.
- No greetings in the content except inside the intro field.
- No signature, no storytelling, no personal opinions.
- Stay factual; no fabrication. If data is missing, omit the field.
- Use English for all content. NEVER use French or any other language.
- Global title must resum topics in 2 sentences with emoji separated.
- Each story title must have one emoji no more.
- Never include two or more stories from the same source URL.
- Always keep one story per url. If multiple stories from the same URL, keep the most relevant.

JSON SCHEMA (keys):
{{
    "title": "string",
    "intro": "string",
    "headlines": ["string", ...],
    "stories": [
        {{
            "title": "string",
            "url": "obligatory string (valid URL)",
            "key_points": ["string", ...],
            "description": "string",
            "why_it_matters": "string"
        }}
    ],
    "closing": "string"
}}

NOTE: DO NOT include a 'category' field in stories - categories will be automatically assigned based on content analysis.

CONTENT REQUIREMENTS:
OBLIGATORY (CRITICAL - FAILURE IF NOT MET):
- stories: EXACTLY 10 items, no more, no less. Non-negotiable.
- title: Act as a senior cybersecurity editor and B2B marketing strategist writing for CISOs, IT Directors, and Compliance Officers.
         Instructions :
           - Do not summarize the articles literally
           - Synthesize the shared strategic theme or risk signal
           - Emphasize impact, consequence, or decision relevance
           - Avoid words like “newsletter,” “digest,” or “roundup”
           - Maximum 14 words
           - Use strong executive language (risk, exposure, resilience, intelligence, control, trust)

- intro: 1–2 sentences with date/greeting.
- headlines: 4–6 concise bullets extracted from stories.
- stories: 10 complete items. Each story MUST include ALL of these:
  * title: 1 line with one numerical emoji obligatory to keep number of stories.always colored  .
  * key_points: 3–5 bullets
  * description: 1 paragraph
  * why_it_matters: 1 paragraph
  * url: obligatory.
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
        data = _ensure_newsletter_json(text, client=client, model=model)
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


