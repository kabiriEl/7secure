from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.pipeline.workflow import build_pipeline_app 

app = FastAPI(title="SafariNewsletter Backend")

# CORS: Allow requests from the Next.js dev server (and common localhost variants)
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost",
    "http://127.0.0.1",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline_app = build_pipeline_app()

DAILY_QUESTION = (
    "Génère une newsletter quotidienne qui résume les incidents, vulnérabilités, "
    "campagnes et tendances en cybersécurité les plus importantes à partir des "
    "articles disponibles aujourd'hui."
)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "SafariNewsletter API"}


@app.post("/run-daily-newsletter")
def run_daily_newsletter():
    print("[API] Starting pipeline...")
    state = pipeline_app.invoke({"question": DAILY_QUESTION})
    rag_answer = state.get("rag_answer", "")
    newsletter_html = state.get("newsletter_html", "")
    print(f"[API] Pipeline complete. HTML length: {len(newsletter_html)}")
    return {"content": rag_answer, "html": newsletter_html}
