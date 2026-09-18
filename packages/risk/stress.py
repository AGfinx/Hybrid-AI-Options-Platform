import math
from typing import Dict, Any, List
from packages.quant.black_scholes import bs_price

class StressScenarioEngine:
    """Evaluates portfolio and proposed trade under spot, vol, and combined shocks."""

    def __init__(self):
        self.spot_shocks = [-0.20, -0.10, -0.05, 0.0, 0.05, 0.10, 0.20]
        self.vol_shocks = [-0.15, -0.10, -0.05, 0.0, 0.05, 0.10, 0.15]

    def evaluate_portfolio(
        self,
        positions: List[Dict[str, Any]],
        spot: float,
        base_iv: float = 0.55,
        r: float = 0.0
    ) -> Dict[str, Any]:
        """Runs the 7x7 scenario matrix across all positions.
        Returns:
            grid: 2D array of P&L values
            max_loss: worst-case loss in the grid
            worst_scenario: (spot_shock, vol_shock) leading to worst loss
        """
        grid = []
        worst_pnl = 0.0
        worst_scenario = {"spot_shock": 0.0, "vol_shock": 0.0}

        for s_shock in self.spot_shocks:
            row = []
            new_s = max(100.0, spot * (1.0 + s_shock))

            for v_shock in self.vol_shocks:
                scenario_pnl = 0.0

                for pos in positions:
                    strike = float(pos.get("strike", spot))
                    T = max(0.0001, float(pos.get("expiry_years", 30/365)))
                    opt_type = pos.get("option_type", "call")
                    qty = float(pos.get("quantity", 0.0))
                    pos_iv = float(pos.get("implied_vol", base_iv))
                    mark_p = float(pos.get("mark_price", 0.0))

                    if mark_p <= 0:
                        mark_p = bs_price(spot, strike, T, r, pos_iv, opt_type)

                    new_iv = max(0.05, pos_iv + v_shock)
                    scen_p = bs_price(new_s, strike, T, r, new_iv, opt_type)

                    pos_pnl = (scen_p - mark_p) * qty
                    scenario_pnl += pos_pnl

                row.append(round(scenario_pnl, 2))
                if scenario_pnl < worst_pnl:
                    worst_pnl = scenario_pnl
                    worst_scenario = {"spot_shock": s_shock, "vol_shock": v_shock}

            grid.append(row)

        return {
            "spot_shocks": self.spot_shocks,
            "vol_shocks": self.vol_shocks,
            "scenario_grid": grid,
            "max_loss": round(abs(worst_pnl), 2),
            "worst_scenario": worst_scenario
        }
