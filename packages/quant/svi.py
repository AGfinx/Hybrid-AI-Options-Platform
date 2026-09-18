import math
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from scipy.optimize import least_squares

def raw_svi_total_variance(k: float, a: float, b: float, rho: float, m: float, sigma: float) -> float:
    """Raw SVI formula: w(k) = a + b * (rho * (k - m) + sqrt((k - m)^2 + sigma^2))"""
    diff = k - m
    val = a + b * (rho * diff + math.sqrt(diff ** 2 + sigma ** 2))
    return max(1e-6, val)

@dataclass
class SVIParameters:
    a: float
    b: float
    rho: float
    m: float
    sigma: float

    def total_variance(self, k: float) -> float:
        return raw_svi_total_variance(k, self.a, self.b, self.rho, self.m, self.sigma)

    def implied_vol(self, k: float, T: float) -> float:
        if T <= 0:
            return 0.55
        w = self.total_variance(k)
        return math.sqrt(w / T)

    def is_admissible(self) -> bool:
        min_w = self.a + self.b * self.sigma * math.sqrt(max(0.0, 1.0 - self.rho ** 2))
        return self.b >= 0.0 and abs(self.rho) < 1.0 and self.sigma > 0.0 and min_w >= 0.0

class SVICalibrator:
    """Calibrates Jim Gatheral's Raw SVI parameterization to option market smiles."""

    def __init__(self):
        pass

    def calibrate_slice(
        self,
        strikes: List[float],
        market_vols: List[float],
        spot: float,
        T: float
    ) -> SVIParameters:
        if len(strikes) < 4 or T <= 0:
            # Fallback default parameterization
            return SVIParameters(a=0.04 * T, b=0.15 * T, rho=-0.2, m=0.0, sigma=0.1)

        # Log-moneyness k = ln(K / S)
        k_vals = np.array([math.log(max(1.0, k) / spot) for k in strikes])
        w_market = np.array([(vol ** 2) * T for vol in market_vols])

        # Objective function for non-linear least squares
        def residuals(params):
            a, b, rho, m, sigma = params
            diff = k_vals - m
            w_model = a + b * (rho * diff + np.sqrt(diff ** 2 + sigma ** 2))
            res = w_model - w_market

            # Penalty for negative total variance
            min_w = a + b * sigma * np.sqrt(1 - rho ** 2)
            if min_w < 0:
                res += abs(min_w) * 100.0
            return res

        # Bounds: a in [-0.5, 2.0], b in [0.001, 2.0], rho in [-0.99, 0.99], m in [-1.0, 1.0], sigma in [0.01, 1.5]
        lower_bounds = [-0.5 * T, 0.001 * T, -0.99, -1.0, 0.01]
        upper_bounds = [2.0 * T, 2.0 * T, 0.99, 1.0, 1.5]

        # Initial guess
        x0 = [0.04 * T, 0.1 * T, -0.2, 0.0, 0.1]

        try:
            opt = least_squares(
                residuals,
                x0=x0,
                bounds=(lower_bounds, upper_bounds),
                ftol=1e-5,
                xtol=1e-5,
                max_nfev=200
            )
            p = opt.x
            return SVIParameters(a=float(p[0]), b=float(p[1]), rho=float(p[2]), m=float(p[3]), sigma=float(p[4]))
        except Exception:
            return SVIParameters(a=0.04 * T, b=0.15 * T, rho=-0.2, m=0.0, sigma=0.1)
