import json
import duckdb
from typing import Dict, Any, List, Optional
import pyarrow.parquet as pq
from db.database import SessionLocal
from db.models import MarketEvent, QuoteSnapshot, Instrument

class ReplayEngine:
    def __init__(self, parquet_path: Optional[str] = None, underlying: str = "BTC"):
        if parquet_path:
            self.parquet_path = parquet_path
        elif underlying.upper() == "ETH":
            self.parquet_path = "data/samples/eth_options_sample.parquet"
        else:
            self.parquet_path = "data/samples/btc_options_sample.parquet"
        self.underlying = underlying.upper()
        self.cursor = 0
        self._table = None
        self._duckdb_conn = None

    def initialize(self):
        if not self._table:
            self._table = pq.read_table(self.parquet_path)
            self._duckdb_conn = duckdb.connect(":memory:")
            self._duckdb_conn.register("market_events", self._table)

    def total_events(self) -> int:
        self.initialize()
        return len(self._table)

    def query(self, query_str: str) -> List[Dict[str, Any]]:
        self.initialize()
        df = self._duckdb_conn.execute(query_str).fetchdf()
        return df.to_dict(orient="records")

    def get_batch(self, batch_size: int = 50) -> List[Dict[str, Any]]:
        self.initialize()
        end_idx = min(self.cursor + batch_size, len(self._table))
        sliced = self._table.slice(self.cursor, end_idx - self.cursor)
        self.cursor = end_idx
        df = sliced.to_pandas()
        return df.to_dict(orient="records")

    def reset(self):
        self.cursor = 0

    def replay_tick_to_db(self, db_session=None) -> Optional[Dict[str, Any]]:
        batch = self.get_batch(1)
        if not batch:
            return None
        event_dict = batch[0]

        should_close = False
        if db_session is None:
            db_session = SessionLocal()
            should_close = True

        try:
            m_event = MarketEvent(
                id=event_dict["event_id"],
                venue_id="deribit",
                event_type=event_dict["event_type"],
                raw_payload_json=json.dumps(event_dict),
                is_replayed=True
            )
            db_session.merge(m_event)

            inst_symbol = event_dict["instrument_name"]
            inst = db_session.query(Instrument).filter_by(symbol=inst_symbol).first()
            if inst:
                q_snap = QuoteSnapshot(
                    id=f"qs_{event_dict['event_id']}",
                    instrument_id=inst.id,
                    market_event_id=m_event.id,
                    best_bid_price=event_dict["best_bid_price"],
                    best_bid_amount=event_dict["best_bid_amount"],
                    best_ask_price=event_dict["best_ask_price"],
                    best_ask_amount=event_dict["best_ask_amount"],
                    mark_price=event_dict["mark_price"],
                    underlying_price=event_dict["underlying_price"],
                    implied_volatility=event_dict["implied_volatility"],
                    delta=event_dict["delta"],
                    vega=event_dict["vega"]
                )
                db_session.merge(q_snap)

            db_session.commit()
            return event_dict
        except Exception:
            db_session.rollback()
            raise
        finally:
            if should_close:
                db_session.close()
