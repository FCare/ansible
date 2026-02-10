#!/usr/bin/env python3
"""
Voight-Kampff - API Key Authentication Service
Inspired by Blade Runner's empathy test
"""

import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import FastAPI, Header, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, Boolean, Text, select
import uvicorn

# Configuration
DB_PATH = os.getenv("VK_DB_PATH", "/data/voight-kampff.db")
SECRET_KEY = os.getenv("VK_SECRET_KEY", "change-this-secret-key-for-production")
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# Database Models
class Base(DeclarativeBase):
    pass


class APIKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    key_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    api_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user: Mapped[str] = mapped_column(String(255))
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


# FastAPI app
app = FastAPI(
    title="Voight-Kampff",
    description="API Key Authentication Service - Testing for humanity, one request at a time",
    version="1.0.0"
)


@app.on_event("startup")
async def startup_event():
    await init_db()
    print("🔍 Voight-Kampff authentication service is running")
    print(f"📁 Database: {DB_PATH}")


@app.get("/")
async def root():
    return {
        "service": "Voight-Kampff",
        "version": "1.0.0",
        "description": "API Key Authentication Service",
        "endpoints": {
            "verify": "/verify - Verify API key (used by Traefik ForwardAuth)",
            "keys": "/keys - Manage API keys",
            "health": "/health - Health check"
        }
    }


@app.get("/health")
async def health():
    return {"status": "operational", "test": "positive"}


@app.get("/verify")
async def verify_api_key(
    x_forwarded_uri: Optional[str] = Header(None),
    x_forwarded_host: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_session)
):
    """
    Verify API key for Traefik ForwardAuth
    
    Expected header: Authorization: Bearer <api_key>
    """
    
    # Extract API key from Authorization header
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header"
        )
    
    api_key = authorization.replace("Bearer ", "").strip()
    
    # Extract service name from forwarded host
    service = "unknown"
    if x_forwarded_host:
        # Extract subdomain (e.g., "tts" from "tts.mon_url.com")
        service = x_forwarded_host.split('.')[0]
    
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
    
    # Return success with custom headers
    return JSONResponse(
        status_code=200,
        content={"valid": True, "user": db_key.user, "service": service},
        headers={
            "X-VK-User": db_key.user,
            "X-VK-Service": service,
            "X-VK-Scopes": db_key.scopes
        }
    )


@app.post("/keys", response_model=APIKeyResponse)
async def create_api_key(
    key_data: APIKeyCreate,
    session: AsyncSession = Depends(get_session)
):
    """
    Create a new API key
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
