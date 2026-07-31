"""Line-for-line Python port of the counting logic in
``indicators/elliott_wave_auto_counter_v1.pine``.

Pine Script cannot be executed outside TradingView, so this module mirrors the
zig-zag engine, the rule tests and the labelling strategy exactly as they are
written in the indicator. ``tools/test_wave_logic.py`` drives it with synthetic
wave structures to prove the rules and the pivot indexing behave as intended.

Keep the two files in sync: if a rule changes in the Pine source, change it here
and extend the test.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

MAX_PIVOTS = 60


@dataclass
class Pivot:
    bar: int
    price: float
    dir: int  # +1 swing high, -1 swing low


@dataclass
class Tag:
    pi: int
    txt: str
    corr: bool
    prov: bool


@dataclass
class Count:
    tags: list[Tag] = field(default_factory=list)
    title: str = "No valid count"
    phase: str = "none"
    legs: int = 0
    anchor: int = -1
    conf: float = 0.0
    diag: bool = False


# ── helpers ──────────────────────────────────────────────────────────────────
def fit(x: float, ideal: float) -> float:
    tol = max(0.08, ideal * 0.18)
    return math.exp(-(((x - ideal) / tol) ** 2.0))


def fit4(x: float, a: float, b: float, c: float, d: float) -> float:
    return max(fit(x, a), fit(x, b), fit(x, c), fit(x, d))


def wave_txt(i: int, corr: bool, sty: str = "1 2 3 4 5 / A B C") -> str:
    hi = {1: "A", 2: "B", 3: "C", 4: "D", 5: "E"}[i]
    return hi if corr else str(i)


def cplx_txt(i: int) -> str:
    return {1: "W", 2: "X", 3: "Y"}[i]


def leg_dir(w: list[Pivot], i: int) -> int:
    return 1 if w[i].dir == -1 else -1


# ── zig-zag engine ───────────────────────────────────────────────────────────
class Zig:
    def __init__(self) -> None:
        self.pv: list[Pivot] = []
        self.changed = False
        self.run_hi: float | None = None
        self.run_hi_bar: int | None = None
        self.run_lo: float | None = None
        self.run_lo_bar: int | None = None

    def add_pivot(self, b: int, p: float, d: int, min_move: float) -> None:
        n = len(self.pv)
        if n == 0:
            self.pv.append(Pivot(b, p, d))
            self.changed = True
        else:
            lp = self.pv[-1]
            if lp.dir == d:
                if (d == 1 and p > lp.price) or (d == -1 and p < lp.price):
                    lp.bar = b
                    lp.price = p
                    self.changed = True
            elif b > lp.bar and abs(p - lp.price) >= min_move:
                self.pv.append(Pivot(b, p, d))
                self.changed = True
        if len(self.pv) > MAX_PIVOTS:
            self.pv.pop(0)

    def step(self, highs: list[float], lows: list[float], i: int, depth: int, min_move: float) -> None:
        """One bar of ``method step``. ``i`` is the current bar index."""
        self.changed = False
        pb = i - depth
        # ta.pivothigh / ta.pivotlow: an extreme with `depth` bars either side
        if pb >= depth:
            window_h = highs[pb - depth : pb + depth + 1]
            if highs[pb] == max(window_h) and window_h.count(highs[pb]) == 1:
                self.add_pivot(pb, highs[pb], 1, min_move)
            window_l = lows[pb - depth : pb + depth + 1]
            if lows[pb] == min(window_l) and window_l.count(lows[pb]) == 1:
                self.add_pivot(pb, lows[pb], -1, min_move)
        # ta.highest / ta.lowest over the window that starts at the pivot bar
        lo_idx = max(0, i - depth)
        w_hi = max(highs[lo_idx : i + 1])
        w_lo = min(lows[lo_idx : i + 1])
        o_hi = lo_idx + highs[lo_idx : i + 1].index(w_hi)
        o_lo = lo_idx + lows[lo_idx : i + 1].index(w_lo)
        if self.changed or self.run_hi is None:
            self.run_hi, self.run_hi_bar = w_hi, o_hi
            self.run_lo, self.run_lo_bar = w_lo, o_lo
        else:
            if highs[i] > self.run_hi:
                self.run_hi, self.run_hi_bar = highs[i], i
            if lows[i] < self.run_lo:
                self.run_lo, self.run_lo_bar = lows[i], i

    def build_work(self, with_prov: bool) -> tuple[list[Pivot], bool]:
        w = list(self.pv)
        hp = False
        if with_prov and w:
            lp = w[-1]
            if lp.dir == -1 and self.run_hi_bar is not None and self.run_hi_bar > lp.bar and self.run_hi > lp.price:
                w.append(Pivot(self.run_hi_bar, self.run_hi, 1))
                hp = True
            elif lp.dir == 1 and self.run_lo_bar is not None and self.run_lo_bar > lp.bar and self.run_lo < lp.price:
                w.append(Pivot(self.run_lo_bar, self.run_lo, -1))
                hp = True
        return w, hp


# ── pattern tests ────────────────────────────────────────────────────────────
def impulse_fit(w, s, legs, allow_diag, allow_trunc):
    n = len(w)
    ok = s >= 0 and 1 <= legs <= 5 and (s + legs) <= (n - 1)
    d = q0 = q1 = q2 = q3 = q4 = q5 = 0.0
    l1 = l2 = l3 = l4 = l5 = 0.0
    total, cnt, dg = 0.0, 0, False
    if ok:
        d = leg_dir(w, s)
        q0 = d * w[s].price
        q1 = d * w[s + 1].price
        l1 = q1 - q0
        ok = l1 > 0
    if ok and legs >= 2:
        q2 = d * w[s + 2].price
        l2 = q1 - q2
        ok = q2 > q0 and l2 > 0  # R1
        if ok:
            total += fit4(l2 / l1, 0.382, 0.5, 0.618, 0.786)
            cnt += 1
    if ok and legs >= 3:
        q3 = d * w[s + 3].price
        l3 = q3 - q2
        ok = q3 > q1
        if ok:
            total += fit4(l3 / l1, 1.0, 1.618, 2.618, 4.236)
            cnt += 1
    if ok and legs >= 4:
        q4 = d * w[s + 4].price
        l4 = q3 - q4
        dg = q4 <= q1
        ok = l4 > 0 and (q4 > q2 if allow_diag else q4 > q1)  # R3
        if ok:
            total += fit4(l4 / l3, 0.236, 0.382, 0.5, 0.618)
            cnt += 1
            total += 1.0 if abs(l2 / l1 - l4 / l3) > 0.15 else 0.4
            cnt += 1
    trunc = False
    if ok and legs >= 5:
        q5 = d * w[s + 5].price
        l5 = q5 - q4
        trunc = q5 <= q3
        ok = l5 > 0 and (allow_trunc or not trunc) and not (l3 < l1 and l3 < l5)  # R2
        # An overlap is only forgiven for a diagonal, and a diagonal is a wedge:
        # its impulse legs either narrow or widen throughout. Without this an
        # overlapping count is free to staple two unrelated moves together.
        if ok and dg:
            ok = (l3 < l1 and l5 < l3) or (l3 > l1 and l5 > l3)
        if ok:
            total += fit4(l5 / l1, 0.382, 0.618, 1.0, 1.618)
            cnt += 1
    sc = total / cnt if (ok and cnt > 0) else 0.0
    # Diagonals and truncations are real but uncommon, so a count that needs one
    # of them has to beat a textbook count by a clear margin to be preferred.
    if dg:
        sc *= 0.80
    if trunc:
        sc *= 0.85
    return ok, sc, dg


def corrective_fit(w, s, legs, allow_expanded=False, limit_price=None):
    n = len(w)
    ok = s >= 0 and 1 <= legs <= 3 and (s + legs) <= (n - 1)
    d = q0 = q1 = q2 = q3 = la = rb = rc = 0.0
    total, cnt, knd = 0.0, 0, "Correction"
    if ok:
        d = leg_dir(w, s)
        q0 = d * w[s].price
        q1 = d * w[s + 1].price
        la = q1 - q0
        ok = la > 0
    if ok and legs >= 2:
        q2 = d * w[s + 2].price
        rb = (q1 - q2) / la
        # Wave B beyond the start of wave A is an expanded flat: real, but
        # uncommon enough that it has to be asked for. Without it a correction
        # can never print a new extreme past the move it is correcting.
        ok = 0.1 < rb <= (1.382 if allow_expanded else 1.05)
        if ok:
            total += fit4(rb, 0.5, 0.618, 0.786, 1.0)
            cnt += 1
            knd = "Zigzag" if rb <= 0.618 else "Zigzag / flat" if rb <= 0.9 else "Flat" if rb <= 1.05 else "Expanded flat"
    if ok and legs >= 3:
        q3 = d * w[s + 3].price
        rc = (q3 - q2) / la
        # A completed correction must finish on the correcting side of where it
        # began, otherwise the net move is with the trend and this is no
        # correction at all.
        ok = 0.382 <= rc <= 4.236 and q3 > q0
        if ok:
            total += fit4(rc, 0.618, 1.0, 1.618, 2.618)
            cnt += 1
    if ok and limit_price is not None:
        # A correction retraces part of a move. Once it erases the whole thing
        # and trades past where that move began, it is not correcting it any
        # more, it is a new impulse in the other direction.
        for k in range(1, legs + 1):
            if d * w[s + k].price > d * limit_price:
                ok = False
    sc = total / cnt if (ok and cnt > 0) else 0.0
    if rb > 1.0:
        sc *= 0.85
    return ok, sc, knd


def triangle_fit(w, s, legs, limit_price=None):
    n = len(w)
    ok = s >= 0 and 4 <= legs <= 5 and (s + legs) <= (n - 1)
    e3 = 0.0
    if ok:
        e1 = abs(w[s + 1].price - w[s].price)
        e2 = abs(w[s + 2].price - w[s + 1].price)
        e3 = abs(w[s + 3].price - w[s + 2].price)
        e4 = abs(w[s + 4].price - w[s + 3].price)
        ok = e3 < e1 and e4 < e2 and e3 > 0 and e4 > 0
    if ok and legs == 5:
        e5 = abs(w[s + 5].price - w[s + 4].price)
        ok = e5 < e3 and e5 > 0
    if ok:
        # every corner has to stay on the correcting side of the start, so a
        # triangle can never drift past the move it is correcting
        d = leg_dir(w, s)
        q0 = d * w[s].price
        ok = all(d * w[s + k].price > q0 for k in range(1, legs + 1))
        if ok and limit_price is not None:
            ok = all(d * w[s + k].price <= d * limit_price for k in range(1, legs + 1))
    return ok


def leg_velocity(w, i) -> float:
    """Price covered per bar by the leg ending at pivot i."""
    db = w[i].bar - w[i - 1].bar
    return abs(w[i].price - w[i - 1].price) / db if db > 0 else 0.0


def impulse_velocity(w, s) -> float:
    """Mean velocity of the directional waves 1, 3 and 5 of an impulse."""
    vs = [leg_velocity(w, s + k) for k in (1, 3, 5) if s + k < len(w)]
    vs = [v for v in vs if v > 0]
    return sum(vs) / len(vs) if vs else 0.0


def leg_character(sub, bar_a, bar_b, allow_diag=True, allow_trunc=True) -> int:
    """Is the leg between two bars built like an impulse or like a correction?

    The oldest discriminator in Elliott: an impulsive leg subdivides into five
    waves at the next degree down, a corrective one into three. Returns +1 for
    impulsive, -1 for corrective and 0 when the lower degree cannot tell.
    """
    if not sub:
        return 0
    idx = [i for i, p in enumerate(sub) if bar_a <= p.bar <= bar_b]
    if len(idx) < 4:
        return 0
    first, legs = idx[0], idx[-1] - idx[0]
    if legs >= 5:
        ok, _, _ = impulse_fit(sub, first, 5, allow_diag, allow_trunc)
        if ok:
            return 1
    if legs == 3:
        ok, _, _ = corrective_fit(sub, first, 3)
        if ok:
            return -1
    return 0


# ── the count ────────────────────────────────────────────────────────────────
def analyze(w, allow_diag, allow_trunc, look, min_fit, sty="1 2 3 4 5 / A B C", has_prov=False, allow_expanded=False, sub=None) -> Count:
    c = Count(tags=[])
    n = len(w)
    i_last = n - 1
    best, best_sc, best_dg = -1, 0.0, False
    best_rank = -1e6
    if n >= 6:
        s_from = max(0, n - 1 - look)
        if n - 6 >= s_from:
            for s in range(s_from, n - 5):
                ok_a, sc_a, dg_a = impulse_fit(w, s, 5, allow_diag, allow_trunc)
                # Rank on quality, with a small bonus for being the more recent
                # structure, so a clean older count is not displaced by a poor
                # newer one that merely ends further to the right.
                rank = sc_a - 0.015 * (i_last - (s + 5))
                if ok_a and sc_a * 100 >= min_fit and rank > best_rank:
                    best, best_sc, best_dg, best_rank = s, sc_a, dg_a, rank
    if best >= 0:
        dir_i = leg_dir(w, best)
        c.phase, c.legs, c.anchor = "impulse", 5, best
        c.conf, c.diag = best_sc * 100, best_dg
        c.title = ("Diagonal " if best_dg else "Impulse ") + ("up" if dir_i == 1 else "down") + " complete"
        for k in range(1, 6):
            c.tags.append(Tag(best + k, wave_txt(k, False, sty), False, has_prov and best + k == i_last))
        e = best + 5
        rem = i_last - e
        if rem > 0:
            tri_legs = min(rem, 5)
            tri = rem >= 4 and triangle_fit(w, e, tri_legs, w[best].price)
            if tri:
                for k in range(1, tri_legs + 1):
                    c.tags.append(Tag(e + k, wave_txt(k, True, sty), True, has_prov and e + k == i_last))
                c.phase, c.legs, c.anchor = "triangle", tri_legs, e
                c.title = "Contracting triangle after the impulse"
            else:
                # Split what follows the impulse into a correction and, if the
                # trend has already resumed, the new impulse riding on it. Only
                # as much of the correction as validates is labelled - A-B-C,
                # then A-B, then A - and of the splits that survive, the one
                # accounting for the most swings wins. Ties go to the longest
                # correction, since three legs is the normal shape.
                cl, sc_c, knd = 0, 0.0, "Correction"
                lg, sc_i, dg_i = 0, 0.0, False
                explained, best_qual = -1, -1.0
                origin = w[best].price
                # Down-up-down after a top reads either as A-B-C or as waves
                # 1-2-3 of a new decline, and the two often score the same. The
                # lower degree breaks the tie: if that first leg subdivides
                # into five it is impulsive, so lean towards the impulse.
                char = leg_character(sub, w[e].bar, w[e + 1].bar, allow_diag, allow_trunc)
                # Second read on the same question: a correction is the market
                # resting, so it should not cover ground faster than the
                # impulse it is undoing. A first leg travelling further per bar
                # than the impulse averaged is behaving like a trend, not a
                # pause. Subdivision is the stronger evidence, so it is
                # weighted double; velocity decides when subdivision is silent.
                iv = impulse_velocity(w, best)
                ratio = (leg_velocity(w, e + 1) / iv) if iv > 0 else 1.0
                mom = 1 if ratio > 1.2 else (-1 if ratio < 0.8 else 0)
                bias = 0.05 - 0.075 * (2 * char + mom)
                if ratio > 2.0:
                    bias -= 0.25
                # t == 0 is the reversal case: no correction at all, the move
                # off the top is impulsive in its own right. It is tried last
                # so an equally long correction reading always wins the tie.
                for t in range(min(rem, 3), -1, -1):
                    ok_t, sc_t, knd_t = True, 0.0, "Correction"
                    if t > 0:
                        ok_t, sc_t, knd_t = corrective_fit(w, e, t, allow_expanded, origin)
                    if not ok_t:
                        continue
                    lg_t, sci_t, dgi_t = 0, 0.0, False
                    for length in range(min(rem - t, 5), 0, -1):
                        if lg_t == 0:
                            ok_i, sci, dgi = impulse_fit(w, e + t, length, allow_diag, allow_trunc)
                            if ok_i:
                                lg_t, sci_t, dgi_t = length, sci, dgi
                    # a single leg is too little to call a new impulse unless
                    # the correction before it is a complete three
                    if lg_t == 1 and t < 3:
                        lg_t = 0
                    qual = (t * sc_t + lg_t * sci_t) / max(1, t + lg_t)
                    if t + lg_t > explained or (t + lg_t == explained and qual > best_qual + bias):
                        explained, best_qual = t + lg_t, qual
                        cl, sc_c, knd = t, sc_t, knd_t
                        lg, sc_i, dg_i = lg_t, sci_t, dgi_t
                for k in range(1, cl + 1):
                    c.tags.append(Tag(e + k, wave_txt(k, True, sty), True, has_prov and e + k == i_last))
                if cl > 0:
                    c.phase, c.legs, c.anchor = "corrective", cl, e
                    if cl >= 2:
                        c.conf = sc_c * 100
                    c.title = knd + (
                        " in progress, wave " + wave_txt(cl + 1, True, sty) if cl < 3 else " complete"
                    )
                if lg > 0:
                    s2 = e + cl
                    for k in range(1, lg + 1):
                        c.tags.append(Tag(s2 + k, wave_txt(k, False, sty), False, has_prov and s2 + k == i_last))
                    dir2 = leg_dir(w, s2)
                    c.phase, c.legs, c.anchor = "impulse", lg, s2
                    c.conf, c.diag = sc_i * 100, dg_i
                    c.title = ("New impulse " + ("up" if dir2 == 1 else "down") + ", wave "
                               + wave_txt(min(lg + 1, 5), False, sty) + " in progress")
                elif rem > cl:
                    c.title += ", structure past it unresolved"
    else:
        lg, sc0, dg0 = 0, 0.0, False
        for i in range(0, 3):
            try_legs = 4 - i
            ok_b, sc_b, dg_b = impulse_fit(w, i_last - try_legs, try_legs, allow_diag, allow_trunc)
            if ok_b and lg == 0 and sc_b * 100 >= min_fit:
                lg, sc0, dg0 = try_legs, sc_b, dg_b
        if lg > 0:
            s = i_last - lg
            dir_p = leg_dir(w, s)
            c.phase, c.legs, c.anchor = "impulse", lg, s
            c.conf, c.diag = sc0 * 100, dg0
            c.title = ("Impulse " + ("up" if dir_p == 1 else "down") + ", wave "
                       + wave_txt(lg + 1, False, sty) + " in progress")
            for k in range(1, lg + 1):
                c.tags.append(Tag(s + k, wave_txt(k, False, sty), False, has_prov and s + k == i_last))
        elif n >= 3:
            cl = min(n - 1, 3)
            s = i_last - cl
            ok_d, sc_d, knd_d = corrective_fit(w, s, cl, allow_expanded)
            if ok_d:
                for k in range(1, cl + 1):
                    c.tags.append(Tag(s + k, wave_txt(k, True, sty), True, has_prov and s + k == i_last))
                c.phase, c.legs, c.anchor = "corrective", cl, s
                c.conf = sc_d * 100
                c.title = knd_d + (" in progress, wave " + wave_txt(cl + 1, True, sty) if cl < 3 else " complete")
    return c


def targets(w, c) -> tuple[list[float], list[str], float | None]:
    lv: list[float] = []
    tx: list[str] = []
    inval: float | None = None
    s, n = c.anchor, len(w)
    if s >= 0 and c.legs >= 1 and s + c.legs <= n - 1:
        d = leg_dir(w, s)
        p0, p1 = w[s].price, w[s + 1].price
        l1 = abs(p1 - p0)
        if c.phase == "impulse":
            if c.legs == 1:
                for r in (0.382, 0.5, 0.618):
                    lv.append(p1 - d * r * l1)
                    tx.append(f"W2 {r:.3f}")
                inval = p0
            elif c.legs == 2:
                p2 = w[s + 2].price
                for r in (1.618, 2.618):
                    lv.append(p2 + d * r * l1)
                    tx.append(f"W3 {r} x W1")
                inval = p2
            elif c.legs == 3:
                p2, p3 = w[s + 2].price, w[s + 3].price
                l3 = abs(p3 - p2)
                for r in (0.236, 0.382, 0.5):
                    lv.append(p3 - d * r * l3)
                    tx.append(f"W4 {r:.3f}")
                inval = p1
            elif c.legs == 4:
                p2, p3, p4 = w[s + 2].price, w[s + 3].price, w[s + 4].price
                l3 = abs(p3 - p2)
                lv.append(p4 + d * 0.618 * (l1 + l3))
                tx.append("W5 0.618 x (W1+W3)")
                lv.append(p4 + d * 1.0 * l1)
                tx.append("W5 = W1")
                lv.append(p4 + d * 1.618 * l1)
                tx.append("W5 1.618 x W1")
                inval = p4
            else:
                p5 = w[s + 5].price
                tot = abs(p5 - p0)
                for r in (0.382, 0.5, 0.618):
                    lv.append(p5 - d * r * tot)
                    tx.append(f"Retrace {r:.3f}")
                inval = p5
        elif c.phase in ("corrective", "complex"):
            if c.legs == 1:
                for r in (0.5, 0.618, 0.786):
                    lv.append(p1 - d * r * l1)
                    tx.append(f"B {r:.3f} x A")
                inval = p0
            elif c.legs == 2:
                p2 = w[s + 2].price
                for r in (0.618, 1.0, 1.618):
                    lv.append(p2 + d * r * l1)
                    tx.append(f"C {r} x A")
                inval = p0
            else:
                p3 = w[s + 3].price
                tot = abs(p3 - p0)
                lv.append(p3 - d * 0.618 * tot)
                tx.append("Resumption 0.618")
                lv.append(p3 - d * 1.0 * tot)
                tx.append("Full retrace of A-B-C")
                inval = p3
        elif c.phase == "triangle":
            pe = w[s + c.legs].price
            wide = abs(w[s + 1].price - w[s].price)
            lv.append(pe - d * 0.618 * wide)
            tx.append("Thrust 0.618 x widest leg")
            lv.append(pe - d * 1.0 * wide)
            tx.append("Thrust = widest leg")
    return lv, tx, inval


def fib_grid(w, c):
    """The Fibonacci ladder for the wave in progress, as the drawing tool draws it.

    Returns the ratios, their prices, the bar the measurement is anchored to, a
    description of what is being measured, and the two ratios bounding the
    primary target zone. Retracing waves (2, 4, B and the correction after an
    impulse) are measured back across the wave before them; extending waves
    (3, 5, C) are projected forward from where they began.
    """
    empty: tuple[list[float], list[float], int | None, str, tuple[float, float] | None] = ([], [], None, "", None)
    s, n = c.anchor, len(w)
    if s < 0 or c.legs < 1 or s + c.legs > n - 1:
        return empty
    d = leg_dir(w, s)
    p = [w[s + i].price for i in range(c.legs + 1)]
    bar = [w[s + i].bar for i in range(c.legs + 1)]
    l1 = abs(p[1] - p[0])

    ratios: tuple[float, ...] = ()
    base = anchor = 0.0
    length = 0.0
    sign = 0
    zone = None
    basis = ""
    anchor_bar = bar[0]

    if c.phase == "impulse":
        if c.legs == 1:                                    # wave 2 retraces wave 1
            ratios, base, length, sign = (0.236, 0.382, 0.5, 0.618, 0.786, 1.0), p[1], l1, -1
            zone, basis, anchor_bar = (0.5, 0.786), "retracement of wave 1", bar[0]
        elif c.legs == 2:                                  # wave 3 projects off wave 1
            ratios, base, length, sign = (1.0, 1.272, 1.618, 2.0, 2.618, 4.236), p[2], l1, 1
            zone, basis, anchor_bar = (1.618, 2.618), "wave 1 projected from wave 2", bar[0]
        elif c.legs == 3:                                  # wave 4 retraces wave 3
            l3 = abs(p[3] - p[2])
            ratios, base, length, sign = (0.236, 0.382, 0.5, 0.618), p[3], l3, -1
            zone, basis, anchor_bar = (0.236, 0.5), "retracement of wave 3", bar[2]
        elif c.legs == 4:                                  # wave 5 projects off wave 1
            ratios, base, length, sign = (0.382, 0.618, 1.0, 1.618, 2.618), p[4], l1, 1
            zone, basis, anchor_bar = (0.618, 1.618), "wave 1 projected from wave 4", bar[0]
        else:                                              # the correction to come
            total = abs(p[5] - p[0])
            ratios, base, length, sign = (0.236, 0.382, 0.5, 0.618, 0.786), p[5], total, -1
            zone, basis, anchor_bar = (0.382, 0.618), "retracement of the impulse", bar[0]
    elif c.phase == "corrective":
        if c.legs == 1:                                    # wave B retraces wave A
            ratios, base, length, sign = (0.236, 0.382, 0.5, 0.618, 0.786, 1.0), p[1], l1, -1
            zone, basis, anchor_bar = (0.5, 0.786), "retracement of wave A", bar[0]
        elif c.legs == 2:                                  # wave C projects off wave A
            ratios, base, length, sign = (0.618, 1.0, 1.272, 1.618, 2.618), p[2], l1, 1
            zone, basis, anchor_bar = (1.0, 1.618), "wave A projected from wave B", bar[0]
        else:                                              # the move out of the correction
            total = abs(p[3] - p[0])
            ratios, base, length, sign = (0.382, 0.618, 1.0, 1.618), p[3], total, -1
            zone, basis, anchor_bar = (0.618, 1.0), "retracement of the correction", bar[0]
    if not ratios or length <= 0:
        return empty

    prices = [base + sign * d * r * length for r in ratios]
    return list(ratios), prices, anchor_bar, basis, zone


def fib_zone_prices(ratios, prices, zone):
    """The two prices bounding the primary target zone, low first."""
    if not zone or not ratios:
        return None, None
    lo = prices[ratios.index(zone[0])] if zone[0] in ratios else None
    hi = prices[ratios.index(zone[1])] if zone[1] in ratios else None
    if lo is None or hi is None:
        return None, None
    return min(lo, hi), max(lo, hi)


def time_targets(w, c) -> tuple[list[int], int | None]:
    """Bar indices where the wave in progress is projected to end.

    Waves relate in time by the same ratios they relate in price, so each
    projection is a Fibonacci multiple of the duration of the wave it is
    usually measured against. Returns the projections and the bar the wave in
    progress started from.
    """
    s, n = c.anchor, len(w)
    if s < 0 or c.legs < 1 or s + c.legs > n - 1:
        return [], None
    start = w[s + c.legs].bar

    def dur(i: int) -> int:
        return w[s + i].bar - w[s + i - 1].bar

    ref, ratios = 0, ()
    if c.phase == "impulse":
        if c.legs == 1:
            ref, ratios = dur(1), (0.382, 0.618, 1.0)          # wave 2
        elif c.legs == 2:
            ref, ratios = dur(1), (1.0, 1.618, 2.618)          # wave 3
        elif c.legs == 3:
            ref, ratios = dur(3), (0.382, 0.618, 1.0)          # wave 4
        elif c.legs == 4:
            ref, ratios = dur(1), (0.618, 1.0, 1.618)          # wave 5
        else:
            ref, ratios = w[s + 5].bar - w[s].bar, (0.382, 0.618, 1.0)   # the correction
    elif c.phase == "corrective":
        if c.legs == 1:
            ref, ratios = dur(1), (0.5, 0.618, 1.0)            # wave B
        elif c.legs == 2:
            ref, ratios = dur(1), (0.618, 1.0, 1.618)          # wave C
        else:
            ref, ratios = w[s + 3].bar - w[s].bar, (0.382, 0.618, 1.0)   # the next impulse
    if ref <= 0 or not ratios:
        return [], start
    return [start + int(round(r * ref)) for r in ratios], start


def run_zigzag(highs, lows, depth, min_move, with_prov=False):
    """Feed a whole series through the engine, exactly as Pine does bar by bar."""
    z = Zig()
    for i in range(len(highs)):
        z.step(highs, lows, i, depth, min_move)
    return z.build_work(with_prov)
