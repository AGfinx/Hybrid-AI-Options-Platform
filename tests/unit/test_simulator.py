import uuid
import pytest
from services.simulator.engine import PaperTradingSimulator
from db.database import SessionLocal, init_db
from db.models import PaperOrder, Instrument, QuoteSnapshot

def test_paper_trading_execution_and_attribution():
    init_db()
    db = SessionLocal()
    sim = PaperTradingSimulator()

    try:
        inst = db.query(Instrument).first()
        assert inst is not None

        order_id = f"test_order_{uuid.uuid4().hex[:8]}"
        order = PaperOrder(
            id=order_id,
            instrument_id=inst.id,
            direction="buy",
            order_type="market",
            quantity=1.0,
            status="pending"
        )
        db.add(order)
        db.commit()

        res = sim.execute_order(order_id, db_session=db)
        assert res["status"] == "filled"
        assert res["fill_price"] > 0
        assert res["fee_paid"] > 0
        assert order.status == "filled"
    finally:
        db.close()
