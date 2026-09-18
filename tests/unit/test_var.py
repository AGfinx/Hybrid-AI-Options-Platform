import pytest
from packages.risk.var import PortfolioVaREngine

def test_var_empty_portfolio():
    """Empty portfolio should return 0 for all VaR and CVaR metrics."""
    engine = PortfolioVaREngine()
    res = engine.calculate_var([], spot=65000.0)
    assert res["var_95"] == 0.0
    assert res["var_99"] == 0.0
    assert res["cvar_99"] == 0.0
    assert res["simulated_paths"] == 10000

def test_var_and_cvar_ordering():
    """For a risky portfolio, Expected Shortfall (CVaR) >= VaR 99% >= VaR 95% >= 0."""
    engine = PortfolioVaREngine(num_simulations=10000, seed=42)
    
    positions = [
        {
            "strike": 65000.0,
            "expiry_years": 30.0 / 365.0,
            "option_type": "call",
            "quantity": 2.0,
            "implied_vol": 0.55,
            "mark_price": 2800.0,
            "delta": 1.0,
            "gamma": 0.00004,
            "vega": 140.0,
            "theta": -60.0
        },
        {
            "strike": 60000.0,
            "expiry_years": 30.0 / 365.0,
            "option_type": "put",
            "quantity": -1.5,
            "implied_vol": 0.58,
            "mark_price": 1200.0,
            "delta": 0.45,
            "gamma": -0.00002,
            "vega": -90.0,
            "theta": 40.0
        }
    ]

    res = engine.calculate_var(positions, spot=65000.0)
    
    var_95 = res["var_95"]
    var_99 = res["var_99"]
    cvar_99 = res["cvar_99"]

    assert var_95 > 0.0, "VaR 95% must be strictly positive"
    assert var_99 >= var_95, f"VaR 99% ({var_99}) must be >= VaR 95% ({var_95})"
    assert cvar_99 >= var_99, f"CVaR 99% ({cvar_99}) must be >= VaR 99% ({var_99})"
    assert "percentile_breakdown" in res
    assert res["percentile_breakdown"]["p99"] == var_99
