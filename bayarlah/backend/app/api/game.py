from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
import redis.asyncio as aioredis
import json
import random

from app.core.dependencies import get_supabase, get_redis
from app.models.game import (
    TanggaGenerateRequest,
    TanggaLockRequest,
    RouletteSpinRequest,
    RouletteLockRequest,
)
from app.utils.game_logic import make_seed, generate_tangga_rungs, traverse_tangga

router = APIRouter()

# Keep private aliases so existing call-sites inside this module are unchanged.
_make_seed = make_seed
_generate_tangga_rungs = generate_tangga_rungs
_traverse_tangga = traverse_tangga


@router.post("/tangga/generate")
async def generate_tangga(
    payload: TanggaGenerateRequest,
    redis: aioredis.Redis = Depends(get_redis),
    supabase: Client = Depends(get_supabase),
):
    key = f"game_state:{payload.bill_id}"
    if await redis.exists(key):
        state = json.loads(await redis.get(key))
        if state.get("locked"):
            raise HTTPException(status_code=409, detail="Game already locked")

    n = len(payload.participant_ids)
    seed = make_seed()
    rungs = generate_tangga_rungs(n, seed)

    state = {
        "mode": "tangga",
        "participants": [str(p) for p in payload.participant_ids],
        "outcome_labels": payload.outcome_labels,
        "seed": seed,
        "rungs": rungs,
        "result": {},
        "locked": False,
    }
    await redis.set(key, json.dumps(state), ex=3600)

    return {"seed": seed, "rungs": rungs, "n_lanes": n}


@router.post("/tangga/lock")
async def lock_tangga(
    payload: TanggaLockRequest,
    redis: aioredis.Redis = Depends(get_redis),
    supabase: Client = Depends(get_supabase),
):
    key = f"game_state:{payload.bill_id}"
    raw = await redis.get(key)
    if not raw:
        raise HTTPException(status_code=404, detail="No active game state")

    state = json.loads(raw)
    if state.get("locked"):
        raise HTTPException(status_code=409, detail="Already locked")

    state["result"] = payload.result
    state["locked"] = True
    await redis.set(key, json.dumps(state), ex=86400)

    result = supabase.table("game_results").insert({
        "bill_id": str(payload.bill_id),
        "game_type": "tangga",
        "seed": state["seed"],
        "result_json": payload.result,
        "is_locked": True,
    }).execute()

    return result.data[0]


@router.post("/roulette/spin")
async def spin_roulette(
    payload: RouletteSpinRequest,
    redis: aioredis.Redis = Depends(get_redis),
):
    key = f"game_state:{payload.bill_id}"
    if await redis.exists(key):
        state = json.loads(await redis.get(key))
        if state.get("locked"):
            raise HTTPException(status_code=409, detail="Game already locked")

    seed = make_seed()
    rng = random.Random(seed)
    angular_velocity = rng.uniform(800, 1200)

    state = {
        "mode": "roulette",
        "participants": [str(p) for p in payload.participant_ids],
        "seed": seed,
        "angular_velocity": angular_velocity,
        "result": {},
        "locked": False,
    }
    await redis.set(key, json.dumps(state), ex=3600)

    return {"seed": seed, "angular_velocity": angular_velocity}


@router.post("/roulette/lock")
async def lock_roulette(
    payload: RouletteLockRequest,
    redis: aioredis.Redis = Depends(get_redis),
    supabase: Client = Depends(get_supabase),
):
    key = f"game_state:{payload.bill_id}"
    raw = await redis.get(key)
    if not raw:
        raise HTTPException(status_code=404, detail="No active game state")

    state = json.loads(raw)
    if state.get("locked"):
        raise HTTPException(status_code=409, detail="Already locked")

    result_data = {str(payload.winner_participant_id): payload.outcome}
    state["result"] = result_data
    state["locked"] = True
    await redis.set(key, json.dumps(state), ex=86400)

    result = supabase.table("game_results").insert({
        "bill_id": str(payload.bill_id),
        "game_type": "roulette",
        "seed": state["seed"],
        "result_json": result_data,
        "is_locked": True,
    }).execute()

    return result.data[0]
