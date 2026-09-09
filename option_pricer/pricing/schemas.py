"""Request and response models for the option pricer."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class OptionStyle(str, Enum):
    european = "european"
    american = "american"
    barrier = "barrier"


class OptionType(str, Enum):
    call = "call"
    put = "put"


class BarrierKind(str, Enum):
    up_and_out = "up_and_out"
    up_and_in = "up_and_in"
    down_and_out = "down_and_out"
    down_and_in = "down_and_in"


class ModelName(str, Enum):
    black_scholes = "black_scholes"
    pde = "pde"
    monte_carlo = "monte_carlo"


class PriceRequest(BaseModel):
    """Market and contract inputs. Vols and rates are decimals (0.20 = 20%)."""

    spot: float = Field(gt=0, description="Spot price of the underlying")
    strike: float = Field(gt=0)
    rate: float = Field(description="Continuous risk-free rate (decimal)")
    dividend: float = Field(description="Continuous dividend / foreign rate (decimal)")
    atm_vol: float = Field(gt=0, le=5, description="ATM implied volatility (decimal)")
    rr_25d: float = Field(
        description="25-delta risk reversal: vol(25d call) - vol(25d put), decimal"
    )
    bf_25d: float = Field(
        description="25-delta butterfly: 0.5*(vol25c+vol25p) - atm, decimal"
    )
    expiry_years: float = Field(gt=0, le=30)
    option_style: OptionStyle = OptionStyle.european
    option_type: OptionType = OptionType.call
    barrier_type: Optional[BarrierKind] = None
    barrier: Optional[float] = Field(default=None, gt=0)
    rebate: float = Field(default=0.0, ge=0)
    model: ModelName = ModelName.black_scholes
    mc_paths: int = Field(default=40000, ge=1000, le=400000)
    mc_steps: int = Field(default=64, ge=8, le=512)
    pde_time_steps: int = Field(default=100, ge=20, le=400)
    pde_spot_steps: int = Field(default=200, ge=50, le=600)
    compare_models: bool = True
    seed: int = 42

    @model_validator(mode="after")
    def validate_barrier_fields(self) -> "PriceRequest":
        if self.option_style == OptionStyle.barrier:
            if self.barrier_type is None:
                raise ValueError("barrier_type is required for barrier options")
            if self.barrier is None:
                raise ValueError("barrier level is required for barrier options")
            if self.barrier_type in (BarrierKind.up_and_out, BarrierKind.up_and_in):
                if self.barrier <= self.spot:
                    raise ValueError("Up barrier must be strictly above spot")
            else:
                if self.barrier >= self.spot:
                    raise ValueError("Down barrier must be strictly below spot")
        return self


class Greeks(BaseModel):
    delta: Optional[float] = None
    gamma: Optional[float] = None
    vega: Optional[float] = None
    theta: Optional[float] = None
    rho: Optional[float] = None


class SmilePillar(BaseModel):
    label: str
    delta: Optional[float] = None
    strike: float
    vol: float


class SmileCurve(BaseModel):
    strikes: list[float]
    vols: list[float]
    pillars: list[SmilePillar]
    vol_25d_put: float
    vol_atm: float
    vol_25d_call: float
    forward: float


class ModelQuote(BaseModel):
    model: ModelName
    label: str
    price: float
    std_error: Optional[float] = None
    greeks: Optional[Greeks] = None
    error: Optional[str] = None


class PriceResponse(BaseModel):
    price: float
    std_error: Optional[float] = None
    greeks: Greeks
    vol_used: float
    implied_vol: Optional[float] = None
    smile: SmileCurve
    model: ModelName
    model_label: str
    comparison: list[ModelQuote] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)
    payoff: dict = Field(default_factory=dict)
