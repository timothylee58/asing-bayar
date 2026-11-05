"""Exact money helpers. Amounts are Decimal and quantised to sen (0.01)."""
from decimal import ROUND_HALF_UP, Decimal

SEN = Decimal("0.01")


def to_money(value) -> Decimal:
    return Decimal(str(value)).quantize(SEN, rounding=ROUND_HALF_UP)


def split_equally(total: Decimal, n: int) -> list[Decimal]:
    """Split `total` into `n` shares that sum to `total` exactly.

    Any leftover sen go one each to the first shares, so RM100.00 / 3 becomes
    33.34 + 33.33 + 33.33 rather than a total that is a sen short.
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    cents = int((to_money(total) / SEN).to_integral_value())
    base, remainder = divmod(cents, n)
    return [Decimal(base + (1 if i < remainder else 0)) * SEN for i in range(n)]
