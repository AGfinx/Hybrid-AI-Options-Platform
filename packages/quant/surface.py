import math
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import numpy as np
from scipy.interpolate import griddata, Rbf
from packages.quant.black_scholes import bs_price, bs_greeks

@dataclass
class SurfacePoint:
    strike: float
    expiry_years: float
    moneyness: float  # K / S
    implied_vol: float
    option_type: str  # call, put
    price: float
    delta: float
    vega: float
    confidence: float
    is_valid: bool

class VolatilitySurface:
    def __init__(self, underlying: str = "BTC", spot: float = 65000.0, r: float = 0.0):
        self.underlying = underlying
        self.spot = spot
        self.r = r
        self.points: List[SurfacePoint] = []
        self.structural_status: str = "valid"  # valid, arbitrage_violated, fallback
        self.confidence: float = 1.0
        self.violations: List[str] = []
        self._interp_fn = None

    def build_from_quotes(self, quotes: List[Dict[str, Any]]) -> "VolatilitySurface":
        valid_points = []
        for q in quotes:
            strike = float(q.get("strike", 0.0))
            T = float(q.get("T", 0.0))
            iv = float(q.get("implied_vol", 0.0))
            opt_type = str(q.get("option_type", "call")).lower()
            bid = float(q.get("best_bid_price", 0.0) or 0.0)
            ask = float(q.get("best_ask_price", 0.0) or 0.0)

            if strike <= 0 or T <= 0 or iv <= 0.01 or iv > 5.0:
                continue

            moneyness = strike / self.spot
            greeks = bs_greeks(self.spot, strike, T, self.r, iv, opt_type)
            price = greeks["price"]

            # Confidence based on spread width
            mid = (bid + ask) / 2.0 if (bid > 0 and ask > 0) else price
            spread_ratio = (ask - bid) / mid if (mid > 0 and ask > bid) else 0.05
            conf = max(0.2, min(1.0, 1.0 - spread_ratio * 2.0))

            pt = SurfacePoint(
                strike=strike,
                expiry_years=T,
                moneyness=moneyness,
                implied_vol=iv,
                option_type=opt_type,
                price=price,
                delta=greeks["delta"],
                vega=greeks["vega"],
                confidence=conf,
                is_valid=True
            )
            valid_points.append(pt)

        self.points = valid_points
        self._validate_and_fit()
        return self

    def _validate_and_fit(self):
        if len(self.points) < 4:
            self.structural_status = "fallback"
            self.confidence = 0.3
            self.violations.append("Insufficient points for surface fitting (minimum 4 required)")
            return

        # 1. Structural Validation: Calendar Arbitrage
        # Group calls by strike and sort by T
        calls_by_strike: Dict[float, List[SurfacePoint]] = {}
        for pt in self.points:
            if pt.option_type == "call":
                calls_by_strike.setdefault(pt.strike, []).append(pt)

        calendar_violations = 0
        for strike, pts in calls_by_strike.items():
            pts_sorted = sorted(pts, key=lambda x: x.expiry_years)
            for i in range(len(pts_sorted) - 1):
                p1 = pts_sorted[i]
                p2 = pts_sorted[i + 1]
                # Price must not decrease with time to expiry (with tolerance for numerical precision)
                if p2.price < p1.price - 1e-4:
                    calendar_violations += 1

        # 2. Structural Validation: Butterfly Arbitrage (Convexity)
        # Group calls by expiry and sort by strike
        calls_by_expiry: Dict[float, List[SurfacePoint]] = {}
        for pt in self.points:
            if pt.option_type == "call":
                calls_by_expiry.setdefault(round(pt.expiry_years, 4), []).append(pt)

        butterfly_violations = 0
        for T, pts in calls_by_expiry.items():
            pts_sorted = sorted(pts, key=lambda x: x.strike)
            for i in range(len(pts_sorted) - 2):
                k1, k2, k3 = pts_sorted[i], pts_sorted[i + 1], pts_sorted[i + 2]
                lambda_w = (k3.strike - k2.strike) / (k3.strike - k1.strike)
                convex_bound = lambda_w * k1.price + (1 - lambda_w) * k3.price
                if k2.price > convex_bound + 1e-4:
                    butterfly_violations += 1

        if calendar_violations > 2 or butterfly_violations > 2:
            self.structural_status = "arbitrage_violated"
            self.confidence = max(0.1, 1.0 - (calendar_violations + butterfly_violations) * 0.15)
            self.violations.append(f"Calendar violations: {calendar_violations}, Butterfly violations: {butterfly_violations}")
        else:
            self.structural_status = "valid"
            self.confidence = max(0.7, 1.0 - (calendar_violations + butterfly_violations) * 0.1)

        # 3. Fit 2D Interpolator
        strikes = np.array([p.strike for p in self.points])
        expiries = np.array([p.expiry_years for p in self.points])
        vols = np.array([p.implied_vol for p in self.points])

        try:
            self._interp_fn = Rbf(strikes, expiries, vols, function="linear", smooth=0.01)
        except Exception:
            self._interp_fn = None

        # 4. SVI Slice Calibration
        from packages.quant.svi import SVICalibrator, SVIParameters
        calibrator = SVICalibrator()
        self.svi_slices: Dict[float, SVIParameters] = {}

        for T, pts in calls_by_expiry.items():
            s_list = [p.strike for p in pts]
            v_list = [p.implied_vol for p in pts]
            svi_p = calibrator.calibrate_slice(s_list, v_list, self.spot, float(T))
            self.svi_slices[float(T)] = svi_p

    def get_vol(self, strike: float, expiry_years: float, model: str = "surface_svi_v1") -> float:
        if model == "surface_svi_v1" and self.svi_slices:
            # Find closest calibrated SVI slice
            closest_T = min(self.svi_slices.keys(), key=lambda t: abs(t - expiry_years))
            svi_param = self.svi_slices[closest_T]
            k = math.log(max(1.0, strike) / self.spot)
            vol = svi_param.implied_vol(k, expiry_years)
            return max(0.05, min(3.0, vol))

        if self._interp_fn:
            try:
                vol = float(self._interp_fn(strike, expiry_years))
                return max(0.05, min(3.0, vol))
            except Exception:
                pass

        # Fallback: nearest neighbor
        if not self.points:
            return 0.55 if self.underlying == "BTC" else 0.65
        dists = [(abs(p.strike - strike) / self.spot + abs(p.expiry_years - expiry_years), p.implied_vol) for p in self.points]
        dists.sort(key=lambda x: x[0])
        return dists[0][1]

    def to_dict(self) -> Dict[str, Any]:
        svi_data = {}
        if hasattr(self, "svi_slices"):
            for T, param in self.svi_slices.items():
                svi_data[f"{round(T * 365)}d"] = {
                    "expiry_years": round(T, 4),
                    "a": round(param.a, 5),
                    "b": round(param.b, 5),
                    "rho": round(param.rho, 4),
                    "m": round(param.m, 4),
                    "sigma": round(param.sigma, 4)
                }

        return {
            "underlying": self.underlying,
            "spot": self.spot,
            "structural_status": self.structural_status,
            "confidence": round(self.confidence, 4),
            "violations": self.violations,
            "point_count": len(self.points),
            "svi_slices": svi_data,
            "points": [
                {
                    "strike": p.strike,
                    "expiry_years": round(p.expiry_years, 4),
                    "moneyness": round(p.moneyness, 4),
                    "implied_vol": round(p.implied_vol, 4),
                    "option_type": p.option_type,
                    "price": round(p.price, 2),
                    "delta": round(p.delta, 4),
                    "vega": round(p.vega, 4),
                    "confidence": round(p.confidence, 3),
                    "is_valid": p.is_valid
                }
                for p in self.points
            ]
        }
