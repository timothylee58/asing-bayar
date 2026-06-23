"""Pydantic model validation tests — no network calls."""
import pytest
from decimal import Decimal
from datetime import date
from uuid import uuid4

from pydantic import ValidationError

from app.models.bill import BillCreate, ParticipantCreate
from app.models.payment import PaymentConfirm
from app.models.game import (
    TanggaGenerateRequest,
    TanggaLockRequest,
    RouletteSpinRequest,
    RouletteLockRequest,
)
from app.models.notification import PushTokenRegister


# ---------------------------------------------------------------------------
# BillCreate
# ---------------------------------------------------------------------------

def _bill_payload(**overrides):
    base = {
        "title": "Makan steamboat",
        "total_amount": Decimal("120.00"),
        "participants": [{"name": "Ali"}, {"name": "Mei"}],
    }
    base.update(overrides)
    return base


def test_bill_create_valid():
    b = BillCreate(**_bill_payload())
    assert b.title == "Makan steamboat"
    assert b.total_amount == Decimal("120.00")
    assert len(b.participants) == 2


def test_bill_create_defaults():
    b = BillCreate(**_bill_payload())
    assert b.emoji_tag == "🍽️"
    assert b.game_mode == "equal"
    assert b.description is None
    assert b.due_date is None


def test_bill_create_with_due_date():
    b = BillCreate(**_bill_payload(due_date=date(2026, 12, 31)))
    assert b.due_date == date(2026, 12, 31)


def test_bill_create_custom_emoji():
    b = BillCreate(**_bill_payload(emoji_tag="🍜"))
    assert b.emoji_tag == "🍜"


def test_bill_create_requires_title():
    with pytest.raises(ValidationError):
        BillCreate(**{k: v for k, v in _bill_payload().items() if k != "title"})


def test_bill_create_requires_total():
    with pytest.raises(ValidationError):
        BillCreate(**{k: v for k, v in _bill_payload().items() if k != "total_amount"})


def test_participant_create_phone_optional():
    p = ParticipantCreate(name="Siti")
    assert p.phone is None


def test_participant_create_with_phone():
    p = ParticipantCreate(name="Siti", phone="+60123456789")
    assert p.phone == "+60123456789"


# ---------------------------------------------------------------------------
# PaymentConfirm
# ---------------------------------------------------------------------------

def test_payment_confirm_valid():
    p = PaymentConfirm(
        participant_id=uuid4(),
        bill_id=uuid4(),
        amount=Decimal("30.00"),
        method="duitnow",
    )
    assert p.method == "duitnow"


def test_payment_confirm_requires_all_fields():
    with pytest.raises(ValidationError):
        PaymentConfirm(participant_id=uuid4(), bill_id=uuid4(), method="cash")


# ---------------------------------------------------------------------------
# TanggaGenerateRequest
# ---------------------------------------------------------------------------

def test_tangga_generate_request_valid():
    ids = [uuid4(), uuid4(), uuid4()]
    req = TanggaGenerateRequest(
        bill_id=uuid4(),
        participant_ids=ids,
        outcome_labels=["Kena kau!", "Lucky!", "Free!"],
    )
    assert len(req.participant_ids) == 3


def test_tangga_lock_request_valid():
    pid = str(uuid4())
    req = TanggaLockRequest(
        bill_id=uuid4(),
        result={pid: "Kena kau!"},
    )
    assert pid in req.result


# ---------------------------------------------------------------------------
# RouletteSpinRequest
# ---------------------------------------------------------------------------

def test_roulette_spin_request_defaults():
    req = RouletteSpinRequest(
        bill_id=uuid4(),
        participant_ids=[uuid4(), uuid4()],
    )
    assert req.include_belanja_segment is True


def test_roulette_spin_request_no_belanja():
    req = RouletteSpinRequest(
        bill_id=uuid4(),
        participant_ids=[uuid4()],
        include_belanja_segment=False,
    )
    assert req.include_belanja_segment is False


def test_roulette_lock_request_valid():
    req = RouletteLockRequest(
        bill_id=uuid4(),
        winner_participant_id=uuid4(),
        outcome="pays all",
    )
    assert req.outcome == "pays all"


# ---------------------------------------------------------------------------
# PushTokenRegister
# ---------------------------------------------------------------------------

def test_push_token_register_valid():
    t = PushTokenRegister(
        token="ExponentPushToken[abc123]",
        participant_id=str(uuid4()),
    )
    assert t.token.startswith("ExponentPushToken[")
