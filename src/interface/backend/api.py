from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from bson import ObjectId
from bson.errors import InvalidId
from passlib.context import CryptContext
from jose import JWTError, jwt
from src.pipeline.workflow import build_pipeline_app
from src.database.mongo import MongoDB 

app = FastAPI(title="7secure Backend")

# Security
SECRET_KEY = "your-secret-key-change-in-production"  # Change this in production!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 * 24 * 60  # 30 days

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# CORS: Allow requests from localhost on any port (for development flexibility)
# The regex matches http://localhost or http://127.0.0.1 with optional port number
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",  # Match localhost on any port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
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







def _convert_objectid_to_str(doc: dict) -> dict:
    """Convert MongoDB ObjectId to string for JSON serialization."""
    if "_id" in doc and isinstance(doc["_id"], ObjectId):
        doc["_id"] = str(doc["_id"])
    return doc


# ==================== Authentication Models ====================
class UserSignup(BaseModel):
    name: str
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict


class UserResponse(BaseModel):
    _id: str
    name: str
    email: str


class SubscribeRequest(BaseModel):
    email: str


# ==================== Authentication Helpers ====================
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get the current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    db = MongoDB()
    collection = db.get_collection("users")
    user = collection.find_one({"email": email})
    if user is None:
        raise credentials_exception
    
    return _convert_objectid_to_str(user)


@app.get("/")
def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "FastAPI backend is running"}


@app.get("/health")
def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "service": "7secure Backend"}


# ==================== Authentication Endpoints ====================
@app.post("/api/auth/signup")
def signup(user_data: UserSignup):
    """Register a new user."""
    try:
        db = MongoDB()
        collection = db.get_collection("users")
        
        # Check if user already exists
        existing_user = collection.find_one({"email": user_data.email})
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create new user
        hashed_password = get_password_hash(user_data.password)
        user_doc = {
            "name": user_data.name,
            "email": user_data.email,
            "password": hashed_password,
            "created_at": datetime.now().isoformat(),
        }
        
        result = db.insert_one("users", user_doc)
        user_doc["_id"] = str(result.inserted_id)
        user_doc.pop("password", None)  # Don't return password
        
        return {"success": True, "message": "User created successfully", "user": user_doc}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[API] Error creating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating user: {str(e)}"
        )


@app.post("/api/auth/login", response_model=Token)
def login(user_data: UserLogin):
    """Login and get access token."""
    try:
        db = MongoDB()
        collection = db.get_collection("users")
        
        # Find user
        user = collection.find_one({"email": user_data.email})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Verify password
        if not verify_password(user_data.password, user["password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user["email"]}, expires_delta=access_token_expires
        )
        
        user_dict = _convert_objectid_to_str(user)
        del user_dict["password"]  # Don't return password
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user_dict
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[API] Error during login: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during login: {str(e)}"
        )


@app.get("/api/auth/me", response_model=dict)
def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information."""
    return {"success": True, "user": current_user}


# ==================== Subscription Endpoints ====================
@app.post("/api/subscribe")
def subscribe(subscribe_data: SubscribeRequest):
    """Subscribe to newsletter."""
    try:
        email = subscribe_data.email
        
        db = MongoDB()
        collection = db.get_collection("subscribers")
        
        # Check if already subscribed
        existing = collection.find_one({"email": email})
        if existing:
            return {
                "success": True,
                "message": "Email already subscribed",
                "subscribed": True
            }
        
        # Add subscriber
        subscriber_doc = {
            "email": email,
            "subscribed_at": datetime.now().isoformat(),
            "active": True
        }
        result = db.insert_one("subscribers", subscriber_doc)
        
        return {
            "success": True,
            "message": "Successfully subscribed to newsletter",
            "subscribed": True
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[API] Error subscribing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error subscribing: {str(e)}"
        )


# ==================== Comments Endpoints ====================
@app.post("/api/newsletters/{newsletter_id}/comments")
def add_comment(newsletter_id: str, comment_data: dict):
    """Add a comment to a newsletter."""
    try:
        # Validate ObjectId format
        try:
            object_id = ObjectId(newsletter_id)
        except (InvalidId, Exception):
            raise HTTPException(status_code=400, detail="Invalid newsletter ID format")
        
        # Verify newsletter exists
        db = MongoDB()
        newsletter_collection = db.get_collection("newsletters")
        newsletter = newsletter_collection.find_one({"_id": object_id})
        if not newsletter:
            raise HTTPException(status_code=404, detail="Newsletter not found")
        
        # Create comment
        comment_doc = {
            "newsletter_id": newsletter_id,
            "author": comment_data.get("author", ""),
            "email": comment_data.get("email", ""),
            "content": comment_data.get("content", ""),
            "created_at": datetime.now().isoformat(),
        }
        
        result = db.insert_one("comments", comment_doc)
        comment_doc["_id"] = str(result.inserted_id)
        
        return {"success": True, "message": "Comment added successfully", "comment": comment_doc}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[API] Error adding comment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding comment: {str(e)}"
        )


@app.get("/api/newsletters/{newsletter_id}/comments")
def get_comments(newsletter_id: str):
    """Get all comments for a newsletter."""
    try:
        # Validate ObjectId format
        try:
            object_id = ObjectId(newsletter_id)
        except (InvalidId, Exception):
            raise HTTPException(status_code=400, detail="Invalid newsletter ID format")
        
        db = MongoDB()
        comments = db.find("comments", query={"newsletter_id": newsletter_id})
        comments = [_convert_objectid_to_str(c) for c in comments]
        
        return {"data": comments, "success": True}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[API] Error fetching comments: {e}")
        return {"data": [], "success": True}


@app.get("/api/newsletters")
def get_newsletters():
    """Get all newsletters from MongoDB."""
    try:
        db = MongoDB()
        newsletters = db.find("newsletters", limit=100)  # Limit to 100 most recent
        # Convert ObjectId to string for JSON
        newsletters = [_convert_objectid_to_str(nl) for nl in newsletters]
        return {"data": newsletters, "success": True}
    except Exception as e:
        print(f"[API] Error fetching newsletters: {e}")
        # Return empty list if collection doesn't exist or error occurs
        return {"data": [], "success": True}


@app.get("/api/newsletters/{newsletter_id}")
def get_newsletter_by_id(newsletter_id: str):
    """Get a specific newsletter by ID."""
    try:
        # Validate ObjectId format
        try:
            object_id = ObjectId(newsletter_id)
        except (InvalidId, Exception):
            raise HTTPException(status_code=400, detail="Invalid newsletter ID format")
        
        db = MongoDB()
        collection = db.get_collection("newsletters")
        newsletter = collection.find_one({"_id": object_id})
        
        if not newsletter:
            raise HTTPException(status_code=404, detail="Newsletter not found")
        
        newsletter = _convert_objectid_to_str(newsletter)
        return {"data": newsletter, "success": True}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[API] Error fetching newsletter {newsletter_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching newsletter: {e}")


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
    newsletter_html = state.get("newsletter_html", "")

    print(f"[API] Pipeline complete. Returning content (len={len(rag_answer)}) and html")
    
    # Save to MongoDB
    try:
        db = MongoDB()
        # Extract title from content (first line or default)
        title = "Newsletter Quotidienne"
        if rag_answer:
            first_line = rag_answer.split("\n")[0].strip()
            if first_line and len(first_line) < 200:
                extracted_title = first_line.replace("#", "").strip()
                if extracted_title:
                    title = extracted_title
        
        newsletter_doc = {
            "title": title,
            "excerpt": rag_answer[:200] + "..." if len(rag_answer) > 200 else rag_answer,
            "content": rag_answer,
            "html": newsletter_html,
            "author": {"name": "7secure"},
            "date": datetime.now().isoformat(),
            "tags": ["cybersécurité", "veille"],
        }
        result = db.insert_one("newsletters", newsletter_doc)
        print(f"[API] Newsletter saved to MongoDB with ID: {result.inserted_id}")
    except Exception as e:
        print(f"[API] Warning: Could not save newsletter to MongoDB: {e}")
    
    return {"content": rag_answer, "html": newsletter_html}
