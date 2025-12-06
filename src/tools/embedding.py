"""Embedding & vector store tools for SafariNewsletter."""

import os
import shutil
from typing import Any, Dict, List

from langchain_community.vectorstores import Chroma
from langchain_community.docstore.document import Document

from src.configs.config import settings
from src.database.mongo import MongoDB
from src.tools.rag_llm import get_embeddings  # on va créer ce helper dans rag_llm.py


def upsert_embeddings(clean_articles: List[Dict[str, Any]]) -> None:
    """Remplace les anciens articles par les nouveaux, et reconstruit le vector store.

    Étapes :
    1. Effacer la collection Mongo d'articles.
    2. Insérer les articles nettoyés du jour.
    3. Supprimer le vector store Chroma existant.
    4. Créer un nouveau vector store à partir des articles en DB.
    """
    db = MongoDB()

    # 1. Drop collection "articles" (pour ne garder que le jour courant)
    print("[EMBEDDING] Purge de la collection Mongo 'articles'")
    db.drop_collection(settings.ARTICLES_COLLECTION)

    # 2. Insérer les nouveaux articles
    print(f"[EMBEDDING] Insertion de {len(clean_articles)} nouveaux articles")
    db.insert_many(settings.ARTICLES_COLLECTION, clean_articles)

    # 3. Supprimer l'ancien vector store
    print(f"[EMBEDDING] Suppression du vector store existant : {settings.VECTORSTORE_DIR}")
    shutil.rmtree(settings.VECTORSTORE_DIR, ignore_errors=True)
    os.makedirs(settings.VECTORSTORE_DIR, exist_ok=True)

    # 4. Re-créer le vector store depuis Mongo
    docs: List[Dict[str, Any]] = db.find(settings.ARTICLES_COLLECTION)

    lc_docs: List[Document] = []
    for d in docs:
        content = d.get("content", "")
        if not content:
            continue
        metadata = {
            "title": d.get("title", ""),
            "url": d.get("url", ""),
            "published": d.get("published"),
        }
        lc_docs.append(Document(page_content=content, metadata=metadata))

    if not lc_docs:
        print("[EMBEDDING] Aucun document à indexer, vector store vide.")
        return

    embeddings = get_embeddings()

    Chroma.from_documents(
        documents=lc_docs,
        embedding=embeddings,
        persist_directory=settings.VECTORSTORE_DIR,
    )

    print(f"[EMBEDDING] Vector store reconstruit avec {len(lc_docs)} documents.")
