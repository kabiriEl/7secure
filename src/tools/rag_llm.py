"""LLM (DeepSeek V3.2 via HuggingFace Inference API) + Embeddings."""

from typing import Any

from huggingface_hub import InferenceClient
from langchain_core.runnables import RunnableLambda
from langchain_core.prompt_values import ChatPromptValue
from langchain_community.embeddings import HuggingFaceEmbeddings

from src.configs.config import settings


def get_llm():
    """Retourne un LLM compatible LangChain, utilisant DeepSeek-V3.2 en API distante."""

    if not settings.HF_API_TOKEN:
        raise ValueError(
            "HF_API_TOKEN n'est pas défini dans les variables d'environnement ou config.py."
        )

    client = InferenceClient(api_key=settings.HF_API_TOKEN)
    model_id = settings.HF_LLM_REPO_ID  # ex : "deepseek-ai/DeepSeek-V3.2"

    def deepseek_chat(input_: Any) -> str:
        """Adaptateur entre LangChain et l'API chat HF.

        - LangChain peut passer une str ou un ChatPromptValue
        - On convertit toujours en string avant d'appeler l'API.
        """
        # 1) Récupérer le texte du prompt
        if isinstance(input_, ChatPromptValue):
            prompt_text = input_.to_string()
        else:
            # Cas simple : déjà une string
            prompt_text = str(input_)

        # 2) Appel à l'API Hugging Face (doc officielle)
        try:
            completion = client.chat.completions.create(
                model=model_id,
                messages=[
                    {
                        "role": "user",
                        "content": prompt_text,
                    }
                ],
                max_tokens=512,
                temperature=0.1,
                top_p=0.9,
            )
        except Exception as e:
            print(f"[LLM] Erreur lors de l'appel API: {e}")
            raise

        # 3) Renvoyer le texte généré
        message = completion.choices[0].message
        # suivant la version de la lib, message peut être un dict ou un objet
        if isinstance(message, dict):
            return message.get("content", "")
        return getattr(message, "content", "")

    return RunnableLambda(deepseek_chat)


def get_embeddings():
    """Embedding model utilisé pour le vector store (local, léger)."""
    return HuggingFaceEmbeddings(model_name=settings.EMBEDDING_MODEL_NAME)



















