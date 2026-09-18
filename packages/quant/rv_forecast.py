import datetime
from typing import Dict, Any, List, Optional
import numpy as np
from sklearn.linear_model import Ridge
from sklearn.model_selection import TimeSeriesSplit

class RealizedVolForecaster:
    def __init__(self, model_version: str = "rv_forecaster_v1"):
        self.model_version = model_version
        self.model = Ridge(alpha=1.0)
        self.is_fitted = False
        self.feature_names = ["rv_7d", "rv_14d", "rv_30d", "return_skew"]
        self.residual_std = 0.04

    def extract_features(self, prices: List[float]) -> Dict[str, float]:
        if len(prices) < 30:
            # Baseline features if historical series is short
            return {
                "rv_7d": 0.52,
                "rv_14d": 0.55,
                "rv_30d": 0.58,
                "return_skew": -0.15
            }

        arr = np.array(prices, dtype=float)
        log_ret = np.diff(np.log(arr))

        # Annualized rolling volatility: sqrt(365) * std(daily)
        rv_7d = float(np.std(log_ret[-7:]) * np.sqrt(365)) if len(log_ret) >= 7 else 0.52
        rv_14d = float(np.std(log_ret[-14:]) * np.sqrt(365)) if len(log_ret) >= 14 else 0.55
        rv_30d = float(np.std(log_ret[-30:]) * np.sqrt(365)) if len(log_ret) >= 30 else 0.58

        mean = np.mean(log_ret[-30:])
        std = np.std(log_ret[-30:])
        skew = float(np.mean(((log_ret[-30:] - mean) / (std + 1e-8)) ** 3)) if std > 1e-8 else 0.0

        return {
            "rv_7d": max(0.1, min(2.5, rv_7d)),
            "rv_14d": max(0.1, min(2.5, rv_14d)),
            "rv_30d": max(0.1, min(2.5, rv_30d)),
            "return_skew": max(-3.0, min(3.0, skew))
        }

    def train_baseline(self, historical_features: np.ndarray, historical_targets: np.ndarray):
        """Train time-aware Ridge regression using TimeSeriesSplit (no data leakage)."""
        if len(historical_features) < 10:
            # Fallback coefficients
            self.model.coef_ = np.array([0.4, 0.35, 0.25, 0.0])
            self.model.intercept_ = 0.02
            self.is_fitted = True
            return

        tscv = TimeSeriesSplit(n_splits=3)
        residuals = []

        for train_idx, test_idx in tscv.split(historical_features):
            X_tr, y_tr = historical_features[train_idx], historical_targets[train_idx]
            X_te, y_te = historical_features[test_idx], historical_targets[test_idx]
            self.model.fit(X_tr, y_tr)
            preds = self.model.predict(X_te)
            residuals.extend(y_te - preds)

        self.model.fit(historical_features, historical_targets)
        self.residual_std = float(np.std(residuals)) if residuals else 0.04
        self.is_fitted = True

    def forecast(
        self,
        features: Dict[str, float],
        horizon_seconds: int = 3600,
        underlying: str = "BTC"
    ) -> Dict[str, Any]:
        vec = np.array([[
            features.get("rv_7d", 0.52),
            features.get("rv_14d", 0.55),
            features.get("rv_30d", 0.58),
            features.get("return_skew", 0.0)
        ]])

        if self.is_fitted:
            pred = float(self.model.predict(vec)[0])
        else:
            # Explicit transparent weighted baseline
            pred = float(0.45 * vec[0][0] + 0.35 * vec[0][1] + 0.20 * vec[0][2])

        forecast_val = max(0.15, min(2.5, pred))
        uncertainty = round(self.residual_std * np.sqrt(max(1.0, horizon_seconds / 3600.0)), 4)

        if forecast_val < 0.40:
            regime = "low"
        elif forecast_val < 0.65:
            regime = "normal"
        elif forecast_val < 0.85:
            regime = "elevated"
        else:
            regime = "extreme"

        valid_until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=horizon_seconds)

        return {
            "underlying": underlying,
            "horizon_seconds": horizon_seconds,
            "forecast": round(forecast_val, 4),
            "uncertainty": uncertainty,
            "regime": regime,
            "valid_until": valid_until.isoformat(),
            "model_version": self.model_version,
            "features_used": features
        }
