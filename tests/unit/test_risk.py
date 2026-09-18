import pytest
from packages.risk.engine import RiskEngine
from packages.risk.stress import StressScenarioEngine

def test_risk_rejection_on_circuit_breaker():
    engine = RiskEngine()
    portfolio = {"total_capital": 500000.0, "used_margin": 10000.0, "delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0, "positions": []}
    proposed = {"strike": 65000, "expiry_years": 0.1, "option_type": "call", "direction": "buy", "quantity": 1.0, "initial_margin": 2000, "delta": 0.5, "gamma": 0.00004, "vega": 70, "theta": -60, "implied_volatility": 0.55, "order_price": 2000}
    limits = {"max_delta": 5.0, "max_gamma": 0.05, "max_vega": 50000.0, "max_theta": 10000.0, "margin_utilization": 0.70, "max_loss": 50000.0, "max_quote_age_seconds": 15.0}
    breakers = [{"name": "emergency_stop", "is_tripped": True, "reason": "Manual operator stop"}]
    market_health = {"quote_age_seconds": 1.0, "is_connected": True, "sequence_gap_detected": False, "spot_price": 65000.0}

    res = engine.evaluate_proposed_action(portfolio, proposed, limits, breakers, market_health)
    assert not res.is_approved
    assert any("Circuit breaker tripped" in r for r in res.rejections)

def test_risk_rejection_on_delta_breach():
    engine = RiskEngine()
    portfolio = {"total_capital": 500000.0, "used_margin": 10000.0, "delta": 4.8, "gamma": 0.0, "vega": 0.0, "theta": 0.0, "positions": []}
    proposed = {"strike": 65000, "expiry_years": 0.1, "option_type": "call", "direction": "buy", "quantity": 2.0, "initial_margin": 4000, "delta": 1.2, "gamma": 0.00004, "vega": 70, "theta": -60, "implied_volatility": 0.55, "order_price": 2000}
    limits = {"max_delta": 5.0, "max_gamma": 0.05, "max_vega": 50000.0, "max_theta": 10000.0, "margin_utilization": 0.70, "max_loss": 50000.0, "max_quote_age_seconds": 15.0}
    breakers = []
    market_health = {"quote_age_seconds": 1.0, "is_connected": True, "sequence_gap_detected": False, "spot_price": 65000.0}

    res = engine.evaluate_proposed_action(portfolio, proposed, limits, breakers, market_health)
    assert not res.is_approved
    assert any("Delta" in r and "breaches limit" in r for r in res.rejections)

def test_risk_rejection_on_stale_data():
    engine = RiskEngine()
    portfolio = {"total_capital": 500000.0, "used_margin": 10000.0, "delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0, "positions": []}
    proposed = {"strike": 65000, "expiry_years": 0.1, "option_type": "call", "direction": "buy", "quantity": 1.0, "initial_margin": 2000, "delta": 0.5, "gamma": 0.00004, "vega": 70, "theta": -60, "implied_volatility": 0.55, "order_price": 2000}
    limits = {"max_delta": 5.0, "max_gamma": 0.05, "max_vega": 50000.0, "max_theta": 10000.0, "margin_utilization": 0.70, "max_loss": 50000.0, "max_quote_age_seconds": 15.0}
    breakers = []
    market_health = {"quote_age_seconds": 45.0, "is_connected": True, "sequence_gap_detected": False, "spot_price": 65000.0}

    res = engine.evaluate_proposed_action(portfolio, proposed, limits, breakers, market_health)
    assert not res.is_approved
    assert any("stale" in r.lower() for r in res.rejections)

def test_stress_scenario_engine():
    engine = StressScenarioEngine()
    positions = [
        {"strike": 65000, "expiry_years": 30/365, "option_type": "call", "quantity": 2.0, "implied_vol": 0.55, "mark_price": 3000.0},
        {"strike": 60000, "expiry_years": 30/365, "option_type": "put", "quantity": -1.0, "implied_vol": 0.58, "mark_price": 1200.0}
    ]
    res = engine.evaluate_portfolio(positions, spot=65000.0)
    assert len(res["scenario_grid"]) == 7
    assert len(res["scenario_grid"][0]) == 7
    assert res["max_loss"] >= 0.0
