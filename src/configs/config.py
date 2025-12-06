


"""Global configuration for SafariNewsletter."""

import os
from dataclasses import dataclass


@dataclass
class Settings:
    # MongoDB
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME: str = os.getenv("MONGO_DB_NAME", "safarinewsletter")
    ARTICLES_COLLECTION: str = os.getenv("ARTICLES_COLLECTION", "articles")

    # Hugging Face / LLM distant (API)
    # Le modèle s'exécute sur les serveurs HuggingFace, pas localement
    HF_API_TOKEN: str = os.getenv("HF_API_TOKEN", "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")
    # Modèles disponibles sur HuggingFace Inference API
    # Format: "model_id" ou "model_id:provider" (le provider sera ignoré)
    # Recommandé: deepseek-ai/DeepSeek-V3.2, Qwen/Qwen2.5-7B-Instruct
    # Alternatives: deepseek-ai/DeepSeek-V2-Chat, Qwen/Qwen2.5-1.5B-Instruct
    HF_LLM_REPO_ID: str = os.getenv(
        "HF_LLM_REPO_ID",
        "deepseek-ai/DeepSeek-V3.2",  # Modèle DeepSeek via API distante
    )
  

    # Modèle d'embeddings local (sentence-transformers)
    EMBEDDING_MODEL_NAME: str = os.getenv(
        "EMBEDDING_MODEL_NAME",
        "sentence-transformers/all-MiniLM-L6-v2",
    )

    # Répertoire de persistance du vector store (Chroma)
    VECTORSTORE_DIR: str = os.getenv("VECTORSTORE_DIR", "data/chroma_store")


settings = Settings()
