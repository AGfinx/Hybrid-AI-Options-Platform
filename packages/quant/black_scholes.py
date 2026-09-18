import math
from typing import Dict, Literal, Optional
from scipy.stats import norm
from scipy.optimize import brentq

def bs_d1(S: float, K: float, T: float, r: float, sigma: float) -> float:
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0
    return (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))

def bs_d2(S: float, K: float, T: float, r: float, sigma: float) -> float:
    return bs_d1(S, K, T, r, sigma) - sigma * math.sqrt(T)

def bs_price(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: Literal["call", "put"] = "call"
) -> float:
    if T <= 0:
        return max(0.0, S - K) if option_type == "call" else max(0.0, K - S)
    if sigma <= 0:
        return max(0.0, S - K * math.exp(-r * T)) if option_type == "call" else max(0.0, K * math.exp(-r * T) - S)

    d1 = bs_d1(S, K, T, r, sigma)
    d2 = d1 - sigma * math.sqrt(T)

    if option_type == "call":
        return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    else:
        return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

def bs_greeks(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: Literal["call", "put"] = "call"
) -> Dict[str, float]:
    if T <= 0.0001 or sigma <= 0.0001 or S <= 0 or K <= 0:
        intrinsic = max(0.0, S - K) if option_type == "call" else max(0.0, K - S)
        delta = 1.0 if (option_type == "call" and S > K) else (-1.0 if (option_type == "put" and S < K) else 0.0)
        return {
            "price": intrinsic,
            "delta": delta,
            "gamma": 0.0,
            "vega": 0.0,
            "theta": 0.0,
            "rho": 0.0
        }

    d1 = bs_d1(S, K, T, r, sigma)
    d2 = d1 - sigma * math.sqrt(T)
    sqrt_T = math.sqrt(T)
    pdf_d1 = norm.pdf(d1)

    price = bs_price(S, K, T, r, sigma, option_type)

    if option_type == "call":
        delta = norm.cdf(d1)
        theta = (- (S * pdf_d1 * sigma) / (2 * sqrt_T) - r * K * math.exp(-r * T) * norm.cdf(d2)) / 365.0
        rho = (K * T * math.exp(-r * T) * norm.cdf(d2)) / 100.0
    else:
        delta = norm.cdf(d1) - 1.0
        theta = (- (S * pdf_d1 * sigma) / (2 * sqrt_T) + r * K * math.exp(-r * T) * norm.cdf(-d2)) / 365.0
        rho = (-K * T * math.exp(-r * T) * norm.cdf(-d2)) / 100.0

    gamma = pdf_d1 / (S * sigma * sqrt_T)
    vega = (S * sqrt_T * pdf_d1) / 100.0  # 1% vol change

    return {
        "price": price,
        "delta": delta,
        "gamma": gamma,
        "vega": vega,
        "theta": theta,
        "rho": rho
    }

def implied_volatility(
    price: float,
    S: float,
    K: float,
    T: float,
    r: float = 0.0,
    option_type: Literal["call", "put"] = "call",
    min_vol: float = 0.01,
    max_vol: float = 5.0
) -> Optional[float]:
    if T <= 0 or price <= 0:
        return None

    # Check arbitrage bounds
    discounted_k = K * math.exp(-r * T)
    if option_type == "call":
        lower_bound = max(0.0, S - discounted_k)
        upper_bound = S
    else:
        lower_bound = max(0.0, discounted_k - S)
        upper_bound = discounted_k

    if price <= lower_bound or price >= upper_bound:
        return None

    def obj(sigma: float) -> float:
        return bs_price(S, K, T, r, sigma, option_type) - price

    try:
        val_min = obj(min_vol)
        val_max = obj(max_vol)
        if val_min * val_max > 0:
            # Price outside the search range
            return None
        sol = brentq(obj, min_vol, max_vol, xtol=1e-6, maxiter=100)
        return float(sol)
    except Exception:
        return None
