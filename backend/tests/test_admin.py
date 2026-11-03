from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api_billing import GrantPayload, admin_claims, admin_grant, admin_me
from app.config import get_settings
from app.db.models import AuditLog, Base, User, UserPlan


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    tables = [User.__table__, UserPlan.__table__, AuditLog.__table__]
    Base.metadata.create_all(engine, tables=tables)
    with Session(engine) as session:
        yield session


def test_non_admin_gets_404(monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_emails", ["admin@example.com"])
    from fastapi.security import HTTPAuthorizationCredentials
    from app.auth import supabase
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")
    monkeypatch.setattr(supabase.SupabaseAuthProvider, "get_claims", lambda self, value: {"email": "other@example.com"})
    with pytest.raises(HTTPException) as exc:
        admin_claims(credentials)
    assert exc.value.status_code == 404


def test_manual_grant_updates_balance(db):
    user = User(id=uuid4(), email="buyer@example.com")
    plan = UserPlan(user_id=user.id, plan="trial", message_quota=0, document_quota=3, messages_used=0,
                    token_balance=0, trial_tokens_used=0, trial_period_start=datetime.utcnow())
    db.add_all([user, plan])
    db.commit()
    claims = {"email": "admin@example.com"}
    admin_grant(GrantPayload(email=user.email, tokens=5000, notify_user=False), claims=claims, db=db)
    db.refresh(plan)
    assert plan.token_balance == 5000


def test_premium_extension_math(db):
    user = User(id=uuid4(), email="buyer@example.com")
    existing = datetime.utcnow() + timedelta(days=10)
    plan = UserPlan(user_id=user.id, plan="trial", message_quota=0, document_quota=3, messages_used=0,
                    token_balance=0, trial_tokens_used=0, trial_period_start=datetime.utcnow(), premium_until=existing)
    db.add_all([user, plan])
    db.commit()
    admin_grant(GrantPayload(email=user.email, premium_days=90, notify_user=False), claims={"email": "admin@example.com"}, db=db)
    db.refresh(plan)
    assert plan.premium_until.date() == (existing + timedelta(days=90)).date()


def test_admin_me_returns_true():
    assert admin_me({"email": "admin@example.com"})["is_admin"] is True


def test_full_name_sync(monkeypatch, db):
    from types import SimpleNamespace
    from app.api_documents import current_user
    import app.api_documents as documents

    user_id = uuid4()
    db.add(User(id=user_id, email="old@example.com", full_name="Old Name"))
    db.commit()

    class Provider:
        def get_claims(self, credentials):
            return {"email": "new@example.com", "user_metadata": {"full_name": "New Name"}}
        def get_user_id(self, credentials):
            return str(user_id)

    monkeypatch.setattr(documents, "get_auth_provider", lambda: Provider())
    import asyncio
    resolved = asyncio.run(current_user(SimpleNamespace(credentials="token"), db))
    db.expire_all()
    user = db.get(User, user_id)
    assert resolved == user_id
    assert user.email == "new@example.com"
    assert user.full_name == "New Name"
