"""RAG tool for SafariNewsletter.

Utilise :
- le vector store Chroma comme retriever,
- Llama 3 via HuggingFaceEndpoint comme générateur.
"""

from typing import List

from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from src.configs.config import settings
from src.tools.rag_llm import get_llm, get_embeddings


def _load_vectorstore() -> Chroma:
    embeddings = get_embeddings()
    vs = Chroma(
        persist_directory=settings.VECTORSTORE_DIR,
        embedding_function=embeddings,
    )
    return vs


def _format_docs(docs) -> str:
    parts: List[str] = []
    for i, d in enumerate(docs):
        meta = d.metadata or {}
        title = meta.get("title", "")
        url = meta.get("url", "")
        parts.append(
            f"[{i+1}] {title}\nURL: {url}\n\n{d.page_content}\n"
        )
    return "\n\n".join(parts)


def answer_with_rag(question: str) -> str:
    """RAG complet : question + context -> réponse texte.

    question: ex. "Génère une newsletter quotidienne résumant les actualités cyber les plus importantes."
    """
    llm = get_llm()
    vectorstore = _load_vectorstore()
    retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

    template = """Tu es un expert en cybersécurité et en veille.

Tu dois générer une newsletter structurée à partir du contexte fourni,
pour informer le lecteur quotidiennement.
la newsletter doit se composer de 5 nouvelles importantes au minimum, chacune avec un titre, description et sources cliquables par exemple ("source").
Si une information n'apparaît pas dans le contexte, ne l'invente PAS.

Question:
{question}

Contexte:
{context}

Rédige en langue de contexte (fr ou en), avec :
- une introduction concise,
- 5 sections claires au minimum,
- tout nouvelle doivent etre expliquée de manière concise,
- les nouvelles doivent etre accompagnées de leurs sources cliquables sous forme de mot "source",
- une structure de newsletter professionnelle.
"""
    prompt = ChatPromptTemplate.from_template(template)

    chain = (
        RunnableParallel(
            {
                "context": retriever | _format_docs,
                "question": RunnablePassthrough(),
            }
        )
        | prompt
        | llm
        | StrOutputParser()
    )

    return chain.invoke(question)
