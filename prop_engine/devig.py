"""No-vig probabilities and line conversion (SPEC §1.2–1.3).

All prices are decimal odds. Two-way markets only (Over/Under).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist

from .config import LINE_CONVERSION


@dataclass(frozen=True)
class NoVig:
    p_over_mult: float
    p_under_mult: float
    p_over_power: float
    p_under_power: float

    @property
    def p_over(self) -> float:
        """Conservative Over probability: the lower of the two methods."""
        return min(self.p_over_mult, self.p_over_power)

    @property
    def p_under(self) -> float:
        """Conservative Under probability: the lower of the two methods."""
        return min(self.p_under_mult, self.p_under_power)


def implied(decimal_odds: float) -> float:
    if decimal_odds <= 1.0:
        raise ValueError(f"decimal odds must be > 1, got {decimal_odds}")
    return 1.0 / decimal_odds


def multiplicative(over: float, under: float) -> tuple[float, float]:
    qo, qu = implied(over), implied(under)
    total = qo + qu
    return qo / total, qu / total


def power(over: float, under: float, tol: float = 1e-12) -> tuple[float, float]:
    """Find k with qo**k + qu**k = 1. Takes more vig off the longer-priced side."""
    qo, qu = implied(over), implied(under)
    lo, hi = 1e-6, 100.0
    # f(k) = qo**k + qu**k - 1 is decreasing in k because 0 < q < 1.
    for _ in range(200):
        mid = (lo + hi) / 2
        if qo**mid + qu**mid > 1.0:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    k = (lo + hi) / 2
    po = qo**k
    return po, 1.0 - po


def devig(over: float, under: float) -> NoVig:
    pom, pum = multiplicative(over, under)
    pop, pup = power(over, under)
    return NoVig(pom, pum, pop, pup)


# --- Line conversion -------------------------------------------------------
# Placeholder until the week-3 projection model: fit a one-parameter distribution
# so P(X > sharp_line) matches the sharp no-vig price, then read P(X > ud_line).


class ConversionError(ValueError):
    pass


def _poisson_sf(line: float, lam: float) -> float:
    """P(X > line) for X ~ Poisson(lam)."""
    k_max = math.floor(line)
    if k_max < 0:
        return 1.0
    term = math.exp(-lam)
    cdf = term
    for k in range(1, k_max + 1):
        term *= lam / k
        cdf += term
    return max(0.0, 1.0 - cdf)


def _solve_poisson(line: float, p_over: float) -> float:
    lo, hi = 1e-9, 200.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if _poisson_sf(line, mid) < p_over:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def convert_p_over(market: str, p_over: float, from_line: float, to_line: float) -> float:
    """Shift a no-vig Over probability from the sharp line to Underdog's line."""
    if from_line == to_line:
        return p_over
    cfg = LINE_CONVERSION.get(market)
    if cfg is None:
        raise ConversionError(f"no conversion settings for {market}")
    gap = abs(to_line - from_line)
    if gap > cfg["max_gap"]:
        raise ConversionError(f"line gap {gap:g} exceeds max {cfg['max_gap']:g} for {market}")
    if not 0.0 < p_over < 1.0:
        raise ConversionError(f"p_over out of range: {p_over}")

    if cfg["dist"] == "normal":
        sd = cfg["sd"]
        z = NormalDist().inv_cdf(1.0 - p_over)
        mu = from_line - sd * z
        return 1.0 - NormalDist(mu, sd).cdf(to_line)
    if cfg["dist"] == "poisson":
        lam = _solve_poisson(from_line, p_over)
        return _poisson_sf(to_line, lam)
    raise ConversionError(f"unknown dist {cfg['dist']!r}")


def per_leg_break_even(payout: float, legs: int) -> float:
    """(1/payout)^(1/legs): valid only for independent, equal-probability legs (SPEC §3)."""
    return (1.0 / payout) ** (1.0 / legs)
