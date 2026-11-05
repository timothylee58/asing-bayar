"""Who-pays games: the server decides every outcome; the client only plays."""
import random
from decimal import Decimal

import pytest

from app.api.game import _dadu_amounts
from app.utils.game_logic import generate_tangga_rungs, traverse_tangga
from tests.conftest import MISSING_ID

LABELS = ["Selamat", "Bayar separuh", "Kena kau lah!"]


def pids(world):
    return [p["id"] for p in world["participants"]]


def generate(client, world, headers, **over):
    body = {"bill_id": world["bill"]["id"], "participant_ids": pids(world), "outcome_labels": LABELS}
    body.update(over)
    return client.post("/api/game/tangga/generate", json=body, headers=headers)


def lock(client, world, headers, lanes=None):
    lanes = lanes if lanes is not None else dict(zip(pids(world), [0, 1, 2], strict=True))
    return client.post("/api/game/tangga/lock", headers=headers,
                       json={"bill_id": world["bill"]["id"], "lanes": lanes})


class TestTangga:
    def test_generates_a_reproducible_ladder(self, client, world, organiser):
        res = generate(client, world, organiser).json()
        assert res["n_lanes"] == 3
        assert res["rungs"] == generate_tangga_rungs(3, res["seed"])

    def test_asking_again_cannot_reroll_the_ladder(self, client, world, organiser):
        first = generate(client, world, organiser).json()
        assert generate(client, world, organiser).json() == first

    @pytest.mark.parametrize("make", [
        lambda w: {"participant_ids": pids(w)[:2], "outcome_labels": LABELS[:2]},                # someone missing
        lambda w: {"participant_ids": pids(w) + [MISSING_ID], "outcome_labels": LABELS + ["x"]},  # a stranger
        lambda w: {"participant_ids": [pids(w)[0]] * 3},                                          # duplicates
        lambda w: {"outcome_labels": LABELS[:2]},                                                 # label count
    ], ids=["missing", "stranger", "duplicates", "label-count"])
    def test_participants_must_be_exactly_the_bills(self, client, world, organiser, make):
        assert generate(client, world, organiser, **make(world)).status_code == 422

    def test_outcomes_are_derived_by_the_server_from_its_own_ladder(self, client, db, world, organiser):
        ladder = generate(client, world, organiser).json()
        lanes = dict(zip(pids(world), [2, 0, 1], strict=True))
        res = lock(client, world, organiser, lanes)
        assert res.status_code == 200, res.text
        expected = {pid: LABELS[traverse_tangga(lane, ladder["rungs"])] for pid, lane in lanes.items()}
        assert db.rows("game_results")[0]["result_json"] == expected
        assert db.rows("game_results")[0]["seed"] == ladder["seed"]

    def test_a_client_supplied_result_is_ignored(self, client, db, world, organiser):
        ladder = generate(client, world, organiser).json()
        res = client.post("/api/game/tangga/lock", headers=organiser, json={
            "bill_id": world["bill"]["id"], "lanes": dict(zip(pids(world), [0, 1, 2], strict=True)),
            "result": {p: "Selamat" for p in pids(world)}})  # try to dodge paying
        assert res.status_code == 200
        stored = db.rows("game_results")[0]["result_json"]
        assert stored == {p: LABELS[traverse_tangga(i, ladder["rungs"])] for i, p in enumerate(pids(world))}

    @pytest.mark.parametrize("lanes", [
        lambda w: dict(zip(pids(w), [0, 0, 1], strict=True)),            # a lane chosen twice
        lambda w: dict(zip(pids(w), [0, 1, 3], strict=True)),            # out of range
        lambda w: dict(zip(pids(w), [-1, 1, 2], strict=True)),           # negative
        lambda w: dict(zip(pids(w)[:2], [0, 1], strict=True)),           # participant missing
        lambda w: {**dict(zip(pids(w), [0, 1, 2], strict=True)), MISSING_ID: 3},  # stranger added
        # A stranger *replaces* a real player: still a valid 0..n-1 permutation, so only the
        # "same participants" check can catch it (and a real player would be left out).
        lambda w: dict(zip([pids(w)[0], pids(w)[1], MISSING_ID], [0, 1, 2], strict=True)),
    ], ids=["duplicate", "range", "negative", "missing", "stranger-added", "stranger-swapped-in"])
    def test_lane_picks_are_validated(self, client, db, world, organiser, lanes):
        generate(client, world, organiser)
        assert lock(client, world, organiser, lanes(world)).status_code == 422
        assert db.rows("game_results") == []

    def test_cannot_lock_without_a_game(self, client, world, organiser):
        assert lock(client, world, organiser).status_code == 404

    def test_locks_once(self, client, db, world, organiser):
        generate(client, world, organiser)
        assert lock(client, world, organiser).status_code == 200
        assert lock(client, world, organiser).status_code == 409
        assert generate(client, world, organiser).status_code == 409
        assert len(db.rows("game_results")) == 1

    def test_a_played_bill_stays_played_after_the_cache_expires(self, client, db, redis, world, organiser):
        generate(client, world, organiser)
        lock(client, world, organiser)
        redis.d.clear()  # state TTL elapsed
        assert generate(client, world, organiser).status_code == 409

    def test_a_concurrent_lock_loses_cleanly(self, client, db, redis, world, organiser):
        generate(client, world, organiser)
        redis.d[f"game_lock:{world['bill']['id']}"] = "1"
        assert lock(client, world, organiser).status_code == 409
        assert db.rows("game_results") == []

    def test_a_failed_write_releases_the_lock_so_it_can_be_retried(self, client, db, world, organiser):
        generate(client, world, organiser)
        db.fail_inserts.add("game_results")
        assert lock(client, world, organiser).status_code == 500
        db.fail_inserts.clear()
        assert lock(client, world, organiser).status_code == 200


def spin(client, world, headers):
    return client.post("/api/game/roulette/spin", headers=headers,
                       json={"bill_id": world["bill"]["id"], "participant_ids": pids(world)})


def lock_roulette(client, world, headers, **over):
    return client.post("/api/game/roulette/lock", headers=headers,
                       json={"bill_id": world["bill"]["id"], **over})


class TestRoulette:
    def test_the_server_picks_the_winner_from_the_seed(self, client, world, organiser):
        res = spin(client, world, organiser).json()
        rng = random.Random(res["seed"])
        assert res["winner_participant_id"] == pids(world)[rng.randrange(3)]
        assert 0.15 <= res["landing_fraction"] <= 0.85 and 800 <= res["angular_velocity"] <= 1200

    def test_spinning_again_cannot_reroll_the_winner(self, client, world, organiser):
        first = spin(client, world, organiser).json()
        assert all(spin(client, world, organiser).json() == first for _ in range(5))

    def test_lock_records_the_servers_winner(self, client, db, world, organiser):
        winner = spin(client, world, organiser).json()["winner_participant_id"]
        res = lock_roulette(client, world, organiser)
        assert res.status_code == 200
        assert db.rows("game_results")[0]["result_json"] == {winner: "Kena kau lah!"}

    def test_a_client_cannot_name_a_different_winner(self, client, db, world, organiser):
        winner = spin(client, world, organiser).json()["winner_participant_id"]
        someone_else = next(p for p in pids(world) if p != winner)
        assert lock_roulette(client, world, organiser, winner_participant_id=someone_else).status_code == 422
        assert lock_roulette(client, world, organiser, winner_participant_id=MISSING_ID).status_code == 422
        assert db.rows("game_results") == []
        assert lock_roulette(client, world, organiser, winner_participant_id=winner).status_code == 200

    def test_cannot_lock_without_spinning(self, client, world, organiser):
        assert lock_roulette(client, world, organiser).status_code == 404

    def test_locks_once(self, client, db, world, organiser):
        spin(client, world, organiser)
        assert lock_roulette(client, world, organiser).status_code == 200
        assert lock_roulette(client, world, organiser).status_code == 409
        assert spin(client, world, organiser).status_code == 409


def roll(client, world, headers, **over):
    return client.post("/api/game/dadu/roll", headers=headers,
                       json={"bill_id": world["bill"]["id"], "participant_ids": pids(world), **over})


class TestDadu:
    def test_splits_the_bills_own_total_and_ignores_a_client_total(self, client, world, organiser):
        res = roll(client, world, organiser, total_amount="9999.99").json()
        assert sum(Decimal(str(a)) for a in res["amounts"].values()) == Decimal("60.00")
        assert all(1 <= r <= 6 for r in res["rolls"].values())

    def test_rolling_again_cannot_reroll(self, client, world, organiser):
        first = roll(client, world, organiser).json()
        assert roll(client, world, organiser).json() == first

    def test_lock_updates_only_this_bills_participants(self, client, db, world, organiser):
        other = db.seed_bill("77777777-7777-4777-8777-777777777777")
        rolled = roll(client, world, organiser).json()
        assert client.post("/api/game/dadu/lock", headers=organiser,
                           json={"bill_id": world["bill"]["id"]}).status_code == 200
        owed = {p["id"]: p["amount_owed"] for p in db.rows("participants", bill_id=world["bill"]["id"])}
        assert owed == {pid: pytest.approx(a) for pid, a in rolled["amounts"].items()}
        assert [p["amount_owed"] for p in db.rows("participants", bill_id=other["bill"]["id"])] == [20.0] * 3

    def test_a_tampered_cached_state_cannot_touch_another_bills_participants(self, client, db, redis, world, organiser):
        """Defence in depth: even if the cached game state named a foreign participant,
        the UPDATE is scoped to this bill, so that participant is untouched."""
        import json

        other = db.seed_bill("77777777-7777-4777-8777-777777777777")
        foreign = other["participants"][0]["id"]
        mine = pids(world)[0]
        redis.d[f"game_state:{world['bill']['id']}"] = json.dumps({
            "mode": "dadu", "participants": [mine, foreign], "seed": "abcd1234", "locked": False,
            "rolls": {mine: 1, foreign: 1}, "amounts": {mine: "30.00", foreign: "999.00"}})
        res = client.post("/api/game/dadu/lock", headers=organiser, json={"bill_id": world["bill"]["id"]})
        assert res.status_code == 200
        assert db.rows("participants", id=foreign)[0]["amount_owed"] == 20.0  # unchanged
        assert db.rows("participants", id=mine)[0]["amount_owed"] == 30.0

    def test_lock_requires_a_dadu_game(self, client, world, organiser):
        spin(client, world, organiser)
        res = client.post("/api/game/dadu/lock", headers=organiser, json={"bill_id": world["bill"]["id"]})
        assert res.status_code == 400

    @pytest.mark.parametrize("total", ["60.00", "100.00", "0.07", "999.99", "33.33"])
    @pytest.mark.parametrize("n", [2, 3, 5, 7, 50])
    def test_amounts_always_sum_to_the_total_exactly(self, total, n):
        rng = random.Random(f"{total}{n}")
        rolls = {str(i): rng.randint(1, 6) for i in range(n)}
        amounts = _dadu_amounts(rolls, Decimal(total))
        assert sum(amounts.values()) == Decimal(total)
        assert all(a >= 0 for a in amounts.values())

    def test_a_lower_roll_pays_more(self):
        amounts = _dadu_amounts({"a": 1, "b": 6}, Decimal("70.00"))
        assert amounts["a"] > amounts["b"]


def test_starting_another_game_replaces_the_unplayed_one(client, redis, world, organiser):
    generate(client, world, organiser)
    spin(client, world, organiser)
    assert lock(client, world, organiser).status_code == 400  # active game is now roulette
