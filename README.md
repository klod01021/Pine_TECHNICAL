# Option Pricer

Web-based option pricer for vanilla European, American, and single-barrier contracts.

The main model is **Black–Scholes**. You can also price with a **PDE** (QuantLib finite difference) and a **simplified Monte Carlo**. The smile is built from **spot**, **ATM vol**, **25Δ risk reversal**, and **25Δ butterfly**.

Pricing uses [QuantLib](https://www.quantlib.org/) and [vollib](https://github.com/vollib/vollib) (Black–Scholes–Merton prices, implied vol, and analytic Greeks).

## Launch in a browser

```bash
python3 -m pip install -r requirements.txt
python3 -m option_pricer
```

That starts the app at [http://127.0.0.1:8000](http://127.0.0.1:8000) and opens your default browser.

Equivalent:

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
| ATM vol | At-the-money implied volatility |
| 25Δ RR | `vol(25Δ call) − vol(25Δ put)` |
| 25Δ BF | `0.5 × (vol 25Δ call + vol 25Δ put) − ATM` |
| Rate | Continuous risk-free rate |
| Dividend / q | Continuous dividend yield (or foreign rate) |

Wing vols are mapped to strikes with forward delta. A quadratic in log-moneyness `ln(K/F)` is fitted through the three pillars. Each contract is priced with the smile vol at its strike (sticky strike).

## Contracts and models

- **European vanilla** — QuantLib analytic Black–Scholes, cross-checked with vollib
- **American vanilla** — Bjerksund–Stensland (Black–Scholes), PDE grid, Longstaff–Schwartz Monte Carlo
- **Barriers** — up/down and in/out; analytic Reiner–Rubinstein, PDE, discrete-path Monte Carlo

Greeks in the UI: **vega per 1 vol point**, **theta per day**, **rho per 1% rate**.

## Tests

```bash
python3 -m pytest
```
