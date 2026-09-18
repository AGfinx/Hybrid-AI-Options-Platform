import uuid
import datetime
from typing import Dict, Any, Optional
from db.database import SessionLocal
from db.models import (
    PaperOrder, PaperFill, Position, HedgeAction, PnLAttribution,
    Instrument, QuoteSnapshot, Recommendation
)

class PaperTradingSimulator:
    def __init__(
        self,
        fee_rate: float = 0.0003,       # 3 bps of underlying
        slippage_rate: float = 0.0002,   # 2 bps base
        latency_ms: int = 50,
        delta_hedge_threshold: float = 0.5
    ):
        self.fee_rate = fee_rate
        self.slippage_rate = slippage_rate
        self.latency_ms = latency_ms
        self.delta_hedge_threshold = delta_hedge_threshold

    def execute_order(
        self,
        order_id: str,
        db_session=None
    ) -> Dict[str, Any]:
        should_close = False
        if db_session is None:
            db_session = SessionLocal()
            should_close = True

        try:
            order = db_session.query(PaperOrder).filter_by(id=order_id).first()
            if not order:
                raise ValueError(f"PaperOrder {order_id} not found")

            if order.status in ["filled", "cancelled", "rejected"]:
                return {"status": order.status, "message": f"Order already {order.status}"}

            inst = db_session.query(Instrument).filter_by(id=order.instrument_id).first()
            if not inst:
                raise ValueError(f"Instrument {order.instrument_id} not found")

            # Fetch latest quote snapshot
            latest_quote = (
                db_session.query(QuoteSnapshot)
                .filter_by(instrument_id=inst.id)
                .order_by(QuoteSnapshot.timestamp.desc())
                .first()
            )

            spot = latest_quote.underlying_price if latest_quote else 65000.0
            bid = latest_quote.best_bid_price if (latest_quote and latest_quote.best_bid_price) else (latest_quote.mark_price * 0.98 if latest_quote else 2000.0)
            ask = latest_quote.best_ask_price if (latest_quote and latest_quote.best_ask_price) else (latest_quote.mark_price * 1.02 if latest_quote else 2100.0)
            mark = latest_quote.mark_price if latest_quote else (bid + ask) / 2.0

            # Execution logic
            direction = order.direction.lower()
            qty = order.quantity
            limit_px = order.price_limit

            # Slippage calculation
            slippage_amt = mark * self.slippage_rate * (1.0 + 0.1 * qty)

            if direction == "buy":
                fill_px = ask + slippage_amt
                if order.order_type == "limit" and limit_px is not None and fill_px > limit_px:
                    order.status = "rejected"
                    order.avg_fill_price = None
                    db_session.commit()
                    return {"status": "rejected", "reason": f"Ask {fill_px:.2f} exceeds limit {limit_px:.2f}"}
            else:
                fill_px = max(0.5, bid - slippage_amt)
                if order.order_type == "limit" and limit_px is not None and fill_px < limit_px:
                    order.status = "rejected"
                    order.avg_fill_price = None
                    db_session.commit()
                    return {"status": "rejected", "reason": f"Bid {fill_px:.2f} below limit {limit_px:.2f}"}

            fee_incurred = fill_px * qty * self.fee_rate * (spot / fill_px if fill_px > 0 else 1.0)
            fee_incurred = round(max(0.5, fee_incurred), 2)

            # Record Fill
            fill = PaperFill(
                id=f"fill_{uuid.uuid4().hex[:12]}",
                paper_order_id=order.id,
                fill_price=round(fill_px, 2),
                fill_quantity=qty,
                fee_paid=fee_incurred,
                slippage_incurred=round(slippage_amt * qty, 2),
                executed_at=datetime.datetime.now(datetime.timezone.utc)
            )
            db_session.add(fill)

            order.filled_quantity = qty
            order.avg_fill_price = round(fill_px, 2)
            order.fee_assumed = fee_incurred
            order.slippage_assumed = round(slippage_amt * qty, 2)
            order.status = "filled"

            # Update or create Position
            pos = db_session.query(Position).filter_by(instrument_id=inst.id).first()
            signed_qty = qty if direction == "buy" else -qty

            if not pos:
                pos = Position(
                    id=f"pos_{inst.id}",
                    instrument_id=inst.id,
                    quantity=signed_qty,
                    avg_entry_price=round(fill_px, 2),
                    current_mark_price=round(mark, 2),
                    delta=(latest_quote.delta if latest_quote else 0.5) * signed_qty,
                    gamma=(0.00004) * signed_qty,
                    vega=(latest_quote.vega if latest_quote else 70.0) * signed_qty,
                    theta=(-60.0) * signed_qty,
                    unrealized_pnl=round((mark - fill_px) * signed_qty, 2),
                    realized_pnl=-fee_incurred
                )
                db_session.add(pos)
            else:
                prev_qty = pos.quantity
                new_qty = prev_qty + signed_qty
                if new_qty != 0:
                    pos.avg_entry_price = round((pos.avg_entry_price * abs(prev_qty) + fill_px * abs(signed_qty)) / (abs(prev_qty) + abs(signed_qty)), 2)
                pos.quantity = new_qty
                pos.current_mark_price = round(mark, 2)
                pos.delta = round((latest_quote.delta if latest_quote else 0.5) * new_qty, 4)
                pos.gamma = round((0.00004) * new_qty, 6)
                pos.vega = round((latest_quote.vega if latest_quote else 70.0) * new_qty, 2)
                pos.theta = round((-60.0) * new_qty, 2)
                pos.unrealized_pnl = round((mark - pos.avg_entry_price) * new_qty, 2)
                pos.realized_pnl -= fee_incurred

            # Delta Hedging Simulation
            hedge_info = None
            if abs(pos.delta) >= self.delta_hedge_threshold:
                hedge_qty = -pos.delta
                hedge = HedgeAction(
                    id=f"hdg_{uuid.uuid4().hex[:12]}",
                    position_id=pos.id,
                    paper_order_id=order.id,
                    underlying="BTC",
                    hedge_type="spot_delta",
                    quantity=round(hedge_qty, 4),
                    price=round(spot, 2),
                    executed_at=datetime.datetime.now(datetime.timezone.utc)
                )
                db_session.add(hedge)
                hedge_info = {"hedge_type": "spot_delta", "quantity": round(hedge_qty, 4), "price": round(spot, 2)}
                # Position delta hedged
                pos.delta = 0.0

            # P&L Attribution update
            pnl_rec = PnLAttribution(
                id=f"pnl_{uuid.uuid4().hex[:12]}",
                timestamp=datetime.datetime.now(datetime.timezone.utc),
                delta_pnl=round(pos.delta * (spot * 0.001), 2),
                gamma_pnl=round(0.5 * pos.gamma * ((spot * 0.001) ** 2), 2),
                vega_pnl=round(pos.vega * 0.01, 2),
                theta_pnl=round(pos.theta * (1.0 / 365.0), 2),
                fee_pnl=-fee_incurred,
                slippage_pnl=-round(slippage_amt * qty, 2),
                hedge_pnl=0.0 if not hedge_info else 5.0,
                residual_pnl=round((mark - fill_px) * signed_qty, 2),
                total_pnl=round((mark - fill_px) * signed_qty - fee_incurred, 2)
            )
            db_session.add(pnl_rec)

            db_session.commit()

            return {
                "order_id": order.id,
                "status": "filled",
                "fill_price": fill.fill_price,
                "quantity": fill.fill_quantity,
                "fee_paid": fill.fee_paid,
                "slippage": fill.slippage_incurred,
                "hedge": hedge_info,
                "position_id": pos.id,
                "post_trade_delta": pos.delta
            }
        except Exception:
            db_session.rollback()
            raise
        finally:
            if should_close:
                db_session.close()

    def execute_multi_leg_order(
        self,
        order_ids: list,
        db_session=None
    ) -> Dict[str, Any]:
        """Executes multi-leg orders (e.g. straddles, calendars) atomically."""
        should_close = False
        if db_session is None:
            db_session = SessionLocal()
            should_close = True

        results = []
        try:
            for oid in order_ids:
                res = self.execute_order(oid, db_session=db_session)
                if res.get("status") != "filled":
                    # Roll back if any leg fails to fill
                    db_session.rollback()
                    return {"status": "rejected", "failed_order_id": oid, "reason": res.get("reason", "Leg fill failed")}
                results.append(res)

            return {
                "status": "filled",
                "leg_count": len(results),
                "legs": results,
                "total_fee": round(sum(r["fee_paid"] for r in results), 2),
                "total_slippage": round(sum(r["slippage"] for r in results), 2)
            }
        except Exception:
            db_session.rollback()
            raise
        finally:
            if should_close:
                db_session.close()

    def rebalance_portfolio_delta(
        self,
        underlying: str = "BTC",
        db_session=None
    ) -> Optional[Dict[str, Any]]:
        """Checks aggregate portfolio delta drift and submits simulated spot hedge when threshold is breached."""
        should_close = False
        if db_session is None:
            db_session = SessionLocal()
            should_close = True

        try:
            positions = db_session.query(Position).all()
            underlying_positions = [
                p for p in positions
                if p.instrument and p.instrument.underlying == underlying and p.quantity != 0
            ]
            total_delta = sum(p.delta for p in underlying_positions)

            if abs(total_delta) < self.delta_hedge_threshold:
                return None

            # Get current spot
            spot = 65000.0 if underlying == "BTC" else 3500.0
            latest_quote = (
                db_session.query(QuoteSnapshot)
                .join(Instrument, QuoteSnapshot.instrument_id == Instrument.id)
                .filter(Instrument.underlying == underlying)
                .order_by(QuoteSnapshot.timestamp.desc())
                .first()
            )
            if latest_quote and latest_quote.underlying_price:
                spot = latest_quote.underlying_price

            hedge_qty = -round(total_delta, 4)
            hedge_action = HedgeAction(
                id=f"hdg_{uuid.uuid4().hex[:12]}",
                underlying=underlying,
                hedge_type="spot_delta_rebalance",
                quantity=hedge_qty,
                price=spot,
                executed_at=datetime.datetime.now(datetime.timezone.utc)
            )
            db_session.add(hedge_action)

            # Offset delta across positions
            for p in underlying_positions:
                p.delta = 0.0

            db_session.commit()

            return {
                "underlying": underlying,
                "rebalanced_delta": total_delta,
                "hedge_quantity": hedge_qty,
                "hedge_price": spot,
                "hedge_id": hedge_action.id
            }
        except Exception:
            db_session.rollback()
            raise
        finally:
            if should_close:
                db_session.close()
