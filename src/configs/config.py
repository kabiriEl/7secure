


"""Global configuration for SafariNewsletter."""

import os
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field

from dotenv import load_dotenv
load_dotenv()


class Settings(BaseSettings):
    """Configuration settings for SafariNewsletter."""
    
    # Hugging Face / LLM distant (API)
    hf_api_token: str = Field(
        default_factory=lambda: os.getenv(
            "HF_API_TOKEN", "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"
        )
    )
    
    # Modèle d'embeddings local (sentence-transformers)
    embedding_model_name: str = Field(
        default_factory=lambda: os.getenv(
            "EMBEDDING_MODEL_NAME",
            "sentence-transformers/all-MiniLM-L6-v2",
        )
    )

    # Répertoire de persistance du vector store (Chroma)
    vectorstore_dir: str = Field(
        default_factory=lambda: os.getenv("VECTORSTORE_DIR", "data/chroma_store")
    )

    # Ollama Cloud configuration
    ollama_api_key: str = Field(
        default_factory=lambda: os.getenv("OLLAMA_API_KEY", "")
    )
    ollama_base_url: str = Field(
        default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "")
    )
    ollama_model: str = Field(
        default_factory=lambda: os.getenv("OLLAMA_MODEL", "")
    )
    ollama_html_model: str = Field(
        default_factory=lambda: os.getenv("OLLAMA_HTML_MODEL", "gpt-oss:120b-cloud")
    )
    use_ollama_html: str = Field(
        default_factory=lambda: os.getenv("USE_OLLAMA_HTML", "0")
    )

    # Ghost CMS configuration
    ghost_admin_api_url: str = Field(
        default_factory=lambda: os.getenv("GHOST_ADMIN_API_URL", "")
    )
    ghost_admin_api_key: str = Field(
        default_factory=lambda: os.getenv("GHOST_ADMIN_API_KEY", "")
    )
    ghost_url: str = Field(
        default_factory=lambda: os.getenv("GHOST_URL", "")
    )
    ghost_newsletter_slug: str = Field(
        default_factory=lambda: os.getenv("GHOST_NEWSLETTER_SLUG", "cybersecurity-daily")
    )
    ghost_post_tags: str = Field(
        default_factory=lambda: os.getenv("GHOST_POST_TAGS", "VeilleCyber,Newsletter")
    )
    ghost_max_image_mb: str = Field(
        default_factory=lambda: os.getenv("GHOST_MAX_IMAGE_MB", "4")
    )
    ghost_image_upload_timeout: str = Field(
        default_factory=lambda: os.getenv("GHOST_IMAGE_UPLOAD_TIMEOUT", "20")
    )

    # Ghost email summary mode (Public Preview card)
    ghost_email_summary_mode: str = Field(
        default_factory=lambda: os.getenv("GHOST_EMAIL_SUMMARY_MODE", "false")
    )
    ghost_public_preview_enabled: str = Field(
        default_factory=lambda: os.getenv("GHOST_PUBLIC_PREVIEW_ENABLED", "true")
    )

    # Database configuration (MongoDB - legacy)
    mongo_uri: str = Field(
        default_factory=lambda: os.getenv("MONGO_URI", "mongodb://localhost:27017")
    )
    mongo_db_name: str = Field(
        default_factory=lambda: os.getenv("MONGO_DB_NAME", "safarinewsletter")
    )
    articles_collection: str = Field(
        default_factory=lambda: os.getenv("ARTICLES_COLLECTION", "articles")
    )

    # General settings
    env: str = Field(default="dev")
    environment: str = Field(
        default_factory=lambda: os.getenv("ENVIRONMENT", "development")
    )
    newsletter_title: str = Field(
        default_factory=lambda: os.getenv("NEWSLETTER_TITLE", "Veille Cyber")
    )
    cors_origins: List[str] = Field(default_factory=list)

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env


class SettingsProxy(Settings):
    """Proxy to provide backwards compatibility for uppercase attribute access."""
    
    def __getattr__(self, name: str):
        # Try lowercase version first (Pydantic v2)
        try:
            return super().__getattribute__(name.lower())
        except AttributeError:
            pass
        
        # Map common uppercase names to lowercase
        uppercase_to_lowercase = {
            'HF_API_TOKEN': 'hf_api_token',
            'EMBEDDING_MODEL_NAME': 'embedding_model_name',
            'VECTORSTORE_DIR': 'vectorstore_dir',
            'OLLAMA_API_KEY': 'ollama_api_key',
            'OLLAMA_BASE_URL': 'ollama_base_url',
            'OLLAMA_MODEL': 'ollama_model',
            'OLLAMA_HTML_MODEL': 'ollama_html_model',
            'USE_OLLAMA_HTML': 'use_ollama_html',
            'GHOST_ADMIN_API_URL': 'ghost_admin_api_url',
            'GHOST_ADMIN_API_KEY': 'ghost_admin_api_key',
            'GHOST_URL': 'ghost_url',
            'GHOST_NEWSLETTER_SLUG': 'ghost_newsletter_slug',
            'GHOST_POST_TAGS': 'ghost_post_tags',
            'GHOST_MAX_IMAGE_MB': 'ghost_max_image_mb',
            'GHOST_IMAGE_UPLOAD_TIMEOUT': 'ghost_image_upload_timeout',
            'GHOST_EMAIL_SUMMARY_MODE': 'ghost_email_summary_mode',
            'GHOST_PUBLIC_PREVIEW_ENABLED': 'ghost_public_preview_enabled',
            'MONGO_URI': 'mongo_uri',
            'MONGO_DB_NAME': 'mongo_db_name',
            'ARTICLES_COLLECTION': 'articles_collection',
            'ENV': 'env',
            'ENVIRONMENT': 'environment',
            'NEWSLETTER_TITLE': 'newsletter_title',
            'CORS_ORIGINS': 'cors_origins',
        }
        
        if name in uppercase_to_lowercase:
            return super().__getattribute__(uppercase_to_lowercase[name])
        
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


# Create singleton instance with proxy for backwards compatibility
_base_settings = Settings()
settings = SettingsProxy(**_base_settings.model_dump())
