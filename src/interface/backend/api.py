from datetime import datetime
from typing import Optional
import os
import re
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler

from src.pipeline.workflow import build_pipeline_app
from src.configs.config import settings


def _clean_markdown_text(text: str) -> str:
    """
    Nettoie complètement le texte de tous les caractères de formatage Markdown.
    """
    text = re.sub(r"\*+", "", text)
    text = re.sub(r"__+", "", text)
    text = re.sub(r"^\s*#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"`+", "", text)
    text = re.sub(r"^[\-_][\-_]+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# app = FastAPI(title="SafariNewsletter Backend (Ghost Frontend)")

# # CORS dev (tu peux durcir plus tard)
# app.add_middleware(
#     CORSMiddleware,
#     allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
#     expose_headers=["*"],
# )

app = FastAPI(title="SafariNewsletter Backend")

if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )




pipeline_app = build_pipeline_app()

DAILY_QUESTION = (
    "Produis une newsletter quotidienne PREMIUM de cybersécurité et menaces IA à partir des sources collectées.\n\n"
    "INSTRUCTIONS CRITIQUES :\n"
    "1. OBLIGATOIRE : Générer au MINIMUM 5 stories (articles distincts avec tous les détails).\n"
    "2. Chaque story DOIT contenir : titre, URL, catégorie, 3-5 key_points, description complète, why_it_matters.\n"
    "3. Prioriser : vulnérabilités zéro-day, exploits actifs, incidents majeurs, menaces IA émergentes, campagnes ciblées.\n"
    "4. Couvrir au minimum 3 catégories distinctes parmi : Vulnerabilities, Threat Intelligence, Malware, AI Security, Data Breaches, IAM.\n\n"
    "EXIGENCES DE QUALITÉ :\n"
    "- Chaque article doit apporter une valeur analytique unique (pas de redondance).\n"
    "- Inclure l'impact sur les organisations et les mesures de mitigation recommandées.\n"
    "- Utiliser un ton professionnel et neutre, adapté aux RSSI et analystes SOC.\n"
    "- Aucun contenu éditorial, salutation ou signature : facts only.\n\n"
    "OBJECTIF :\n"
    "Permettre aux décideurs IT/Sécurité de comprendre les risques critiques du jour"
    " et leur impact concret sur l'infrastructure (scores de criticité : critique/élevé/moyen)."
)


# ==================== APScheduler Setup ====================
# Protection contre double exécution en mode --reload (uvicorn)
# La variable d'environnement RUN_MAIN n'existe que dans le process principal
# (pas dans le reloader), donc on évite de lancer le scheduler deux fois.
scheduler = BackgroundScheduler()


def automated_daily_job():
    """
    Job automatique exécuté tous les jours à 08:00 par APScheduler.
    Lance le pipeline complet et publie la newsletter dans Ghost.
    """
    print("[SCHEDULER] ========================================")
    print(f"[SCHEDULER] Starting automated daily job at {datetime.now().isoformat()}")
    print("[SCHEDULER] ========================================")
    
    try:
        state = pipeline_app.invoke({"question": DAILY_QUESTION})
        
        rag_answer = state.get("rag_answer", "") or ""
        newsletter_html = state.get("newsletter_html", "") or ""
        ghost_post_id = state.get("ghost_post_id", "") or ""
        ghost_post_url = state.get("ghost_post_url", "") or ""
        
        print(f"[SCHEDULER] Pipeline completed successfully")
        print(f"[SCHEDULER] RAG answer length: {len(rag_answer)} chars")
        print(f"[SCHEDULER] Newsletter HTML length: {len(newsletter_html)} chars")
        print(f"[SCHEDULER] Ghost post ID: {ghost_post_id}")
        print(f"[SCHEDULER] Ghost post URL: {ghost_post_url}")
        print("[SCHEDULER] ========================================")
        
    except Exception as e:
        print(f"[SCHEDULER] ERROR: Pipeline execution failed: {e}")
        print("[SCHEDULER] ========================================")
        # On ne lève pas l'exception pour ne pas crasher le scheduler
        # Le job va simplement réessayer le lendemain


@app.on_event("startup")
def startup_event():
    """
    Démarrage du scheduler APScheduler au lancement de FastAPI.
    Protection contre double exécution en mode uvicorn --reload.
    """
    # Protection: ne démarre le scheduler que dans le process principal
    # En mode --reload, uvicorn crée un process parent (reloader) et un process enfant (app)
    # On ne veut exécuter le scheduler que dans le process enfant (celui qui run l'app)
    if os.environ.get("RUN_MAIN") == "true" or not os.environ.get("RUN_MAIN"):
        # RUN_MAIN=true signifie qu'on est dans le process enfant (mode reload)
        # Si RUN_MAIN n'existe pas, on est en mode normal (pas de reload)
        # Dans les deux cas, on démarre le scheduler
        
        # Configurer le job quotidien à 08:00
        scheduler.add_job(
            automated_daily_job,
            trigger="cron",
            hour=8,
            minute=0,
            id="daily_newsletter_job",
            replace_existing=True,
        )
        
        scheduler.start()
        print("[SCHEDULER] APScheduler started - Daily job configured for 08:00")
        print("[SCHEDULER] Next run:", scheduler.get_jobs()[0].next_run_time if scheduler.get_jobs() else "No jobs scheduled")
    else:
        print("[SCHEDULER] Skipping scheduler start (reloader process)")


@app.on_event("shutdown")
def shutdown_event():
    """Arrêt propre du scheduler APScheduler."""
    if scheduler.running:
        scheduler.shutdown()
        print("[SCHEDULER] APScheduler stopped")


# ==================== Endpoints ====================

@app.get("/")
def root():
    return {"status": "ok", "message": "Backend is running (Ghost is the frontend)"}


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "SafariNewsletter Backend"}


@app.post("/run-daily-newsletter")
def run_daily_newsletter():
    """
    Lance le pipeline (scrape->rag->html->publish draft to Ghost),
    et renvoie le contenu + info Ghost.
    """
    print("[API] Starting pipeline...")
    try:
        state = pipeline_app.invoke({"question": DAILY_QUESTION})
    except Exception as e:
        print(f"[API] Pipeline invocation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Pipeline error: {e}")

    rag_answer = state.get("rag_answer", "") or ""
    newsletter_html = state.get("newsletter_html", "") or ""
    
    # Parse the RAG JSON to extract title and content for API response
    newsletter_title = ""
    try:
        rag_data = json.loads(rag_answer)
        if isinstance(rag_data, dict):
            newsletter_title = (rag_data.get("title") or "").strip()
    except (json.JSONDecodeError, ValueError):
        pass
    
    if not newsletter_title:
        newsletter_title = "Cybersecurity Newsletter"

    # Newsletter archivée dans Ghost (pas de stockage parallèle MongoDB)

    print("[API] Pipeline complete.")

    return {
        "title": newsletter_title,
        "content": rag_answer,
        "html": newsletter_html,
        "ghost": {
            "status": state.get("ghost_status", ""),
            "post_id": state.get("ghost_post_id", ""),
            "slug": state.get("ghost_post_slug", ""),
            "url": state.get("ghost_post_url", ""),
        },
    }
































# from datetime import datetime, timedelta
# from typing import Optional
# import re
# from fastapi import FastAPI, HTTPException, Depends, status
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# from pydantic import BaseModel, EmailStr
# from bson import ObjectId
# from bson.errors import InvalidId
# from passlib.context import CryptContext
# from jose import JWTError, jwt
# from src.pipeline.workflow import build_pipeline_app
# from src.tools.filtering import CATEGORIES
# from src.database.mongo import MongoDB 


# def _clean_markdown_text(text: str) -> str:
#     """
#     Nettoie complètement le texte de tous les caractères de formatage Markdown.
#     """
#     # Supprimer tous les astérisques (**text** et *text*)
#     text = re.sub(r'\*+', '', text)
#     # Supprimer les underscores de formatage (__)
#     text = re.sub(r'__+', '', text)
#     # Supprimer les dièses au début de ligne (titres Markdown)
#     text = re.sub(r'^\s*#+\s*', '', text, flags=re.MULTILINE)
#     # Supprimer les backticks (code inline)
#     text = re.sub(r'`+', '', text)
#     # Supprimer les tirets isolés en début de ligne (listes Markdown non-standard)
#     text = re.sub(r'^[\-_][\-_]+$', '', text, flags=re.MULTILINE)
#     # Nettoyer les espaces multiples
#     text = re.sub(r'\s+', ' ', text)
#     return text.strip()


# app = FastAPI(title="7secure Backend")

# # Security
# SECRET_KEY = "your-secret-key-change-in-production"  # Change this in production!
# ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = 30 * 24 * 60  # 30 days

# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# security = HTTPBearer()

# # CORS: Allow requests from localhost on any port (for development flexibility)
# # The regex matches http://localhost or http://127.0.0.1 with optional port number
# app.add_middleware(
#     CORSMiddleware,
#     allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",  # Match localhost on any port
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
#     expose_headers=["*"],
# )

# pipeline_app = build_pipeline_app()

# DAILY_QUESTION = (
#     "Produis la newsletter quotidienne de VEILLE cybersécurité à partir des sources collectées aujourd’hui.\n\n"

#     "INSTRUCTIONS OPÉRATIONNELLES :\n"
#     "- Identifier, prioriser et structurer les événements cybersécurité les plus importants du jour.\n"
#     "- Traiter plusieurs sujets distincts (ne pas se limiter à une seule source).\n"
#     "- Mettre en avant les vulnérabilités critiques, alertes éditeurs/agences, incidents, campagnes et tendances.\n\n"

#     "EXIGENCES CLÉS :\n"
#     "- Respecter strictement la structure de veille imposée (titre principal, à la une, articles détaillés).\n"
#     "- Ne pas produire de lettre éditoriale : aucune salutation, aucune signature, aucun appel au lecteur.\n"
#     "- Supprimer les doublons et les contenus à faible valeur ajoutée.\n\n"

#     "OBJECTIF FINAL :\n"
#     "- Permettre à un RSSI ou à un analyste SOC de comprendre en moins de 5 minutes\n"
#     "  les événements cybersécurité majeurs de la journée et leur impact concret."
# )







# def _convert_objectid_to_str(doc: dict) -> dict:
#     """Convert MongoDB ObjectId to string for JSON serialization."""
#     if "_id" in doc and isinstance(doc["_id"], ObjectId):
#         doc["_id"] = str(doc["_id"])
#     return doc


# # ==================== Authentication Models ====================
# class UserSignup(BaseModel):
#     name: str
#     email: str
#     password: str


# class UserLogin(BaseModel):
#     email: str
#     password: str


# class Token(BaseModel):
#     access_token: str
#     token_type: str
#     user: dict


# class UserResponse(BaseModel):
#     _id: str
#     name: str
#     email: str


# class SubscribeRequest(BaseModel):
#     email: str


# # ==================== Authentication Helpers ====================
# def verify_password(plain_password: str, hashed_password: str) -> bool:
#     """Verify a password against its hash."""
#     return pwd_context.verify(plain_password, hashed_password)


# def get_password_hash(password: str) -> str:
#     """Hash a password."""
#     return pwd_context.hash(password)


# def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
#     """Create a JWT access token."""
#     to_encode = data.copy()
#     if expires_delta:
#         expire = datetime.utcnow() + expires_delta
#     else:
#         expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
#     to_encode.update({"exp": expire})
#     encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
#     return encoded_jwt


# async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
#     """Get the current authenticated user from JWT token."""
#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Could not validate credentials",
#         headers={"WWW-Authenticate": "Bearer"},
#     )
#     try:
#         token = credentials.credentials
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         email: str = payload.get("sub")
#         if email is None:
#             raise credentials_exception
#     except JWTError:
#         raise credentials_exception
    
#     db = MongoDB()
#     collection = db.get_collection("users")
#     user = collection.find_one({"email": email})
#     if user is None:
#         raise credentials_exception
    
#     return _convert_objectid_to_str(user)


# @app.get("/")
# def root():
#     """Health check endpoint."""
#     return {"status": "ok", "message": "FastAPI backend is running"}


# @app.get("/health")
# def health_check():
#     """Health check endpoint for monitoring."""
#     return {"status": "healthy", "service": "7secure Backend"}


# # ==================== Authentication Endpoints ====================
# @app.post("/api/auth/signup")
# def signup(user_data: UserSignup):
#     """Register a new user."""
#     try:
#         db = MongoDB()
#         collection = db.get_collection("users")
        
#         # Check if user already exists
#         existing_user = collection.find_one({"email": user_data.email})
#         if existing_user:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="Email already registered"
#             )
        
#         # Create new user
#         hashed_password = get_password_hash(user_data.password)
#         user_doc = {
#             "name": user_data.name,
#             "email": user_data.email,
#             "password": hashed_password,
#             "created_at": datetime.now().isoformat(),
#         }
        
#         result = db.insert_one("users", user_doc)
#         user_doc["_id"] = str(result.inserted_id)
#         user_doc.pop("password", None)  # Don't return password
        
#         return {"success": True, "message": "User created successfully", "user": user_doc}
#     except HTTPException:
#         raise
#     except Exception as e:
#         print(f"[API] Error creating user: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Error creating user: {str(e)}"
#         )


# @app.post("/api/auth/login", response_model=Token)
# def login(user_data: UserLogin):
#     """Login and get access token."""
#     try:
#         db = MongoDB()
#         collection = db.get_collection("users")
        
#         # Find user
#         user = collection.find_one({"email": user_data.email})
#         if not user:
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Incorrect email or password"
#             )
        
#         # Verify password
#         if not verify_password(user_data.password, user["password"]):
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Incorrect email or password"
#             )
        
#         # Create access token
#         access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
#         access_token = create_access_token(
#             data={"sub": user["email"]}, expires_delta=access_token_expires
#         )
        
#         user_dict = _convert_objectid_to_str(user)
#         del user_dict["password"]  # Don't return password
        
#         return {
#             "access_token": access_token,
#             "token_type": "bearer",
#             "user": user_dict
#         }
#     except HTTPException:
#         raise
#     except Exception as e:
#         print(f"[API] Error during login: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Error during login: {str(e)}"
#         )


# @app.get("/api/auth/me", response_model=dict)
# def get_current_user_info(current_user: dict = Depends(get_current_user)):
#     """Get current user information."""
#     return {"success": True, "user": current_user}


# # ==================== Subscription Endpoints ====================
# @app.post("/api/subscribe")
# def subscribe(subscribe_data: SubscribeRequest):
#     """Subscribe to newsletter."""
#     try:
#         email = subscribe_data.email
        
#         db = MongoDB()
#         collection = db.get_collection("subscribers")
        
#         # Check if already subscribed
#         existing = collection.find_one({"email": email})
#         if existing:
#             return {
#                 "success": True,
#                 "message": "Email already subscribed",
#                 "subscribed": True
#             }
        
#         # Add subscriber
#         subscriber_doc = {
#             "email": email,
#             "subscribed_at": datetime.now().isoformat(),
#             "active": True
#         }
#         result = db.insert_one("subscribers", subscriber_doc)
        
#         return {
#             "success": True,
#             "message": "Successfully subscribed to newsletter",
#             "subscribed": True
#         }
#     except HTTPException:
#         raise
#     except Exception as e:
#         print(f"[API] Error subscribing: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Error subscribing: {str(e)}"
#         )


# # ==================== Comments Endpoints ====================
# @app.post("/api/newsletters/{newsletter_id}/comments")
# def add_comment(newsletter_id: str, comment_data: dict):
#     """Add a comment to a newsletter."""
#     try:
#         # Validate ObjectId format
#         try:
#             object_id = ObjectId(newsletter_id)
#         except (InvalidId, Exception):
#             raise HTTPException(status_code=400, detail="Invalid newsletter ID format")
        
#         # Verify newsletter exists
#         db = MongoDB()
#         newsletter_collection = db.get_collection("newsletters")
#         newsletter = newsletter_collection.find_one({"_id": object_id})
#         if not newsletter:
#             raise HTTPException(status_code=404, detail="Newsletter not found")
        
#         # Create comment
#         comment_doc = {
#             "newsletter_id": newsletter_id,
#             "author": comment_data.get("author", ""),
#             "email": comment_data.get("email", ""),
#             "content": comment_data.get("content", ""),
#             "created_at": datetime.now().isoformat(),
#         }
        
#         result = db.insert_one("comments", comment_doc)
#         comment_doc["_id"] = str(result.inserted_id)
        
#         return {"success": True, "message": "Comment added successfully", "comment": comment_doc}
#     except HTTPException:
#         raise
#     except Exception as e:
#         print(f"[API] Error adding comment: {e}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Error adding comment: {str(e)}"
#         )


# @app.get("/api/newsletters/{newsletter_id}/comments")
# def get_comments(newsletter_id: str):
#     """Get all comments for a newsletter."""
#     try:
#         # Validate ObjectId format
#         try:
#             object_id = ObjectId(newsletter_id)
#         except (InvalidId, Exception):
#             raise HTTPException(status_code=400, detail="Invalid newsletter ID format")
        
#         db = MongoDB()
#         comments = db.find("comments", query={"newsletter_id": newsletter_id})
#         comments = [_convert_objectid_to_str(c) for c in comments]
        
#         return {"data": comments, "success": True}
#     except HTTPException:
#         raise
#     except Exception as e:
#         print(f"[API] Error fetching comments: {e}")
#         return {"data": [], "success": True}


# @app.get("/api/newsletters")
# def get_newsletters():
#     """Get all newsletters from MongoDB."""
#     try:
#         db = MongoDB()
#         newsletters = db.find("newsletters")  # Get all newsletters without limit
#         # Convert ObjectId to string for JSON
#         newsletters = [_convert_objectid_to_str(nl) for nl in newsletters]
#         return {"data": newsletters, "success": True}
#     except Exception as e:
#         print(f"[API] Error fetching newsletters: {e}")
#         # Return empty list if collection doesn't exist or error occurs
#         return {"data": [], "success": True}


# @app.get("/api/newsletters/{newsletter_id}")
# def get_newsletter_by_id(newsletter_id: str):
#     """Get a specific newsletter by ID."""
#     try:
#         # Validate ObjectId format
#         try:
#             object_id = ObjectId(newsletter_id)
#         except (InvalidId, Exception):
#             raise HTTPException(status_code=400, detail="Invalid newsletter ID format")
        
#         db = MongoDB()
#         collection = db.get_collection("newsletters")
#         newsletter = collection.find_one({"_id": object_id})
        
#         if not newsletter:
#             raise HTTPException(status_code=404, detail="Newsletter not found")
        
#         newsletter = _convert_objectid_to_str(newsletter)
#         return {"data": newsletter, "success": True}
#     except HTTPException:
#         raise
#     except Exception as e:
#         print(f"[API] Error fetching newsletter {newsletter_id}: {e}")
#         raise HTTPException(status_code=500, detail=f"Error fetching newsletter: {e}")


# @app.post("/run-daily-newsletter")
# def run_daily_newsletter():
#     print("[API] Starting pipeline...")
#     try:
#         state = pipeline_app.invoke({"question": DAILY_QUESTION})
#     except Exception as e:
#         print(f"[API] Pipeline invocation failed: {e}")
#         # Bubble up as HTTP 500 so clients get a clear error
#         raise HTTPException(status_code=500, detail=f"Pipeline error: {e}")

#     rag_answer = state.get("rag_answer", "")
#     newsletter_html = state.get("newsletter_html", "")
    
#     # Nettoyer complètement le rag_answer de tout formatage Markdown
#     rag_answer = _clean_markdown_text(rag_answer)
    
#     # Derive tags (categories) from filtered articles
#     try:
#         from collections import Counter
#         filtered_articles = state.get("filtered_articles", []) or []
#         cat_counter = Counter(
#             [a.get("category") for a in filtered_articles if a.get("category")]
#         )
#         top_categories = [c for c, _ in cat_counter.most_common(3)]
#         # Ensure at least 2 tags using the known category list
#         all_categories = list(CATEGORIES.keys())
#         for cat in all_categories:
#             if len(top_categories) >= 2:
#                 break
#             if cat not in top_categories:
#                 top_categories.append(cat)
#         # Keep max 3
#         top_categories = top_categories[:3]
#     except Exception:
#         top_categories = []

#     print(f"[API] Pipeline complete. Returning content (len={len(rag_answer)}) and html")
    
#     # Save to MongoDB
#     try:
#         db = MongoDB()
#         # Extract title from content (first meaningful line)
#         title = "Newsletter Cybersécurité"
#         if rag_answer:
#             # Find first non-empty line
#             lines = [line.strip() for line in rag_answer.split("\n") if line.strip()]
#             if lines:
#                 # Use first meaningful line as title (limit to 160 chars for readability)
#                 first_meaningful = lines[0]
#                 if len(first_meaningful) <= 70:
#                     title = first_meaningful
#                 else:
#                     # Truncate and add ellipsis if too long
#                     title = first_meaningful[:157] + "..."
        
#         newsletter_doc = {
#             "title": title,
#             "excerpt": rag_answer[:200] + "..." if len(rag_answer) > 200 else rag_answer,
#             "content": rag_answer,
#             "html": newsletter_html,
#             "author": {"name": "7secure"},
#             "date": datetime.now().isoformat(),
#             "tags": top_categories if top_categories else ["cybersécurité", "veille"],
#         }
#         result = db.insert_one("newsletters", newsletter_doc)
#         print(f"[API] Newsletter saved to MongoDB with ID: {result.inserted_id}")
#     except Exception as e:
#         print(f"[API] Warning: Could not save newsletter to MongoDB: {e}")
    
#     return {"content": rag_answer, "html": newsletter_html}
