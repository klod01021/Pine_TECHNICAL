"""Drives the Python port of the indicator's counting logic with synthetic
price paths whose wave structure is known in advance.

Run with:  python3 tools/test_wave_logic.py
"""

from __future__ import annotations

import math
import sys

from wave_logic_reference import Zig, analyze, impulse_fit, leg_dir, run_zigzag, targets

EPS = 0.05
DEPTH = 5
BARS = 12


def make_series(points: list[float], bars: int = BARS, noise: float = 0.0):
    """Piecewise linear path through `points`, one bar per step.

    Returns (highs, lows) plus the bar index of every turning point so tests can
    assert that the zig-zag recovered exactly the swings that were injected.
    """
    highs: list[float] = []
    lows: list[float] = []
    turns: list[int] = []
    for i in range(len(points) - 1):
        a, b = points[i], points[i + 1]
        turns.append(len(highs))
        for j in range(bars):
            v = a + (b - a) * j / bars
            if noise and j not in (0, bars - 1):
                v += noise * math.sin(j * 2.3 + i)
            highs.append(v + EPS)
            lows.append(v - EPS)
    turns.append(len(highs))
    highs.append(points[-1] + EPS)
    lows.append(points[-1] - EPS)
    return highs, lows, turns


def pivots_of(points, min_move=0.0, noise=0.0, with_prov=False):
    highs, lows, _ = make_series(points, noise=noise)
    return run_zigzag(highs, lows, DEPTH, min_move, with_prov)


def prices(w):
    return [round(p.price, 2) for p in w]


def labels(count):
    return [t.txt + ("?" if t.prov else "") for t in count.tags]


CASES: list[tuple[str, callable]] = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn

    return deco


# ── swing detection ──────────────────────────────────────────────────────────
@case("zig-zag recovers the injected swings")
def _():
    w, _ = pivots_of([115, 100, 120, 110, 150, 135, 165, 160])
    # a swing low is taken from `low` (-EPS), a swing high from `high` (+EPS)
    assert prices(w) == [99.95, 120.05, 109.95, 150.05, 134.95, 165.05], prices(w)
    assert [p.dir for p in w] == [-1, 1, -1, 1, -1, 1]
    assert [p.bar for p in w] == [12, 24, 36, 48, 60, 72], [p.bar for p in w]


@case("noise below the filter does not create extra swings")
def _():
    w, _ = pivots_of([115, 100, 120, 110, 150, 135, 165, 160], min_move=4.0, noise=1.2)
    assert len(w) == 6, prices(w)


# ── impulses ─────────────────────────────────────────────────────────────────
@case("clean bull impulse is labelled 1-5")
def _():
    w, _ = pivots_of([115, 100, 120, 110, 150, 135, 165, 160])
    c = analyze(w, True, True, 25, 0)
    assert c.phase == "impulse" and c.legs == 5, (c.phase, c.legs)
    assert labels(c) == ["1", "2", "3", "4", "5"]
    assert [t.pi for t in c.tags] == [1, 2, 3, 4, 5]
    assert c.conf > 40, c.conf


@case("clean bear impulse is labelled 1-5")
def _():
    w, _ = pivots_of([85, 100, 80, 90, 50, 65, 35, 40])
    c = analyze(w, True, True, 25, 0)
    assert c.phase == "impulse" and c.legs == 5, (c.phase, c.legs)
    assert labels(c) == ["1", "2", "3", "4", "5"]


@case("impulse followed by A-B-C")
def _():
    w, _ = pivots_of([115, 100, 120, 110, 150, 135, 165, 140, 155, 128, 133])
    c = analyze(w, True, True, 25, 0)
    assert labels(c) == ["1", "2", "3", "4", "5", "A", "B", "C"], labels(c)
    assert c.phase == "corrective" and c.legs == 3
    assert c.title.startswith("Zigzag"), c.title


@case("impulse, correction, then a new impulse in progress")
def _():
    w, _ = pivots_of([115, 100, 120, 110, 150, 135, 165, 140, 155, 128, 175, 160, 168])
    c = analyze(w, True, True, 25, 0)
    assert labels(c)[:8] == ["1", "2", "3", "4", "5", "A", "B", "C"], labels(c)
    assert labels(c)[8:] == ["1", "2"], labels(c)
    assert c.phase == "impulse" and c.legs == 2, (c.phase, c.legs)
    assert "wave 3 in progress" in c.title, c.title


@case("partial impulse reports the wave in progress")
def _():
    w, _ = pivots_of([115, 100, 120, 110, 150, 145])
    c = analyze(w, True, True, 25, 0)
    assert c.phase == "impulse" and c.legs == 3, (c.phase, c.legs)
    assert labels(c) == ["1", "2", "3"]
    assert "wave 4 in progress" in c.title, c.title


@case("the live swing is counted and flagged with '?'")
def _():
    # price is still inside wave 5, so the fifth swing is not confirmed yet
    w, hp = pivots_of([115, 100, 120, 110, 150, 135, 160], with_prov=True)
    assert hp is True
    c = analyze(w, True, True, 25, 0, has_prov=hp)
    assert labels(c) == ["1", "2", "3", "4", "5?"], labels(c)
    assert c.tags[-1].prov is True


# ── the three hard rules ─────────────────────────────────────────────────────
@case("R1 rejects a wave 2 that retraces beyond the start of wave 1")
def _():
    w, _ = pivots_of([115, 100, 120, 95, 150, 135, 165, 160])
    c = analyze(w, True, True, 25, 0)
    assert not (c.phase == "impulse" and c.legs == 5), (c.phase, c.legs, labels(c))


@case("R2 rejects wave 3 being the shortest of 1, 3 and 5")
def _():
    w, _ = pivots_of([145, 100, 130, 115, 140, 132, 175, 170])
    c = analyze(w, True, True, 25, 0)
    assert not (c.phase == "impulse" and c.legs == 5), (c.phase, c.legs, labels(c))


@case("R3 rejects a wave 4 that overlaps wave 1 when diagonals are off")
def _():
    w, _ = pivots_of([115, 100, 120, 110, 150, 115, 165, 160])
    strict = analyze(w, False, True, 25, 0)
    assert not (strict.phase == "impulse" and strict.legs == 5), (strict.phase, strict.legs)
    loose = analyze(w, True, True, 25, 0)
    assert loose.phase == "impulse" and loose.legs == 5 and loose.diag is True
    assert loose.title.startswith("Diagonal"), loose.title


@case("a truncated wave 5 is rejected when truncation is disallowed")
def _():
    w, _ = pivots_of([115, 100, 120, 110, 150, 135, 148, 143])
    strict = analyze(w, True, False, 25, 0)
    assert not (strict.phase == "impulse" and strict.legs == 5)
    loose = analyze(w, True, True, 25, 0)
    assert loose.phase == "impulse" and loose.legs == 5


# ── other structures ─────────────────────────────────────────────────────────
@case("contracting triangle after an impulse")
def _():
    w, _ = pivots_of([115, 100, 120, 110, 150, 135, 165, 145, 160, 147, 157, 149, 153])
    c = analyze(w, True, True, 25, 0)
    assert c.phase == "triangle", (c.phase, labels(c), c.title)
    assert labels(c)[5:] == ["A", "B", "C", "D", "E"], labels(c)


@case("a new impulse is counted even after a one-legged correction")
def _():
    # 1-5 up to 165, one sharp leg down to 140, then an obvious new 1-2-3 up.
    # This must not be smeared into a "diagonal" spanning both moves.
    w, _ = pivots_of([115, 100, 120, 110, 150, 135, 165, 140, 170, 158, 200, 190])
    c = analyze(w, True, True, 25, 0)
    assert labels(c) == ["1", "2", "3", "4", "5", "A", "1", "2", "3"], labels(c)
    assert c.phase == "impulse" and c.legs == 3, (c.phase, c.legs)
    assert "New impulse up" in c.title, c.title


@case("an overlapping count must be a real wedge to pass as a diagonal")
def _():
    # wave 4 overlaps wave 1 but the legs do not narrow, so this is not a
    # diagonal, it is two different moves being stitched together
    w, _ = pivots_of([145, 135, 165, 140, 170, 158, 200, 190])
    for s in range(0, max(1, len(w) - 5)):
        ok, sc, dg = impulse_fit(w, s, 5, True, True)
        assert not (ok and dg), f"non-wedge overlap accepted at s={s}"


@case("a genuine contracting diagonal is still accepted")
def _():
    # each impulse leg shorter than the last, wave 4 back inside wave 1
    w, _ = pivots_of([110, 100, 130, 115, 137, 122, 140, 138])
    ok, sc, dg = impulse_fit(w, 0, 5, True, True)
    assert ok and dg, (ok, dg)
    c = analyze(w, True, True, 25, 0)
    assert c.title.startswith("Diagonal up"), c.title


@case("one lone leg after a short correction is not called an impulse")
def _():
    w, _ = pivots_of([115, 100, 120, 110, 150, 135, 165, 140, 175, 170])
    c = analyze(w, True, True, 25, 0)
    assert labels(c) == ["1", "2", "3", "4", "5", "A"], labels(c)
    assert "unresolved" in c.title, c.title


@case("a correction may not finish above the top it is correcting")
def _():
    # after the 5-wave top at 165, price makes a HIGHER high at 175: whatever
    # this is, it is not an A-B-C correction of that impulse
    w, _ = pivots_of([115, 100, 120, 110, 150, 135, 165, 150, 175, 170, 172])
    c = analyze(w, True, True, 25, 0)
    top = w[5].price
    for t in c.tags:
        if t.corr:
            assert w[t.pi].price < top, f"corrective label {t.txt} sits above the impulse top {top}"
    assert "B" not in labels(c) and "C" not in labels(c), labels(c)


@case("a running flat is still accepted")
def _():
    # C ends above the low of A, but the whole correction stays below the top
    w, _ = pivots_of([115, 100, 120, 110, 150, 135, 165, 145, 162, 150, 156])
    c = analyze(w, True, True, 25, 0)
    assert labels(c) == ["1", "2", "3", "4", "5", "A", "B", "C"], labels(c)


@case("an expanded flat needs the option, and stays rejected without it")
def _():
    # wave B pokes past the start of A, wave C still ends well below it
    pts = [115, 100, 120, 110, 150, 135, 165, 150, 168, 140, 145]
    w, _ = pivots_of(pts)
    strict = analyze(w, True, True, 25, 0, allow_expanded=False)
    assert "B" not in labels(strict), labels(strict)
    loose = analyze(w, True, True, 25, 0, allow_expanded=True)
    assert labels(loose) == ["1", "2", "3", "4", "5", "A", "B", "C"], labels(loose)
    assert "Expanded flat" in loose.title, loose.title


@case("a triangle that drifts above the top is not a triangle")
def _():
    w, _ = pivots_of([115, 100, 120, 110, 150, 135, 165, 145, 170, 150, 168, 155, 160])
    c = analyze(w, True, True, 25, 0)
    assert c.phase != "triangle", (c.phase, labels(c))
    for t in c.tags:
        if t.corr:
            assert w[t.pi].price < w[5].price, labels(c)


@case("unresolved structure after a correction is left unlabelled")
def _():
    # clean impulse, clean A-B-C, then chop that is neither an impulse nor a
    # readable correction: the script must not invent W-X-Y labels for it
    w, _ = pivots_of([115, 100, 120, 110, 150, 135, 165, 140, 155, 128, 133, 129, 134])
    c = analyze(w, True, True, 25, 0)
    assert "W" not in labels(c) and "X" not in labels(c) and "Y" not in labels(c), labels(c)
    assert labels(c)[:8] == ["1", "2", "3", "4", "5", "A", "B", "C"], labels(c)


@case("nothing is forced when the structure is unreadable")
def _():
    w, _ = pivots_of([100, 101, 100, 101, 100])
    c = analyze(w, True, True, 25, 0)
    assert c.legs <= 3


# ── targets and invalidation ─────────────────────────────────────────────────
@case("wave 5 projection and invalidation are anchored correctly")
def _():
    w, _ = pivots_of([115, 100, 120, 110, 150, 135, 140])
    c = analyze(w, True, True, 25, 0)
    assert c.phase == "impulse" and c.legs == 4, (c.phase, c.legs)
    lv, tx, inval = targets(w, c)
    p1, p2, p3, p4 = (w[i].price for i in (1, 2, 3, 4))
    l1, l3 = p1 - w[0].price, p3 - p2
    assert math.isclose(inval, p4)
    assert math.isclose(lv[tx.index("W5 = W1")], p4 + l1)
    assert math.isclose(lv[tx.index("W5 0.618 x (W1+W3)")], p4 + 0.618 * (l1 + l3))
    assert all(v > p4 for v in lv), lv


@case("bear invalidation sits above the wave 2 high")
def _():
    w, _ = pivots_of([85, 100, 80, 90, 85])
    c = analyze(w, True, True, 25, 0)
    assert c.phase == "impulse" and c.legs == 2, (c.phase, c.legs)
    lv, tx, inval = targets(w, c)
    assert math.isclose(inval, w[2].price)
    assert all(v < w[2].price for v in lv), lv


@case("retracement targets follow a completed impulse")
def _():
    w, _ = pivots_of([115, 100, 120, 110, 150, 135, 165, 160])
    c = analyze(w, True, True, 25, 0)
    lv, tx, inval = targets(w, c)
    p0, p5 = w[0].price, w[5].price
    assert math.isclose(inval, p5)
    assert math.isclose(lv[tx.index("Retrace 0.500")], p5 - 0.5 * (p5 - p0))


@case("random walks never break the swing or label invariants")
def _():
    import random

    random.seed(7)
    checked = 0
    for _ in range(300):
        bars = random.randint(60, 400)
        price = 100.0
        highs: list[float] = []
        lows: list[float] = []
        for _ in range(bars):
            price *= 1 + random.gauss(0, 0.012)
            rng = abs(random.gauss(0, 0.006)) * price
            highs.append(price + rng)
            lows.append(price - rng)
        depth = random.choice([3, 5, 8, 13])
        min_move = random.choice([0.0, 1.0, 3.0])
        for prov in (False, True):
            w, hp = run_zigzag(highs, lows, depth, min_move, prov)
            # the skeleton must alternate high/low and always move forward
            assert all(w[i].dir != w[i + 1].dir for i in range(len(w) - 1))
            assert all(w[i].bar < w[i + 1].bar for i in range(len(w) - 1))
            assert len(w) <= 61  # MAX_PIVOTS, plus the provisional swing
            c = analyze(w, True, True, random.choice([6, 25, 55]), 0, has_prov=hp)
            idx = [t.pi for t in c.tags]
            assert all(0 < i < len(w) for i in idx), (idx, len(w))
            assert idx == sorted(idx) and len(set(idx)) == len(idx), idx
            assert 0.0 <= c.conf <= 100.0, c.conf
            # any accepted overlap must be a genuine wedge
            if c.diag and c.legs == 5 and c.anchor >= 0:
                d = leg_dir(w, c.anchor)
                q = [d * w[c.anchor + i].price for i in range(6)]
                e1, e3, e5 = q[1] - q[0], q[3] - q[2], q[5] - q[4]
                assert (e3 < e1 and e5 < e3) or (e3 > e1 and e5 > e3), (e1, e3, e5)
            # no corrective label may sit past the move it is correcting
            corr = [t for t in c.tags if t.corr]
            if corr:
                a = corr[0].pi - 1
                d = leg_dir(w, a)
                la = abs(w[a + 1].price - w[a].price)
                for t in corr:
                    assert d * w[t.pi].price > d * w[a].price - 0.06 * la, (
                        f"{t.txt} at {w[t.pi].price} is past the start {w[a].price}"
                    )
            lv, tx, inval = targets(w, c)
            assert len(lv) == len(tx)
            assert all(math.isfinite(v) for v in lv), lv
            checked += 1
    assert checked == 600


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
