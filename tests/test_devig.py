import math

import pytest

from prop_engine.devig import (
    ConversionError,
    convert_p_over,
    devig,
    multiplicative,
    per_leg_break_even,
    power,
)


def test_multiplicative_even_market():
    po, pu = multiplicative(1.909, 1.909)  # -110 / -110
    assert po == pytest.approx(0.5)
    assert pu == pytest.approx(0.5)


def test_multiplicative_sums_to_one():
    po, pu = multiplicative(1.80, 2.05)
    assert po + pu == pytest.approx(1.0)
    assert po == pytest.approx((1 / 1.80) / (1 / 1.80 + 1 / 2.05))


def test_power_solves_exponent():
    over, under = 1.80, 2.05
    po, pu = power(over, under)
    assert po + pu == pytest.approx(1.0, abs=1e-9)
    k = math.log(po) / math.log(1 / over)
    assert (1 / under) ** k == pytest.approx(pu, abs=1e-9)


def test_power_takes_more_vig_off_longshot():
    # Power devig gives the favorite more probability than multiplicative does.
    pom, _ = multiplicative(1.50, 2.60)
    pop, _ = power(1.50, 2.60)
    assert pop > pom


def test_conservative_picks_lower_per_side():
    nv = devig(1.50, 2.60)
    assert nv.p_over == min(nv.p_over_mult, nv.p_over_power)
    assert nv.p_under == min(nv.p_under_mult, nv.p_under_power)
    assert nv.p_over + nv.p_under < 1.0 + 1e-12


def test_invalid_odds():
    with pytest.raises(ValueError):
        devig(1.0, 2.0)


def test_convert_same_line_is_identity():
    assert convert_p_over("player_reception_yds", 0.55, 64.5, 64.5) == 0.55


def test_convert_higher_line_lowers_p_over():
    p = convert_p_over("player_reception_yds", 0.50, 64.5, 66.5)
    # Normal sd 24: 2 yds up from the median is about 3.3 pts of probability.
    assert p == pytest.approx(1 - 0.5 - (0.5 - __import__("statistics").NormalDist(0, 24).cdf(-2)), abs=1e-9)
    assert 0.46 < p < 0.5


def test_convert_lower_line_raises_p_over():
    assert convert_p_over("player_rush_yds", 0.50, 60.5, 55.5) > 0.5


def test_convert_poisson_receptions():
    p = convert_p_over("player_receptions", 0.50, 4.5, 5.5)
    assert 0.25 < p < 0.5
    # Same line round-trips through the Poisson fit.
    assert convert_p_over("player_receptions", 0.42, 4.5, 4.5) == 0.42


def test_convert_gap_too_large():
    with pytest.raises(ConversionError):
        convert_p_over("player_reception_yds", 0.5, 50.5, 70.5)


def test_pass_tds_require_exact_line():
    with pytest.raises(ConversionError):
        convert_p_over("player_pass_tds", 0.5, 1.5, 0.5)


@pytest.mark.parametrize("legs,payout,expected", [(2, 3, 0.577), (3, 6, 0.550), (4, 10, 0.562), (5, 20, 0.549)])
def test_break_even_matches_spec_table(legs, payout, expected):
    assert per_leg_break_even(payout, legs) == pytest.approx(expected, abs=5e-4)
