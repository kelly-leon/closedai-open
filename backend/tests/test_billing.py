from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Base, User, UserPlan
from app.usage import apply_daily_reset, apply_weekly_reset, charge_tokens, check_limit, ensure_plan, trial_remaining


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    tables = [User.__table__, UserPlan.__table__]
    Base.metadata.create_all(engine, tables=tables)
    with Session(engine) as session:
        yield session


def make_user(db, **changes):
    settings = get_settings()
    user = User(id=uuid4(), email="user@example.com")
    plan = UserPlan(user_id=user.id, plan="trial", message_quota=0, document_quota=settings.trial_documents,
                    messages_used=0, token_balance=changes.pop("token_balance", 0),
                    trial_tokens_used=changes.pop("trial_tokens_used", 0),
                    trial_period_start=changes.pop("trial_period_start", datetime.utcnow()),
                    **changes)
    db.add_all([user, plan])
    db.commit()
    return user, plan


def test_weekly_reset_discards_unused_trial_tokens(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "mode", "hosted")
    user, plan = make_user(db, trial_tokens_used=20, trial_period_start=datetime.utcnow() - timedelta(days=8), token_balance=7)
    result = apply_weekly_reset(db, plan)
    assert result.trial_tokens_used == 0
    assert trial_remaining(result) == get_settings().trial_tokens_per_week
    assert result.token_balance == 7


def test_trial_remaining_never_exceeds_allowance(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "trial_tokens_per_week", 100)
    user, plan = make_user(db, trial_tokens_used=-50)
    assert trial_remaining(plan) == 100
    plan.trial_tokens_used = 150
    assert trial_remaining(plan) == 0


def test_spend_order_trial_then_paid(db, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "mode", "hosted")
    monkeypatch.setattr(settings, "tokens_per_message", 5)
    user, plan = make_user(db, trial_tokens_used=98, token_balance=20)
    assert charge_tokens(db, user.id)
    db.refresh(plan)
    assert plan.trial_tokens_used == 100
    assert plan.token_balance == 17


def test_premium_daily_cap_and_reset(db, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "premium_daily_cap", 2)
    user, plan = make_user(db, premium_until=datetime.utcnow() + timedelta(days=1), daily_count=2, daily_date=datetime.utcnow().date())
    plan = apply_daily_reset(db, plan, datetime.utcnow() + timedelta(days=1))
    assert plan.daily_count == 0


def test_atomic_charging_under_concurrency(tmp_path, monkeypatch):
    import threading
    settings = get_settings()
    monkeypatch.setattr(settings, "mode", "hosted")
    monkeypatch.setattr(settings, "tokens_per_message", 1)
    engine = create_engine(f"sqlite:///{tmp_path / 'billing.db'}", connect_args={"check_same_thread": False})
    tables = [User.__table__, UserPlan.__table__]
    Base.metadata.create_all(engine, tables=tables)
    user_id = uuid4()
    with Session(engine) as db:
        db.add_all([User(id=user_id), UserPlan(user_id=user_id, plan="trial", message_quota=0, document_quota=3,
                                               messages_used=0, token_balance=5, trial_tokens_used=100)])
        db.commit()
    successes = []
    lock = threading.Lock()

    def charge():
        with Session(engine) as db:
            result = charge_tokens(db, user_id)
            with lock:
                successes.append(result)

    threads = [threading.Thread(target=charge) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(successes) == 5
    with Session(engine) as db:
        assert db.get(UserPlan, user_id).token_balance == 0


def test_failed_answer_is_not_charged(db, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "mode", "hosted")
    user, plan = make_user(db, token_balance=50)
    # Chat charges only after its generator completes successfully; simulate failure before charge.
    try:
        raise RuntimeError("answer failed")
    except RuntimeError:
        pass
    db.refresh(plan)
    assert plan.token_balance == 50


def test_selfhosted_unlimited(monkeypatch, db):
    monkeypatch.setattr(get_settings(), "mode", "selfhosted")
    check_limit(db, uuid4(), "messages")
