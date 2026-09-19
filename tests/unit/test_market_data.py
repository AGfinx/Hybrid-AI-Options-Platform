import pytest
import time
from services.market_data.collector import DeribitMarketDataCollector

def test_collector_offline_health():
    """Verify collector operates in offline mode safely by default without network calls."""
    collector = DeribitMarketDataCollector(live_enabled=False)
    status = collector.get_health_status()
    
    assert status["venue"] == "deribit"
    assert status["live_feed_enabled"] is False
    assert status["sequence_status"] == "continuous"
    assert status["spot_price"] == 65000.0

def test_collector_sequence_gap_detection():
    """Verify sequence continuity monitor identifies dropped or out-of-order packets."""
    collector = DeribitMarketDataCollector(live_enabled=False)
    
    # Send continuous packet
    collector.record_event({"sequence_id": 100, "underlying_price": 65100.0})
    assert collector.sequence_gap_detected is False
    assert collector.spot_price == 65100.0

    collector.record_event({"sequence_id": 101, "underlying_price": 65120.0})
    assert collector.sequence_gap_detected is False

    # Skip sequence 102 and jump to 105
    collector.record_event({"sequence_id": 105, "underlying_price": 65150.0})
    assert collector.sequence_gap_detected is True
    
    status = collector.get_health_status()
    assert status["sequence_status"] == "gap_detected"
    assert status["data_quality"] == "degraded"

def test_collector_stale_quote_detection():
    """Verify collector flags data as stale when events exceed freshness threshold."""
    collector = DeribitMarketDataCollector(live_enabled=False)
    collector.last_event_time = time.time() - 35.0  # 35 seconds ago
    
    status = collector.get_health_status()
    assert status["data_quality"] == "stale"
    assert status["quote_age_seconds"] >= 35.0
