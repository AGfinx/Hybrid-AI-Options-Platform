# Dataset Audit Report
Generated: 2026-09-19T04:59:30.162923+00:00

## Summary

### btc_options_sample.parquet
- **File size**: 441,628 bytes (0.42 MB)
- **Rows**: 11,200
- **Columns**: 14
- **Memory usage**: 1.91 MB
- **Duplicate rows**: 0

**Time Range**: 2026-09-18T10:00:00+00:00 to 2026-09-18T10:16:35+00:00
- Time span: 0.28 hours
- Unique timestamps: 200
- Avg interval: 5.00 seconds

**Strikes**: 7 unique (55000 to 75000)
- Source: parsed_from_instrument_name

**Expiries**: 4 unique expiry codes
- Codes: 02OCT26, 17NOV26, 18OCT26, 25SEP26
- Source: parsed_from_instrument_name

**Underlyings**: BTC

**Available Data Fields**:
- Bid/Ask: Yes
- Underlying spot price: Yes
- Implied volatility: Yes
- Greeks (delta, vega): Yes
- Volume (bid/ask amount): Yes
- Mark price: Yes

**Implied Volatility Stats**:
- Range: 0.5213 to 0.5875
- Mean: 0.5518, Std: 0.0161
- Negative IV count: 0

**Spot Price Range**: 64334.43 to 65221.13 (mean: 64611.25)

**Data Quality Issues**:
- Negative spreads: 0
- Zero/negative bids: 0
- Zero/negative asks: 0
- Missing values: 0 total across all columns

**Data Nature**: Likely Synthetic
- Detected patterns consistent with synthetic generation (regular timestamps, round strikes, parametric IV)

**Time-Series Forecasting Suitability**: Suitable
- 200 unique timestamps over 0.3 hours

**Column Details**:
- `event_id`: str (missing: 0)
- `timestamp`: str (missing: 0)
- `event_type`: str (missing: 0)
- `instrument_name`: str (missing: 0)
- `underlying`: str (missing: 0)
- `underlying_price`: float64 (missing: 0)
- `best_bid_price`: float64 (missing: 0)
- `best_bid_amount`: float64 (missing: 0)
- `best_ask_price`: float64 (missing: 0)
- `best_ask_amount`: float64 (missing: 0)
- `mark_price`: float64 (missing: 0)
- `implied_volatility`: float64 (missing: 0)
- `delta`: float64 (missing: 0)
- `vega`: float64 (missing: 0)

---

### eth_options_sample.parquet
- **File size**: 361,316 bytes (0.34 MB)
- **Rows**: 11,200
- **Columns**: 14
- **Memory usage**: 1.90 MB
- **Duplicate rows**: 0

**Time Range**: 2026-09-18T10:00:00+00:00 to 2026-09-18T10:16:35+00:00
- Time span: 0.28 hours
- Unique timestamps: 200
- Avg interval: 5.00 seconds

**Strikes**: 7 unique (2800 to 4200)
- Source: parsed_from_instrument_name

**Expiries**: 4 unique expiry codes
- Codes: 02OCT26, 17NOV26, 18OCT26, 25SEP26
- Source: parsed_from_instrument_name

**Underlyings**: ETH

**Available Data Fields**:
- Bid/Ask: Yes
- Underlying spot price: Yes
- Implied volatility: Yes
- Greeks (delta, vega): Yes
- Volume (bid/ask amount): Yes
- Mark price: Yes

**Implied Volatility Stats**:
- Range: 0.6207 to 0.6978
- Mean: 0.6553, Std: 0.0189
- Negative IV count: 0

**Spot Price Range**: 3500.00 to 3563.98 (mean: 3542.65)

**Data Quality Issues**:
- Negative spreads: 0
- Zero/negative bids: 0
- Zero/negative asks: 0
- Missing values: 0 total across all columns

**Data Nature**: Likely Synthetic
- Detected patterns consistent with synthetic generation (regular timestamps, round strikes, parametric IV)

**Time-Series Forecasting Suitability**: Suitable
- 200 unique timestamps over 0.3 hours

**Column Details**:
- `event_id`: str (missing: 0)
- `timestamp`: str (missing: 0)
- `event_type`: str (missing: 0)
- `instrument_name`: str (missing: 0)
- `underlying`: str (missing: 0)
- `underlying_price`: float64 (missing: 0)
- `best_bid_price`: float64 (missing: 0)
- `best_bid_amount`: float64 (missing: 0)
- `best_ask_price`: float64 (missing: 0)
- `best_ask_amount`: float64 (missing: 0)
- `mark_price`: float64 (missing: 0)
- `implied_volatility`: float64 (missing: 0)
- `delta`: float64 (missing: 0)
- `vega`: float64 (missing: 0)

---
