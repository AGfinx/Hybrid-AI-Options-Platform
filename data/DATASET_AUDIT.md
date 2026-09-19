# Dataset Audit Report: `btc_options_sample.parquet`

**Audit Date**: 2026-09-18 19:31:48 UTC  
**Target File**: `data/samples/btc_options_sample.parquet`  
**File Size**: 0.42 MB  

---

## 1. Executive Summary

| Metric | Value |
|---|---|
| **Total Observations (Rows)** | `11,200` |
| **Total Features (Columns)** | `14` |
| **Missing Values** | `0` |
| **Duplicate Records** | `0` |
| **Time Span** | `2026-09-18T10:00:00+00:00` to `2026-09-18T10:16:35+00:00` |
| **Duration** | `995 seconds` (~`16.6 minutes`) |
| **Discrete Timestamps** | `200` |
| **Sampling Interval** | `5.0 seconds` (High-frequency regular tick grid) |
| **Underlying Assets** | `BTC` |
| **Unique Instruments** | `56` |
| **Strike Count** | `7` strikes (`[55000.0, 60000.0, 62500.0, 65000.0, 67500.0, 70000.0, 75000.0]`) |
| **Expiry Count** | `4` expiries (`['02OCT26', '17NOV26', '18OCT26', '25SEP26']`) |
| **Bid / Ask Quotes** | `Yes` (`best_bid_price`, `best_ask_price`, quantities) |
| **Underlying Spot Price** | `Yes` (`underlying_price`) |
| **Implied Volatility (IV)** | `Yes` (`implied_volatility`) |
| **Greeks Included** | `delta, vega` |
| **Data Nature** | **SYNTHETIC** |
| **Density for Forecasting** | **Sufficient for high-frequency/tick forecasting; Insufficient for macro multi-day forecasting** |

---

## 2. Column Schema & Data Types

| Column Name | Data Type | Missing Count | Description |
|---|---|---|---|
| `event_id` | `str` | `0` | |
| `timestamp` | `str` | `0` | |
| `event_type` | `str` | `0` | |
| `instrument_name` | `str` | `0` | |
| `underlying` | `str` | `0` | |
| `underlying_price` | `float64` | `0` | |
| `best_bid_price` | `float64` | `0` | |
| `best_bid_amount` | `float64` | `0` | |
| `best_ask_price` | `float64` | `0` | |
| `best_ask_amount` | `float64` | `0` | |
| `mark_price` | `float64` | `0` | |
| `implied_volatility` | `float64` | `0` | |
| `delta` | `float64` | `0` | |
| `vega` | `float64` | `0` | |

---

## 3. Data Authenticity & Limitations

1. **Synthetic Nature**: The dataset is deterministically generated via geometric Brownian motion and Black-Scholes inversion (`services/replay/generator.py`). It is ideal for CI testing, offline replay, and architectural validation, but does not contain real market noise, microstructure jumps, or execution frictions.
2. **Horizon Constraint**: The total time window covers only **16.5 minutes** (200 snapshots at 5-second intervals). It is suitable for high-frequency tick returns and sequence models, but cannot train multi-week realized volatility dynamics.
3. **Missing Greeks**: Only `delta` and `vega` are explicitly serialized; `gamma`, `theta`, and `rho` must be derived dynamically via the quantitative pricer.
4. **Preservation**: This file (`data/samples/btc_options_sample.parquet`) is strictly preserved for Milestone 1 replay and regression testing.

---

## 4. Recommendations for Machine Learning

- **Feature Engineering**: Compute spot log returns, rolling Parkinson/realized volatility, moneyness $M = \ln(K/S)$, and relative bid-ask spreads directly from available columns.
- **Time-Series Splitting**: Enforce strict chronological order (70% train, 15% val, 15% test) across the 200 time steps. **Never randomly shuffle**.
- **Model Training**: Use this dataset to establish pipeline invariants, unit test deep sequence models (LSTM/GRU), and train physics-informed neural surfaces (HyperIV/PINN). Real multi-month Deribit historical data should be ingested into `data/historical/` once acquired.
