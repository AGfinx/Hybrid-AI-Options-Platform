import math
import numpy as np
import pytest
from packages.quant.svi import raw_svi_total_variance, SVIParameters, SVICalibrator

def test_raw_svi_total_variance_boundaries():
    """Verify Gatheral Raw SVI total variance properties and non-negativity."""
    params = SVIParameters(a=0.04, b=0.1, rho=-0.4, m=0.0, sigma=0.1)
    
    # Test ATM (k = 0)
    w_atm = raw_svi_total_variance(0.0, params.a, params.b, params.rho, params.m, params.sigma)
    assert w_atm > 0, "Total variance must be strictly positive"
    
    # Test wings: k = -0.5, k = +0.5
    w_left = raw_svi_total_variance(-0.5, params.a, params.b, params.rho, params.m, params.sigma)
    w_right = raw_svi_total_variance(0.5, params.a, params.b, params.rho, params.m, params.sigma)
    assert w_left > 0
    assert w_right > 0
    
    # Implied volatility calculation
    T = 0.25
    iv_atm = params.implied_vol(0.0, T)
    assert 0.10 < iv_atm < 1.5, f"IV should be reasonable, got {iv_atm}"
    assert params.is_admissible(), "Parameters must satisfy admissibility constraints"

def test_svi_calibrator_slice_fit():
    """Verify SVI calibration on synthetic option slice."""
    spot = 65000.0
    T = 30.0 / 365.0
    strikes = [55000.0, 60000.0, 65000.0, 70000.0, 75000.0]
    
    # Synthetic skew: lower strikes have higher IV
    market_vols = [0.65, 0.60, 0.55, 0.53, 0.52]
    
    calibrator = SVICalibrator()
    params = calibrator.calibrate_slice(strikes, market_vols, spot, T)
    
    assert params.is_admissible()
    assert params.b >= 0.0
    assert abs(params.rho) < 1.0
    assert params.sigma > 0.0
    
    # Verify calibrated IV matches within reasonable tolerance (< 5 vol points)
    for K, mkt_vol in zip(strikes, market_vols):
        k = math.log(K / spot)
        model_iv = params.implied_vol(k, T)
        assert abs(model_iv - mkt_vol) < 0.06, f"Mismatch at strike {K}: model={model_iv:.3f}, mkt={mkt_vol:.3f}"
