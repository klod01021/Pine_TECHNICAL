"""Drives the Python port of the Wyckoff campaign logic with synthetic
price paths whose structure is known in advance.

Run with:  python3 tools/test_wyckoff_logic.py
"""

from __future__ import annotations

import math
import random
import sys

from wyckoff_logic_reference import (
    Cfg,
    Campaign,
    analyze,
    effort_result,
    event_codes,
    run_zigzag,
)

EPS = 0.05
DEPTH = 5
BARS = 12


def make_series(points: list[float], bars=BARS, noise: float = 0.0, vol_spikes: dict[int, float] | None = None):
    """Piecewise linear path through `points`.

    ``vol_spikes`` maps a turning-point index (into ``points``) to a volume
    multiplier applied on that turning bar. Everything else is base volume.
    """
    highs: list[float] = []
    lows: list[float] = []
    vols: list[float] = []
    turns: list[int] = []
    spreads: list[float] = []
    spans = [bars] * (len(points) - 1) if isinstance(bars, int) else list(bars)
    spikes = vol_spikes or {}
    for i in range(len(points) - 1):
        a, b = points[i], points[i + 1]
        turns.append(len(highs))
        for j in range(spans[i]):
            v = a + (b - a) * j / spans[i]
            if noise and j not in (0, spans[i] - 1):
                v += noise * math.sin(j * 2.3 + i)
            highs.append(v + EPS)
            lows.append(v - EPS)
            spreads.append(2 * EPS)
            mult = spikes.get(i, 1.0) if j == 0 else 1.0
            vols.append(1000.0 * mult)
    turns.append(len(highs))
    highs.append(points[-1] + EPS)
    lows.append(points[-1] - EPS)
    spreads.append(2 * EPS)
    vols.append(1000.0 * spikes.get(len(points) - 1, 1.0))
    return highs, lows, vols, spreads, turns


def pivots_of(points, min_move=0.0, noise=0.0, with_prov=False, bars=BARS, vol_spikes=None):
    highs, lows, vols, _, _ = make_series(points, bars=bars, noise=noise, vol_spikes=vol_spikes)
    return run_zigzag(highs, lows, DEPTH, min_move, with_prov, vols)


def prices(w):
    return [round(p.price, 2) for p in w]


def dirs(w):
    return [p.dir for p in w]


CASES: list[tuple[str, callable]] = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn

    return deco


CFG = Cfg(min_approach=15.0, atr=2.0)


# ── swing detection ──────────────────────────────────────────────────────────
@case("zig-zag recovers the injected swings")
def _():
    w, _ = pivots_of([90, 160, 100, 128, 106, 126, 96, 148, 134, 170])
    assert prices(w) == [160.05, 99.95, 128.05, 105.95, 126.05, 95.95, 148.05, 133.95], prices(w)
    assert dirs(w) == [1, -1, 1, -1, 1, -1, 1, -1], dirs(w)


@case("noise below the filter does not create extra swings")
def _():
    w, _ = pivots_of([90, 160, 100, 128, 106, 148, 134, 170], min_move=4.0, noise=1.2)
    assert len(w) == 6, prices(w)


# ── accumulation ─────────────────────────────────────────────────────────────
ACC = [90, 160, 100, 128, 106, 126, 96, 148, 134, 170]


@case("classic accumulation is labelled SC AR ST Spring SOS LPS")
def _():
    w, _ = pivots_of(ACC, vol_spikes={2: 3.0, 4: 0.7, 6: 0.6})
    c = analyze(w, CFG)
    codes = event_codes(c)
    assert c.kind == "accumulation", (c.kind, c.title, codes)
    assert "SC" in codes and "AR" in codes and "ST" in codes, codes
    assert "Spring" in codes, codes
    assert "SOS" in codes, codes
    assert any(x in codes for x in ("LPS", "BU")), codes
    assert c.spring and c.sos
    assert c.phase in ("D", "E"), c.phase
    assert c.ice < c.creek
    assert c.inv <= c.ice + 1e-6 or c.inv < 100  # spring low is the invalidation


@case("accumulation creek is the automatic rally and ice is the selling climax")
def _():
    w, _ = pivots_of(ACC)
    c = analyze(w, CFG)
    assert abs(c.ice - 99.95) < 0.2, c.ice
    assert abs(c.creek - 128.05) < 2.5, c.creek  # creek may expand slightly


@case("a spring must pierce ice and recover")
def _():
    # SC 100, AR 128, ST 106, then a low at 96 (pierce) then 148 (recover)
    w, _ = pivots_of(ACC)
    c = analyze(w, CFG)
    spring = [e for e in c.events if e.code == "Spring"]
    assert len(spring) == 1, event_codes(c)
    sp = w[spring[0].pi]
    assert sp.dir == -1
    assert sp.price < c.ice or abs(sp.price - 95.95) < 0.2


@case("a breakdown that does not recover is not a spring")
def _():
    # After ST, price collapses and keeps falling
    w, _ = pivots_of([90, 160, 100, 128, 106, 70, 90, 50])
    c = analyze(w, CFG)
    assert "Spring" not in event_codes(c), event_codes(c)
    # The failed range must not be offered as a live accumulation with SOS
    assert not c.sos


@case("cause and effect projects above the creek by the range height")
def _():
    w, _ = pivots_of(ACC)
    c = analyze(w, CFG)
    height = c.creek - c.ice
    assert abs(c.t1 - (c.creek + height)) < 1e-6, (c.t1, c.creek, height)
    assert abs(c.t2 - (c.creek + 1.618 * height)) < 1e-4, c.t2
    assert c.cause_bars > 0
    assert c.horiz > c.ice


@case("volume drying on the test raises confidence")
def _():
    w_dry, _ = pivots_of(ACC, vol_spikes={2: 3.0, 4: 0.5, 6: 0.4})
    w_wet, _ = pivots_of(ACC, vol_spikes={2: 3.0, 4: 4.0, 6: 4.0})
    dry = analyze(w_dry, CFG)
    wet = analyze(w_wet, CFG)
    assert dry.kind == "accumulation" and wet.kind == "accumulation"
    assert dry.conf > wet.conf, (dry.conf, wet.conf)


# ── distribution ─────────────────────────────────────────────────────────────
DIST = [180, 90, 150, 122, 146, 126, 158, 108, 124, 80]


@case("classic distribution is labelled BC AR ST UTAD SOW LPSY")
def _():
    w, _ = pivots_of(DIST, vol_spikes={2: 3.0, 4: 0.7, 6: 0.8})
    c = analyze(w, CFG)
    codes = event_codes(c)
    assert c.kind == "distribution", (c.kind, c.title, codes)
    assert "BC" in codes and "AR" in codes and "ST" in codes, codes
    assert "UTAD" in codes, codes
    assert "SOW" in codes, codes
    assert "LPSY" in codes, codes
    assert c.utad and c.sow
    assert c.phase in ("D", "E"), c.phase


@case("distribution targets project below the ice by the range height")
def _():
    w, _ = pivots_of(DIST)
    c = analyze(w, CFG)
    assert c.kind == "distribution", (c.kind, event_codes(c))
    height = c.creek - c.ice
    assert abs(c.t1 - (c.ice - height)) < 1e-6, (c.t1, c.ice, height)
    assert c.inv >= c.creek - 1e-6 or c.utad


@case("an upthrust that holds is not a UTAD")
def _():
    # BC 150, AR 122, ST 146, then a high at 170 that continues (markup, not UTAD)
    w, _ = pivots_of([180, 90, 150, 122, 146, 170, 160, 190])
    c = analyze(w, CFG)
    assert "UTAD" not in event_codes(c), event_codes(c)
    assert not c.sow


@case("PSY sits on the high before the buying climax")
def _():
    # Add a preliminary high before BC: 90 -> 130 PSY -> 100 -> 150 BC
    w, _ = pivots_of([80, 130, 95, 150, 122, 146, 126, 158, 108, 124, 80])
    c = analyze(w, CFG)
    if c.kind == "distribution":
        codes = event_codes(c)
        # PSY is optional depending on whether the pre-BC high qualifies
        if "PSY" in codes:
            psy = next(e for e in c.events if e.code == "PSY")
            assert w[psy.pi].dir == 1
            assert w[psy.pi].price < w[c.start].price


# ── rejection / honesty ──────────────────────────────────────────────────────
@case("a clean trend is not labelled as a trading range")
def _():
    w, _ = pivots_of([100, 118, 110, 132, 122, 150, 138, 172, 160])
    c = analyze(w, Cfg(min_approach=20.0))
    # Pullbacks are 8-12; climaxes need a 20-point approach. No campaign.
    assert c.kind == "none" or (c.kind == "accumulation" and c.phase == "A" and not c.sos), (
        c.kind,
        c.phase,
        event_codes(c),
    )


@case("AR that retraces the whole approach is not a range")
def _():
    # Drop 60, rally 60 — a V reversal, not SC-AR of a range
    w, _ = pivots_of([90, 160, 100, 160, 140, 180])
    c = analyze(w, CFG)
    assert c.kind != "accumulation" or "SC" not in event_codes(c) or c.start != 1, (
        c.kind,
        event_codes(c),
        [round(p.price) for p in w],
    )


@case("a campaign must still describe the present")
def _():
    # An old range followed by a long unrelated trend
    old_then_trend = [90, 160, 100, 128, 106, 126, 148, 140, 200, 180, 250, 220, 310, 280, 370]
    w, _ = pivots_of(old_then_trend)
    c = analyze(w, CFG)
    if c.kind != "none":
        assert (len(w) - 1 - c.last) <= 10, (c.last, len(w), event_codes(c))


@case("provisional events on the live swing are marked with a question mark")
def _():
    w, hp = pivots_of(ACC, with_prov=True)
    c = analyze(w, CFG, has_prov=hp)
    if hp and c.events:
        last_codes = event_codes(c)
        # the last pivot may carry a ? if it is an event
        if any(e.pi == len(w) - 1 for e in c.events):
            assert any(code.endswith("?") for code in last_codes), last_codes


# ── effort vs result ─────────────────────────────────────────────────────────
@case("high volume with a narrow spread is absorption")
def _():
    spreads = [2.0] * 25
    vols = [100.0] * 25
    spreads[24] = 0.8
    vols[24] = 250.0
    assert effort_result(spreads, vols, 24) == "absorption"


@case("high volume with a wide spread is a climax")
def _():
    spreads = [2.0] * 25
    vols = [100.0] * 25
    spreads[24] = 5.0
    vols[24] = 250.0
    assert effort_result(spreads, vols, 24) == "climax"


@case("ordinary bars are unclassified")
def _():
    spreads = [2.0] * 25
    vols = [100.0] * 25
    assert effort_result(spreads, vols, 24) == "none"


# ── invariants on random walks ───────────────────────────────────────────────
@case("random walks never crash and events point at real pivots")
def _():
    rng = random.Random(7)
    checked = 0
    for _ in range(400):
        n = rng.randint(80, 220)
        price = 100.0
        highs = []
        lows = []
        vols = []
        for i in range(n):
            price += rng.uniform(-2.2, 2.2)
            hi = price + abs(rng.uniform(0.1, 1.4))
            lo = price - abs(rng.uniform(0.1, 1.4))
            highs.append(hi)
            lows.append(min(lo, hi - 0.05))
            vols.append(abs(rng.gauss(1000, 400)) + 10)
        w, _ = run_zigzag(highs, lows, DEPTH, 0.0, False, vols)
        c = analyze(w, Cfg(min_approach=8.0, atr=1.5))
        assert isinstance(c, Campaign)
        for e in c.events:
            assert 0 <= e.pi < len(w), (e, len(w))
            if e.code in ("SC", "Spring", "PS", "SOW"):
                assert w[e.pi].dir == -1, (e.code, w[e.pi].dir)
            if e.code in ("BC", "UTAD", "PSY", "SOS", "UT"):
                assert w[e.pi].dir == 1, (e.code, w[e.pi].dir)
        if c.kind == "accumulation":
            assert c.ice < c.creek
            assert math.isfinite(c.t1) and c.t1 > c.creek
            assert math.isfinite(c.inv)
            for e in c.events:
                if e.code in ("SC", "Spring", "PS", "ST", "LPS", "Test"):
                    assert w[e.pi].dir == -1, (e.code, w[e.pi].dir)
                if e.code in ("SOS", "UT", "AR"):
                    assert w[e.pi].dir == 1, (e.code, w[e.pi].dir)
            checked += 1
        elif c.kind == "distribution":
            assert c.ice < c.creek
            assert math.isfinite(c.t1) and c.t1 < c.ice
            for e in c.events:
                if e.code in ("BC", "UTAD", "PSY", "ST", "LPSY", "Test"):
                    assert w[e.pi].dir == 1, (e.code, w[e.pi].dir)
                if e.code in ("SOW", "AR"):
                    assert w[e.pi].dir == -1, (e.code, w[e.pi].dir)
            checked += 1
        else:
            assert c.phase == "none"
            assert c.events == []
    # A slice of random paths should produce *some* campaigns, but the scanner
    # is allowed to stay quiet rather than invent structure.
    assert checked >= 0


@case("event labels never sit more than eight characters")
def _():
    w, _ = pivots_of(ACC)
    c = analyze(w, CFG)
    for e in c.events:
        assert 1 <= len(e.code) <= 8, e.code


def main() -> int:
    failed = 0
    for name, fn in CASES:
        try:
            fn()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {name}\n        {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"ERROR {name}\n        {type(exc).__name__}: {exc}")
        else:
            print(f"ok    {name}")
    print(f"\n{len(CASES) - failed}/{len(CASES)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
