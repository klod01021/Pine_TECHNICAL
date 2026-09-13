# Option Pricer

Web-based option pricer for vanilla European, American, and single-barrier contracts.

The main model is **Black–Scholes**. You can also price with a **PDE** (QuantLib finite difference) and a **simplified Monte Carlo**. The smile can be built from **ATM + 10Δ/25Δ risk reversal and butterfly** quotes, or from **your own strike / vol points** (the pricer interpolates the rest).

Pricing uses [QuantLib](https://www.quantlib.org/) and [vollib](https://github.com/vollib/vollib) (Black–Scholes–Merton prices, implied vol, and analytic Greeks).

## Launch in a browser

Install [Python 3](https://www.python.org/downloads/) once if it is not already on the machine. Then double-click the launcher for your OS (keep it in this project folder):

| OS | Double-click |
| --- | --- |
| macOS | `Launch Pricer.command` or `Launch Pricer.app` |
| Windows | `Launch Pricer.bat` |

The first run creates a local `.venv`, installs QuantLib / vollib / FastAPI, starts the server, and opens [http://127.0.0.1:8000](http://127.0.0.1:8000). Leave the Terminal / Command Prompt window open. Press **Ctrl+C** there to stop the pricer.

On macOS, if Gatekeeper blocks the file, right-click it and choose **Open**.

From a terminal you can do the same thing with:

```bash
python3 -m pip install -r requirements.txt
python3 -m option_pricer
```

or:

```bash
python3 launch.py
```

Useful flags:

```bash
python3 -m option_pricer --host 127.0.0.1 --port 8000
python3 -m option_pricer --no-browser
```

## Market inputs

| Input | Meaning |
| --- | --- |
| Spot | Underlying price |
| ATM vol | At-the-money implied volatility (quote mode) |
| 25Δ RR | `vol(25Δ call) − vol(25Δ put)` |
| 25Δ BF | `0.5 × (vol 25Δ call + vol 25Δ put) − ATM` |
| 10Δ RR | `vol(10Δ call) − vol(10Δ put)` |
| 10Δ BF | `0.5 × (vol 10Δ call + vol 10Δ put) − ATM` |
| Custom points | Strike / implied-vol nodes you type yourself |
| Rate | Continuous risk-free rate |
| Dividend / q | Continuous dividend yield (or foreign rate) |

Two ways to build the smile:

1. **RR / BF quotes** — wing vols are mapped to strikes with forward delta. The five pillars (10Δ put, 25Δ put, ATM, 25Δ call, 10Δ call) are interpolated in log-moneyness with a shape-preserving spline. If 10Δ quotes are omitted, those wings are implied from the 25Δ quadratic.
2. **Custom points** — type (or paste) at least two strike / vol nodes. Those strikes are honored exactly. Every other strike is interpolated in log-moneyness (`ln(K/F)`, PCHIP when there are three or more points, linear when there are two). Outside the outermost input strikes the wings are held flat. Use **Load from RR / BF** to seed the editor from the current quotes.

The pricer builds the **full smile at every listed strike**: each row has its own implied vol plus European call and put prices. Input rows are labeled in the surface table. The selected contract uses that strike’s vol under Black–Scholes. **PDE** and **Monte Carlo** use the smile as local volatility along the spot path, not a single flat vol.

API: set `smile_source` to `"custom"` and pass `custom_vols` as `[{ "strike": 80, "vol": 0.24 }, ...]` (vols as decimals). Quote-mode fields can still be sent; they are ignored while `smile_source` is `"custom"`.

## Contracts and models

- **European vanilla** — QuantLib analytic Black–Scholes, cross-checked with vollib
- **American vanilla** — Bjerksund–Stensland (Black–Scholes), PDE grid, Longstaff–Schwartz Monte Carlo
- **Barriers** — up/down and in/out; analytic Reiner–Rubinstein, PDE, discrete-path Monte Carlo

Greeks in the UI: **vega per 1 vol point**, **theta per day**, **rho per 1% rate**.

## Tests

```bash
python3 -m pytest
```
