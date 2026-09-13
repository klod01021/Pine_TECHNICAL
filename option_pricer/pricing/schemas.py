"""Request and response models for the option pricer."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal, Optional

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


class SmileSource(str, Enum):
    quotes = "quotes"
    custom = "custom"


class VolPoint(BaseModel):
    strike: float = Field(gt=0)
    vol: float = Field(gt=0, le=5, description="Implied vol as a decimal (0.20 = 20%)")


class TwoSided(BaseModel):
    """Bid / offer pair. Mid is the average."""

    bid: float
    offer: float


class TenorVolPoint(BaseModel):
    strike: float = Field(gt=0)
    bid: float = Field(gt=0, le=5, description="Bid implied vol as a decimal")
    offer: float = Field(gt=0, le=5, description="Offer implied vol as a decimal")


class TenorSlice(BaseModel):
    tenor: Literal["1M", "3M", "6M", "1Y"]
    expiry_years: Optional[float] = Field(default=None, gt=0, le=30)
    swap_points: TwoSided
    vols: list[TenorVolPoint] = Field(min_length=2)


class PriceRequest(BaseModel):
    """Market and contract inputs. Vols and rates are decimals (0.20 = 20%)."""

    spot: float = Field(gt=0, description="Spot price of the underlying")
    strike: float = Field(gt=0)
    rate: float = Field(description="Continuous risk-free rate (decimal)")
    dividend: float = Field(description="Continuous dividend / foreign rate (decimal)")
    atm_vol: Optional[float] = Field(
        default=None, gt=0, le=5, description="ATM implied volatility (decimal)"
    )
    rr_25d: Optional[float] = Field(
        default=None,
        description="25-delta risk reversal: vol(25d call) - vol(25d put), decimal",
    )
    bf_25d: Optional[float] = Field(
        default=None,
        description="25-delta butterfly: 0.5*(vol25c+vol25p) - atm, decimal",
    )
    rr_10d: Optional[float] = Field(
        default=None,
        description="10-delta risk reversal: vol(10d call) - vol(10d put), decimal. "
        "Omit to imply 10Δ from the 25Δ smile.",
    )
    bf_10d: Optional[float] = Field(
        default=None,
        description="10-delta butterfly: 0.5*(vol10c+vol10p) - atm, decimal. "
        "Omit to imply 10Δ from the 25Δ smile.",
    )
    expiry_years: Optional[float] = Field(default=None, gt=0, le=30)
    expiry_date: Optional[date] = None
    value_date: Optional[date] = None
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
    surface_points: int = Field(default=23, ge=11, le=61)
    smile_source: SmileSource = SmileSource.quotes
    custom_vols: list[VolPoint] = Field(default_factory=list)
    spot_bid: Optional[float] = Field(default=None, gt=0)
    spot_offer: Optional[float] = Field(default=None, gt=0)
    rate_bid: Optional[float] = None
    rate_offer: Optional[float] = None
    dividend_bid: Optional[float] = None
    dividend_offer: Optional[float] = None
    swap_point_scale: float = Field(default=1.0, gt=0)
    tenors: list[TenorSlice] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_barrier_fields(self) -> "PriceRequest":
        if self.expiry_date is not None:
            value = self.value_date or date.today()
            days = (self.expiry_date - value).days
            if days < 1:
                raise ValueError("Expiry date must be after the value date")
            self.expiry_years = days / 365.0
        elif self.expiry_years is None:
            raise ValueError("Provide expiry_years or expiry_date")
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
        if self.tenors:
            labels = [slice_.tenor for slice_ in self.tenors]
            if len(labels) != len(set(labels)):
                raise ValueError("Each tenor can appear only once")
            return self
        if self.atm_vol is None or self.rr_25d is None or self.bf_25d is None:
            raise ValueError("ATM vol, 25Δ RR and 25Δ BF are required without a tenor surface")
        if self.smile_source == SmileSource.custom and len(self.custom_vols) < 2:
            raise ValueError("Custom smile needs at least two strike/vol points")
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


class SurfaceRow(BaseModel):
    strike: float
    vol: float
    call: float
    put: float
    call_delta: Optional[float] = None
    put_delta: Optional[float] = None
    pillar: Optional[str] = None
    selected: bool = False
    vol_bid: Optional[float] = None
    vol_offer: Optional[float] = None
    call_bid: Optional[float] = None
    call_offer: Optional[float] = None
    put_bid: Optional[float] = None
    put_offer: Optional[float] = None


class SmileCurve(BaseModel):
    strikes: list[float]
    vols: list[float]
    pillars: list[SmilePillar]
    vol_10d_put: float
    vol_25d_put: float
    vol_atm: float
    vol_25d_call: float
    vol_10d_call: float
    forward: float


class ModelQuote(BaseModel):
    model: ModelName
    label: str
    price: float
    price_bid: Optional[float] = None
    price_offer: Optional[float] = None
    std_error: Optional[float] = None
    greeks: Optional[Greeks] = None
    error: Optional[str] = None


class PriceResponse(BaseModel):
    price: float
    price_bid: Optional[float] = None
    price_offer: Optional[float] = None
    std_error: Optional[float] = None
    greeks: Greeks
    vol_used: float
    vol_bid: Optional[float] = None
    vol_offer: Optional[float] = None
    implied_vol: Optional[float] = None
    forward: Optional[float] = None
    forward_bid: Optional[float] = None
    forward_offer: Optional[float] = None
    smile: SmileCurve
    model: ModelName
    model_label: str
    comparison: list[ModelQuote] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)
    payoff: dict = Field(default_factory=dict)
    surface: list[SurfaceRow] = Field(default_factory=list)
