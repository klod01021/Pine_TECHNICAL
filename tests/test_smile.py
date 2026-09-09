import pytest

from option_pricer.pricing.smile import build_smile


def test_rr_and_butterfly_reconstruct_wing_vols():
    atm, rr, bf = 0.20, -0.012, 0.004
    smile = build_smile(100, 0.05, 0.01, 0.5, atm, rr, bf)
    assert smile.vol_25d_call - smile.vol_25d_put == pytest.approx(rr)
    assert 0.5 * (smile.vol_25d_call + smile.vol_25d_put) - atm == pytest.approx(bf)


def test_flat_smile_when_rr_and_bf_are_zero():
    smile = build_smile(100, 0.0, 0.0, 1.0, 0.2, 0.0, 0.0)
    for strike in (80, 100, 120):
        assert smile.vol_at(strike) == pytest.approx(0.2, abs=1e-10)


def test_put_skew_makes_downside_vol_higher():
    smile = build_smile(100, 0.01, 0.0, 0.25, 0.20, rr_25d=-0.03, bf_25d=0.005)
    assert smile.vol_at(80) > smile.vol_at(120)
    assert smile.vol_25d_put > smile.vol_25d_call
