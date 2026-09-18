import pytest
from packages.quant.opportunity import OpportunityCalculator

def test_evaluate_straddle_delta_neutral():
    """Verify long straddle evaluation produces delta-neutral greeks and positive vega."""
    calc = OpportunityCalculator()
    spot = 65000.0
    strike = 65000.0
    T = 30.0 / 365.0

    call_q = {
        "instrument_id": "inst_btc_c_65000",
        "symbol": "BTC-65000-C",
        "best_bid_price": 2800.0,
        "best_ask_price": 2900.0,
        "implied_vol": 0.52
    }
    put_q = {
        "instrument_id": "inst_btc_p_65000",
        "symbol": "BTC-65000-P",
        "best_bid_price": 2750.0,
        "best_ask_price": 2850.0,
        "implied_vol": 0.52
    }

    forecast_vol = 0.62  # 10 vol points premium forecast

    opp = calc.evaluate_straddle(
        underlying="BTC",
        spot=spot,
        strike=strike,
        expiry_years=T,
        call_quote=call_q,
        put_quote=put_q,
        forecast_vol=forecast_vol,
        uncertainty=0.02,
        quantity=1.0
    )

    assert opp is not None
    assert opp["strategy_type"] == "long_straddle_delta_neutral"
    assert len(opp["legs"]) == 2
    assert opp["legs"][0]["direction"] == "buy"
    assert opp["legs"][1]["direction"] == "buy"
    
    # Delta should be near zero (delta-neutral)
    assert abs(opp["delta"]) < 0.15, f"Expected near zero delta for ATM straddle, got {opp['delta']}"
    # Vega should be strongly positive
    assert opp["vega"] > 50.0
    # Net edge should be positive
    assert opp["net_edge"] > 0.02
    assert opp["initial_margin"] == round(2900.0 + 2850.0, 2)

def test_evaluate_calendar_spread():
    """Verify calendar spread evaluation produces near short, far long structure with positive theta."""
    calc = OpportunityCalculator()
    spot = 65000.0
    strike = 65000.0

    near_q = {
        "instrument_id": "inst_btc_7d",
        "symbol": "BTC-65000-C-7D",
        "best_bid_price": 1200.0,
        "best_ask_price": 1250.0,
        "T": 7.0 / 365.0,
        "implied_vol": 0.62  # Elevated near-term vol
    }
    far_q = {
        "instrument_id": "inst_btc_30d",
        "symbol": "BTC-65000-C-30D",
        "best_bid_price": 2700.0,
        "best_ask_price": 2800.0,
        "T": 30.0 / 365.0,
        "implied_vol": 0.52  # Cheaper far-term vol
    }

    opp = calc.evaluate_calendar_spread(
        underlying="BTC",
        spot=spot,
        strike=strike,
        near_quote=near_q,
        far_quote=far_q,
        forecast_vol=0.52,
        uncertainty=0.02,
        quantity=1.0
    )

    assert opp is not None
    assert opp["strategy_type"] == "vol_calendar_spread"
    assert len(opp["legs"]) == 2
    # Leg 1: Sell near
    assert opp["legs"][0]["direction"] == "sell"
    assert opp["legs"][0]["expiry_years"] == near_q["T"]
    # Leg 2: Buy far
    assert opp["legs"][1]["direction"] == "buy"
    assert opp["legs"][1]["expiry_years"] == far_q["T"]
    # Positive theta decay expected
    assert opp["theta"] > 0
    assert opp["net_edge"] > 0.01
