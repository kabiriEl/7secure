


"""Global configuration for SafariNewsletter."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv
load_dotenv()

@dataclass
class Settings:
    # MongoDB
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME: str = os.getenv("MONGO_DB_NAME", "safarinewsletter")
    ARTICLES_COLLECTION: str = os.getenv("ARTICLES_COLLECTION", "articles")

    # Hugging Face / LLM distant (API)
    # Le modèle s'exécute sur les serveurs HuggingFace, pas localement
    HF_API_TOKEN: str = os.getenv("HF_API_TOKEN", "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")
    
  

    # Modèle d'embeddings local (sentence-transformers)
    EMBEDDING_MODEL_NAME: str = os.getenv(
        "EMBEDDING_MODEL_NAME",
        "sentence-transformers/all-MiniLM-L6-v2",
    )

    # Répertoire de persistance du vector store (Chroma)
    VECTORSTORE_DIR: str = os.getenv("VECTORSTORE_DIR", "data/chroma_store")

  
    
   
    OLLAMA_API_KEY: str = os.getenv("OLLAMA_API_KEY")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL")



settings = Settings()
