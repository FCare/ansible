#!/usr/bin/env python3
"""
Voight-Kampff - API Key Authentication Service with Web Interface
Inspired by Blade Runner's empathy test
"""

import os
import secrets
import re
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import FastAPI, Header, HTTPException, Depends, status, Request, Form, Cookie
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, Boolean, Text, select
from passlib.context import CryptContext
from itsdangerous import URLSafeTimedSerializer
import uvicorn

# Configuration
DB_PATH = os.getenv("VK_DB_PATH", "/data/voight-kampff.db")
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"
SECRET_KEY = os.getenv("VK_SECRET_KEY", secrets.token_urlsafe(32))
SESSION_EXPIRE_HOURS = int(os.getenv("VK_SESSION_EXPIRE_HOURS", "24"))

# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
session_serializer = URLSafeTimedSerializer(SECRET_KEY)

# Templates
templates = Jinja2Templates(directory="/app/templates")

# Database Models
class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

class Session(Base):
    __tablename__ = "sessions"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    session_token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    user_id: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    last_used: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

class APIKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    key_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    api_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column()  # Reference to User.id
    user: Mapped[str] = mapped_column(String(255))  # Keep for backward compatibility
    scopes: Mapped[str] = mapped_column(Text)  # Comma-separated list of allowed services
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_used: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

# Pydantic Models
class APIKeyCreate(BaseModel):
    key_name: str = Field(..., description="Unique name for this API key")
    user: str = Field(..., description="Username or identifier")
    scopes: List[str] = Field(..., description="List of allowed services (tts, stt, llm, assistant)")
    expires_in_days: Optional[int] = Field(None, description="Number of days until expiration (None = no expiration)")

class APIKeyResponse(BaseModel):
    id: int
    key_name: str
    api_key: str
    user: str
    scopes: List[str]
    is_active: bool
    created_at: datetime
    last_used: Optional[datetime]
    expires_at: Optional[datetime]

class APIKeyList(BaseModel):
    id: int
    key_name: str
    user: str
    scopes: List[str]
    is_active: bool
    created_at: datetime
    last_used: Optional[datetime]
    expires_at: Optional[datetime]

class VerifyResponse(BaseModel):
    valid: bool
    user: str
    service: str
    scopes: List[str]

# Database setup
engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# Utility functions
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_session_token() -> str:
    return secrets.token_urlsafe(32)

def serialize_session(user_id: int) -> str:
    return session_serializer.dumps({"user_id": user_id})

def deserialize_session(token: str) -> Optional[int]:
    try:
        data = session_serializer.loads(token, max_age=SESSION_EXPIRE_HOURS * 3600)
        return data.get("user_id")
    except:
        return None

def validate_password(password: str) -> bool:
    """Validate password strength"""
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    return True

async def get_current_user(request: Request, session_db: AsyncSession = Depends(get_session)) -> Optional[User]:
    """Get current user from session cookie"""
    session_cookie = request.cookies.get("vk_session")
    if not session_cookie:
        return None
    
    user_id = deserialize_session(session_cookie)
    if not user_id:
        return None
    
    # Get user from database
    result = await session_db.execute(
        select(User).where(User.id == user_id, User.is_active == True)
    )
    return result.scalar_one_or_none()

# FastAPI app
app = FastAPI(
    title="Voight-Kampff",
    description="API Key Authentication Service - Testing for humanity, one request at a time",
    version="2.0.0"
)

@app.on_event("startup")
async def startup_event():
    await init_db()
    print("🔍 Voight-Kampff authentication service is running")
    print(f"📁 Database: {DB_PATH}")
    print(f"🌐 Web interface available at /auth/")

@app.get("/")
async def root():
    return {
        "service": "Voight-Kampff",
        "version": "2.0.0",
        "description": "API Key Authentication Service with Web Interface",
        "endpoints": {
            "verify": "/verify - Verify API key (used by Traefik ForwardAuth)",
            "keys": "/keys - Manage API keys",
            "web": "/auth/ - Web interface",
            "health": "/health - Health check"
        }
    }

@app.get("/health")
async def health():
    return {"status": "operational", "test": "positive"}

# ========== WEB AUTHENTICATION ENDPOINTS ==========

@app.get("/auth/login", response_class=HTMLResponse)
async def login_page(request: Request, redirect: Optional[str] = None, error: Optional[str] = None):
    """Login page"""
    return templates.TemplateResponse("login.html", {
        "request": request,
        "redirect_after": redirect,
        "error": error
    })

@app.post("/auth/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    redirect_after: Optional[str] = Form(None),
    session_db: AsyncSession = Depends(get_session)
):
    """Process login form"""
    # Get user from database
    result = await session_db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "redirect_after": redirect_after,
            "error": "Nom d'utilisateur ou mot de passe incorrect"
        })
    
    if not user.is_active:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "redirect_after": redirect_after,
            "error": "Compte désactivé"
        })
    
    # Update last login
    user.last_login = datetime.utcnow()
    await session_db.commit()
    
    # Create session
    session_token = serialize_session(user.id)
    
    # Prepare response
    if redirect_after:
        response = RedirectResponse(url=redirect_after, status_code=303)
    else:
        response = RedirectResponse(url="/auth/dashboard", status_code=303)
    
    # Set session cookie
    response.set_cookie(
        key="vk_session",
        value=session_token,
        max_age=SESSION_EXPIRE_HOURS * 3600,
        httponly=True,
        secure=True,
        samesite="lax"
    )
    
    return response

@app.get("/auth/register", response_class=HTMLResponse)
async def register_page(request: Request, redirect: Optional[str] = None, error: Optional[str] = None):
    """Registration page"""
    return templates.TemplateResponse("register.html", {
        "request": request,
        "redirect_after": redirect,
        "error": error
    })

@app.post("/auth/register")
async def register_submit(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    redirect_after: Optional[str] = Form(None),
    session_db: AsyncSession = Depends(get_session)
):
    """Process registration form"""
    
    # Validation
    if password != password_confirm:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "redirect_after": redirect_after,
            "error": "Les mots de passe ne correspondent pas"
        })
    
    if not validate_password(password):
        return templates.TemplateResponse("register.html", {
            "request": request,
            "redirect_after": redirect_after,
            "error": "Le mot de passe ne respecte pas les exigences de sécurité"
        })
    
    # Check if user exists
    result = await session_db.execute(
        select(User).where(
            (User.username == username) | (User.email == email)
        )
    )
    if result.scalar_one_or_none():
        return templates.TemplateResponse("register.html", {
            "request": request,
            "redirect_after": redirect_after,
            "error": "Ce nom d'utilisateur ou email est déjà utilisé"
        })
    
    # Create user
    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password)
    )
    session_db.add(user)
    await session_db.commit()
    await session_db.refresh(user)
    
    # Create session
    session_token = serialize_session(user.id)
    
    # Prepare response
    if redirect_after:
        response = RedirectResponse(url=redirect_after, status_code=303)
    else:
        response = RedirectResponse(url="/auth/dashboard", status_code=303)
    
    # Set session cookie
    response.set_cookie(
        key="vk_session",
        value=session_token,
        max_age=SESSION_EXPIRE_HOURS * 3600,
        httponly=True,
        secure=True,
        samesite="lax"
    )
    
    return response

@app.get("/auth/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    current_user: User = Depends(get_current_user),
    session_db: AsyncSession = Depends(get_session),
    success: Optional[str] = None,
    error: Optional[str] = None
):
    """Dashboard page"""
    if not current_user:
        return RedirectResponse(url=f"/auth/login?redirect={request.url}", status_code=303)
    
    # Get user's API keys
    result = await session_db.execute(
        select(APIKey).where(APIKey.user_id == current_user.id).order_by(APIKey.created_at.desc())
    )
    api_keys = result.scalars().all()
    
    # Format API keys for display
    api_keys_formatted = []
    for key in api_keys:
        api_keys_formatted.append({
            'id': key.id,
            'key_name': key.key_name,
            'api_key': key.api_key,
            'scopes': [s.strip() for s in key.scopes.split(',')],
            'is_active': key.is_active,
            'created_at': key.created_at,
            'last_used': key.last_used,
            'expires_at': key.expires_at
        })
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": current_user.username,
        "api_keys": api_keys_formatted,
        "success": success,
        "error": error
    })

@app.post("/auth/dashboard/create-key")
async def create_key_web(
    request: Request,
    key_name: str = Form(...),
    scopes: List[str] = Form(...),
    expires_in_days: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    session_db: AsyncSession = Depends(get_session)
):
    """Create API key from web interface"""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=303)
    
    try:
        # Check if key_name already exists for this user
        result = await session_db.execute(
            select(APIKey).where(APIKey.key_name == key_name, APIKey.user_id == current_user.id)
        )
        if result.scalar_one_or_none():
            return RedirectResponse(
                url=f"/auth/dashboard?error=Une clé avec ce nom existe déjà",
                status_code=303
            )
        
        # Generate secure API key
        new_api_key = secrets.token_urlsafe(48)
        
        # Calculate expiration
        expires_at = None
        if expires_in_days and expires_in_days.strip():
            expires_at = datetime.utcnow() + timedelta(days=int(expires_in_days))
        
        # Create new key
        db_key = APIKey(
            key_name=key_name,
            api_key=new_api_key,
            user_id=current_user.id,
            user=current_user.username,  # For backward compatibility
            scopes=','.join(scopes),
            expires_at=expires_at
        )
        
        session_db.add(db_key)
        await session_db.commit()
        
        return RedirectResponse(
            url=f"/auth/dashboard?success=Clé API créée avec succès: {key_name}",
            status_code=303
        )
        
    except Exception as e:
        return RedirectResponse(
            url=f"/auth/dashboard?error=Erreur lors de la création de la clé: {str(e)}",
            status_code=303
        )

@app.post("/auth/dashboard/toggle-key/{key_id}")
async def toggle_key_web(
    key_id: int,
    current_user: User = Depends(get_current_user),
    session_db: AsyncSession = Depends(get_session)
):
    """Toggle API key status from web interface"""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=303)
    
    result = await session_db.execute(
        select(APIKey).where(APIKey.id == key_id, APIKey.user_id == current_user.id)
    )
    db_key = result.scalar_one_or_none()
    
    if not db_key:
        return RedirectResponse(
            url=f"/auth/dashboard?error=Clé API introuvable",
            status_code=303
        )
    
    db_key.is_active = not db_key.is_active
    await session_db.commit()
    
    status_text = "activée" if db_key.is_active else "désactivée"
    return RedirectResponse(
        url=f"/auth/dashboard?success=Clé API {status_text} avec succès",
        status_code=303
    )

@app.post("/auth/dashboard/delete-key/{key_id}")
async def delete_key_web(
    key_id: int,
    current_user: User = Depends(get_current_user),
    session_db: AsyncSession = Depends(get_session)
):
    """Delete API key from web interface"""
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=303)
    
    result = await session_db.execute(
        select(APIKey).where(APIKey.id == key_id, APIKey.user_id == current_user.id)
    )
    db_key = result.scalar_one_or_none()
    
    if not db_key:
        return RedirectResponse(
            url=f"/auth/dashboard?error=Clé API introuvable",
            status_code=303
        )
    
    await session_db.delete(db_key)
    await session_db.commit()
    
    return RedirectResponse(
        url=f"/auth/dashboard?success=Clé API supprimée avec succès",
        status_code=303
    )

@app.get("/auth/logout")
async def logout():
    """Logout and clear session"""
    response = RedirectResponse(url="/auth/login", status_code=303)
    response.delete_cookie(key="vk_session")
    return response

# ========== VERIFICATION ENDPOINT (ENHANCED FOR COOKIES) ==========

@app.get("/verify")
async def verify_api_key(
    request: Request,
    x_forwarded_uri: Optional[str] = Header(None),
    x_forwarded_host: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_session)
):
    """
    Enhanced verify endpoint for Traefik ForwardAuth
    Supports both API keys and session cookies
    """
    
    api_key = None
    user_name = "unknown"
    
    # Extract service name from forwarded host
    service = "unknown"
    if x_forwarded_host:
        service = x_forwarded_host.split('.')[0]
    
    # Method 1: Try Authorization header (Bearer token)
    if authorization and authorization.startswith("Bearer "):
        api_key = authorization.replace("Bearer ", "").strip()
    
    # Method 2: Try X-API-Key header
    elif x_api_key:
        api_key = x_api_key.strip()
    
    # Method 3: Try session cookie
    elif request.cookies.get("vk_session"):
        session_cookie = request.cookies.get("vk_session")
        user_id = deserialize_session(session_cookie)
        
        if user_id:
            # Get user from database
            user_result = await session.execute(
                select(User).where(User.id == user_id, User.is_active == True)
            )
            user = user_result.scalar_one_or_none()
            
            if user:
                user_name = user.username
                
                # Get user's first active API key for this service or any service
                api_key_result = await session.execute(
                    select(APIKey).where(
                        APIKey.user_id == user_id,
                        APIKey.is_active == True
                    ).order_by(APIKey.created_at.desc())
                )
                user_keys = api_key_result.scalars().all()
                
                # Find a key that matches the service or has global access
                for key in user_keys:
                    allowed_scopes = [s.strip() for s in key.scopes.split(',')]
                    if service in allowed_scopes or '*' in allowed_scopes:
                        api_key = key.api_key
                        break
    
    # If no authentication method found, check if it's a browser request
    if not api_key:
        # Check if this is a browser request (Accept header contains text/html)
        accept_header = request.headers.get("accept", "")
        user_agent = request.headers.get("user-agent", "")
        
        is_browser = (
            "text/html" in accept_header or
            "Mozilla" in user_agent
        )
        
        if is_browser:
            # Redirect browser users to login page
            redirect_url = f"https://auth.caronboulme.fr/auth/login"
            if x_forwarded_uri:
                # Add the original URL as redirect parameter
                from urllib.parse import quote
                redirect_url += f"?redirect={quote(f'https://{x_forwarded_host}{x_forwarded_uri}')}"
            
            return RedirectResponse(url=redirect_url, status_code=302)
        else:
            # Return 401 for API clients
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid authentication"
            )
    
    # Query database for API key
    result = await session.execute(
        select(APIKey).where(APIKey.api_key == api_key)
    )
    db_key = result.scalar_one_or_none()
    
    if not db_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    # Check if key is active
    if not db_key.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key is disabled"
        )
    
    # Check expiration
    if db_key.expires_at and db_key.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key has expired"
        )
    
    # Check scopes
    allowed_scopes = [s.strip() for s in db_key.scopes.split(',')]
    if service not in allowed_scopes and '*' not in allowed_scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: API key does not have permission for service '{service}'"
        )
    
    # Update last_used timestamp
    db_key.last_used = datetime.utcnow()
    await session.commit()
    
    # Use the original user name if available, otherwise fall back to API key user
    final_user = user_name if user_name != "unknown" else db_key.user
    
    # Return success with custom headers
    return JSONResponse(
        status_code=200,
        content={"valid": True, "user": final_user, "service": service},
        headers={
            "X-VK-User": final_user,
            "X-VK-Service": service,
            "X-VK-Scopes": db_key.scopes
        }
    )

# ========== ORIGINAL API ENDPOINTS ==========

@app.post("/keys", response_model=APIKeyResponse)
async def create_api_key(
    key_data: APIKeyCreate,
    session: AsyncSession = Depends(get_session)
):
    """
    Create a new API key (original API endpoint)
    """
    
    # Check if key_name already exists
    result = await session.execute(
        select(APIKey).where(APIKey.key_name == key_data.key_name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An API key with this name already exists"
        )
    
    # Generate secure API key
    new_api_key = secrets.token_urlsafe(48)
    
    # Calculate expiration
    expires_at = None
    if key_data.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=key_data.expires_in_days)
    
    # Create new key
    db_key = APIKey(
        key_name=key_data.key_name,
        api_key=new_api_key,
        user_id=0,  # For API-created keys, use 0 as default user_id
        user=key_data.user,
        scopes=','.join(key_data.scopes),
        expires_at=expires_at
    )
    
    session.add(db_key)
    await session.commit()
    await session.refresh(db_key)
    
    return APIKeyResponse(
        id=db_key.id,
        key_name=db_key.key_name,
        api_key=db_key.api_key,
        user=db_key.user,
        scopes=key_data.scopes,
        is_active=db_key.is_active,
        created_at=db_key.created_at,
        last_used=db_key.last_used,
        expires_at=db_key.expires_at
    )

@app.get("/keys", response_model=List[APIKeyList])
async def list_api_keys(
    session: AsyncSession = Depends(get_session)
):
    """
    List all API keys (without exposing the actual keys)
    """
    result = await session.execute(select(APIKey))
    keys = result.scalars().all()
    
    return [
        APIKeyList(
            id=key.id,
            key_name=key.key_name,
            user=key.user,
            scopes=[s.strip() for s in key.scopes.split(',')],
            is_active=key.is_active,
            created_at=key.created_at,
            last_used=key.last_used,
            expires_at=key.expires_at
        )
        for key in keys
    ]

@app.delete("/keys/{key_id}")
async def delete_api_key(
    key_id: int,
    session: AsyncSession = Depends(get_session)
):
    """
    Delete an API key
    """
    result = await session.execute(
        select(APIKey).where(APIKey.id == key_id)
    )
    db_key = result.scalar_one_or_none()
    
    if not db_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    await session.delete(db_key)
    await session.commit()
    
    return {"message": "API key deleted successfully"}

@app.patch("/keys/{key_id}/toggle")
async def toggle_api_key(
    key_id: int,
    session: AsyncSession = Depends(get_session)
):
    """
    Enable or disable an API key
    """
    result = await session.execute(
        select(APIKey).where(APIKey.id == key_id)
    )
    db_key = result.scalar_one_or_none()
    
    if not db_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )
    
    db_key.is_active = not db_key.is_active
    await session.commit()
    
    return {
        "message": f"API key {'enabled' if db_key.is_active else 'disabled'}",
        "is_active": db_key.is_active
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=False,
        log_level="info"
    )
