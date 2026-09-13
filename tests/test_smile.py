import pytest

from option_pricer.pricing.smile import build_smile


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
