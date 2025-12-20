"""Embedding & vector store tools for SafariNewsletter.

Implements:
- Chunking (splitting long documents into smaller chunks for better retrieval)
- Rich metadata attached to each chunk (source url, title, published date, doc_id, chunk_id, positions)
- Same MongoDB flow + fallback in-memory
- Safe Chroma rebuild with full cleanup + retries
"""

import os
import shutil
import time
import hashlib
from typing import Any, Dict, List, Optional, Tuple

from langchain_community.vectorstores import Chroma
from langchain_community.docstore.document import Document
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.configs.config import settings
from src.database.mongo import MongoDB


# -----------------------------
# Embeddings
# -----------------------------
def get_embeddings() -> HuggingFaceEmbeddings:
    """Embedding model used for the vector store."""
    return HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL_NAME)


# -----------------------------
# Chroma maintenance
# -----------------------------
def _clean_chroma_store() -> None:
    """Fully wipe Chroma directory to avoid corrupted state."""
    vectorstore_dir = settings.VECTORSTORE_DIR
    if os.path.exists(vectorstore_dir):
        try:
            shutil.rmtree(vectorstore_dir, ignore_errors=True)
            time.sleep(0.5)
            print(f"[EMBEDDING] Dossier Chroma nettoyé: {vectorstore_dir}")
        except Exception as e:
            print(f"[EMBEDDING] Attention lors du nettoyage: {e}")

    os.makedirs(vectorstore_dir, exist_ok=True)


# -----------------------------
# Chunking + metadata helpers
# -----------------------------
def _stable_id_from_text(text: str) -> str:
    """Create a stable id (hash) from text content."""
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _extract_fields(d: Any) -> Tuple[str, str, str, Optional[Any]]:
    """Extract (content, title, url, published) from either Mongo dict or input dict."""
    if isinstance(d, dict):
        content = d.get("content") or d.get("page_content") or d.get("text") or ""
        title = d.get("title", "") or ""
        url = d.get("url", "") or ""
        published = d.get("published")
        return content, title, url, published

    # Unexpected type
    return str(d), "", "", None


def _make_text_splitter() -> RecursiveCharacterTextSplitter:
    """Build a splitter using config values if present, else sensible defaults."""
    # Optional config values (won't crash if missing)
    chunk_size = getattr(settings, "CHUNK_SIZE", 900)
    chunk_overlap = getattr(settings, "CHUNK_OVERLAP", 150)

    # For news/articles, separators that preserve meaning reasonably well
    separators = ["\n\n", "\n", ". ", " ", ""]
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=separators,
        length_function=len,
        is_separator_regex=False,
    )


def _chunk_one_document(
    content: str,
    base_metadata: Dict[str, Any],
    doc_id: str,
) -> Tuple[List[Document], List[str]]:
    """Split one document into chunks and return (chunk_docs, chunk_ids)."""
    splitter = _make_text_splitter()
    chunks = splitter.split_text(content)

    chunk_docs: List[Document] = []
    chunk_ids: List[str] = []

    for idx, chunk_text in enumerate(chunks):
        if not chunk_text.strip():
            continue

        # Metadata per chunk (very important in RAG!)
        chunk_metadata = dict(base_metadata)
        chunk_metadata.update(
            {
                "doc_id": doc_id,              # stable id for the original article
                "chunk_id": idx,               # index inside the article
                "chunk_count": len(chunks),    # total chunks for the article
            }
        )

        # Create a stable unique id per chunk for Chroma
        # (doc_id + chunk_id is enough here since we rebuild store, but still stable)
        chroma_id = f"{doc_id}::chunk::{idx}"
        chunk_ids.append(chroma_id)

        chunk_docs.append(Document(page_content=chunk_text, metadata=chunk_metadata))

    return chunk_docs, chunk_ids


def _build_chunked_documents(docs: List[Any]) -> Tuple[List[Document], List[str]]:
    """Convert docs to LangChain Documents, then chunk them with metadata."""
    all_chunk_docs: List[Document] = []
    all_chunk_ids: List[str] = []

    for d in docs:
        content, title, url, published = _extract_fields(d)
        if not content or not content.strip():
            continue

        # Stable doc_id: prefer URL (if present), else hash of content
        doc_id = _stable_id_from_text(url) if url else _stable_id_from_text(content[:5000])

        base_metadata = {
            "title": title,
            "url": url,
            "published": published,
            # Helpful for debugging / filtering later
            "source": "mongo" if isinstance(d, dict) and "_id" in d else "memory",
        }

        chunk_docs, chunk_ids = _chunk_one_document(content, base_metadata, doc_id)
        all_chunk_docs.extend(chunk_docs)
        all_chunk_ids.extend(chunk_ids)

    return all_chunk_docs, all_chunk_ids


# -----------------------------
# Main upsert/rebuild
# -----------------------------
def upsert_embeddings(clean_articles: List[Dict[str, Any]]) -> None:
    """Replace old articles and rebuild the vector store with chunking + metadata.

    Pipeline:
    1) Drop + insert new articles in Mongo
    2) Read them back
    3) Build chunked Documents (each chunk carries metadata)
    4) Wipe Chroma and rebuild from scratch (retry on corruption)
    """
    db = MongoDB()

    # 1-3. Mongo operations with fallback
    try:
        print("[EMBEDDING] Purge de la collection Mongo 'articles'")
        db.drop_collection(settings.ARTICLES_COLLECTION)

        print(f"[EMBEDDING] Insertion de {len(clean_articles)} nouveaux articles")
        db.insert_many(settings.ARTICLES_COLLECTION, clean_articles)

        print("[EMBEDDING] Lecture des articles depuis Mongo")
        docs: List[Dict[str, Any]] = db.find(settings.ARTICLES_COLLECTION)
    except Exception as e:
        print(f"[EMBEDDING] ⚠️ MongoDB indisponible ou erreur: {e}. Utilisation du fallback en mémoire.")
        docs = clean_articles

    # Build chunked docs + ids
    chunked_docs, chunk_ids = _build_chunked_documents(docs)

    if not chunked_docs:
        print("[EMBEDDING] Aucun chunk à indexer, vector store vide.")
        _clean_chroma_store()
        return

    embeddings = get_embeddings()

    # Clean before create
    print("[EMBEDDING] Nettoyage préventif du vector store")
    _clean_chroma_store()

    max_retries = 3
    last_error: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        try:
            print(f"[EMBEDDING] Tentative {attempt}/{max_retries} de création du vector store (chunks)...")

            # Build and persist
            Chroma.from_documents(
                documents=chunked_docs,
                embedding=embeddings,
                persist_directory=settings.VECTORSTORE_DIR,
                ids=chunk_ids,  # stable per-chunk ids
            )

            print(
                f"[EMBEDDING] ✅ Vector store créé avec succès: "
                f"{len(chunked_docs)} chunks indexés (depuis {len(docs)} articles)."
            )
            return

        except Exception as e:
            last_error = e
            error_msg = str(e)
            print(f"[EMBEDDING] ❌ Tentative {attempt}/{max_retries} échouée")
            print(f"[EMBEDDING] Erreur: {error_msg[:180]}")

            if attempt < max_retries:
                print("[EMBEDDING] Nettoyage complet avant nouvelle tentative...")
                _clean_chroma_store()
                time.sleep(1)
            else:
                print(f"[EMBEDDING] ⚠️ Échec après {max_retries} tentatives")

    if last_error:
        print(f"[EMBEDDING] ERREUR CRITIQUE: {last_error}")
        raise RuntimeError(
            f"Impossible de créer le vector store après {max_retries} tentatives. "
            f"Erreur: {str(last_error)[:300]}"
        )
