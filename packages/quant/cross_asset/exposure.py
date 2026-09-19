"""
Cross-Asset Exposure Representation

Represents and tracks cross-asset options/underlying exposures.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class AssetExposure:
    """Exposure for a single underlying asset."""
    underlying: str
    delta: float = 0.0          # Spot delta exposure
    gamma: float = 0.0          # Gamma exposure
    vega: float = 0.0           # Vega exposure ($/1% vol)
    theta: float = 0.0          # Theta exposure ($/day)
    notional: float = 0.0       # Total option notional
    net_options_value: float = 0.0  # Net option value
    positions: Dict = field(default_factory=dict)  # instrument -> qty
    
    def add_position(self, instrument: str, qty: float, greeks: Dict):
        """Add position to exposure."""
        self.positions[instrument] = self.positions.get(instrument, 0) + qty
        self.delta += greeks.get("delta", 0) * qty
        self.gamma += greeks.get("gamma", 0) * qty
        self.vega += greeks.get("vega", 0) * qty
        self.theta += greeks.get("theta", 0) * qty
        self.notional += abs(qty) * greeks.get("mark_price", 0)
    
    def to_dict(self) -> Dict:
        return {
            "underlying": self.underlying,
            "delta": self.delta,
            "gamma": self.gamma,
            "vega": self.vega,
            "theta": self.theta,
            "notional": self.notional,
            "net_options_value": self.net_options_value,
            "positions": self.positions,
        }


class CrossAssetExposure:
    """
    Aggregated cross-asset exposure tracker.
    
    Combines exposures across multiple underlyings (BTC, ETH, etc.)
    and computes cross-asset risk metrics.
    """
    
    def __init__(self):
        self.exposures: Dict[str, AssetExposure] = {}
        self.correlation_matrix: Optional[pd.DataFrame] = None
    
    def add_asset_exposure(self, exposure: AssetExposure):
        """Add or update exposure for an underlying."""
        self.exposures[exposure.underlying] = exposure
    
    def update_from_positions(self, positions: List[Dict], greeks_map: Dict):
        """
        Update exposures from position list.
        
        Args:
            positions: List of {instrument_id, quantity, underlying, ...}
            greeks_map: instrument_id -> {delta, gamma, vega, theta, mark_price}
        """
        self.exposures = {}
        
        for pos in positions:
            underlying = pos.get("underlying", "UNKNOWN")
            instrument = pos.get("instrument_id", "")
            qty = pos.get("quantity", 0)
            
            if underlying not in self.exposures:
                self.exposures[underlying] = AssetExposure(underlying=underlying)
            
            greeks = greeks_map.get(instrument, {})
            self.exposures[underlying].add_position(instrument, qty, greeks)
    
    def set_correlation_matrix(self, corr_matrix: pd.DataFrame):
        """Set cross-asset correlation matrix."""
        self.correlation_matrix = corr_matrix
    
    def aggregate_delta(self) -> Dict[str, float]:
        """Get delta exposure per underlying."""
        return {u: exp.delta for u, exp in self.exposures.items()}
    
    def aggregate_greeks(self) -> Dict[str, Dict[str, float]]:
        """Get all Greeks per underlying."""
        return {u: {"delta": e.delta, "gamma": e.gamma, "vega": e.vega, "theta": e.theta} 
                for u, e in self.exposures.items()}
    
    def total_vega(self) -> float:
        """Total vega across all assets."""
        return sum(e.vega for e in self.exposures.values())
    
    def total_theta(self) -> float:
        """Total theta across all assets."""
        return sum(e.theta for e in self.exposures.values())
    
    def cross_asset_delta_risk(self) -> float:
        """
        Compute cross-asset delta risk using correlation.
        
        If we have BTC delta and ETH delta with correlation rho:
        Combined risk = sqrt(delta_btc^2 + delta_eth^2 + 2*rho*delta_btc*delta_eth)
        """
        if len(self.exposures) < 2 or self.correlation_matrix is None:
            return sum(abs(e.delta) for e in self.exposures.values())  # Conservative sum
        
        deltas = []
        underlyings = []
        
        for u, exp in self.exposures.items():
            if u in self.correlation_matrix.index:
                deltas.append(exp.delta)
                underlyings.append(u)
        
        if len(deltas) < 2:
            return sum(abs(d) for d in deltas)
        
        deltas = np.array(deltas)
        # Get sub-matrix
        corr_sub = self.correlation_matrix.loc[underlyings, underlyings].values
        
        # Portfolio variance = w' * Sigma * w
        # where w = deltas (in BTC-equivalent units)
        # Need to normalize by spot prices for proper units
        # Simplified: assume deltas already in comparable units
        portfolio_var = deltas @ corr_sub @ deltas
        
        return np.sqrt(max(0, portfolio_var))
    
    def diversification_benefit(self) -> float:
        """
        Compute diversification benefit from cross-asset positions.
        
        Benefit = (Sum of individual risks) - (Portfolio risk)
        """
        individual_risk = sum(abs(e.delta) for e in self.exposures.values())
        portfolio_risk = self.cross_asset_delta_risk()
        
        return max(0, individual_risk - portfolio_risk)
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert to DataFrame for reporting."""
        rows = []
        for u, exp in self.exposures.items():
            rows.append(exp.to_dict())
        return pd.DataFrame(rows)
    
    def summary(self) -> Dict:
        """Get exposure summary."""
        return {
            "underlyings": list(self.exposures.keys()),
            "total_vega": self.total_vega(),
            "total_theta": self.total_theta(),
            "aggregate_delta": self.aggregate_delta(),
            "cross_asset_delta_risk": self.cross_asset_delta_risk(),
            "diversification_benefit": self.diversification_benefit(),
            "has_correlation": self.correlation_matrix is not None,
        }