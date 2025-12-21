"""LangGraph workflow for end-to-end daily pipeline.

Étapes :
1. scrape      -> raw_articles
2. filter      -> filtered_articles
3. preprocess  -> clean_articles
4. summarize   -> summaries
5. embed       -> met à jour Mongo + vector store
6. rag         -> rag_answer (texte brut)
7. html        -> newsletter_html (HTML)
"""

from typing import Any, Dict, List, TypedDict

from langgraph.graph import StateGraph, END

from src.tools.scraper import scrape_sources
from src.tools.preprocess import preprocess_articles
from src.tools.embedding import upsert_embeddings
from src.tools.rag import answer_with_rag
# from src.tools.summarizer import summarize_articles
from src.tools.html_generator import generate_newsletter_html
from src.tools.filtering import filter_articles


class PipelineState(TypedDict, total=False):
    question: str
    raw_articles: List[Dict[str, Any]]
    filtered_articles: List[Dict[str, Any]]
    clean_articles: List[Dict[str, Any]]
    summaries: List[Dict[str, Any]]
    rag_answer: str
    newsletter_html: str


# --- Nœuds du graph ---------------------------------------------------------


def scrape_node(state: PipelineState) -> PipelineState:
    raw = scrape_sources()
    return {**state, "raw_articles": raw}


def filter_node(state: PipelineState) -> PipelineState:
    raw = state.get("raw_articles", [])
    filtered = filter_articles(raw)
    return {**state, "filtered_articles": filtered}


def preprocess_node(state: PipelineState) -> PipelineState:
    # Use filtered_articles from the previous node
    articles_to_process = state.get("filtered_articles", [])
    clean = preprocess_articles(articles_to_process)
    return {**state, "clean_articles": clean}


# def summarize_node(state: PipelineState) -> PipelineState:
#     clean = state.get("clean_articles", [])
#     summaries = summarize_articles(clean)
#     return {**state, "summaries": summaries}


def embed_node(state: PipelineState) -> PipelineState:
    # Prefer summaries if available to reduce vector store size
    to_embed = state.get("clean_articles", state.get("clean_articles", []))
    upsert_embeddings(to_embed)
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
    # workflow.add_node("summarize", summarize_node)
    workflow.add_node("embed", embed_node)
    workflow.add_node("rag", rag_node)
    workflow.add_node("html", html_node)

    workflow.set_entry_point("scrape")
    workflow.add_edge("scrape", "filter")
    workflow.add_edge("filter", "preprocess")
    # workflow.add_edge("preprocess", "summarize")
    workflow.add_edge("preprocess", "embed")
    workflow.add_edge("embed", "rag")
    workflow.add_edge("rag", "html")
    workflow.add_edge("html", END)

    app = workflow.compile()
    return app
