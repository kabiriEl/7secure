"""Embedding & vector store tools for SafariNewsletter."""

import os
import shutil
import time
from typing import Any, Dict, List

from langchain_community.vectorstores import Chroma
from langchain_community.docstore.document import Document
from langchain_community.embeddings import HuggingFaceEmbeddings

from src.configs.config import settings
from src.database.mongo import MongoDB


def get_embeddings():
    """Embedding model utilisé pour le vector store (local, léger)."""
    return HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL_NAME)


def _clean_chroma_store():
    """Nettoie complètement le dossier Chroma pour éviter les corruptions."""
    vectorstore_dir = settings.VECTORSTORE_DIR
    if os.path.exists(vectorstore_dir):
        try:
            shutil.rmtree(vectorstore_dir, ignore_errors=True)
            time.sleep(0.5)  # Attendre que le système libère les ressources
            print(f"[EMBEDDING] Dossier Chroma nettoyé: {vectorstore_dir}")
        except Exception as e:
            print(f"[EMBEDDING] Attention lors du nettoyage: {e}")
    
    # Recréer le dossier vide
    os.makedirs(vectorstore_dir, exist_ok=True)


def upsert_embeddings(clean_articles: List[Dict[str, Any]]) -> None:
    """Remplace les anciens articles par les nouveaux, et reconstruit le vector store.

    Étapes :
    1. Effacer la collection Mongo d'articles.
    2. Insérer les articles nettoyés du jour.
    3. Supprimer le vector store Chroma existant (y compris fichiers de BD corrompus).
    4. Créer un nouveau vector store à partir des articles en DB.
    
    Gère automatiquement les corruptions Chroma avec retry automatique.
    """
    db = MongoDB()

    # 1. Drop collection "articles" (pour ne garder que le jour courant)
    print("[EMBEDDING] Purge de la collection Mongo 'articles'")
    db.drop_collection(settings.ARTICLES_COLLECTION)

    # 2. Insérer les nouveaux articles
    print(f"[EMBEDDING] Insertion de {len(clean_articles)} nouveaux articles")
    db.insert_many(settings.ARTICLES_COLLECTION, clean_articles)

    # 3. Récupérer les articles depuis Mongo
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
        # Même sans documents, nettoyer Chroma
        _clean_chroma_store()
        return

    embeddings = get_embeddings()

    # Nettoyage préventif avant la création
    print("[EMBEDDING] Nettoyage préventif du vector store")
    _clean_chroma_store()

    # Tentative de création avec retry automatique en cas de corruption
    max_retries = 3
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[EMBEDDING] Tentative {attempt}/{max_retries} de création du vector store...")
            Chroma.from_documents(
                documents=lc_docs,
                embedding=embeddings,
                persist_directory=settings.VECTORSTORE_DIR,
            )
            print(f"[EMBEDDING] ✅ Vector store créé avec succès avec {len(lc_docs)} documents.")
            return
            
        except Exception as e:
            last_error = e
            error_msg = str(e)
            print(f"[EMBEDDING] ❌ Tentative {attempt}/{max_retries} échouée")
            print(f"[EMBEDDING] Erreur: {error_msg[:150]}")
            
            if attempt < max_retries:
                # Nettoyage complet et attendre avant de réessayer
                print(f"[EMBEDDING] Nettoyage complet avant nouvelle tentative...")
                _clean_chroma_store()
                time.sleep(1)  # Attendre 1 seconde avant de réessayer
            else:
                print(f"[EMBEDDING] ⚠️ Échec après {max_retries} tentatives")
    
    # Si tous les retries ont échoué, afficher l'erreur
    if last_error:
        print(f"[EMBEDDING] ERREUR CRITIQUE: {last_error}")
        raise RuntimeError(
            f"Impossible de créer le vector store après {max_retries} tentatives. "
            f"Erreur: {str(last_error)[:200]}"
        )
