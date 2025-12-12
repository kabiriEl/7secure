"""LangGraph workflow for end-to-end daily pipeline.

Étapes :
1. scrape      -> raw_articles
2. preprocess  -> clean_articles
3. embed       -> met à jour Mongo + vector store
4. rag         -> rag_answer (texte brut)
5. newsletter  -> newsletter (structure dict)
"""

from typing import Any, Dict, List, TypedDict

from langgraph.graph import StateGraph, END

from src.tools.scraper import scrape_sources
from src.tools.preprocess import preprocess_articles
from src.tools.embedding import upsert_embeddings
from src.tools.rag import answer_with_rag
from src.tools.summarizer import summarize_articles
from src.tools.html_generator import generate_newsletter_html
from src.tools.filtering import filter_articles


class PipelineState(TypedDict, total=False):
    question: str
    raw_articles: List[Dict[str, Any]]
    clean_articles: List[Dict[str, Any]]
    rag_answer: str
    newsletter: Dict[str, Any]


# --- Nœuds du graph ---------------------------------------------------------


def scrape_node(state: PipelineState) -> PipelineState:
    raw = scrape_sources()
    return {**state, "raw_articles": raw}


def filter_node(state: PipelineState) -> PipelineState:
    raw = state.get("raw_articles", [])
    filtered = filter_articles(raw)
    return {**state, "filtered_articles": filtered}


def preprocess_node(state: PipelineState) -> PipelineState:
    # Use filtered_articles if available, otherwise fall back to raw_articles
    articles_to_process = state.get("filtered_articles", state.get("raw_articles", []))
    clean = preprocess_articles(articles_to_process)
    return {**state, "clean_articles": clean}


def summarize_node(state: PipelineState) -> PipelineState:
    clean = state.get("clean_articles", [])
    summaries = summarize_articles(clean)
    return {**state, "summaries": summaries}


def embed_node(state: PipelineState) -> PipelineState:
    # Preferer les résumés si disponibles pour réduire la taille du vector store
    clean = state.get("summaries", state.get("clean_articles", []))
    upsert_embeddings(clean)
    return state


def rag_node(state: PipelineState) -> PipelineState:
    question = state.get("question") or (
        "Génère une newsletter quotidienne qui résume les incidents et "
        "tendances en cybersécurité les plus importantes à partir des articles disponibles."
    )
    answer = answer_with_rag(question)
    return {**state, "rag_answer": answer}


def html_node(state: PipelineState) -> PipelineState:
    rag_answer = state.get("rag_answer", "")
    html_output = generate_newsletter_html(rag_answer)
    return {**state, "newsletter_html": html_output}


# --- Construction de l'app LangGraph ----------------------------------------


def build_pipeline_app():
    workflow = StateGraph(PipelineState)

    workflow.add_node("scrape", scrape_node)
    workflow.add_node("filter", filter_node)
    workflow.add_node("preprocess", preprocess_node)
    workflow.add_node("embed", embed_node)
    workflow.add_node("rag", rag_node)
    workflow.add_node("summarize", summarize_node)
    workflow.add_node("html", html_node)

    workflow.set_entry_point("scrape")
    workflow.add_edge("scrape", "filter")
    workflow.add_edge("filter", "preprocess")
    workflow.add_edge("preprocess", "summarize")
    workflow.add_edge("summarize", "embed")
    workflow.add_edge("embed", "rag")
    workflow.add_edge("rag", "html")
    workflow.add_edge("html", END)
    

    app = workflow.compile()
    return app
