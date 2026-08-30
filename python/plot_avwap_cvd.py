"""Render Anchored VWAP + CVD the way it appears on a chart."""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import PatchCollection
from matplotlib.patches import Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parent))

from anchored_vwap_cvd import VwapCvdConfig, compute_anchored_vwap_cvd, generate_synthetic_ohlcv

UP = "#26a69a"
DOWN = "#ef5350"
VWAP = "#2962FF"
BAND = "#5B8DEF"
BG = "#131722"
PANE = "#1a1e2a"
TEXT = "#d1d4dc"
GRID = "#2a2e39"


def plot_anchored_vwap_cvd(
    result: pd.DataFrame,
    title: str = "Anchored VWAP + CVD",
    outfile: str | Path | None = None,
    show: bool = False,
) -> Path | None:
    if result.empty:
        raise ValueError("result is empty")

    x = np.arange(len(result))
    fig, (ax_px, ax_cvd) = plt.subplots(
        2,
        1,
        sharex=True,
        figsize=(14, 8),
        gridspec_kw={"height_ratios": [2.4, 1.0]},
        facecolor=BG,
    )
    for ax in (ax_px, ax_cvd):
        ax.set_facecolor(PANE)
        ax.tick_params(colors=TEXT, labelsize=8)
        ax.yaxis.label.set_color(TEXT)
        ax.xaxis.label.set_color(TEXT)
        for spine in ax.spines.values():
            spine.set_color(GRID)
        ax.grid(True, color=GRID, linewidth=0.6, alpha=0.7)

    _candles(ax_px, result, x)
    ax_px.plot(x, result["vwap"], color=VWAP, lw=1.6, label="Anchored VWAP", zorder=4)
    if "vwap_upper_1" in result.columns:
        ax_px.plot(x, result["vwap_upper_1"], color=BAND, lw=0.8, alpha=0.85)
        ax_px.plot(x, result["vwap_lower_1"], color=BAND, lw=0.8, alpha=0.85)
        ax_px.fill_between(x, result["vwap_upper_1"], result["vwap_lower_1"], color=BAND, alpha=0.10, zorder=1)
    if "vwap_upper_2" in result.columns:
        ax_px.plot(x, result["vwap_upper_2"], color=BAND, lw=0.6, alpha=0.45, ls="--")
        ax_px.plot(x, result["vwap_lower_2"], color=BAND, lw=0.6, alpha=0.45, ls="--")

    _mark_anchors(ax_px, result, x)
    _mark_divs(ax_px, result, x, use_price=True)

    ax_px.set_ylabel("Price")
    ax_px.set_title(title, color=TEXT, fontsize=13, pad=10)
    ax_px.legend(loc="upper left", facecolor=PANE, edgecolor=GRID, labelcolor=TEXT, fontsize=8)

    colors = np.where(result["delta"].to_numpy() >= 0, UP, DOWN)
    ax_cvd.bar(x, result["cvd"], color=colors, width=0.85, alpha=0.88, label="CVD")
    ax_cvd.plot(x, result["cvd_smooth"], color="#f5c542", lw=1.2, label="CVD EMA")
    ax_cvd.axhline(0.0, color=GRID, lw=0.8)
    _mark_divs(ax_cvd, result, x, use_price=False)
    ax_cvd.set_ylabel("CVD")
    ax_cvd.legend(loc="upper left", facecolor=PANE, edgecolor=GRID, labelcolor=TEXT, fontsize=8)

    _date_ticks(ax_cvd, result, x)
    fig.tight_layout()

    path = None
    if outfile is not None:
        path = Path(outfile)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=140, facecolor=fig.get_facecolor(), bbox_inches="tight")
    if show:
        plt.show()
    plt.close(fig)
    return path


def _candles(ax, df: pd.DataFrame, x: np.ndarray) -> None:
    o = df["open"].to_numpy()
    h = df["high"].to_numpy()
    l = df["low"].to_numpy()
    c = df["close"].to_numpy()
    up = c >= o
    colors = np.where(up, UP, DOWN)
    ax.vlines(x, l, h, color=colors, linewidth=0.7, zorder=2)
    bodies = [
        Rectangle((i - 0.35, min(o[i], c[i])), 0.7, max(abs(c[i] - o[i]), (h[i] - l[i]) * 0.02), facecolor=colors[i])
        for i in range(len(df))
    ]
    ax.add_collection(PatchCollection(bodies, match_original=True, zorder=3))


def _mark_anchors(ax, df: pd.DataFrame, x: np.ndarray) -> None:
    for i in np.flatnonzero(df["new_anchor"].to_numpy()):
        ax.axvline(x[i], color="#787b86", lw=0.6, ls=":", alpha=0.7)


def _mark_divs(ax, df: pd.DataFrame, x: np.ndarray, use_price: bool) -> None:
    y_low = df["low"] if use_price else df["cvd"]
    y_high = df["high"] if use_price else df["cvd"]
    if df["bull_div"].any():
        idx = np.flatnonzero(df["bull_div"].to_numpy())
        ax.scatter(x[idx], y_low.iloc[idx], marker="^", s=36, color=UP, zorder=5, label="Bull div")
    if df["bear_div"].any():
        idx = np.flatnonzero(df["bear_div"].to_numpy())
        ax.scatter(x[idx], y_high.iloc[idx], marker="v", s=36, color=DOWN, zorder=5, label="Bear div")


def _date_ticks(ax, df: pd.DataFrame, x: np.ndarray) -> None:
    if not isinstance(df.index, pd.DatetimeIndex) or len(df) == 0:
        return
    step = max(len(df) // 8, 1)
    ticks = x[::step]
    labels = [df.index[i].strftime("%b %d %H:%M") for i in ticks]
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, rotation=18, ha="right")


def main() -> None:
    ohlcv = generate_synthetic_ohlcv()
    result = compute_anchored_vwap_cvd(ohlcv, VwapCvdConfig(anchor="session", cvd_ema=8, stdev_mults=(1.0, 2.0)))
    out = Path(__file__).resolve().parents[1] / "examples" / "avwap_cvd_demo.png"
    plot_anchored_vwap_cvd(result, outfile=out)
    last = result.iloc[-1]
    print(f"wrote {out}")
    print(f"last close={last.close:.4f}  vwap={last.vwap:.4f}  cvd={last.cvd:.0f}")


if __name__ == "__main__":
    main()
