"""Tests for pure game logic — no Supabase/Redis required."""
import string

from app.utils.game_logic import make_seed, generate_tangga_rungs, traverse_tangga


# ---------------------------------------------------------------------------
# make_seed
# ---------------------------------------------------------------------------

def test_make_seed_default_length():
    assert len(make_seed()) == 8


def test_make_seed_custom_length():
    assert len(make_seed(12)) == 12


def test_make_seed_charset():
    allowed = set(string.ascii_lowercase + string.digits)
    for _ in range(50):
        seed = make_seed()
        assert all(c in allowed for c in seed)


def test_make_seed_random():
    # Two calls should (overwhelmingly) produce different seeds.
    seeds = {make_seed() for _ in range(20)}
    assert len(seeds) > 1


# ---------------------------------------------------------------------------
# generate_tangga_rungs
# ---------------------------------------------------------------------------

SEED = "abc123xy"


def test_rungs_deterministic():
    """Same seed must produce identical rungs every time."""
    r1 = generate_tangga_rungs(4, SEED)
    r2 = generate_tangga_rungs(4, SEED)
    assert r1 == r2


def test_rungs_different_seeds():
    r1 = generate_tangga_rungs(4, "aaaaaaaa")
    r2 = generate_tangga_rungs(4, "bbbbbbbb")
    assert r1 != r2


def test_rungs_sorted_by_y():
    rungs = generate_tangga_rungs(5, SEED)
    ys = [r["y"] for r in rungs]
    assert ys == sorted(ys)


def test_rungs_y_in_range():
    rungs = generate_tangga_rungs(5, SEED)
    for r in rungs:
        assert 0.05 <= r["y"] <= 0.95


def test_rungs_lane_in_range():
    n = 6
    rungs = generate_tangga_rungs(n, SEED)
    for r in rungs:
        assert 0 <= r["lane"] <= n - 2


def test_rungs_target_count():
    """Should generate up to n_lanes * 3 unique rungs."""
    n = 4
    rungs = generate_tangga_rungs(n, SEED)
    assert len(rungs) <= n * 3
    assert len(rungs) > 0


def test_rungs_two_lanes():
    rungs = generate_tangga_rungs(2, SEED)
    # Only one possible lane index (0) for a 2-lane ladder.
    for r in rungs:
        assert r["lane"] == 0


def test_rungs_structure():
    rungs = generate_tangga_rungs(3, SEED)
    for r in rungs:
        assert set(r.keys()) == {"lane", "y"}


# ---------------------------------------------------------------------------
# traverse_tangga
# ---------------------------------------------------------------------------

def test_traverse_no_rungs_stays_in_lane():
    for lane in range(5):
        assert traverse_tangga(lane, []) == lane


def test_traverse_rung_shifts_right():
    # Rung at lane 0 connects lane 0 → lane 1.
    rungs = [{"lane": 0, "y": 0.5}]
    assert traverse_tangga(0, rungs) == 1


def test_traverse_rung_shifts_left():
    # A player starting at lane 1 hits a rung at lane 0 and crosses left.
    rungs = [{"lane": 0, "y": 0.5}]
    assert traverse_tangga(1, rungs) == 0


def test_traverse_unrelated_rung_no_effect():
    # Player at lane 2, rung at lane 0 — no crossing.
    rungs = [{"lane": 0, "y": 0.5}]
    assert traverse_tangga(2, rungs) == 2


def test_traverse_multiple_rungs():
    # Lane 0 → crosses right at y=0.3 → lane 1
    # At y=0.7 lane 1 hits rung at lane 1 → crosses right to lane 2
    rungs = [
        {"lane": 0, "y": 0.3},  # lane 0 → 1
        {"lane": 1, "y": 0.7},  # lane 1 → 2
    ]
    assert traverse_tangga(0, rungs) == 2


def test_traverse_cross_then_back():
    # Lane 0 → right to 1 (y=0.3), then left back to 0 (y=0.7).
    rungs = [
        {"lane": 0, "y": 0.3},  # 0 → 1
        {"lane": 0, "y": 0.7},  # 1 → 0  (rung at lane 0 affects player at lane 1)
    ]
    assert traverse_tangga(0, rungs) == 0


def test_traverse_end_lane_within_bounds():
    """End lane from a real ladder must stay within [0, n-1]."""
    n = 5
    rungs = generate_tangga_rungs(n, SEED)
    for start in range(n):
        end = traverse_tangga(start, rungs)
        assert 0 <= end < n


def test_traverse_all_outcomes_reachable():
    """Different start lanes produce different end lanes (bijective mapping)."""
    n = 4
    rungs = generate_tangga_rungs(n, SEED)
    ends = [traverse_tangga(i, rungs) for i in range(n)]
    assert len(set(ends)) == n
