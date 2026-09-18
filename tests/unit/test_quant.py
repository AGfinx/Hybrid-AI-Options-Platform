import math
import pytest
from packages.quant.black_scholes import bs_price, bs_greeks, implied_volatility
from packages.quant.surface import VolatilitySurface
from packages.quant.rv_forecast import RealizedVolForecaster
from packages.quant.opportunity import OpportunityCalculator

def test_put_call_parity():
    S = 65000.0
    K = 65000.0
    T = 30.0 / 365.0
    r = 0.05
    sigma = 0.55

    call_px = bs_price(S, K, T, r, sigma, option_type="call")
    put_px = bs_price(S, K, T, r, sigma, option_type="put")

    # C - P = S - K * exp(-r * T)
    parity_lhs = call_px - put_px
    parity_rhs = S - K * math.exp(-r * T)
    assert abs(parity_lhs - parity_rhs) < 1e-4

def test_bs_greeks():
    S = 65000.0
    K = 65000.0
    T = 30.0 / 365.0
    r = 0.0
    sigma = 0.55

    cg = bs_greeks(S, K, T, r, sigma, option_type="call")
    assert 0.0 < cg["delta"] < 1.0
    assert cg["gamma"] > 0
    assert cg["vega"] > 0
    assert cg["theta"] < 0

    pg = bs_greeks(S, K, T, r, sigma, option_type="put")
    assert -1.0 < pg["delta"] < 0.0
    assert pg["gamma"] > 0
    assert pg["vega"] > 0

def test_implied_volatility_inversion():
    S = 65000.0
    K = 62500.0
    T = 14.0 / 365.0
    sigma_true = 0.62

    price = bs_price(S, K, T, 0.0, sigma_true, option_type="call")
    sigma_inv = implied_volatility(price, S, K, T, 0.0, option_type="call")

    assert sigma_inv is not None
    assert abs(sigma_inv - sigma_true) < 1e-4

def test_volatility_surface_checks():
    surface = VolatilitySurface(underlying="BTC", spot=65000.0)
    quotes = [
        {"strike": 55000, "T": 0.05, "implied_vol": 0.60, "option_type": "call", "best_bid_price": 10500, "best_ask_price": 10600},
        {"strike": 65000, "T": 0.05, "implied_vol": 0.55, "option_type": "call", "best_bid_price": 2400, "best_ask_price": 2450},
        {"strike": 75000, "T": 0.05, "implied_vol": 0.58, "option_type": "call", "best_bid_price": 300, "best_ask_price": 320},
        {"strike": 65000, "T": 0.10, "implied_vol": 0.55, "option_type": "call", "best_bid_price": 3400, "best_ask_price": 3450},
    ]
    surface.build_from_quotes(quotes)
    assert surface.structural_status in ["valid", "arbitrage_violated"]
    vol = surface.get_vol(65000, 0.05)
    assert 0.1 < vol < 2.0

def test_realized_vol_forecaster():
    forecaster = RealizedVolForecaster()
    features = {"rv_7d": 0.50, "rv_14d": 0.54, "rv_30d": 0.56, "return_skew": -0.1}
    fc = forecaster.forecast(features, horizon_seconds=3600)
    assert 0.1 < fc["forecast"] < 2.0
    assert fc["regime"] in ["low", "normal", "elevated", "extreme"]
    assert "valid_until" in fc

def test_opportunity_calculator():
    calc = OpportunityCalculator(min_edge_threshold=0.01)
    opp = calc.evaluate_opportunity(
        underlying="BTC",
        spot=65000.0,
        strike=65000.0,
        expiry_years=30.0 / 365.0,
        option_type="call",
        best_bid=3400.0,
        best_ask=3450.0,
        implied_vol=0.50,
        forecast_vol=0.60,
        uncertainty=0.03,
        surface_confidence=0.95
    )
    assert opp is not None
    assert opp["net_edge"] > 0.01
    assert opp["gross_edge"] == 0.10
    assert opp["direction"] == "buy"
