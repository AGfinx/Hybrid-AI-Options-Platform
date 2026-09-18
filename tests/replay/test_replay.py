import pytest
from services.replay.engine import ReplayEngine
from db.database import SessionLocal, init_db

def test_deterministic_replay():
    init_db()
    db = SessionLocal()
    replay = ReplayEngine()

    try:
        assert replay.total_events() > 0

        # Query DuckDB
        btc_quotes = replay.query("SELECT COUNT(*) as cnt FROM market_events WHERE underlying = 'BTC'")
        assert btc_quotes[0]["cnt"] > 0

        # Step 5 ticks to DB
        replay.reset()
        for _ in range(5):
            ev = replay.replay_tick_to_db(db_session=db)
            assert ev is not None
            assert ev["underlying"] == "BTC"
    finally:
        db.close()
