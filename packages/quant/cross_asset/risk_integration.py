"""
Cross-Asset Risk Integration

Integrates cross-asset hedge calculations with the existing risk engine
WITHOUT bypassing its fail-closed behavior.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from packages.risk.engine import RiskEngine, RiskCheckResult
from packages.quant.cross_asset.exposure import CrossAssetExposure
from packages.quant.cross_asset.hedge_ratio import HedgeRatioCalculator, compute_portfolio_hedge


@dataclass
class CrossAssetHedgeAction:
    """Recommended cross-asset hedge action."""
    hedge_instrument: str
    hedge_notional: float
    hedge_ratio: float
    confidence: float
    risk_reduction_estimate: float
    reason: str


class CrossAssetRiskIntegrator:
    """
    Integrates cross-asset hedging with the existing risk engine.
    
    CRITICAL: Does NOT bypass or weaken the existing risk engine.
    Only provides ADDITIONAL information for the risk engine to consider.
    The risk engine remains the sole gatekeeper with fail-closed behavior.
    """
    
    def __init__(
        self,
        risk_engine: RiskEngine,
        hedge_calculator: Optional[HedgeRatioCalculator] = None,
        max_cross_asset_hedge_notional: float = 100000.0,
        min_confidence: float = 0.6
    ):
        self.risk_engine = risk_engine
        self.hedge_calculator = hedge_calculator or HedgeRatioCalculator()
        self.max_cross_asset_hedge_notional = max_cross_asset_hedge_notional
        self.min_confidence = min_confidence
        
        self.cross_asset_exposure = CrossAssetExposure()
        self.recommended_hedges: List[CrossAssetHedgeAction] = []
    
    def update_exposures(
        self,
        positions: List[Dict],
        greeks_map: Dict,
        correlation_matrix: Optional[Any] = None
    ):
        """Update cross-asset exposures from current positions."""
        self.cross_asset_exposure.update_from_positions(positions, greeks_map)
        
        if correlation_matrix is not None:
            self.cross_asset_exposure.set_correlation_matrix(correlation_matrix)
    
    def compute_cross_asset_hedges(
        self,
        asset_returns: Dict[str, Any],  # underlying -> returns series
        hedge_instruments: Dict[str, Any],  # hedge_name -> returns series
        portfolio_notional: Dict[str, float]  # underlying -> notional
    ) -> List[CrossAssetHedgeAction]:
        """
        Compute recommended cross-asset hedges.
        
        Returns list of hedge actions for the risk engine to evaluate.
        """
        # Use portfolio hedge calculator
        hedge_results = compute_portfolio_hedge(
            portfolio_notional,
            hedge_instruments,
            asset_returns,
            self.hedge_calculator
        )
        
        actions = []
        
        for hedge_name, result in hedge_results.items():
            if result.confidence < self.min_confidence:
                continue
            
            if result.hedge_notional == 0:
                continue
            
            # Cap notional
            capped_notional = max(
                -self.max_cross_asset_hedge_notional,
                min(self.max_cross_asset_hedge_notional, result.hedge_notional)
            )
            
            action = CrossAssetHedgeAction(
                hedge_instrument=hedge_name,
                hedge_notional=capped_notional,
                hedge_ratio=result.hedge_ratio,
                confidence=result.confidence,
                risk_reduction_estimate=result.risk_reduction,
                reason=f"Cross-asset hedge: {result.method}, R²={result.diagnostics.get('r2', 0):.3f}"
            )
            
            actions.append(action)
        
        self.recommended_hedges = actions
        return actions
    
    def evaluate_hedge_impact(
        self,
        proposed_hedges: List[CrossAssetHedgeAction],
        current_portfolio: Dict[str, Any],
        limits: Dict[str, float],
        market_health: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate impact of proposed cross-asset hedges on risk metrics.
        
        Returns risk impact assessment for the risk engine.
        """
        # Calculate current cross-asset delta risk
        current_delta_risk = self.cross_asset_exposure.cross_asset_delta_risk()
        current_diversification = self.cross_asset_exposure.diversification_benefit()
        
        # Estimate post-hedge metrics
        # This is a simplified estimate - real implementation would
        # simulate the hedge positions through the risk engine
        
        total_hedge_notional = sum(abs(h.hedge_notional) for h in proposed_hedges)
        total_risk_reduction = sum(h.risk_reduction_estimate for h in proposed_hedges)
        avg_confidence = np.mean([h.confidence for h in proposed_hedges]) if proposed_hedges else 0
        
        # Estimated new delta risk (conservative: assume perfect hedge)
        estimated_delta_risk = current_delta_risk * (1 - total_risk_reduction)
        
        # Check if hedges violate any limits
        limit_violations = []
        
        # Check notional limits
        for hedge in proposed_hedges:
            if abs(hedge.hedge_notional) > limits.get("max_cross_asset_hedge_notional", self.max_cross_asset_hedge_notional):
                limit_violations.append(
                    f"Hedge notional {hedge.hedge_notional:.0f} exceeds limit for {hedge.hedge_instrument}"
                )
        
        return {
            "current_delta_risk": current_delta_risk,
            "current_diversification_benefit": current_diversification,
            "proposed_hedge_notional": total_hedge_notional,
            "estimated_delta_risk_after_hedge": estimated_delta_risk,
            "estimated_risk_reduction": total_risk_reduction,
            "average_hedge_confidence": avg_confidence,
            "limit_violations": limit_violations,
            "hedge_count": len(proposed_hedges),
            "recommendation": "approve" if not limit_violations and avg_confidence >= self.min_confidence else "reject",
        }
    
    def augment_risk_check(
        self,
        portfolio: Dict[str, Any],
        proposed_action: Dict[str, Any],
        limits: Dict[str, float],
        circuit_breakers: List[Dict[str, Any]],
        market_health: Dict[str, Any],
        asset_returns: Optional[Dict] = None,
        hedge_instruments: Optional[Dict] = None,
        portfolio_notional: Optional[Dict] = None
    ) -> RiskCheckResult:
        """
        Augment the standard risk check with cross-asset information.
        
        This does NOT modify the risk engine's decision.
        It only provides additional context.
        
        The risk engine's result is still the final authority.
        """
        # First, run standard risk check
        base_result = self.risk_engine.evaluate_proposed_action(
            portfolio, proposed_action, limits, circuit_breakers, market_health
        )
        
        # If base check fails, cross-asset cannot override
        if not base_result.is_approved:
            return base_result
        
        # If cross-asset data available, compute hedges
        cross_asset_info = {}
        
        if asset_returns and hedge_instruments and portfolio_notional:
            hedges = self.compute_cross_asset_hedges(
                asset_returns, hedge_instruments, portfolio_notional
            )
            
            impact = self.evaluate_hedge_impact(
                hedges, portfolio, limits, market_health
            )
            
            cross_asset_info = {
                "recommended_hedges": [
                    {
                        "instrument": h.hedge_instrument,
                        "notional": h.hedge_notional,
                        "ratio": h.hedge_ratio,
                        "confidence": h.confidence,
                    }
                    for h in hedges
                ],
                "impact_assessment": impact,
                "cross_asset_exposure": self.cross_asset_exposure.summary(),
            }
            
            # Add to result
            base_result.cross_asset_info = cross_asset_info
            
            # If hedges would be rejected, add warning
            if impact.get("recommendation") == "reject":
                base_result.warnings.append(
                    f"Cross-asset hedge recommendation rejected: {impact.get('limit_violations', ['low confidence'])}"
                )
        
        return base_result
    
    def get_hedge_recommendations(self) -> List[CrossAssetHedgeAction]:
        """Get current hedge recommendations."""
        return self.recommended_hedges.copy()


import numpy as np