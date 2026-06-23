import os

os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")

import string
from app.api.game import _make_seed, _generate_tangga_rungs, _traverse_tangga


class TestMakeSeed:
    def test_default_length(self):
        assert len(_make_seed()) == 8

    def test_custom_length(self):
        assert len(_make_seed(16)) == 16

    def test_valid_charset(self):
        allowed = set(string.ascii_lowercase + string.digits)
        seed = _make_seed(100)
        assert all(c in allowed for c in seed)

    def test_randomness(self):
        # Very unlikely to produce the same seed twice in 10 tries
        seeds = {_make_seed() for _ in range(10)}
        assert len(seeds) > 1


class TestGenerateTanggaRungs:
    def test_deterministic(self):
        assert _generate_tangga_rungs(4, "xyz123") == _generate_tangga_rungs(4, "xyz123")

    def test_different_seeds_give_different_rungs(self):
        assert _generate_tangga_rungs(4, "aaa") != _generate_tangga_rungs(4, "bbb")

    def test_sorted_ascending_by_y(self):
        rungs = _generate_tangga_rungs(5, "sort_me")
        ys = [r["y"] for r in rungs]
        assert ys == sorted(ys)

    def test_y_within_bounds(self):
        for rung in _generate_tangga_rungs(4, "bounds"):
            assert 0.05 <= rung["y"] <= 0.95

    def test_lane_indices_within_bounds(self):
        n = 5
        for rung in _generate_tangga_rungs(n, "lanes"):
            assert 0 <= rung["lane"] <= n - 2

    def test_two_lane_ladder(self):
        # Only lane 0 is valid when n_lanes == 2
        rungs = _generate_tangga_rungs(2, "two_lane")
        assert all(r["lane"] == 0 for r in rungs)

    def test_scales_with_lane_count(self):
        small = _generate_tangga_rungs(2, "scale")
        large = _generate_tangga_rungs(6, "scale")
        assert len(large) >= len(small)


class TestTraverseTangga:
    def test_no_rungs_returns_start_lane(self):
        assert _traverse_tangga(2, []) == 2

    def test_rung_on_own_lane_shifts_right(self):
        # Player on lane 1, rung at lane 1 → shifts to lane 2
        assert _traverse_tangga(1, [{"lane": 1, "y": 0.5}]) == 2

    def test_rung_on_left_lane_shifts_left(self):
        # Player on lane 2, rung at lane 1 (lane-1) → shifts to lane 1
        assert _traverse_tangga(2, [{"lane": 1, "y": 0.5}]) == 1

    def test_unrelated_rung_has_no_effect(self):
        # Player on lane 0, rung at lane 3 → no change
        assert _traverse_tangga(0, [{"lane": 3, "y": 0.5}]) == 0

    def test_chained_rungs(self):
        # Start at 0 → rung 0 → go to 1 → rung 1 → go to 2
        rungs = [{"lane": 0, "y": 0.3}, {"lane": 1, "y": 0.7}]
        assert _traverse_tangga(0, rungs) == 2

    def test_rungs_applied_in_y_order(self):
        # Rungs sorted by y; verify the traversal respects order
        # Start at 1: rung@0.3 shifts right to 2, rung@0.7 on lane 1 is skipped
        rungs = [{"lane": 1, "y": 0.3}, {"lane": 3, "y": 0.7}]
        result = _traverse_tangga(1, rungs)
        assert result == 2
