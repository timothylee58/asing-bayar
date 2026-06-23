import json
from unittest.mock import AsyncMock, MagicMock
from tests.conftest import FAKE_BILL_ID, FAKE_PARTICIPANT_ID, FAKE_PARTICIPANT_ID_2

GAME_RESULT_ROW = {
    "id": "a0000000-0000-4000-8000-000000000099",
    "bill_id": FAKE_BILL_ID,
    "game_type": "tangga",
    "seed": "abc12345",
    "result_json": {},
    "played_at": "2024-01-01T00:00:00+00:00",
    "is_locked": True,
}

LOCKED_STATE = json.dumps({
    "mode": "tangga",
    "participants": [FAKE_PARTICIPANT_ID],
    "outcome_labels": ["Pays"],
    "seed": "abc12345",
    "rungs": [],
    "result": {FAKE_PARTICIPANT_ID: "Pays"},
    "locked": True,
})

UNLOCKED_STATE = json.dumps({
    "mode": "tangga",
    "participants": [FAKE_PARTICIPANT_ID],
    "outcome_labels": ["Pays"],
    "seed": "abc12345",
    "rungs": [],
    "result": {},
    "locked": False,
})

TANGGA_GENERATE_PAYLOAD = {
    "bill_id": FAKE_BILL_ID,
    "participant_ids": [FAKE_PARTICIPANT_ID, FAKE_PARTICIPANT_ID_2],
    "outcome_labels": ["Pays the bill", "Goes free"],
}

TANGGA_LOCK_PAYLOAD = {
    "bill_id": FAKE_BILL_ID,
    "result": {FAKE_PARTICIPANT_ID: "Pays the bill"},
}


# --- Tangga generate ---

def test_generate_tangga_success(client, mock_redis):
    mock_redis.exists = AsyncMock(return_value=0)
    r = client.post("/api/game/tangga/generate", json=TANGGA_GENERATE_PAYLOAD)
    assert r.status_code == 200
    body = r.json()
    assert "seed" in body
    assert "rungs" in body
    assert body["n_lanes"] == 2


def test_generate_tangga_returns_valid_rungs(client, mock_redis):
    mock_redis.exists = AsyncMock(return_value=0)
    body = client.post("/api/game/tangga/generate", json=TANGGA_GENERATE_PAYLOAD).json()
    for rung in body["rungs"]:
        assert 0.05 <= rung["y"] <= 0.95
        assert rung["lane"] == 0  # n_lanes=2 → only lane 0 valid


def test_generate_tangga_already_locked_returns_409(client, mock_redis):
    mock_redis.exists = AsyncMock(return_value=1)
    mock_redis.get = AsyncMock(return_value=LOCKED_STATE)
    r = client.post("/api/game/tangga/generate", json=TANGGA_GENERATE_PAYLOAD)
    assert r.status_code == 409


# --- Tangga lock ---

def test_lock_tangga_success(client, mock_redis, mock_supabase):
    mock_redis.exists = AsyncMock(return_value=1)
    mock_redis.get = AsyncMock(return_value=UNLOCKED_STATE)
    mock_supabase.table.return_value.execute.return_value.data = [GAME_RESULT_ROW]
    r = client.post("/api/game/tangga/lock", json=TANGGA_LOCK_PAYLOAD)
    assert r.status_code == 200
    assert r.json()["is_locked"] is True


def test_lock_tangga_no_state_returns_404(client, mock_redis):
    mock_redis.get = AsyncMock(return_value=None)
    r = client.post("/api/game/tangga/lock", json=TANGGA_LOCK_PAYLOAD)
    assert r.status_code == 404


def test_lock_tangga_already_locked_returns_409(client, mock_redis):
    mock_redis.get = AsyncMock(return_value=LOCKED_STATE)
    r = client.post("/api/game/tangga/lock", json=TANGGA_LOCK_PAYLOAD)
    assert r.status_code == 409


# --- Roulette spin ---

ROULETTE_SPIN_PAYLOAD = {
    "bill_id": FAKE_BILL_ID,
    "participant_ids": [FAKE_PARTICIPANT_ID, FAKE_PARTICIPANT_ID_2],
}


def test_spin_roulette_success(client, mock_redis):
    mock_redis.exists = AsyncMock(return_value=0)
    r = client.post("/api/game/roulette/spin", json=ROULETTE_SPIN_PAYLOAD)
    assert r.status_code == 200
    body = r.json()
    assert "seed" in body
    assert "angular_velocity" in body
    assert 800 <= body["angular_velocity"] <= 1200


def test_spin_roulette_already_locked_returns_409(client, mock_redis):
    roulette_locked = json.dumps({"mode": "roulette", "locked": True, "seed": "x"})
    mock_redis.exists = AsyncMock(return_value=1)
    mock_redis.get = AsyncMock(return_value=roulette_locked)
    r = client.post("/api/game/roulette/spin", json=ROULETTE_SPIN_PAYLOAD)
    assert r.status_code == 409


# --- Roulette lock ---

ROULETTE_LOCK_PAYLOAD = {
    "bill_id": FAKE_BILL_ID,
    "winner_participant_id": FAKE_PARTICIPANT_ID,
    "outcome": "Pays the bill",
}

ROULETTE_UNLOCKED_STATE = json.dumps({
    "mode": "roulette",
    "participants": [FAKE_PARTICIPANT_ID],
    "seed": "abc12345",
    "angular_velocity": 950.0,
    "result": {},
    "locked": False,
})

ROULETTE_RESULT_ROW = {**GAME_RESULT_ROW, "game_type": "roulette"}


def test_lock_roulette_success(client, mock_redis, mock_supabase):
    mock_redis.get = AsyncMock(return_value=ROULETTE_UNLOCKED_STATE)
    mock_supabase.table.return_value.execute.return_value.data = [ROULETTE_RESULT_ROW]
    r = client.post("/api/game/roulette/lock", json=ROULETTE_LOCK_PAYLOAD)
    assert r.status_code == 200


def test_lock_roulette_no_state_returns_404(client, mock_redis):
    mock_redis.get = AsyncMock(return_value=None)
    r = client.post("/api/game/roulette/lock", json=ROULETTE_LOCK_PAYLOAD)
    assert r.status_code == 404
