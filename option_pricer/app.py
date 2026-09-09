"""FastAPI application serving the option pricer UI and JSON API."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from option_pricer.pricing.engine import price_option
from option_pricer.pricing.schemas import PriceRequest, PriceResponse
from option_pricer.pricing.smile import build_smile
from option_pricer.pricing.ql_market import year_fraction

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="Option Pricer",
    description="Web option pricer using Black-Scholes, PDE and Monte Carlo.",
    version="1.0.0",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/price", response_model=PriceResponse)
def api_price(request: PriceRequest) -> PriceResponse:
    try:
        return price_option(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/smile")
def api_smile(request: PriceRequest) -> dict:
    _, t = year_fraction(request.expiry_years)
    smile = build_smile(
        spot=request.spot,
        rate=request.rate,
        dividend=request.dividend,
        t=t,
        atm_vol=request.atm_vol,
        rr_25d=request.rr_25d,
        bf_25d=request.bf_25d,
    )
    return {
        "smile": smile.curve().model_dump(),
        "vol_at_strike": smile.vol_at(request.strike),
        "warnings": list(smile.warnings),
    }
