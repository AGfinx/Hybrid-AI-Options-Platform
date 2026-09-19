"""
Hedge Ratio Calculator

Computes optimal hedge ratios for cross-asset positions.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from packages.quant.cross_asset.correlation import estimate_hedge_ratio, CrossAssetCorrelation


@dataclass
class HedgeRatioResult:
    """Result of hedge ratio calculation."""
    hedge_ratio: float          # Units of hedge per unit of asset
    hedge_notional: float       # Notional amount of hedge
    confidence: float           # Confidence in estimate (0-1)
    method: str                 # Method used
    diagnostics: Dict           # Additional info
    risk_reduction: float       # Estimated variance reduction


class HedgeRatioCalculator:
    """
    Calculates optimal hedge ratios for cross-asset positions.
    
    Supports:
    - Single asset hedge (e.g., hedge ETH portfolio with BTC futures)
    - Multi-asset hedge (basket of hedges)
    - Dynamic hedge ratios (time-varying)
    - Minimum variance hedge ratio
    """
    
    def __init__(
        self,
        correlation_estimator: Optional[CrossAssetCorrelation] = None,
        min_observations: int = 60,
        max_hedge_ratio: float = 5.0,
        confidence_threshold: float = 0.5
    ):
        self.correlation_estimator = correlation_estimator or CrossAssetCorrelation()
        self.min_observations = min_observations
        self.max_hedge_ratio = max_hedge_ratio
        self.confidence_threshold = confidence_threshold
    
    def calculate_hedge_ratio(
        self,
        asset_returns: pd.Series,
        hedge_returns: pd.Series,
        asset_notional: float,
        method: str = "ols",
        asset_name: str = "asset",
        hedge_name: str = "hedge"
    ) -> HedgeRatioResult:
        """
        Calculate optimal hedge ratio.
        
        Args:
            asset_returns: Returns of asset to hedge
            hedge_returns: Returns of hedging instrument
            asset_notional: Notional value of asset position
            method: "ols" or "correlation"
            asset_name: Name for reporting
            hedge_name: Name for reporting
            
        Returns:
            HedgeRatioResult with ratio and diagnostics
        """
        # Estimate hedge ratio
        beta, diagnostics = estimate_hedge_ratio(asset_returns, hedge_returns, method)
        
        # Cap at maximum
        beta_capped = np.clip(beta, -self.max_hedge_ratio, self.max_hedge_ratio)
        
        # Hedge notional
        hedge_notional = -beta_capped * asset_notional  # Negative = short hedge
        
        # Confidence based on R² and sample size
        n_obs = diagnostics.get("n_obs", 0)
        r2 = diagnostics.get("r2", diagnostics.get("correlation", 0) ** 2)
        
        # Confidence increases with R² and sample size
        sample_confidence = min(1.0, n_obs / 252)  # Full year = 1.0
        fit_confidence = max(0.0, r2)  # R² as fit quality
        confidence = (sample_confidence + fit_confidence) / 2
        
        # Estimated risk reduction
        # Variance reduction = beta^2 * Var(hedge) / Var(asset) * correlation^2
        # Simplified: proportional to R²
        risk_reduction = max(0.0, r2)
        
        # Check if hedge is reliable
        if confidence < self.confidence_threshold:
            beta_capped = 0.0
            hedge_notional = 0.0
            confidence = 0.0
            risk_reduction = 0.0
        
        return HedgeRatioResult(
            hedge_ratio=beta_capped,
            hedge_notional=hedge_notional,
            confidence=confidence,
            method=method,
            diagnostics=diagnostics,
            risk_reduction=risk_reduction
        )
    
    def calculate_dynamic_hedge_ratios(
        self,
        asset_returns: pd.Series,
        hedge_returns: pd.Series,
        asset_notional: float,
        window: int = 60,
        method: str = "ols"
    ) -> pd.DataFrame:
        """
        Calculate time-varying hedge ratios using rolling window.
        
        Returns DataFrame with timestamp, hedge_ratio, hedge_notional, confidence.
        """
        results = []
        
        for i in range(window, len(asset_returns)):
            asset_window = asset_returns.iloc[i-window:i]
            hedge_window = hedge_returns.iloc[i-window:i]
            
            result = self.calculate_hedge_ratio(
                asset_window, hedge_window, asset_notional, method
            )
            
            results.append({
                "timestamp": asset_returns.index[i],
                "hedge_ratio": result.hedge_ratio,
                "hedge_notional": result.hedge_notional,
                "confidence": result.confidence,
                "risk_reduction": result.risk_reduction,
                "r2": result.diagnostics.get("r2", np.nan),
            })
        
        return pd.DataFrame(results)
    
    def calculate_multi_asset_hedge(
        self,
        asset_returns: pd.Series,
        hedge_returns_dict: Dict[str, pd.Series],
        asset_notional: float,
        method: str = "ols"
    ) -> Dict[str, HedgeRatioResult]:
        """
        Calculate hedge ratios using multiple hedging instruments.
        
        Uses multivariate regression to find optimal combination.
        """
        # Align all series
        all_returns = pd.concat([asset_returns] + list(hedge_returns_dict.values()), axis=1, join="inner").dropna()
        
        if len(all_returns) < self.min_observations:
            return {name: HedgeRatioResult(0, 0, 0, method, {"error": "Insufficient data"}, 0) 
                    for name in hedge_returns_dict}
        
        y = all_returns.iloc[:, 0].values  # asset
        X = all_returns.iloc[:, 1:].values  # hedges
        hedge_names = list(hedge_returns_dict.keys())
        
        # Multivariate OLS: beta = (X'X)^-1 X'y
        try:
            XtX = X.T @ X
            Xty = X.T @ y
            betas = np.linalg.solve(XtX, Xty)
        except np.linalg.LinAlgError:
            # Singular matrix - use pseudo-inverse
            betas = np.linalg.pinv(X) @ y
        
        # Cap betas
        betas = np.clip(betas, -self.max_hedge_ratio, self.max_hedge_ratio)
        
        # Calculate R² for overall fit
        y_pred = X @ betas
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        
        results = {}
        for i, name in enumerate(hedge_names):
            beta = betas[i]
            hedge_notional = -beta * asset_notional
            
            # Confidence based on overall R²
            confidence = max(0.0, r2)
            
            diagnostics = {
                "method": "multivariate_ols",
                "beta": beta,
                "overall_r2": r2,
                "n_obs": len(y),
                "all_betas": dict(zip(hedge_names, betas)),
            }
            
            if confidence < self.confidence_threshold:
                beta = 0.0
                hedge_notional = 0.0
                confidence = 0.0
            
            results[name] = HedgeRatioResult(
                hedge_ratio=beta,
                hedge_notional=hedge_notional,
                confidence=confidence,
                method=method,
                diagnostics=diagnostics,
                risk_reduction=confidence
            )
        
        return results
    
    def minimum_variance_hedge(
        self,
        asset_returns: pd.Series,
        hedge_returns: pd.Series,
        asset_notional: float
    ) -> HedgeRatioResult:
        """
        Minimum variance hedge ratio (classic).
        
        h* = Cov(S, F) / Var(F)
        where S = spot (asset), F = futures (hedge)
        """
        return self.calculate_hedge_ratio(
            asset_returns, hedge_returns, asset_notional, method="ols"
        )
    
    def tail_hedge_ratio(
        self,
        asset_returns: pd.Series,
        hedge_returns: pd.Series,
        asset_notional: float,
        quantile: float = 0.05
    ) -> HedgeRatioResult:
        """
        Tail-risk hedge ratio.
        
        Estimates hedge ratio conditional on extreme market moves.
        Uses quantile regression or conditional correlation.
        """
        # Condition on tail events
        asset_q = asset_returns.quantile(quantile)
        hedge_q = hedge_returns.quantile(quantile)
        
        # Filter for joint tail events
        tail_mask = (asset_returns <= asset_q) | (hedge_returns <= hedge_q)
        
        if tail_mask.sum() < 20:
            # Fallback to regular
            return self.minimum_variance_hedge(asset_returns, hedge_returns, asset_notional)
        
        tail_asset = asset_returns[tail_mask]
        tail_hedge = hedge_returns[tail_mask]
        
        return self.calculate_hedge_ratio(
            tail_asset, tail_hedge, asset_notional, method="ols"
        )


def compute_portfolio_hedge(
    portfolio: Dict[str, float],  # asset_name -> notional
    hedge_instruments: Dict[str, pd.Series],  # hedge_name -> returns
    asset_returns: Dict[str, pd.Series],  # asset_name -> returns
    calculator: HedgeRatioCalculator
) -> Dict[str, HedgeRatioResult]:
    """
    Compute aggregate hedge for a multi-asset portfolio.
    
    Args:
        portfolio: Dict of asset -> notional
        hedge_instruments: Dict of hedge_name -> returns series
        asset_returns: Dict of asset_name -> returns series
        calculator: HedgeRatioCalculator instance
        
    Returns:
        Dict of hedge_name -> HedgeRatioResult
    """
    results = {}
    
    # For each hedge instrument, compute combined hedge ratio
    for hedge_name, hedge_rets in hedge_instruments.items():
        # Aggregate asset returns weighted by notional
        total_notional = sum(portfolio.values())
        
        if total_notional == 0:
            results[hedge_name] = HedgeRatioResult(0, 0, 0, "portfolio", {}, 0)
            continue
        
        # Weighted asset returns
        weighted_returns = pd.Series(0.0, index=hedge_rets.index)
        
        for asset_name, notional in portfolio.items():
            if asset_name in asset_returns:
                weight = notional / total_notional
                # Align
                aligned_asset, aligned_hedge = asset_returns[asset_name].align(
                    hedge_rets, join="inner"
                )
                if len(aligned_asset) > calculator.min_observations:
                    weighted_returns += weight * aligned_asset
        
        # Calculate hedge ratio for this hedge instrument
        result = calculator.calculate_hedge_ratio(
            weighted_returns, hedge_rets, total_notional,
            asset_name="portfolio", hedge_name=hedge_name
        )
        
        results[hedge_name] = result
    
    return results