"""
Cross-Asset Hedging Foundation

Research component for BTC/ETH cross-asset hedge relationships.
Integrates with existing risk engine without bypassing safety.
"""

from packages.quant.cross_asset.correlation import CrossAssetCorrelation
from packages.quant.cross_asset.hedge_ratio import HedgeRatioCalculator
from packages.quant.cross_asset.exposure import CrossAssetExposure
from packages.quant.cross_asset.risk_integration import CrossAssetRiskIntegrator

__all__ = [
    "CrossAssetCorrelation",
    "HedgeRatioCalculator",
    "CrossAssetExposure",
    "CrossAssetRiskIntegrator",
]