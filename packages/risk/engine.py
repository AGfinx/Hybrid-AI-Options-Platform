import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from packages.risk.stress import StressScenarioEngine
from packages.risk.var import PortfolioVaREngine

@dataclass
class RiskCheckResult:
    is_approved: bool
    rejections: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    post_trade_greeks: Dict[str, float] = field(default_factory=dict)
    limit_utilization: Dict[str, float] = field(default_factory=dict)
    stress_results: Optional[Dict[str, Any]] = None
    var_results: Optional[Dict[str, Any]] = None

class RiskEngine:
    def __init__(self):
        self.stress_engine = StressScenarioEngine()
        self.var_engine = PortfolioVaREngine()

    def evaluate_proposed_action(
        self,
        portfolio: Dict[str, Any],
        proposed_action: Dict[str, Any],
        limits: Dict[str, float],
        circuit_breakers: List[Dict[str, Any]],
        market_health: Dict[str, Any]
    ) -> RiskCheckResult:
        rejections = []
        warnings = []

        # 1. Circuit Breakers & Emergency Stop check
        for cb in circuit_breakers:
            if cb.get("is_tripped", False):
                rejections.append(f"Circuit breaker tripped: '{cb.get('name')}' ({cb.get('reason') or 'No reason provided'})")

        # 2. Market Data Freshness & Connection Quality
        quote_age = market_health.get("quote_age_seconds", 0.0)
        max_quote_age = limits.get("max_quote_age_seconds", 15.0)
        if quote_age > max_quote_age:
            rejections.append(f"Market data stale: quote age {quote_age:.1f}s exceeds limit {max_quote_age:.1f}s")

        if not market_health.get("is_connected", True):
            rejections.append("Market data feed disconnected; fail closed.")

        if market_health.get("sequence_gap_detected", False):
            rejections.append("Market feed sequence gap detected; fail closed.")

        # 3. Capital & Margin Checks
        total_capital = float(portfolio.get("total_capital", 500000.0))
        current_margin = float(portfolio.get("used_margin", 0.0))
        new_margin = float(proposed_action.get("initial_margin", 0.0))
        projected_margin = current_margin + new_margin
        max_margin_ratio = limits.get("margin_utilization", 0.70)
        margin_util = projected_margin / total_capital if total_capital > 0 else 1.0

        if margin_util > max_margin_ratio:
            rejections.append(f"Margin utilization {margin_util:.1%} exceeds maximum limit {max_margin_ratio:.1%}")
        elif margin_util > max_margin_ratio * 0.8:
            warnings.append(f"Margin utilization {margin_util:.1%} nearing limit {max_margin_ratio:.1%}")

        # 4. Portfolio Greeks Checks
        curr_delta = float(portfolio.get("delta", 0.0))
        curr_gamma = float(portfolio.get("gamma", 0.0))
        curr_vega = float(portfolio.get("vega", 0.0))
        curr_theta = float(portfolio.get("theta", 0.0))

        add_delta = float(proposed_action.get("delta", 0.0))
        add_gamma = float(proposed_action.get("gamma", 0.0))
        add_vega = float(proposed_action.get("vega", 0.0))
        add_theta = float(proposed_action.get("theta", 0.0))

        proj_delta = curr_delta + add_delta
        proj_gamma = curr_gamma + add_gamma
        proj_vega = curr_vega + add_vega
        proj_theta = curr_theta + add_theta

        max_delta = limits.get("max_delta", 5.0)
        max_gamma = limits.get("max_gamma", 0.05)
        max_vega = limits.get("max_vega", 50000.0)
        max_theta = limits.get("max_theta", 10000.0)

        delta_util = abs(proj_delta) / max_delta if max_delta > 0 else 0.0
        gamma_util = abs(proj_gamma) / max_gamma if max_gamma > 0 else 0.0
        vega_util = abs(proj_vega) / max_vega if max_vega > 0 else 0.0
        theta_util = abs(proj_theta) / max_theta if max_theta > 0 else 0.0

        if abs(proj_delta) > max_delta:
            rejections.append(f"Projected Delta ({proj_delta:.2f}) breaches limit (±{max_delta:.2f})")
        if abs(proj_gamma) > max_gamma:
            rejections.append(f"Projected Gamma ({proj_gamma:.5f}) breaches limit (±{max_gamma:.5f})")
        if abs(proj_vega) > max_vega:
            rejections.append(f"Projected Vega (${proj_vega:,.0f}) breaches limit (±${max_vega:,.0f})")
        if abs(proj_theta) > max_theta:
            rejections.append(f"Projected Theta (${proj_theta:,.0f}) breaches limit (±${max_theta:,.0f})")

        # 5. Stress Scenario Evaluation
        spot = float(market_health.get("spot_price", 65000.0))
        existing_positions = portfolio.get("positions", [])
        combined_positions = list(existing_positions)

        # Add proposed trade as temporary position for stress
        direction = proposed_action.get("direction", "buy")
        qty = float(proposed_action.get("quantity", 1.0)) * (1.0 if direction == "buy" else -1.0)
        combined_positions.append({
            "strike": proposed_action.get("strike", spot),
            "expiry_years": proposed_action.get("expiry_years", 30/365),
            "option_type": proposed_action.get("option_type", "call"),
            "quantity": qty,
            "implied_vol": proposed_action.get("implied_volatility", 0.55),
            "mark_price": proposed_action.get("order_price", 0.0)
        })

        stress_res = self.stress_engine.evaluate_portfolio(combined_positions, spot)
        max_stress_loss = stress_res["max_loss"]
        max_allowed_loss = limits.get("max_loss", 50000.0)

        if max_stress_loss > max_allowed_loss:
            rejections.append(f"Worst-case stress loss (${max_stress_loss:,.0f}) exceeds risk limit (${max_allowed_loss:,.0f})")

        is_approved = len(rejections) == 0

        return RiskCheckResult(
            is_approved=is_approved,
            rejections=rejections,
            warnings=warnings,
            post_trade_greeks={
                "delta": round(proj_delta, 4),
                "gamma": round(proj_gamma, 6),
                "vega": round(proj_vega, 2),
                "theta": round(proj_theta, 2),
                "margin": round(projected_margin, 2)
            },
            limit_utilization={
                "delta": round(delta_util, 3),
                "gamma": round(gamma_util, 3),
                "vega": round(vega_util, 3),
                "theta": round(theta_util, 3),
                "margin": round(margin_util, 3)
            },
            stress_results=stress_res
        )

    def calculate_portfolio_risk(
        self,
        positions: List[Dict[str, Any]],
        spot: float,
        total_capital: float,
        limits: Dict[str, float],
        r: float = 0.0
    ) -> Dict[str, Any]:
        total_delta = 0.0
        total_gamma = 0.0
        total_vega = 0.0
        total_theta = 0.0
        used_margin = 0.0
        unrealized_pnl = 0.0

        for pos in positions:
            total_delta += float(pos.get("delta", 0.0))
            total_gamma += float(pos.get("gamma", 0.0))
            total_vega += float(pos.get("vega", 0.0))
            total_theta += float(pos.get("theta", 0.0))
            used_margin += float(pos.get("margin", 0.0))
            unrealized_pnl += float(pos.get("unrealized_pnl", 0.0))

        stress_res = self.stress_engine.evaluate_portfolio(positions, spot, r=r)
        var_res = self.var_engine.calculate_var(positions, spot, spot_vol=0.55)

        max_delta = limits.get("max_delta", 5.0)
        max_vega = limits.get("max_vega", 50000.0)
        margin_limit = limits.get("margin_utilization", 0.70)

        return {
            "total_capital": total_capital,
            "used_margin": round(used_margin, 2),
            "available_capital": round(max(0.0, total_capital - used_margin), 2),
            "margin_utilization": round(used_margin / total_capital if total_capital > 0 else 0.0, 4),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "greeks": {
                "delta": round(total_delta, 4),
                "gamma": round(total_gamma, 6),
                "vega": round(total_vega, 2),
                "theta": round(total_theta, 2)
            },
            "utilization": {
                "delta": round(abs(total_delta) / max_delta if max_delta > 0 else 0.0, 3),
                "vega": round(abs(total_vega) / max_vega if max_vega > 0 else 0.0, 3),
                "margin": round((used_margin / total_capital) / margin_limit if total_capital > 0 and margin_limit > 0 else 0.0, 3)
            },
            "stress": stress_res,
            "var": var_res
        }
