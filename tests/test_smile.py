import math

import pytest

from option_pricer.pricing.smile import build_smile, build_smile_from_points, smile_from_request
from option_pricer.pricing.schemas import PriceRequest, SmileSource, VolPoint


def test_rr_and_butterfly_reconstruct_wing_vols():
    atm, rr, bf = 0.20, -0.012, 0.004
    smile = build_smile(100, 0.05, 0.01, 0.5, atm, rr, bf)
    assert smile.vol_25d_call - smile.vol_25d_put == pytest.approx(rr)
    assert 0.5 * (smile.vol_25d_call + smile.vol_25d_put) - atm == pytest.approx(bf)


def test_10d_rr_and_butterfly_reconstruct_wing_vols():
    atm, rr25, bf25 = 0.20, -0.012, 0.004
    rr10, bf10 = -0.030, 0.012
    smile = build_smile(
        100, 0.05, 0.01, 0.5, atm, rr25, bf25, rr_10d=rr10, bf_10d=bf10
    )
    assert smile.vol_10d_call - smile.vol_10d_put == pytest.approx(rr10)
    assert 0.5 * (smile.vol_10d_call + smile.vol_10d_put) - atm == pytest.approx(bf10)
    assert smile.vol_25d_call - smile.vol_25d_put == pytest.approx(rr25)
    assert smile.ten_delta_source == "quoted"
    labels = [p.label for p in smile.curve().pillars]
    assert labels == ["10Δ put", "25Δ put", "ATM", "25Δ call", "10Δ call"]


def test_flat_smile_when_rr_and_bf_are_zero():
    smile = build_smile(100, 0.0, 0.0, 1.0, 0.2, 0.0, 0.0, rr_10d=0.0, bf_10d=0.0)
    for strike in (70, 80, 100, 120, 140):
        assert smile.vol_at(strike) == pytest.approx(0.2, abs=1e-10)


def test_put_skew_makes_downside_vol_higher():
    smile = build_smile(100, 0.01, 0.0, 0.25, 0.20, rr_25d=-0.03, bf_25d=0.005)
    assert smile.vol_at(80) > smile.vol_at(120)
    assert smile.vol_25d_put > smile.vol_25d_call
    assert smile.ten_delta_source == "implied_from_25d"


def test_quoted_10d_steepens_far_wings_vs_25d_only():
    only_25 = build_smile(100, 0.02, 0.0, 0.5, 0.20, rr_25d=-0.012, bf_25d=0.004)
    with_10 = build_smile(
        100,
        0.02,
        0.0,
        0.5,
        0.20,
        rr_25d=-0.012,
        bf_25d=0.004,
        rr_10d=-0.035,
        bf_10d=0.014,
    )
    assert with_10.vol_10d_put > only_25.vol_10d_put
    assert with_10.vol_at(with_10.strike_10d_put) == pytest.approx(with_10.vol_10d_put)
    assert with_10.vol_at(with_10.strike_25d_put) == pytest.approx(with_10.vol_25d_put)
    assert with_10.vol_at(70) == pytest.approx(with_10.vol_10d_put)
    assert with_10.vol_at(70) > only_25.vol_at(70)


def test_custom_points_are_honored_and_interpolated():
    smile = build_smile_from_points(
        100, 0.0, 0.0, 1.0, [(80, 0.24), (100, 0.20), (120, 0.18)]
    )
    assert smile.source == "custom"
    assert smile.vol_at(80) == pytest.approx(0.24)
    assert smile.vol_at(100) == pytest.approx(0.20)
    assert smile.vol_at(120) == pytest.approx(0.18)
    mid = smile.vol_at(90)
    assert 0.20 < mid < 0.24
    assert smile.vol_at(60) == pytest.approx(0.24)
    assert smile.vol_at(140) == pytest.approx(0.18)
    assert [p.label for p in smile.curve().pillars] == ["Input", "Input", "Input"]


def test_two_point_custom_smile_is_linear_in_log_moneyness():
    smile = build_smile_from_points(100, 0.0, 0.0, 1.0, [(80, 0.24), (120, 0.16)])
    x80 = math.log(80 / 100)
    x120 = math.log(120 / 100)
    expected = 0.24 + (0.0 - x80) / (x120 - x80) * (0.16 - 0.24)
    assert smile.vol_at(100) == pytest.approx(expected)
    assert smile.atm_vol == pytest.approx(expected)
    assert smile.ten_delta_source == "custom"


def test_custom_smile_rejects_fewer_than_two_points():
    with pytest.raises(ValueError, match="at least two"):
        build_smile_from_points(100, 0.0, 0.0, 1.0, [(100, 0.2)])


def test_smile_from_request_uses_custom_points():
    request = PriceRequest(
        spot=100,
        strike=100,
        rate=0.05,
        dividend=0.0,
        atm_vol=0.20,
        rr_25d=0.0,
        bf_25d=0.0,
        expiry_years=1.0,
        smile_source=SmileSource.custom,
        custom_vols=[
            VolPoint(strike=90, vol=0.22),
            VolPoint(strike=110, vol=0.18),
        ],
    )
    smile = smile_from_request(request, 1.0)
    assert smile.source == "custom"
    assert smile.vol_at(90) == pytest.approx(0.22)
    assert smile.vol_at(110) == pytest.approx(0.18)
