"""
Cross-Asset Correlation Estimation

Estimates correlation between BTC and ETH for hedging purposes.
Uses robust statistical methods suitable for financial time-series.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from scipy import stats


class CrossAssetCorrelation:
    """
    Estimates and maintains cross-asset correlations.
    
    Methods:
    - Pearson (linear correlation)
    - Spearman (rank correlation, robust to outliers)
    - Rolling window estimates
    - EWMA (exponentially weighted)
    - Regime-aware (separate correlations for different vol regimes)
    """
    
    def __init__(
        self,
        window: int = 60,
        min_periods: int = 20,
        method: str = "spearman"
    ):
        """
        Args:
            window: Rolling window size
            min_periods: Minimum observations for valid estimate
            method: "pearson", "spearman", "kendall"
        """
        self.window = window
        self.min_periods = min_periods
        self.method = method
        
        # State
        self.correlation_history = []
        self.current_correlation = None
    
    def compute_correlation(
        self,
        returns_a: pd.Series,
        returns_b: pd.Series,
        method: Optional[str] = None
    ) -> float:
        """
        Compute correlation between two return series.
        
        Args:
            returns_a: First asset returns
            returns_b: Second asset returns
            method: Override default method
            
        Returns:
            Correlation coefficient
        """
        method = method or self.method
        
        # Align series
        aligned = pd.concat([returns_a, returns_b], axis=1, join="inner").dropna()
        
        if len(aligned) < self.min_periods:
            return np.nan
        
        a = aligned.iloc[:, 0]
        b = aligned.iloc[:, 1]
        
        if method == "pearson":
            return a.corr(b, method="pearson")
        elif method == "spearman":
            return a.corr(b, method="spearman")
        elif method == "kendall":
            return a.corr(b, method="kendall")
        else:
            raise ValueError(f"Unknown method: {method}")
    
    def rolling_correlation(
        self,
        returns_a: pd.Series,
        returns_b: pd.Series
    ) -> pd.Series:
        """
        Compute rolling correlation.
        """
        method = self.method
        
        if method == "pearson":
            return returns_a.rolling(self.window, min_periods=self.min_periods).corr(returns_b)
        else:
            # For non-Pearson, use apply
            def corr_func(window):
                if len(window) < self.min_periods:
                    return np.nan
                a = window.iloc[:, 0]
                b = window.iloc[:, 1]
                return a.corr(b, method=method)
            
            combined = pd.concat([returns_a, returns_b], axis=1)
            return combined.rolling(self.window, min_periods=self.min_periods).apply(corr_func, raw=False)
    
    def ewma_correlation(
        self,
        returns_a: pd.Series,
        returns_b: pd.Series,
        halflife: int = 30
    ) -> pd.Series:
        """
        Exponentially weighted moving average correlation.
        
        More responsive to recent changes than rolling window.
        """
        # Align
        aligned = pd.concat([returns_a, returns_b], axis=1, join="inner").dropna()
        a = aligned.iloc[:, 0]
        b = aligned.iloc[:, 1]
        
        # EWMA covariance and variances
        ewma_cov = a.ewm(halflife=halflife).cov(b)
        ewma_var_a = a.ewm(halflife=halflife).var()
        ewma_var_b = b.ewm(halflife=halflife).var()
        
        ewma_corr = ewma_cov / np.sqrt(ewma_var_a * ewma_var_b + 1e-10)
        
        return ewma_corr
    
    def regime_correlation(
        self,
        returns_a: pd.Series,
        returns_b: pd.Series,
        regime_indicator: pd.Series,
        regime_values: List[int] = None
    ) -> Dict[int, float]:
        """
        Compute correlation conditional on market regime.
        
        Args:
            returns_a, returns_b: Return series
            regime_indicator: Regime label for each timestamp
            regime_values: Specific regimes to compute (default: all unique)
            
        Returns:
            Dict mapping regime -> correlation
        """
        if regime_values is None:
            regime_values = regime_indicator.unique()
        
        results = {}
        
        for regime in regime_values:
            mask = regime_indicator == regime
            if mask.sum() < self.min_periods:
                results[regime] = np.nan
                continue
            
            a_regime = returns_a[mask]
            b_regime = returns_b[mask]
            
            corr = self.compute_correlation(a_regime, b_regime)
            results[regime] = corr
        
        return results
    
    def correlation_stability(
        self,
        returns_a: pd.Series,
        returns_b: pd.Series,
        n_splits: int = 10
    ) -> Dict:
        """
        Assess correlation stability over time.
        
        Splits data into chunks and computes correlation in each.
        """
        n = len(returns_a)
        chunk_size = n // n_splits
        
        correlations = []
        
        for i in range(n_splits):
            start = i * chunk_size
            end = (i + 1) * chunk_size if i < n_splits - 1 else n
            
            a_chunk = returns_a.iloc[start:end]
            b_chunk = returns_b.iloc[start:end]
            
            if len(a_chunk) >= self.min_periods:
                corr = self.compute_correlation(a_chunk, b_chunk)
                if not np.isnan(corr):
                    correlations.append(corr)
        
        if not correlations:
            return {"mean": np.nan, "std": np.nan, "min": np.nan, "max": np.nan}
        
        return {
            "mean": np.mean(correlations),
            "std": np.std(correlations),
            "min": np.min(correlations),
            "max": np.max(correlations),
            "values": correlations,
        }
    
    def update(self, returns_a: pd.Series, returns_b: pd.Series) -> float:
        """
        Update correlation with latest data.
        
        Returns current correlation estimate.
        """
        corr = self.compute_correlation(returns_a, returns_b)
        
        if not np.isnan(corr):
            self.correlation_history.append(corr)
            # Keep last 1000
            if len(self.correlation_history) > 1000:
                self.correlation_history = self.correlation_history[-1000:]
            self.current_correlation = corr
        
        return corr


def estimate_hedge_ratio(
    returns_asset: pd.Series,
    returns_hedge: pd.Series,
    method: str = "ols"
) -> Tuple[float, Dict]:
    """
    Estimate optimal hedge ratio (beta).
    
    Hedge ratio = Cov(asset, hedge) / Var(hedge)
    
    Args:
        returns_asset: Asset to hedge (e.g., ETH options portfolio)
        returns_hedge: Hedging instrument (e.g., BTC futures)
        method: "ols" (OLS regression), "correlation" (corr * std_ratio)
        
    Returns:
        (hedge_ratio, diagnostics)
    """
    # Align
    aligned = pd.concat([returns_asset, returns_hedge], axis=1, join="inner").dropna()
    
    if len(aligned) < 30:
        return 0.0, {"error": "Insufficient data"}
    
    y = aligned.iloc[:, 0].values  # asset
    x = aligned.iloc[:, 1].values  # hedge
    
    if method == "ols":
        # OLS: y = alpha + beta * x
        # beta = Cov(x,y) / Var(x)
        cov = np.cov(x, y)[0, 1]
        var_x = np.var(x)
        beta = cov / var_x if var_x > 0 else 0.0
        
        # Alpha
        alpha = np.mean(y) - beta * np.mean(x)
        
        # R-squared
        y_pred = alpha + beta * x
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        
        # Standard error of beta
        residuals = y - y_pred
        se_beta = np.sqrt(np.var(residuals) / (len(x) * var_x)) if var_x > 0 else np.inf
        
        diagnostics = {
            "method": "ols",
            "alpha": alpha,
            "beta": beta,
            "r2": r2,
            "se_beta": se_beta,
            "n_obs": len(x),
            "covariance": cov,
            "var_hedge": var_x,
        }
        
        return beta, diagnostics
    
    elif method == "correlation":
        corr = np.corrcoef(x, y)[0, 1]
        beta = corr * np.std(y) / (np.std(x) + 1e-10)
        
        diagnostics = {
            "method": "correlation",
            "correlation": corr,
            "beta": beta,
            "n_obs": len(x),
        }
        
        return beta, diagnostics
    
    else:
        raise ValueError(f"Unknown method: {method}")