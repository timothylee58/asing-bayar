"""Pure deterministic game logic — no I/O dependencies."""
import random
import string


def make_seed(n: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def generate_tangga_rungs(n_lanes: int, seed: str) -> list[dict]:
    if n_lanes < 2:
        return []
    rng = random.Random(seed)
    n_rungs = n_lanes * 3
    rungs: list[dict] = []
    used: set[tuple] = set()

    for _ in range(n_rungs * 5):
        if len(rungs) >= n_rungs:
            break
        lane = rng.randint(0, n_lanes - 2)
        y = rng.uniform(0.05, 0.95)
        y_rounded = round(y, 2)
        key = (lane, round(y_rounded, 1))
        if key not in used:
            used.add(key)
            rungs.append({"lane": lane, "y": y_rounded})

    return sorted(rungs, key=lambda r: r["y"])


def traverse_tangga(start_lane: int, rungs: list[dict]) -> int:
    lane = start_lane
    for rung in rungs:
        if rung["lane"] == lane:
            lane += 1
        elif rung["lane"] == lane - 1:
            lane -= 1
    return lane
