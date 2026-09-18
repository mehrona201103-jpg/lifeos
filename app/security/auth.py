"""
Password hashing, session management, dependencies
"""
from datetime import datetime, timezone
from typing import Optional
from fastapi import Request, HTTPException, status, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from app.config import settings
from app.database.connection import get_db
from app.database.models import User, UserRole

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
serializer = URLSafeTimedSerializer(settings.SECRET_KEY, salt="lifeos-session")

# Simple in-memory rate limit for login attempts (IP -> list of timestamps)
_login_attempts = {}
MAX_ATTEMPTS = 8
LOCKOUT_SECONDS = 300  # 5 minutes


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


def create_session_token(user_id: int) -> str:
    return serializer.dumps({"uid": user_id})


def decode_session_token(token: str, max_age: int = None) -> Optional[int]:
    if max_age is None:
        max_age = settings.SESSION_MAX_AGE
    try:
        data = serializer.loads(token, max_age=max_age)
        return data.get("uid")
    except (BadSignature, SignatureExpired):
        return None


def check_login_rate_limit(ip: str) -> bool:
    """Return True if allowed, False if locked out."""
    import time
    now = time.time()
    attempts = _login_attempts.get(ip, [])
    attempts = [t for t in attempts if now - t < LOCKOUT_SECONDS]
    _login_attempts[ip] = attempts
    return len(attempts) < MAX_ATTEMPTS


def record_login_attempt(ip: str):
    import time
    _login_attempts.setdefault(ip, []).append(time.time())


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not token:
        return None
    user_id = decode_session_token(token)
    if not user_id:
        return None
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active or user.is_blocked:
        return None
    return user


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )
    return user


def require_admin(request: Request, db: Session = Depends(get_db)) -> User:
    user = require_user(request, db)
    if user.role != UserRole.admin.value:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def set_session_cookie(response, user_id: int):
    token = create_session_token(user_id)
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.SESSION_MAX_AGE,
        httponly=True,
        secure=settings.ENVIRONMENT == "production",
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response):
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        secure=settings.ENVIRONMENT == "production",
        httponly=True,
        samesite="lax",
    )
