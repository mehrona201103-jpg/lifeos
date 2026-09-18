"""
Auth routes: register, login, logout, admin login
"""
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pathlib import Path
import re
import logging

from app.database.connection import get_db, ensure_tables
from app.database.models import User, UserRole
from app.security.auth import (
    hash_password, verify_password, set_session_cookie, clear_session_cookie,
    get_current_user, check_login_rate_limit, record_login_attempt, get_client_ip
)
from app.config import settings

logger = logging.getLogger("lifeos.auth")
router = APIRouter(tags=["Auth"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def validate_password(password: str) -> Optional[str]:
    if len(password) < 6:
        return "Пароль должен быть не менее 6 символов"
    return None


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, db: Session = Depends(get_db)):
    ensure_tables()
    user = get_current_user(request, db)
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(
        "auth/register.html",
        {"request": request, "error": None, "username": "", "display_name": "", "email": ""},
    )


@router.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    display_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: Session = Depends(get_db),
):
    ensure_tables()
    error = None
    username = username.strip().lower()
    email = email.strip().lower()
    display_name = display_name.strip()

    if len(username) < 3 or len(username) > 30:
        error = "Имя пользователя: от 3 до 30 символов"
    elif not re.match(r"^[a-z0-9_]+$", username):
        error = "Только латиница, цифры и _ (без пробелов)"
    elif len(display_name) < 1:
        error = "Укажите отображаемое имя"
    elif not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        error = "Некорректный email"
    elif password != password_confirm:
        error = "Пароли не совпадают"
    else:
        pwd_err = validate_password(password)
        if pwd_err:
            error = pwd_err
        else:
            try:
                if db.query(User).filter(User.username == username).first():
                    error = "Это имя пользователя уже занято"
                elif db.query(User).filter(User.email == email).first():
                    error = "Этот email уже зарегистрирован"
            except Exception as e:
                logger.exception("DB check error: %s", e)
                # retry table create once
                ensure_tables()
                try:
                    if db.query(User).filter(User.username == username).first():
                        error = "Это имя пользователя уже занято"
                    elif db.query(User).filter(User.email == email).first():
                        error = "Этот email уже зарегистрирован"
                except Exception as e2:
                    logger.exception("DB check retry failed: %s", e2)
                    error = f"Ошибка базы данных: {type(e2).__name__}. Проверьте DATABASE_URL и PostgreSQL."

    if error:
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": error, "username": username,
             "display_name": display_name, "email": email},
            status_code=400,
        )

    try:
        user = User(
            username=username,
            display_name=display_name,
            email=email,
            hashed_password=hash_password(password),
            role=UserRole.user.value,
            theme="light",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        logger.exception("Register commit failed: %s", e)
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request,
             "error": f"Не удалось создать аккаунт ({type(e).__name__}). Попробуйте другой email.",
             "username": username, "display_name": display_name, "email": email},
            status_code=400,
        )

    response = RedirectResponse("/dashboard", status_code=303)
    set_session_cookie(response, user.id)
    return response


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    ensure_tables()
    user = get_current_user(request, db)
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(
        "auth/login.html",
        {"request": request, "error": None, "login": ""},
    )


@router.post("/login")
async def login(
    request: Request,
    login: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    ensure_tables()
    ip = get_client_ip(request)
    if not check_login_rate_limit(ip):
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Слишком много попыток. Подождите.", "login": login},
            status_code=429,
        )

    login_val = login.strip().lower()
    try:
        user = db.query(User).filter(
            or_(User.email == login_val, User.username == login_val)
        ).first()
    except Exception as e:
        logger.exception("Login DB error: %s", e)
        ensure_tables()
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Ошибка базы данных. Попробуйте позже.", "login": login},
            status_code=500,
        )

    if not user or not verify_password(password, user.hashed_password):
        record_login_attempt(ip)
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Неверный email/имя или пароль", "login": login},
            status_code=401,
        )

    if user.is_blocked or not user.is_active:
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Аккаунт заблокирован", "login": login},
            status_code=403,
        )

    try:
        user.last_login = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        db.rollback()

    response = RedirectResponse("/dashboard", status_code=303)
    set_session_cookie(response, user.id)
    return response


@router.get("/logout")
@router.post("/logout")
async def logout(request: Request):
    response = RedirectResponse("/", status_code=303)
    clear_session_cookie(response)
    return response


@router.get("/admin-login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    try:
        ensure_tables()
        return templates.TemplateResponse(
            "auth/admin_login.html",
            {"request": request, "error": None},
        )
    except Exception as e:
        logger.exception("admin-login page error: %s", e)
        return HTMLResponse(
            f"<h1>Admin Login</h1><p>Error loading page: {type(e).__name__}</p>"
            f"<form method='post'><input name='password' type='password'/>"
            f"<button type='submit'>Login</button></form>",
            status_code=200,
        )


@router.post("/admin-login")
async def admin_login(
    request: Request,
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    ensure_tables()
    ip = get_client_ip(request)
    if not check_login_rate_limit(ip):
        return templates.TemplateResponse(
            "auth/admin_login.html",
            {"request": request, "error": "Слишком много попыток."},
            status_code=429,
        )

    if not settings.ADMIN_PASSWORD or password != settings.ADMIN_PASSWORD:
        record_login_attempt(ip)
        return templates.TemplateResponse(
            "auth/admin_login.html",
            {"request": request, "error": "Неверный пароль администратора"},
            status_code=401,
        )

    try:
        admin = db.query(User).filter(User.role == UserRole.admin.value).first()
        if not admin:
            admin = User(
                username="admin",
                display_name="Administrator",
                email="admin@lifeos.local",
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
                role=UserRole.admin.value,
                theme="light",
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
        else:
            admin.last_login = datetime.now(timezone.utc)
            db.commit()
    except Exception as e:
        db.rollback()
        logger.exception("Admin login DB error: %s", e)
        return templates.TemplateResponse(
            "auth/admin_login.html",
            {"request": request, "error": f"Ошибка БД: {type(e).__name__}. Проверьте PostgreSQL."},
            status_code=500,
        )

    response = RedirectResponse("/admin", status_code=303)
    set_session_cookie(response, admin.id)
    return response
