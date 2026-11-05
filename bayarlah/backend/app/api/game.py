"""Who-pays games. The server is authoritative for every outcome.

Previously the client reported results (the roulette winner, the tangga result
map, the dadu total) and the endpoints needed no login, so anyone could decide
who paid. Now:

* every endpoint needs the organiser's token and ownership of the bill;
* participants must be exactly the bill's participants;
* the outcome is derived on the server from a CSPRNG seed (reproducible/auditable
  from that seed) and committed when the game starts, so it cannot be re-rolled
  by calling start again;
* locking is atomic (Redis SET NX plus a unique DB row per bill).
"""
import json
import random
from decimal import ROUND_HALF_UP, Decimal

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from supabase import Client

from app.core.access import (
    assert_same_participants,
    first,
    is_unique_violation,
    require_bill_owner,
)
from app.core.dependencies import get_current_user, get_redis, get_supabase
from app.models.game import (
    DaduLockRequest,
    DaduRollRequest,
    RouletteLockRequest,
    RouletteSpinRequest,
    TanggaGenerateRequest,
    TanggaLockRequest,
)
from app.services.money import to_money
from app.utils.game_logic import generate_tangga_rungs, make_seed, traverse_tangga

router = APIRouter()

# Kept for modules/tests that import the old private names.
_make_seed = make_seed
_generate_tangga_rungs = generate_tangga_rungs
_traverse_tangga = traverse_tangga

STATE_TTL = 3600
LOCKED_TTL = 86400
DEFAULT_ROULETTE_OUTCOME = "Kena kau lah!"


def _state_key(bill_id) -> str:
    return f"game_state:{bill_id}"


async def _load_state(redis: aioredis.Redis, bill_id) -> dict | None:
    raw = await redis.get(_state_key(bill_id))
    return json.loads(raw) if raw else None


def _assert_not_played(supabase: Client, bill_id) -> None:
    res = supabase.table("game_results").select("id").eq("bill_id", str(bill_id)).limit(1).execute()
    if first(res):
        raise HTTPException(status_code=409, detail="A game has already been played for this bill")


def _active_state(state: dict | None, mode: str) -> dict | None:
    """The unlocked state for `mode`, 409 if the game is already locked."""
    if state and state.get("locked"):
        raise HTTPException(status_code=409, detail="Game already locked")
    if state and state.get("mode") == mode:
        return state
    return None


def _require_state(state: dict | None, mode: str) -> dict:
    if not state:
        raise HTTPException(status_code=404, detail="No active game state")
    if state.get("locked"):
        raise HTTPException(status_code=409, detail="Already locked")
    if state.get("mode") != mode:
        raise HTTPException(status_code=400, detail=f"Active game is not {mode}")
    return state


async def _commit(
    redis: aioredis.Redis,
    supabase: Client,
    state: dict,
    bill_id,
    game_type: str,
    result_json: dict,
    apply=None,
) -> dict:
    """Atomically lock the game, run `apply` (side effects), record the result."""
    lock_key = f"game_lock:{bill_id}"
    if not await redis.set(lock_key, "1", nx=True, ex=60):
        raise HTTPException(status_code=409, detail="Already locked")
    try:
        if apply:
            apply()
        row = (
            supabase.table("game_results")
            .insert(
                {
                    "bill_id": str(bill_id),
                    "game_type": game_type,
                    "seed": state["seed"],
                    "result_json": result_json,
                    "is_locked": True,
                }
            )
            .execute()
            .data[0]
        )
    except Exception as exc:  # noqa: BLE001
        await redis.delete(lock_key)
        if is_unique_violation(exc):
            raise HTTPException(status_code=409, detail="Already locked") from exc
        logger.error(f"locking {game_type} for bill {bill_id} failed: {exc}")
        raise
    state["locked"] = True
    state["result"] = result_json
    await redis.set(_state_key(bill_id), json.dumps(state), ex=LOCKED_TTL)
    return row


# ── Tangga (ladder) ───────────────────────────────────────────────────────────


@router.post("/tangga/generate")
async def generate_tangga(
    payload: TanggaGenerateRequest,
    user=Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
    supabase: Client = Depends(get_supabase),
):
    require_bill_owner(supabase, payload.bill_id, user)
    _assert_not_played(supabase, payload.bill_id)
    ids = [str(p) for p in payload.participant_ids]
    assert_same_participants(supabase, payload.bill_id, ids)
    n = len(ids)
    if len(payload.outcome_labels) != n:
        raise HTTPException(status_code=422, detail="Need exactly one outcome label per participant")

    existing = _active_state(await _load_state(redis, payload.bill_id), "tangga")
    if existing and set(existing["participants"]) == set(ids) and existing["labels"] == payload.outcome_labels:
        # Same ladder as before: re-requesting must not be a way to re-roll.
        return {"seed": existing["seed"], "rungs": existing["rungs"], "n_lanes": n}

    seed = make_seed()
    rungs = generate_tangga_rungs(n, seed)
    state = {
        "mode": "tangga",
        "participants": ids,
        "labels": payload.outcome_labels,
        "seed": seed,
        "rungs": rungs,
        "result": {},
        "locked": False,
    }
    await redis.set(_state_key(payload.bill_id), json.dumps(state), ex=STATE_TTL)
    return {"seed": seed, "rungs": rungs, "n_lanes": n}


@router.post("/tangga/lock")
async def lock_tangga(
    payload: TanggaLockRequest,
    user=Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
    supabase: Client = Depends(get_supabase),
):
    require_bill_owner(supabase, payload.bill_id, user)
    state = _require_state(await _load_state(redis, payload.bill_id), "tangga")

    lanes = {str(pid): lane for pid, lane in payload.lanes.items()}
    n = len(state["participants"])
    if set(lanes) != set(state["participants"]):
        raise HTTPException(status_code=422, detail="lanes must cover exactly the game's participants")
    if sorted(lanes.values()) != list(range(n)):
        raise HTTPException(status_code=422, detail="Each lane must be chosen exactly once")

    result = {
        pid: state["labels"][traverse_tangga(lane, state["rungs"])] for pid, lane in lanes.items()
    }
    return await _commit(redis, supabase, state, payload.bill_id, "tangga", result)


# ── Roulette ──────────────────────────────────────────────────────────────────


@router.post("/roulette/spin")
async def spin_roulette(
    payload: RouletteSpinRequest,
    user=Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
    supabase: Client = Depends(get_supabase),
):
    require_bill_owner(supabase, payload.bill_id, user)
    _assert_not_played(supabase, payload.bill_id)
    ids = [str(p) for p in payload.participant_ids]
    assert_same_participants(supabase, payload.bill_id, ids)

    existing = _active_state(await _load_state(redis, payload.bill_id), "roulette")
    if existing and set(existing["participants"]) == set(ids):
        state = existing  # the winner is already committed; spinning again can't change it
    else:
        seed = make_seed()
        rng = random.Random(seed)
        state = {
            "mode": "roulette",
            "participants": ids,
            "seed": seed,
            "winner_id": ids[rng.randrange(len(ids))],
            "landing_fraction": rng.uniform(0.15, 0.85),
            "angular_velocity": rng.uniform(800, 1200),
            "result": {},
            "locked": False,
        }
        await redis.set(_state_key(payload.bill_id), json.dumps(state), ex=STATE_TTL)

    return {
        "seed": state["seed"],
        "angular_velocity": state["angular_velocity"],
        "winner_participant_id": state["winner_id"],
        "landing_fraction": state["landing_fraction"],
    }


@router.post("/roulette/lock")
async def lock_roulette(
    payload: RouletteLockRequest,
    user=Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
    supabase: Client = Depends(get_supabase),
):
    require_bill_owner(supabase, payload.bill_id, user)
    state = _require_state(await _load_state(redis, payload.bill_id), "roulette")

    if payload.winner_participant_id and str(payload.winner_participant_id) != state["winner_id"]:
        raise HTTPException(status_code=422, detail="Winner does not match the spin result")

    result = {state["winner_id"]: payload.outcome or DEFAULT_ROULETTE_OUTCOME}
    return await _commit(redis, supabase, state, payload.bill_id, "roulette", result)


# ── Dadu (dice) ───────────────────────────────────────────────────────────────
# Lower roll (1) = unlucky = pays more. factor = 7 - roll; share ∝ factor.


def _roll_dadu(participant_ids: list[str], seed: str) -> dict[str, int]:
    rng = random.Random(seed)
    return {pid: rng.randint(1, 6) for pid in participant_ids}


def _dadu_amounts(rolls: dict[str, int], total_amount: Decimal) -> dict[str, Decimal]:
    factors = {pid: 7 - roll for pid, roll in rolls.items()}
    total_factor = sum(factors.values())
    amounts: dict[str, Decimal] = {}
    running = Decimal("0")
    pids = list(factors.keys())
    for i, pid in enumerate(pids):
        if i == len(pids) - 1:
            amounts[pid] = total_amount - running  # last share absorbs rounding: sum is exact
        else:
            amt = (
                Decimal(str(factors[pid])) / Decimal(str(total_factor)) * total_amount
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            amounts[pid] = amt
            running += amt
    return amounts


@router.post("/dadu/roll")
async def roll_dadu(
    payload: DaduRollRequest,
    user=Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
    supabase: Client = Depends(get_supabase),
):
    bill = require_bill_owner(supabase, payload.bill_id, user)
    _assert_not_played(supabase, payload.bill_id)
    ids = [str(p) for p in payload.participant_ids]
    assert_same_participants(supabase, payload.bill_id, ids)
    total = to_money(bill["total_amount"])  # the bill's own total, never a client value

    existing = _active_state(await _load_state(redis, payload.bill_id), "dadu")
    if existing and set(existing["participants"]) == set(ids):
        state = existing
    else:
        seed = make_seed()
        rolls = _roll_dadu(ids, seed)
        amounts = _dadu_amounts(rolls, total)
        state = {
            "mode": "dadu",
            "participants": ids,
            "seed": seed,
            "total_amount": str(total),
            "rolls": rolls,
            "amounts": {pid: str(amt) for pid, amt in amounts.items()},
            "locked": False,
        }
        await redis.set(_state_key(payload.bill_id), json.dumps(state), ex=STATE_TTL)

    return {
        "seed": state["seed"],
        "rolls": state["rolls"],
        "amounts": {pid: float(Decimal(a)) for pid, a in state["amounts"].items()},
    }


@router.post("/dadu/lock")
async def lock_dadu(
    payload: DaduLockRequest,
    user=Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
    supabase: Client = Depends(get_supabase),
):
    require_bill_owner(supabase, payload.bill_id, user)
    state = _require_state(await _load_state(redis, payload.bill_id), "dadu")
    amounts = state["amounts"]

    def apply_amounts() -> None:
        for pid, amount in amounts.items():
            # Scoped to this bill, so a participant id from elsewhere can never be touched.
            supabase.table("participants").update({"amount_owed": float(Decimal(amount))}).eq(
                "id", pid
            ).eq("bill_id", str(payload.bill_id)).execute()

    return await _commit(
        redis,
        supabase,
        state,
        payload.bill_id,
        "dadu",
        {"rolls": state["rolls"], "amounts": amounts},
        apply=apply_amounts,
    )
