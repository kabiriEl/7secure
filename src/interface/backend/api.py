from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from src.pipeline.workflow import build_pipeline_app 

app = FastAPI(title="7secure Backend")

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
    "Produis la newsletter quotidienne de VEILLE cybersécurité à partir des sources collectées aujourd’hui.\n\n"

    "INSTRUCTIONS OPÉRATIONNELLES :\n"
    "- Identifier, prioriser et structurer les événements cybersécurité les plus importants du jour.\n"
    "- Traiter plusieurs sujets distincts (ne pas se limiter à une seule source).\n"
    "- Mettre en avant les vulnérabilités critiques, alertes éditeurs/agences, incidents, campagnes et tendances.\n\n"

    "EXIGENCES CLÉS :\n"
    "- Respecter strictement la structure de veille imposée (titre principal, à la une, articles détaillés).\n"
    "- Ne pas produire de lettre éditoriale : aucune salutation, aucune signature, aucun appel au lecteur.\n"
    "- Supprimer les doublons et les contenus à faible valeur ajoutée.\n\n"

    "OBJECTIF FINAL :\n"
    "- Permettre à un RSSI ou à un analyste SOC de comprendre en moins de 5 minutes\n"
    "  les événements cybersécurité majeurs de la journée et leur impact concret."
)







@app.post("/run-daily-newsletter")
def run_daily_newsletter():
    print("[API] Starting pipeline...")
    try:
        state = pipeline_app.invoke({"question": DAILY_QUESTION})
    except Exception as e:
        print(f"[API] Pipeline invocation failed: {e}")
        # Bubble up as HTTP 500 so clients get a clear error
        raise HTTPException(status_code=500, detail=f"Pipeline error: {e}")

    rag_answer = state.get("rag_answer", "")
    # newsletter_html = state.get("newsletter_html", "")

    print(f"[API] Pipeline complete. Returning content (len={len(rag_answer)}) and html")
    # return {"content": rag_answer, "html": newsletter_html}
    return {"content": rag_answer}
