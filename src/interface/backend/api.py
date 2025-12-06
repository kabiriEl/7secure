from fastapi import FastAPI
from src.pipeline.workflow import build_pipeline_app 

app = FastAPI(title="SafariNewsletter Backend")

pipeline_app = build_pipeline_app()

DAILY_QUESTION = (
    "Génère une newsletter quotidienne qui résume les incidents, vulnérabilités, "
    "campagnes et tendances en cybersécurité les plus importantes à partir des "
    "articles disponibles aujourd'hui."
)


@app.post("/run-daily-newsletter")
def run_daily_newsletter():
    state = pipeline_app.invoke({"question": DAILY_QUESTION})
    rag_answer = state.get("rag_answer", "")
    return {"content": rag_answer}
