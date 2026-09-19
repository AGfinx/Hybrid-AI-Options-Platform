# Historical Data Directory

This directory is reserved for **real historical market data** from Deribit or other exchanges.

## Current Status

**No real historical data is currently available.**

The existing `data/samples/` directory contains **synthetic data only** generated for:
- Deterministic replay testing
- Integration testing
- Regression testing
- Development without external network dependencies

## Data Requirements

To populate this directory with real data, you would need:

1. **Deribit historical data subscription** or access to their historical API
2. **Data collection pipeline** that:
   - Fetches option chain snapshots at regular intervals
   - Stores raw WebSocket messages for reproducibility
   - Normalizes and validates quote quality
   - Handles sequence gaps and reconnections
3. **Sufficient time span** for ML training:
   - Minimum: 3-6 months for basic volatility modeling
   - Recommended: 12+ months for regime-aware models
   - Multiple market regimes (low vol, high vol, crash, recovery)

## Expected Schema

Real historical data should match or extend the synthetic schema:

```python
{
    "event_id": str,           # Unique event identifier
    "timestamp": datetime,     # UTC timestamp
    "event_type": str,         # "quote", "trade", "ticker"
    "instrument_name": str,    # e.g., "BTC-25SEP26-65000-C"
    "underlying": str,         # "BTC" or "ETH"
    "underlying_price": float, # Spot price
    "best_bid_price": float,
    "best_bid_amount": float,
    "best_ask_price": float,
    "best_ask_amount": float,
    "mark_price": float,
    "implied_volatility": float,
    "delta": float,
    "vega": float,
    # Additional fields for real data:
    "gamma": float,
    "theta": float,
    "rho": float,
    "open_interest": float,
    "volume_24h": float,
    "mark_iv": float,
    "bid_iv": float,
    "ask_iv": float,
}
```

## Usage

Once populated, this data would be used for:
- Training ML models (RV forecasting, HyperIV)
- Backtesting strategies
- Stress testing with real market events
- Model validation across regimes

**Do not commit real historical data to git.** Use DVC, cloud storage, or local-only paths.