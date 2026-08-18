"""Line-for-line Python port of the campaign logic in
``indicators/wyckoff_method.pine``.

Pine Script cannot be executed outside TradingView, so this module mirrors the
zig-zag engine, the trading-range scanner and the event labels exactly as they
are written in the indicator. ``tools/test_wyckoff_logic.py`` drives it with
synthetic accumulation and distribution paths.

Keep the two files in sync: if a rule changes in the Pine source, change it
here and extend the test.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

MAX_PIVOTS = 60

# Most swings that can follow a completed range (SOS/LPS or SOW/LPSY plus a
# short markup/markdown) and still belong to that campaign. A range with more
# than this after it is history, not the present structure.
MAX_TAIL = 10


@dataclass
class Pivot:
    bar: int
    price: float
    dir: int  # +1 swing high, -1 swing low
    vol: float = 0.0


@dataclass
class Event:
    pi: int
    code: str
    prov: bool = False


@dataclass
class Campaign:
    events: list[Event] = field(default_factory=list)
    kind: str = "none"  # accumulation | distribution | none
    phase: str = "none"  # A B C D E none
    title: str = "No campaign"
    start: int = -1  # climax pivot index
    last: int = -1  # last pivot that still belongs to the campaign
    ice: float = math.nan
    creek: float = math.nan
    conf: float = 0.0
    spring: bool = False
    utad: bool = False
    sos: bool = False
    sow: bool = False
    t1: float = math.nan
    t2: float = math.nan
    horiz: float = math.nan
    inv: float = math.nan
    cause_bars: int = 0


@dataclass
class Cfg:
    min_approach: float = 10.0
    min_ar_frac: float = 0.30
    max_ar_frac: float = 0.95
    st_zone: float = 0.45
    spring_max: float = 0.40
    breakout_tol: float = 0.02
    max_look: int = 25
    min_conf: float = 0.0
    horiz_div: float = 3.0
    atr: float = 1.0


# ── zig-zag engine ───────────────────────────────────────────────────────────
class Zig:
    def __init__(self) -> None:
        self.pv: list[Pivot] = []
        self.changed = False
        self.run_hi: float | None = None
        self.run_hi_bar: int | None = None
        self.run_lo: float | None = None
        self.run_lo_bar: int | None = None

    def add_pivot(self, b: int, p: float, d: int, min_move: float, vol: float = 0.0) -> None:
        n = len(self.pv)
        if n == 0:
            self.pv.append(Pivot(b, p, d, vol))
            self.changed = True
        else:
            lp = self.pv[-1]
            if lp.dir == d:
                if (d == 1 and p > lp.price) or (d == -1 and p < lp.price):
                    lp.bar = b
                    lp.price = p
                    lp.vol = vol
                    self.changed = True
            elif b > lp.bar and abs(p - lp.price) >= min_move:
                self.pv.append(Pivot(b, p, d, vol))
                self.changed = True
        if len(self.pv) > MAX_PIVOTS:
            self.pv.pop(0)

    def step(
        self,
        highs: list[float],
        lows: list[float],
        i: int,
        depth: int,
        min_move: float,
        volumes: list[float] | None = None,
    ) -> None:
        self.changed = False
        pb = i - depth
        vol_at = 0.0
        if volumes is not None and 0 <= pb < len(volumes):
            vol_at = volumes[pb]
        if pb >= depth:
            window_h = highs[pb - depth : pb + depth + 1]
            if highs[pb] == max(window_h) and window_h.count(highs[pb]) == 1:
                self.add_pivot(pb, highs[pb], 1, min_move, vol_at)
            window_l = lows[pb - depth : pb + depth + 1]
            if lows[pb] == min(window_l) and window_l.count(lows[pb]) == 1:
                self.add_pivot(pb, lows[pb], -1, min_move, vol_at)
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
            if (
                lp.dir == -1
                and self.run_hi_bar is not None
                and self.run_hi_bar > lp.bar
                and self.run_hi > lp.price
            ):
                w.append(Pivot(self.run_hi_bar, self.run_hi, 1, 0.0))
                hp = True
            elif (
                lp.dir == 1
                and self.run_lo_bar is not None
                and self.run_lo_bar > lp.bar
                and self.run_lo < lp.price
            ):
                w.append(Pivot(self.run_lo_bar, self.run_lo, -1, 0.0))
                hp = True
        return w, hp


def run_zigzag(
    highs: list[float],
    lows: list[float],
    depth: int,
    min_move: float,
    with_prov: bool = False,
    volumes: list[float] | None = None,
) -> tuple[list[Pivot], bool]:
    z = Zig()
    for i in range(len(highs)):
        z.step(highs, lows, i, depth, min_move, volumes)
    return z.build_work(with_prov)


# ── effort vs result ─────────────────────────────────────────────────────────
def _sma(xs: list[float], end: int, length: int) -> float:
    a = max(0, end - length + 1)
    window = xs[a : end + 1]
    return sum(window) / len(window) if window else 0.0


def effort_result(
    spreads: list[float],
    volumes: list[float],
    i: int,
    length: int = 20,
    effort_mult: float = 1.6,
    result_mult: float = 0.70,
    climax_vol: float = 2.0,
    climax_spr: float = 1.5,
) -> str:
    """Classify bar ``i``. Returns absorption | climax | none."""
    if i < 0 or i >= len(spreads):
        return "none"
    vol_ma = _sma(volumes, i, length)
    spr_ma = _sma(spreads, i, length)
    if vol_ma <= 0 or spr_ma <= 0:
        return "none"
    vol, spr = volumes[i], spreads[i]
    if vol >= climax_vol * vol_ma and spr >= climax_spr * spr_ma:
        return "climax"
    if vol >= effort_mult * vol_ma and spr <= result_mult * spr_ma:
        return "absorption"
    return "none"


# ── campaign scanner ─────────────────────────────────────────────────────────
def _mark_prov(events: list[Event], n: int, has_prov: bool) -> None:
    if has_prov and events and n > 0:
        for e in events:
            if e.pi == n - 1:
                e.prov = True


def _targets(kind: str, ice: float, creek: float, cause_bars: int, cfg: Cfg) -> tuple[float, float, float]:
    height = creek - ice
    if height <= 0 or math.isnan(height):
        return math.nan, math.nan, math.nan
    if kind == "accumulation":
        t1 = creek + height
        t2 = creek + 1.618 * height
        horiz = ice + (cause_bars * cfg.atr / cfg.horiz_div)
    else:
        t1 = ice - height
        t2 = ice - 1.618 * height
        horiz = creek - (cause_bars * cfg.atr / cfg.horiz_div)
    return t1, t2, horiz


def _title(kind: str, phase: str) -> str:
    if kind == "none":
        return "No campaign"
    name = "Accumulation" if kind == "accumulation" else "Distribution"
    extra = {
        "A": "Phase A — stopping the trend",
        "B": "Phase B — building cause",
        "C": "Phase C — the test",
        "D": "Phase D — leaving the range",
        "E": "Phase E — trend underway",
    }.get(phase, "in progress")
    return f"{name}, {extra}"


def try_accumulation(w: list[Pivot], sc_i: int, cfg: Cfg, has_prov: bool) -> Campaign | None:
    n = len(w)
    if sc_i < 1 or sc_i + 1 >= n:
        return None
    if w[sc_i].dir != -1 or w[sc_i - 1].dir != 1 or w[sc_i + 1].dir != 1:
        return None

    drop = w[sc_i - 1].price - w[sc_i].price
    if drop < cfg.min_approach:
        return None
    rally = w[sc_i + 1].price - w[sc_i].price
    if rally < drop * cfg.min_ar_frac or rally > drop * cfg.max_ar_frac:
        return None

    ice = w[sc_i].price
    creek = w[sc_i + 1].price
    height = creek - ice
    if height <= 0:
        return None

    events: list[Event] = []
    if sc_i >= 2 and w[sc_i - 2].dir == -1:
        ps_drop = w[sc_i - 1].price - w[sc_i - 2].price
        if w[sc_i - 2].price > w[sc_i].price and ps_drop >= drop * 0.25:
            events.append(Event(sc_i - 2, "PS"))
    events.append(Event(sc_i, "SC"))
    events.append(Event(sc_i + 1, "AR"))

    spring_i = -1
    sos_i = -1
    st_i = -1
    lps_i = -1
    last = sc_i + 1
    phase = "A"
    failed = False

    j = sc_i + 2
    while j < n:
        p = w[j]
        height = creek - ice
        if height <= 0:
            break
        if p.dir == -1:
            if p.price < ice - cfg.spring_max * height:
                failed = True
                break
            if p.price < ice:
                recovered = (j + 1 < n and w[j + 1].dir == 1 and w[j + 1].price > ice) or (j == n - 1)
                if recovered:
                    events.append(Event(j, "Spring"))
                    spring_i = j
                    phase = "C"
                    last = j
                else:
                    failed = True
                    break
            else:
                loc = (p.price - ice) / height
                if sos_i >= 0:
                    code = "BU" if p.price >= creek - 0.08 * height else "LPS"
                    events.append(Event(j, code))
                    lps_i = j
                    phase = "D"
                    last = j
                elif spring_i >= 0:
                    events.append(Event(j, "Test"))
                    phase = "C"
                    last = j
                elif loc <= cfg.st_zone or st_i < 0:
                    events.append(Event(j, "ST"))
                    if st_i < 0:
                        st_i = j
                    phase = "B"
                    last = j
                else:
                    last = j
                    if phase == "A":
                        phase = "B"
        else:
            if p.price > creek + cfg.breakout_tol * height:
                next_fails = j + 1 < n and w[j + 1].dir == -1 and w[j + 1].price < creek
                if next_fails:
                    events.append(Event(j, "UT"))
                    creek = p.price
                    last = j
                    if spring_i < 0 and sos_i < 0:
                        phase = "B"
                else:
                    events.append(Event(j, "SOS"))
                    sos_i = j
                    phase = "D"
                    last = j
            elif p.price > creek:
                if sos_i < 0 and spring_i < 0:
                    creek = p.price
                    last = j
                elif sos_i >= 0:
                    events.append(Event(j, "SOS"))
                    sos_i = j
                    last = j
                    phase = "D"
                else:
                    last = j
            else:
                if sos_i >= 0 and (creek - p.price) <= 0.15 * height:
                    events.append(Event(j, "BU"))
                    phase = "D"
                    last = j
                else:
                    last = j
                    if st_i >= 0 and sos_i < 0 and spring_i < 0:
                        phase = "B"
        j += 1

    if failed and st_i < 0 and spring_i < 0:
        return None
    if failed and sos_i < 0 and spring_i < 0:
        return None
    if st_i < 0 and spring_i < 0 and sos_i < 0:
        if n - 1 - last > 2:
            return None

    if sos_i >= 0:
        for k in range(sos_i + 1, n):
            if w[k].dir == -1 and w[k].price > creek:
                phase = "E"
                last = max(last, k)
                break
            if w[k].dir == -1:
                last = max(last, k)

    _mark_prov(events, n, has_prov)

    conf = 30.0
    if st_i >= 0:
        conf += 12.0
    if spring_i >= 0:
        conf += 18.0
    if sos_i >= 0:
        conf += 12.0
    if lps_i >= 0:
        conf += 8.0
    ar_frac = rally / drop
    if 0.35 <= ar_frac <= 0.75:
        conf += 8.0
    if w[sc_i].vol > 0 and st_i >= 0 and 0 < w[st_i].vol < w[sc_i].vol:
        conf += 12.0
    if w[sc_i].vol > 0 and spring_i >= 0 and 0 < w[spring_i].vol < w[sc_i].vol:
        conf += 8.0
    conf = min(conf, 100.0)

    cause_bars = w[last].bar - w[sc_i].bar
    inv = w[spring_i].price if spring_i >= 0 else ice
    t1, t2, horiz = _targets("accumulation", ice, creek, cause_bars, cfg)

    return Campaign(
        events=events,
        kind="accumulation",
        phase=phase,
        title=_title("accumulation", phase),
        start=sc_i,
        last=last,
        ice=ice,
        creek=creek,
        conf=conf,
        spring=spring_i >= 0,
        sos=sos_i >= 0,
        t1=t1,
        t2=t2,
        horiz=horiz,
        inv=inv,
        cause_bars=cause_bars,
    )


def try_distribution(w: list[Pivot], bc_i: int, cfg: Cfg, has_prov: bool) -> Campaign | None:
    n = len(w)
    if bc_i < 1 or bc_i + 1 >= n:
        return None
    if w[bc_i].dir != 1 or w[bc_i - 1].dir != -1 or w[bc_i + 1].dir != -1:
        return None

    rise = w[bc_i].price - w[bc_i - 1].price
    if rise < cfg.min_approach:
        return None
    reaction = w[bc_i].price - w[bc_i + 1].price
    if reaction < rise * cfg.min_ar_frac or reaction > rise * cfg.max_ar_frac:
        return None

    creek = w[bc_i].price
    ice = w[bc_i + 1].price
    height = creek - ice
    if height <= 0:
        return None

    events: list[Event] = []
    if bc_i >= 2 and w[bc_i - 2].dir == 1:
        ps_rise = w[bc_i - 2].price - w[bc_i - 1].price
        if w[bc_i - 2].price < w[bc_i].price and ps_rise >= rise * 0.25:
            events.append(Event(bc_i - 2, "PSY"))
    events.append(Event(bc_i, "BC"))
    events.append(Event(bc_i + 1, "AR"))

    utad_i = -1
    sow_i = -1
    st_i = -1
    lpsy_i = -1
    last = bc_i + 1
    phase = "A"
    failed = False

    j = bc_i + 2
    while j < n:
        p = w[j]
        height = creek - ice
        if height <= 0:
            break
        if p.dir == 1:
            if p.price > creek:
                recovered = (j + 1 < n and w[j + 1].dir == -1 and w[j + 1].price < creek) or (j == n - 1)
                penetration = p.price - creek
                if recovered and penetration <= cfg.spring_max * height:
                    events.append(Event(j, "UTAD"))
                    utad_i = j
                    phase = "C"
                    last = j
                else:
                    # Held breakout, or a poke so large it is a new trend.
                    failed = True
                    break
            else:
                loc = (creek - p.price) / height
                if sow_i >= 0:
                    events.append(Event(j, "LPSY"))
                    lpsy_i = j
                    phase = "D"
                    last = j
                elif utad_i >= 0:
                    events.append(Event(j, "Test"))
                    phase = "C"
                    last = j
                elif loc <= cfg.st_zone or st_i < 0:
                    events.append(Event(j, "ST"))
                    if st_i < 0:
                        st_i = j
                    phase = "B"
                    last = j
                else:
                    last = j
                    if phase == "A":
                        phase = "B"
        else:
            if p.price < ice - cfg.breakout_tol * height:
                # A Sign of Weakness is a break of the ice. A later rally that
                # stays below the creek (LPSY) is expected; only a full recovery
                # back above the creek means the break failed.
                full_recovery = j + 1 < n and w[j + 1].dir == 1 and w[j + 1].price > creek
                if full_recovery:
                    last = j
                else:
                    events.append(Event(j, "SOW"))
                    sow_i = j
                    phase = "D"
                    last = j
            elif p.price < ice:
                if sow_i < 0 and utad_i < 0:
                    ice = p.price
                    last = j
                elif sow_i >= 0:
                    events.append(Event(j, "SOW"))
                    sow_i = j
                    last = j
                    phase = "D"
                else:
                    last = j
            else:
                last = j
                if st_i >= 0 and sow_i < 0 and utad_i < 0:
                    phase = "B"
        j += 1

    if failed and st_i < 0 and utad_i < 0:
        return None
    if failed and sow_i < 0 and utad_i < 0:
        return None
    if st_i < 0 and utad_i < 0 and sow_i < 0:
        if n - 1 - last > 2:
            return None

    if sow_i >= 0:
        for k in range(sow_i + 1, n):
            if w[k].dir == 1 and w[k].price < ice:
                phase = "E"
                last = max(last, k)
                break
            if w[k].dir == 1:
                last = max(last, k)

    _mark_prov(events, n, has_prov)

    conf = 30.0
    if st_i >= 0:
        conf += 12.0
    if utad_i >= 0:
        conf += 18.0
    if sow_i >= 0:
        conf += 12.0
    if lpsy_i >= 0:
        conf += 8.0
    ar_frac = reaction / rise
    if 0.35 <= ar_frac <= 0.75:
        conf += 8.0
    if w[bc_i].vol > 0 and st_i >= 0 and 0 < w[st_i].vol < w[bc_i].vol:
        conf += 12.0
    if w[bc_i].vol > 0 and utad_i >= 0 and 0 < w[utad_i].vol < w[bc_i].vol:
        conf += 8.0
    conf = min(conf, 100.0)

    cause_bars = w[last].bar - w[bc_i].bar
    inv = w[utad_i].price if utad_i >= 0 else creek
    t1, t2, horiz = _targets("distribution", ice, creek, cause_bars, cfg)

    return Campaign(
        events=events,
        kind="distribution",
        phase=phase,
        title=_title("distribution", phase),
        start=bc_i,
        last=last,
        ice=ice,
        creek=creek,
        conf=conf,
        utad=utad_i >= 0,
        sow=sow_i >= 0,
        t1=t1,
        t2=t2,
        horiz=horiz,
        inv=inv,
        cause_bars=cause_bars,
    )


def analyze(w: list[Pivot], cfg: Cfg | None = None, has_prov: bool = False) -> Campaign:
    cfg = cfg or Cfg()
    n = len(w)
    empty = Campaign()
    if n < 3:
        return empty
    start = max(1, n - cfg.max_look)
    best: Campaign | None = None
    best_score = -1e18
    i = start
    while i < n - 1:
        for camp in (
            try_accumulation(w, i, cfg, has_prov),
            try_distribution(w, i, cfg, has_prov),
        ):
            if camp is None or camp.kind == "none":
                continue
            if n - 1 - camp.last > MAX_TAIL:
                continue
            if camp.conf < cfg.min_conf:
                continue
            score = camp.conf - 1.5 * (n - 1 - camp.last) + 2.0 * len(camp.events)
            if score > best_score:
                best_score = score
                best = camp
        i += 1
    return best if best is not None else empty


def event_codes(camp: Campaign) -> list[str]:
    return [e.code + ("?" if e.prov else "") for e in camp.events]
