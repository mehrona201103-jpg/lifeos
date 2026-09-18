from datetime import date, timedelta
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from pathlib import Path

from app.database.connection import get_db
from app.database.models import Transaction
from app.security.auth import get_current_user

router = APIRouter(prefix="/finance", tags=["Finance"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

EXPENSE_CATS = ["Food", "Transport", "Shopping", "Entertainment", "Education", "Subscriptions", "Other"]
INCOME_CATS = ["Salary", "Freelance", "Business", "Gift", "Other"]


@router.get("", response_class=HTMLResponse)
async def finance_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    txs = db.query(Transaction).filter(Transaction.user_id == user.id).order_by(
        Transaction.transaction_date.desc(), Transaction.created_at.desc()
    ).limit(50).all()

    def sum_type(t, start=None, end=None):
        q = db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
            Transaction.user_id == user.id, Transaction.type == t
        )
        if start:
            q = q.filter(Transaction.transaction_date >= start)
        if end:
            q = q.filter(Transaction.transaction_date <= end)
        return q.scalar() or 0

    total_income = sum_type("income")
    total_expense = sum_type("expense")
    balance = total_income - total_expense

    return templates.TemplateResponse("finance/index.html", {"request": request, 
        "user": user, "active": "finance", "transactions": txs,
        "balance": balance, "total_income": total_income, "total_expense": total_expense,
        "income_today": sum_type("income", today, today),
        "expense_today": sum_type("expense", today, today),
        "income_week": sum_type("income", week_start, today),
        "expense_week": sum_type("expense", week_start, today),
        "income_month": sum_type("income", month_start, today),
        "expense_month": sum_type("expense", month_start, today),
        "expense_cats": EXPENSE_CATS, "income_cats": INCOME_CATS,
        "currency": user.currency, "today": today.isoformat(),
    })


@router.post("/create")
async def create_tx(
    request: Request,
    amount: float = Form(...),
    type: str = Form(...),
    category: str = Form(...),
    description: str = Form(""),
    transaction_date: str = Form(""),
    currency: str = Form("TJS"),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if amount <= 0:
        return RedirectResponse("/finance", status_code=303)
    if type not in ("income", "expense"):
        return RedirectResponse("/finance", status_code=303)
    td = date.today()
    if transaction_date:
        try:
            td = date.fromisoformat(transaction_date)
        except ValueError:
            pass
    tx = Transaction(
        user_id=user.id, amount=round(amount, 2), type=type, category=category,
        description=description.strip() or None, currency=currency or user.currency,
        transaction_date=td
    )
    db.add(tx)
    db.commit()
    return RedirectResponse("/finance", status_code=303)


@router.post("/{tx_id}/delete")
async def delete_tx(tx_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", status_code=303)
    tx = db.query(Transaction).filter(Transaction.id == tx_id, Transaction.user_id == user.id).first()
    if tx:
        db.delete(tx)
        db.commit()
    return RedirectResponse("/finance", status_code=303)
