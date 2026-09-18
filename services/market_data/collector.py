import os
import json
import time
import datetime
import asyncio
import logging
from typing import Dict, Any, Optional, Callable
import httpx

logger = logging.getLogger("market_data_collector")

class DeribitMarketDataCollector:
    """Public Deribit market data adapter with safety gates and heartbeat management."""

    def __init__(
        self,
        live_enabled: bool = False,
        ws_url: str = "wss://www.deribit.com/ws/api/v2",
        http_url: str = "https://www.deribit.com/api/v2"
    ):
        self.live_enabled = live_enabled or os.getenv("DERIBIT_LIVE_ENABLED", "false").lower() == "true"
        self.ws_url = ws_url
        self.http_url = http_url
        self.is_running = False
        self.is_connected = False
        self.last_event_time = time.time()
        self.last_sequence_id = 0
        self.sequence_gap_detected = False
        self.spot_price = 65000.0
        self.on_event_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self._backoff_seconds = 1.0

    async def fetch_instruments(self, currency: str = "BTC") -> list:
        """Fetch active public option instruments via public REST API."""
        if not self.live_enabled:
            return []

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self.http_url}/public/get_instruments",
                params={"currency": currency, "kind": "option", "expired": "false"}
            )
            data = resp.json()
            return data.get("result", [])

    def record_event(self, event_data: Dict[str, Any]):
        """Records an incoming market event and tracks sequence continuity and freshness."""
        now = time.time()
        self.last_event_time = now
        seq = event_data.get("sequence_id")
        if seq is not None:
            if self.last_sequence_id > 0 and seq > self.last_sequence_id + 1:
                self.sequence_gap_detected = True
                logger.warning(f"Sequence gap detected: expected {self.last_sequence_id + 1}, received {seq}")
            self.last_sequence_id = seq

        if "underlying_price" in event_data:
            self.spot_price = float(event_data["underlying_price"])

        if self.on_event_callback:
            try:
                self.on_event_callback(event_data)
            except Exception as e:
                logger.error(f"Error in on_event_callback: {e}")

    def get_health_status(self) -> Dict[str, Any]:
        """Calculates connection state, quote age freshness, and sequence integrity."""
        now = time.time()
        quote_age = round(now - self.last_event_time, 2)
        quality = "healthy"
        if quote_age > 30.0:
            quality = "stale"
        elif self.sequence_gap_detected:
            quality = "degraded"

        return {
            "venue": "deribit",
            "is_connected": self.is_connected or not self.live_enabled, # In offline mode, consider operational
            "live_feed_enabled": self.live_enabled,
            "last_event_time": datetime.datetime.fromtimestamp(self.last_event_time, tz=datetime.timezone.utc).isoformat(),
            "quote_age_seconds": quote_age,
            "sequence_status": "gap_detected" if self.sequence_gap_detected else "continuous",
            "data_quality": quality,
            "spot_price": self.spot_price
        }

    async def start(self):
        """Starts connection worker if live enabled, otherwise mock monitor."""
        self.is_running = True
        if not self.live_enabled:
            logger.info("Deribit live market data disabled. Operating in deterministic offline mode.")
            self.is_connected = True
            return

        while self.is_running:
            try:
                import websockets
                logger.info(f"Connecting to Deribit public WebSocket: {self.ws_url}")
                async with websockets.connect(self.ws_url, ping_interval=20, ping_timeout=10) as ws:
                    self.is_connected = True
                    self._backoff_seconds = 1.0
                    logger.info("Connected to Deribit public WebSocket successfully.")

                    # Subscribe to public BTC ticker channels
                    sub_msg = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "public/subscribe",
                        "params": {
                            "channels": ["ticker.BTC-*.100ms", "trades.BTC-any.raw"]
                        }
                    }
                    await ws.send(json.dumps(sub_msg))

                    while self.is_running:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        self.record_event(data)
            except Exception as e:
                self.is_connected = False
                logger.warning(f"Deribit WebSocket disconnected ({e}). Reconnecting in {self._backoff_seconds}s...")
                await asyncio.sleep(self._backoff_seconds)
                self._backoff_seconds = min(30.0, self._backoff_seconds * 2.0)

    def stop(self):
        self.is_running = False
        self.is_connected = False
