import math
from typing import Dict, Any, List, Optional
import numpy as np

class PortfolioVaREngine:
    """Computes 1-day Value-at-Risk (VaR 95%, 99%) and Expected Shortfall (CVaR)."""

    def __init__(self, trading_days_per_year: int = 365, num_simulations: int = 10000, seed: int = 42):
        self.dt = 1.0 / trading_days_per_year
        self.sqrt_dt = math.sqrt(self.dt)
        self.default_simulations = num_simulations
        self.seed = seed

    def calculate_var(
        self,
        positions: List[Dict[str, Any]],
        spot: float,
        spot_vol: float = 0.55,
        num_simulations: Optional[int] = None
    ) -> Dict[str, Any]:
        n_sim = num_simulations or self.default_simulations
        if not positions or spot <= 0:
            return {
                "var_95_1d": 0.0,
                "var_99_1d": 0.0,
                "cvar_99_1d": 0.0,
                "var_95": 0.0,
                "var_99": 0.0,
                "cvar_99": 0.0,
                "percentile_breakdown": {"p95": 0.0, "p99": 0.0, "p99_9": 0.0},
                "portfolio_daily_vol": 0.0,
                "method": "delta_gamma_monte_carlo",
                "simulations": n_sim,
                "simulated_paths": n_sim
            }

        # Aggregate portfolio sensitivities
        total_delta = sum(float(p.get("delta", 0.0)) for p in positions)
        total_gamma = sum(float(p.get("gamma", 0.0)) for p in positions)
        total_vega = sum(float(p.get("vega", 0.0)) for p in positions)
        total_theta = sum(float(p.get("theta", 0.0)) for p in positions)

        # 1-day standard deviation of underlying asset return
        daily_spot_vol = spot_vol * self.sqrt_dt
        daily_vol_vol = 0.80 * self.sqrt_dt  # vol-of-vol assumption ~80% annualized

        # Monte Carlo simulation of joint spot and vol shocks with negative correlation (leverage effect ~ -0.4)
        np.random.seed(self.seed)
        cov = np.array([[1.0, -0.4], [-0.4, 1.0]])
        shocks = np.random.multivariate_normal([0.0, 0.0], cov, size=n_sim)

        spot_returns = shocks[:, 0] * daily_spot_vol
        vol_changes = shocks[:, 1] * daily_vol_vol * 100.0  # in vol percentage points

        # Delta-Gamma-Vega-Theta Taylor expansion P&L approximation:
        # PnL = Delta * dS + 0.5 * Gamma * (dS)^2 + Vega * dVol + Theta * dt
        dS = spot * spot_returns
        simulated_pnl = (
            total_delta * dS +
            0.5 * total_gamma * (dS ** 2) +
            total_vega * vol_changes +
            total_theta * self.dt
        )

        # Losses are negative P&L
        losses = -simulated_pnl

        # 95% and 99% quantiles
        var_95 = float(np.percentile(losses, 95))
        var_99 = float(np.percentile(losses, 99))

        # Expected Shortfall (CVaR 99%): mean of losses exceeding 99th percentile
        tail_losses = losses[losses >= var_99]
        cvar_99 = float(np.mean(tail_losses)) if len(tail_losses) > 0 else var_99

        portfolio_daily_std = float(np.std(simulated_pnl))

        return {
            "var_95_1d": round(max(0.0, var_95), 2),
            "var_99_1d": round(max(0.0, var_99), 2),
            "cvar_99_1d": round(max(0.0, cvar_99), 2),
            "var_95": round(max(0.0, var_95), 2),
            "var_99": round(max(0.0, var_99), 2),
            "cvar_99": round(max(0.0, cvar_99), 2),
            "percentile_breakdown": {
                "p95": round(max(0.0, var_95), 2),
                "p99": round(max(0.0, var_99), 2),
                "p99_9": round(max(0.0, float(np.percentile(losses, 99.9))), 2)
            },
            "portfolio_daily_vol": round(portfolio_daily_std, 2),
            "method": "delta_gamma_monte_carlo",
            "simulations": n_sim,
            "simulated_paths": n_sim
        }
