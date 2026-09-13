# Option Pricer

Web-based option pricer for vanilla European, American, and single-barrier contracts.

The main model is **Black–Scholes**. You can also price with a **PDE** (QuantLib finite difference) and a **simplified Monte Carlo**.

The **Pricer** page is just expiry date, strike, and a bid / offer price. The **Market** page is the editable **1M / 3M / 6M / 1Y** vol surface with **swap points** and bid / offer on every input.

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

## Pricer page

| Input | Meaning |
| --- | --- |
| Date of expiry | Option maturity (1M / 3M / 6M / 1Y chips snap the date) |
| Strike level | Strike to price |
| Bid / Offer | Two-way premium from the bid and offer markets |

Call / put is the only other control on this page.

## Market page

| Input | Meaning |
| --- | --- |
| Spot bid / offer | Underlying cash |
| Rate bid / offer | Continuous discount rate |
| Swap points | Per tenor, bid / offer. `Forward = spot + swap points / scale` |
| Vol surface | Strike × 1M / 3M / 6M / 1Y cells, each bid / offer (percent in the UI) |
| RR / BF quotes | Optional seed; **Load from RR / BF** writes pillars into the grid |

Swap points replace a typed dividend: `q` is implied so the forward matches. An expiry between two tenors interpolates **total variance** `σ²T` and the swap points. Outside 1M–1Y the wings stay flat.

You can still send the older single-smile API (`atm_vol` + RR/BF, or `custom_vols`) with no `tenors` array. With a surface, POST `tenors` as 1M / 3M / 6M / 1Y slices of `{ swap_points: {bid, offer}, vols: [{strike, bid, offer}, ...] }` (vols as decimals). Optional `spot_bid` / `spot_offer` / `rate_bid` / `rate_offer` and `expiry_date` + `value_date`.

The selected contract uses that strike’s interpolated vol under Black–Scholes. **PDE** and **Monte Carlo** use the smile as local volatility along the spot path.

## Contracts and models

- **European vanilla** — QuantLib analytic Black–Scholes, cross-checked with vollib
- **American vanilla** — Bjerksund–Stensland (Black–Scholes), PDE grid, Longstaff–Schwartz Monte Carlo
- **Barriers** — up/down and in/out; analytic Reiner–Rubinstein, PDE, discrete-path Monte Carlo

Greeks in the UI: **vega per 1 vol point**, **theta per day**, **rho per 1% rate**.

## Tests

```bash
python3 -m pytest
```
