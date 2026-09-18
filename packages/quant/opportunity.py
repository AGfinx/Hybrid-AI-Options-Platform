import datetime
import math
from typing import Dict, Any, List, Optional
from packages.quant.black_scholes import bs_price, bs_greeks
from packages.quant.surface import VolatilitySurface

class OpportunityCalculator:
    def __init__(
        self,
        fee_rate: float = 0.0003,      # 3 bps of underlying
        slippage_rate: float = 0.0002,  # 2 bps
        hedge_cost_rate: float = 0.0002,# 2 bps rehedge cost
        funding_rate: float = 0.0001,   # 1 bp carry
        min_edge_threshold: float = 0.015 # 1.5% net vol edge minimum
    ):
        self.fee_rate = fee_rate
        self.slippage_rate = slippage_rate
        self.hedge_cost_rate = hedge_cost_rate
        self.funding_rate = funding_rate
        self.min_edge_threshold = min_edge_threshold

    def evaluate_opportunity(
        self,
        underlying: str,
        spot: float,
        strike: float,
        expiry_years: float,
        option_type: str,
        best_bid: float,
        best_ask: float,
        implied_vol: float,
        forecast_vol: float,
        uncertainty: float,
        surface_confidence: float = 1.0,
        surface_status: str = "valid",
        quantity: float = 1.0
    ) -> Optional[Dict[str, Any]]:
        # Fail early if data or surface is invalid
        if surface_status != "valid" or surface_confidence < 0.5:
            return None

        if best_bid <= 0 or best_ask <= best_bid or spot <= 0 or expiry_years <= 0:
            return None

        mid_price = (best_bid + best_ask) / 2.0
        spread = best_ask - best_bid
        spread_cost_vol = (spread / spot) / (math.sqrt(expiry_years) + 1e-4)

        # Volatility difference
        gross_vol_diff = forecast_vol - implied_vol
        abs_gross_edge = abs(gross_vol_diff)

        # Direction: if forecast > IV, we buy options (long vol). If IV > forecast, we sell options (short vol)
        if gross_vol_diff > 0:
            direction = "buy"
            order_price = best_ask
            strategy_name = f"long_vol_{option_type}"
        else:
            direction = "sell"
            order_price = best_bid
            strategy_name = f"short_vol_{option_type}"

        # Drag components (in volatility points equivalent)
        spread_drag = spread_cost_vol * 0.5
        fee_drag = (self.fee_rate * spot / mid_price) * 0.01 if mid_price > 0 else 0.002
        fee_drag = max(0.001, min(0.03, fee_drag))
        slippage_drag = self.slippage_rate * (1.0 + 0.1 * quantity)
        hedge_drag = self.hedge_cost_rate * (1.0 + 10.0 * abs(0.5 - (strike / spot)))
        carry_drag = self.funding_rate * expiry_years * 365.0
        uncertainty_penalty = (uncertainty * 0.5) + (1.0 - surface_confidence) * 0.05

        total_drag = (
            spread_drag +
            fee_drag +
            slippage_drag +
            hedge_drag +
            carry_drag +
            uncertainty_penalty
        )

        net_edge = abs_gross_edge - total_drag

        # Filter below threshold
        if net_edge < self.min_edge_threshold:
            return None

        # Compute Greeks
        greeks = bs_greeks(spot, strike, expiry_years, 0.0, implied_vol, option_type)
        mult = 1.0 if direction == "buy" else -1.0
        delta = greeks["delta"] * quantity * mult
        gamma = greeks["gamma"] * quantity * mult
        vega = greeks["vega"] * quantity * mult
        theta = greeks["theta"] * quantity * mult

        # Approximate margin and stress max loss
        # Reg-T / crypto exchange standard: premium + 15% of spot - OTM amount (min 10% of spot)
        otm_amount = max(0.0, (strike - spot) if option_type == "call" else (spot - strike))
        initial_margin = max(order_price * quantity, (order_price + max(0.10 * spot, 0.15 * spot - otm_amount)) * quantity) if direction == "sell" else order_price * quantity

        # Stress test scenario (±20% spot, ±15% vol)
        stress_loss = self._calculate_stress_max_loss(
            spot, strike, expiry_years, option_type, implied_vol, direction, quantity
        )

        rationale = (
            f"Forecast vol ({forecast_vol:.1%}) diverges from market IV ({implied_vol:.1%}) "
            f"with gross edge of {abs_gross_edge:.2%}. After accounting for spread ({spread_drag:.2%}), "
            f"fees ({fee_drag:.2%}), slippage ({slippage_drag:.2%}), hedging ({hedge_drag:.2%}), "
            f"and uncertainty penalty ({uncertainty_penalty:.2%}), expected net edge is {net_edge:.2%}."
        )

        expiry_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=30)

        return {
            "underlying": underlying,
            "strategy_type": strategy_name,
            "direction": direction,
            "option_type": option_type,
            "strike": strike,
            "expiry_years": expiry_years,
            "quantity": quantity,
            "order_price": round(order_price, 2),
            "implied_volatility": round(implied_vol, 4),
            "forecast_volatility": round(forecast_vol, 4),
            "gross_edge": round(abs_gross_edge, 4),
            "net_edge": round(net_edge, 4),
            "spread_cost": round(spread_drag, 4),
            "fee_cost": round(fee_drag, 4),
            "slippage_cost": round(slippage_drag, 4),
            "hedge_cost": round(hedge_drag, 4),
            "carry_cost": round(carry_drag, 4),
            "uncertainty_penalty": round(uncertainty_penalty, 4),
            "delta": round(delta, 4),
            "gamma": round(gamma, 6),
            "vega": round(vega, 2),
            "theta": round(theta, 2),
            "initial_margin": round(initial_margin, 2),
            "stress_max_loss": round(stress_loss, 2),
            "confidence": round(surface_confidence * (1.0 - min(0.5, uncertainty)), 3),
            "rationale": rationale,
            "expiry_at": expiry_at.isoformat()
        }

    def _calculate_stress_max_loss(
        self,
        spot: float,
        strike: float,
        T: float,
        option_type: str,
        base_iv: float,
        direction: str,
        qty: float
    ) -> float:
        base_p = bs_price(spot, strike, T, 0.0, base_iv, option_type)
        worst_loss = 0.0
        mult = 1.0 if direction == "buy" else -1.0

        for spot_shock in [-0.20, -0.10, 0.0, 0.10, 0.20]:
            for vol_shock in [-0.15, -0.05, 0.0, 0.05, 0.15]:
                new_s = max(100.0, spot * (1.0 + spot_shock))
                new_iv = max(0.05, base_iv + vol_shock)
                scen_p = bs_price(new_s, strike, T, 0.0, new_iv, option_type)
                pnl = (scen_p - base_p) * mult * qty
                if pnl < 0:
                    worst_loss = max(worst_loss, abs(pnl))

        return worst_loss

    def evaluate_straddle(
        self,
        underlying: str,
        spot: float,
        strike: float,
        expiry_years: float,
        call_quote: Dict[str, Any],
        put_quote: Dict[str, Any],
        forecast_vol: float,
        uncertainty: float,
        quantity: float = 1.0
    ) -> Optional[Dict[str, Any]]:
        call_bid = float(call_quote.get("best_bid_price", 0) or 0)
        call_ask = float(call_quote.get("best_ask_price", 0) or 0)
        put_bid = float(put_quote.get("best_bid_price", 0) or 0)
        put_ask = float(put_quote.get("best_ask_price", 0) or 0)

        call_iv = float(call_quote.get("implied_vol", 0.55))
        put_iv = float(put_quote.get("implied_vol", 0.55))
        avg_iv = (call_iv + put_iv) / 2.0

        if call_ask <= 0 or put_ask <= 0 or spot <= 0 or expiry_years <= 0:
            return None

        gross_edge = forecast_vol - avg_iv
        if gross_edge < self.min_edge_threshold:
            return None  # Only recommend straddle when forecast vol exceeds market IV

        # Drag: combined call + put spread and fees
        call_spread = call_ask - call_bid
        put_spread = put_ask - put_bid
        spread_drag = ((call_spread + put_spread) / spot) / (math.sqrt(expiry_years) + 1e-4) * 0.4
        fee_drag = self.fee_rate * 2.0
        slippage_drag = self.slippage_rate * 1.5 * (1.0 + 0.1 * quantity)
        hedge_drag = self.hedge_cost_rate * 0.5  # straddle is intrinsically delta-neutral
        uncertainty_penalty = uncertainty * 0.5

        total_drag = spread_drag + fee_drag + slippage_drag + hedge_drag + uncertainty_penalty
        net_edge = gross_edge - total_drag

        if net_edge < self.min_edge_threshold:
            return None

        call_greeks = bs_greeks(spot, strike, expiry_years, 0.0, call_iv, "call")
        put_greeks = bs_greeks(spot, strike, expiry_years, 0.0, put_iv, "put")

        net_delta = round((call_greeks["delta"] + put_greeks["delta"]) * quantity, 4)
        net_gamma = round((call_greeks["gamma"] + put_greeks["gamma"]) * quantity, 6)
        net_vega = round((call_greeks["vega"] + put_greeks["vega"]) * quantity, 2)
        net_theta = round((call_greeks["theta"] + put_greeks["theta"]) * quantity, 2)

        total_cost = (call_ask + put_ask) * quantity

        legs = [
            {
                "instrument_id": call_quote.get("instrument_id", f"inst_{underlying.lower()}_c"),
                "symbol": call_quote.get("symbol", f"{underlying}-CALL-{int(strike)}"),
                "direction": "buy",
                "option_type": "call",
                "strike": strike,
                "expiry_years": expiry_years,
                "order_price": call_ask,
                "quantity": quantity
            },
            {
                "instrument_id": put_quote.get("instrument_id", f"inst_{underlying.lower()}_p"),
                "symbol": put_quote.get("symbol", f"{underlying}-PUT-{int(strike)}"),
                "direction": "buy",
                "option_type": "put",
                "strike": strike,
                "expiry_years": expiry_years,
                "order_price": put_ask,
                "quantity": quantity
            }
        ]

        # Straddle max loss is the total premium paid
        stress_loss = total_cost

        rationale = (
            f"Pure delta-neutral volatility play. Forecast vol ({forecast_vol:.1%}) exceeds market IV ({avg_iv:.1%}) "
            f"by {gross_edge:.2%}. Combined Net Edge is +{net_edge:.2%} with initial delta of {net_delta:+.3f}."
        )

        expiry_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=30)

        return {
            "underlying": underlying,
            "strategy_type": "long_straddle_delta_neutral",
            "legs": legs,
            "order_price": round(call_ask + put_ask, 2),
            "implied_volatility": round(avg_iv, 4),
            "forecast_volatility": round(forecast_vol, 4),
            "gross_edge": round(gross_edge, 4),
            "net_edge": round(net_edge, 4),
            "spread_cost": round(spread_drag, 4),
            "fee_cost": round(fee_drag, 4),
            "slippage_cost": round(slippage_drag, 4),
            "hedge_cost": round(hedge_drag, 4),
            "carry_cost": 0.0,
            "uncertainty_penalty": round(uncertainty_penalty, 4),
            "delta": net_delta,
            "gamma": net_gamma,
            "vega": net_vega,
            "theta": net_theta,
            "initial_margin": round(total_cost, 2),
            "stress_max_loss": round(stress_loss, 2),
            "confidence": 0.92,
            "rationale": rationale,
            "expiry_at": expiry_at.isoformat()
        }

    def evaluate_calendar_spread(
        self,
        underlying: str,
        spot: float,
        strike: float,
        near_quote: Dict[str, Any],
        far_quote: Dict[str, Any],
        forecast_vol: float,
        uncertainty: float,
        quantity: float = 1.0
    ) -> Optional[Dict[str, Any]]:
        near_bid = float(near_quote.get("best_bid_price", 0) or 0)
        far_ask = float(far_quote.get("best_ask_price", 0) or 0)
        T_near = float(near_quote.get("T", 7/365))
        T_far = float(far_quote.get("T", 30/365))

        near_iv = float(near_quote.get("implied_vol", 0.55))
        far_iv = float(far_quote.get("implied_vol", 0.50))

        if near_bid <= 0 or far_ask <= 0 or T_far <= T_near:
            return None

        # Term structure edge: sell rich near-term vol, buy cheap far-term vol
        vol_skew_edge = near_iv - far_iv
        if vol_skew_edge < 0.02:
            return None

        drag = self.fee_rate * 2.0 + self.slippage_rate * 2.0 + uncertainty * 0.3
        net_edge = vol_skew_edge - drag
        if net_edge < self.min_edge_threshold:
            return None

        near_g = bs_greeks(spot, strike, T_near, 0.0, near_iv, "call")
        far_g = bs_greeks(spot, strike, T_far, 0.0, far_iv, "call")

        net_delta = round((far_g["delta"] - near_g["delta"]) * quantity, 4)
        net_gamma = round((far_g["gamma"] - near_g["gamma"]) * quantity, 6)
        net_vega = round((far_g["vega"] - near_g["vega"]) * quantity, 2)
        net_theta = round((far_g["theta"] - near_g["theta"]) * quantity, 2)

        net_debit = max(10.0, (far_ask - near_bid) * quantity)

        legs = [
            {
                "instrument_id": near_quote.get("instrument_id", "inst_near"),
                "symbol": near_quote.get("symbol", f"{underlying}-NEAR-{int(strike)}"),
                "direction": "sell",
                "option_type": "call",
                "strike": strike,
                "expiry_years": T_near,
                "order_price": near_bid,
                "quantity": quantity
            },
            {
                "instrument_id": far_quote.get("instrument_id", "inst_far"),
                "symbol": far_quote.get("symbol", f"{underlying}-FAR-{int(strike)}"),
                "direction": "buy",
                "option_type": "call",
                "strike": strike,
                "expiry_years": T_far,
                "order_price": far_ask,
                "quantity": quantity
            }
        ]

        rationale = (
            f"Calendar Term-Structure Arbitrage: Short near tenor ({round(T_near*365)}d) at IV {near_iv:.1%}, "
            f"Long far tenor ({round(T_far*365)}d) at IV {far_iv:.1%}. Positive theta decay with vega convexity."
        )

        expiry_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=30)

        return {
            "underlying": underlying,
            "strategy_type": "vol_calendar_spread",
            "legs": legs,
            "order_price": round(far_ask - near_bid, 2),
            "implied_volatility": round((near_iv + far_iv) / 2.0, 4),
            "forecast_volatility": round(forecast_vol, 4),
            "gross_edge": round(vol_skew_edge, 4),
            "net_edge": round(net_edge, 4),
            "spread_cost": round(self.slippage_rate * 2.0, 4),
            "fee_cost": round(self.fee_rate * 2.0, 4),
            "slippage_cost": round(self.slippage_rate, 4),
            "hedge_cost": 0.0,
            "carry_cost": 0.0,
            "uncertainty_penalty": round(uncertainty * 0.3, 4),
            "delta": net_delta,
            "gamma": net_gamma,
            "vega": net_vega,
            "theta": net_theta,
            "initial_margin": round(net_debit * 1.5, 2),
            "stress_max_loss": round(net_debit, 2),
            "confidence": 0.90,
            "rationale": rationale,
            "expiry_at": expiry_at.isoformat()
        }
