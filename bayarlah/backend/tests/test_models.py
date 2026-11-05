"""Pydantic model validation tests — no network calls."""
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.bill import BillCreate, ParticipantCreate
from app.models.game import (
    RouletteLockRequest,
    RouletteSpinRequest,
    TanggaGenerateRequest,
    TanggaLockRequest,
)
from app.models.notification import PushTokenRegister
from app.models.payment import PaymentConfirm

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


@pytest.mark.parametrize("given,expected", [
    ("+60123456789", "60123456789"),      # wa.me wants digits only
    ("0123456789", "60123456789"),        # local Malaysian number
    ("012-345 6789", "60123456789"),      # punctuation from a text field
    ("+65 9123 4567", "6591234567"),      # other countries keep their code
])
def test_participant_phone_is_normalised(given, expected):
    assert ParticipantCreate(name="Siti", phone=given).phone == expected


@pytest.mark.parametrize("bad", ["123", "abc", "1" * 16])
def test_participant_phone_must_be_plausible(bad):
    with pytest.raises(ValidationError):
        ParticipantCreate(name="Siti", phone=bad)


def test_blank_phone_is_treated_as_none():
    assert ParticipantCreate(name="Siti", phone="  ").phone is None


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


def test_payment_confirm_requires_ids_and_method():
    with pytest.raises(ValidationError):
        PaymentConfirm(participant_id=uuid4(), bill_id=uuid4())  # no method
    with pytest.raises(ValidationError):
        PaymentConfirm(bill_id=uuid4(), method="cash")           # no participant


def test_payment_confirm_amount_is_optional_because_the_server_decides_it():
    assert PaymentConfirm(participant_id=uuid4(), bill_id=uuid4(), method="cash").amount is None


@pytest.mark.parametrize("amount", ["0", "-1", "1.234"])
def test_payment_confirm_rejects_nonsense_amounts(amount):
    with pytest.raises(ValidationError):
        PaymentConfirm(participant_id=uuid4(), bill_id=uuid4(), method="cash", amount=amount)


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


def test_tangga_lock_request_takes_lane_picks_not_results():
    a, b = uuid4(), uuid4()
    req = TanggaLockRequest(bill_id=uuid4(), lanes={str(a): 0, str(b): 1})
    assert req.lanes == {a: 0, b: 1}
    assert not hasattr(req, "result")


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
        participant_ids=[uuid4(), uuid4()],
        include_belanja_segment=False,
    )
    assert req.include_belanja_segment is False


def test_roulette_needs_at_least_two_players():
    with pytest.raises(ValidationError):
        RouletteSpinRequest(bill_id=uuid4(), participant_ids=[uuid4()])


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
    t = PushTokenRegister(token="ExponentPushToken[abc123]")
    assert t.token.startswith("ExponentPushToken[")


def test_push_token_identity_is_not_client_supplied():
    t = PushTokenRegister(token="ExponentPushToken[abc123]", user_id="someone-else", participant_id="x")
    assert not hasattr(t, "user_id") and not hasattr(t, "participant_id")
