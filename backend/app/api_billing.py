import threading
import time
from datetime import datetime, timedelta
from html import escape
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api_documents import current_user
from app.auth.factory import get_auth_provider
from app.config import get_settings
from app.db.models import AuditLog, RedeemCode, User, UsageEvent
from app.db.session import get_db
from app.mailer import mailer_configured, mailer_status, send_email
from app.notify import configured_providers, send_notification
from app.usage import apply_daily_reset, apply_weekly_reset, code_hash, documents_used, ensure_plan, normalize_code, trial_remaining, valid_admin_key

router = APIRouter(tags=["credits"])
bearer = HTTPBearer(auto_error=False)
failures: dict[UUID, list[float]] = {}
failures_lock = threading.Lock()
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class CreateCodes(BaseModel):
    count: int = Field(gt=0, le=1000)
    tokens: int = Field(gt=0)
    premium_days: int = 0


class RedeemPayload(BaseModel):
    code: str


class GrantPayload(BaseModel):
    email: str
    tokens: int = 0
    premium_days: int = 0
    note: str = ""
    notify_user: bool = True


def generate_code() -> str:
    import secrets
    blocks = ["".join(secrets.choice(ALPHABET) for _ in range(4)) for _ in range(3)]
    return "-".join(blocks)


def admin_claims(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    settings = get_settings()
    claims = get_auth_provider().get_claims(credentials)
    email = str(claims.get("email", "")).strip().lower()
    if email not in {value.lower() for value in settings.admin_emails}:
        raise HTTPException(status_code=404, detail="Not found")
    return claims


def award_email(user: User, tokens: int, premium_days: int, plan, reason: str) -> tuple[str, str, str]:
    settings = get_settings()
    first_name = (user.full_name or "").split()[0] if user.full_name else "there"
    subject = "Your ClosedAI credits have been added"
    text = (
        f"Hi {first_name},\n\n"
        f"{reason}\n"
        f"Credits added: {tokens:,}\n"
        f"Premium days added: {premium_days}\n"
        f"New token balance: {plan.token_balance:,}\n"
        f"Open ClosedAI: {settings.frontend_url.rstrip('/')}/app"
    )
    html = (
        f"<p>Hi {escape(first_name)},</p>"
        f"<p>{escape(reason)}</p>"
        f"<p>Credits added: {tokens:,}<br>Premium days added: {premium_days}<br>"
        f"New token balance: {plan.token_balance:,}</p>"
        f'<p><a href="{escape(settings.frontend_url.rstrip("/") + "/app", quote=True)}">Open ClosedAI</a></p>'
    )
    return subject, text, html


@router.get("/admin/me")
def admin_me(claims=Depends(admin_claims)) -> dict[str, object]:
    settings = get_settings()
    return {"is_admin": True, "notifier_configured": bool(configured_providers()), "mailer_configured": mailer_configured(), "mail_provider": settings.mail_provider, "mailer_status": mailer_status()}


@router.get("/admin/notify-test")
def notify_test(claims=Depends(admin_claims)) -> list[dict[str, object]]:
    return send_notification("ClosedAI notification test. If you received this, alerts are working.")


@router.get("/admin/email-test")
def email_test(claims=Depends(admin_claims)) -> dict[str, object]:
    email = str(claims.get("email", "")).strip()
    settings = get_settings()
    if not mailer_configured():
        return {"provider": settings.mail_provider, "ok": False, "error": "mailer disabled"}
    sent = send_email(email, "ClosedAI email test", "This is a ClosedAI email test.", "<p>This is a ClosedAI email test.</p>")
    return {"provider": settings.mail_provider, "ok": sent, "error": "" if sent else "email delivery failed"}


@router.get("/admin/llm-test")
def llm_test(claims=Depends(admin_claims)) -> dict[str, object]:
    import time
    from app.agent.llm import create_llm_provider
    settings = get_settings()
    started = time.monotonic()
    try:
        provider = create_llm_provider(settings)
        provider.complete("Reply with one short word.", [{"role": "user", "content": "Reply with OK."}])
        text, calls, _, _ = provider.complete(
            "Use the test tool exactly once.",
            [{"role": "user", "content": "Run the test tool."}],
            [{"name": "test_tool", "description": "Return a successful test result.", "input_schema": {"type": "object", "properties": {}}}],
        )
        ok = bool(text or calls)
        return {"provider": settings.llm_provider, "model": settings.llm_model or settings.anthropic_model,
                "ok": ok, "latency_ms": round((time.monotonic() - started) * 1000),
                "tool_calls_ok": bool(calls), "error": "" if ok else "provider returned no response"}
    except Exception as exc:
        return {"provider": settings.llm_provider, "model": settings.llm_model or settings.anthropic_model,
                "ok": False, "latency_ms": round((time.monotonic() - started) * 1000),
                "tool_calls_ok": False, "error": str(exc)}


@router.post("/admin/codes")
def create_codes(payload: CreateCodes, x_admin_key: str | None = Header(default=None), db: Session = Depends(get_db)) -> list[str]:
    if not valid_admin_key(x_admin_key):
        raise HTTPException(status_code=401, detail="Invalid admin key")
    codes = []
    rows = []
    for _ in range(payload.count):
        while True:
            plain = generate_code()
            if db.scalar(select(RedeemCode).where(RedeemCode.code_hash == code_hash(plain))) is None:
                break
        codes.append(plain)
        rows.append(RedeemCode(code_hash=code_hash(plain), plan_name="paid", message_quota=0, document_quota=0,
                               duration_days=payload.premium_days, token_grant=payload.tokens))
    db.add_all(rows)
    db.commit()
    return codes


@router.post("/redeem")
def redeem(payload: RedeemPayload, user_id: UUID = Depends(current_user), db: Session = Depends(get_db), background_tasks: BackgroundTasks = BackgroundTasks()) -> dict[str, object]:
    now = time.monotonic()
    with failures_lock:
        attempts = [stamp for stamp in failures.get(user_id, []) if now - stamp < 3600]
        if len(attempts) >= 5:
            raise HTTPException(status_code=429, detail="Too many attempts. Please try again later.")
    normalized = normalize_code(payload.code)
    row = db.scalar(select(RedeemCode).where(RedeemCode.code_hash == code_hash(normalized)))
    if row is None or row.redeemed_at is not None:
        with failures_lock:
            failures[user_id] = attempts + [now]
        raise HTTPException(status_code=400, detail="Invalid or already used code.")
    row = db.get(RedeemCode, row.id, with_for_update=True)
    if row.redeemed_at is not None:
        raise HTTPException(status_code=400, detail="Invalid or already used code.")
    plan = ensure_plan(db, user_id)
    tokens = getattr(row, "token_grant", 0)
    plan.token_balance += tokens
    if row.duration_days:
        start = max(datetime.utcnow(), plan.premium_until or datetime.min)
        plan.premium_until = start + timedelta(days=row.duration_days)
    plan.has_purchased = True
    row.redeemed_by = user_id
    row.redeemed_at = datetime.utcnow()
    user = db.get(User, user_id)
    db.commit()
    if user and user.email and mailer_configured():
        subject, text, html = award_email(user, tokens, row.duration_days or 0, plan, "Your redeem code was applied successfully.")
        background_tasks.add_task(send_email, user.email, subject, text, html)
    return {"tokens_added": tokens, "premium_until": plan.premium_until.isoformat() if plan.premium_until else None}


@router.post("/admin/grant")
def admin_grant(payload: GrantPayload, claims=Depends(admin_claims), db: Session = Depends(get_db), background_tasks: BackgroundTasks = BackgroundTasks()) -> dict[str, object]:
    user = db.scalar(select(User).where(func.lower(User.email) == payload.email.strip().lower()))
    if user is None or payload.tokens < 0 or payload.premium_days < 0 or not (payload.tokens or payload.premium_days):
        raise HTTPException(status_code=400, detail="Unable to grant credits.")
    plan = ensure_plan(db, user.id)
    plan.token_balance += payload.tokens
    if payload.premium_days:
        plan.premium_until = max(datetime.utcnow(), plan.premium_until or datetime.min) + timedelta(days=payload.premium_days)
    plan.has_purchased = plan.has_purchased or bool(payload.tokens)
    db.add(AuditLog(admin_email=str(claims.get("email", "")), target_user_id=user.id, change=f"{payload.note}; tokens={payload.tokens}; premium_days={payload.premium_days}".strip("; ")))
    db.commit()
    if payload.notify_user and user.email and mailer_configured():
        subject, text, html = award_email(user, payload.tokens, payload.premium_days, plan, payload.note or "Credits were added to your account.")
        background_tasks.add_task(send_email, user.email, subject, text, html)
    return {"status": "granted"}


@router.get("/admin/usage-summary")
def usage_summary(claims=Depends(admin_claims), db: Session = Depends(get_db)) -> dict[str, object]:
    def summary(days: int) -> dict[str, object]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        rows = db.scalars(select(UsageEvent).where(UsageEvent.created_at >= cutoff)).all()
        count = len(rows)
        return {"answers": count, "average_input_tokens": round(sum(row.input_tokens for row in rows) / count, 2) if count else 0,
                "average_output_tokens": round(sum(row.output_tokens for row in rows) / count, 2) if count else 0,
                "per_model": {model: sum(1 for row in rows if row.model == model) for model in {row.model for row in rows}}}
    return {"last_7_days": summary(7), "last_30_days": summary(30)}


@router.get("/me/usage")
def usage(user_id: UUID = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    settings = get_settings()
    if settings.mode != "hosted":
        return {"plan": "unlimited", "tokens_available": None, "trial_tokens_remaining": None, "trial_resets_at": None,
                "token_balance": None, "premium_until": None, "daily_used": None, "daily_cap": None,
                "documents_used": 0, "document_quota": None}
    plan = apply_weekly_reset(db, ensure_plan(db, user_id))
    premium = plan.premium_until is not None and plan.premium_until > datetime.utcnow()
    if premium:
        apply_daily_reset(db, plan)
    used = documents_used(db, user_id)
    quota = settings.premium_documents if premium else (settings.paid_documents if plan.has_purchased else settings.trial_documents)
    return {"plan": "premium" if premium else ("paid" if plan.has_purchased else "trial"),
            "tokens_available": trial_remaining(plan) + plan.token_balance,
            "trial_tokens_remaining": trial_remaining(plan),
            "trial_resets_at": (plan.trial_period_start + timedelta(days=7)).isoformat(),
            "token_balance": plan.token_balance,
            "premium_until": plan.premium_until.isoformat() if plan.premium_until else None,
            "daily_used": plan.daily_count if premium else None,
            "daily_cap": settings.premium_daily_cap if premium else None,
            "documents_used": used,
            "document_quota": quota}
