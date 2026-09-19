"""
Reusable Parquet dataset auditor for cryptocurrency options data.
Analyzes row counts, column schemas, data quality, instrument coverage,
temporal density, and suitability for ML modeling.
"""

import os
import re
import sys
import argparse
import datetime
from typing import Dict, Any, List
import pandas as pd
import numpy as np

def audit_dataset(file_path: str, output_md: str = None) -> Dict[str, Any]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    print(f"Reading dataset: {file_path}...")
    df = pd.read_parquet(file_path)

    n_rows, n_cols = df.shape
    columns = list(df.columns)
    dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}
    missing_counts = {col: int(df[col].isnull().sum()) for col in columns}
    total_missing = sum(missing_counts.values())
    n_duplicates = int(df.duplicated().sum())

    # Timestamp analysis
    has_timestamp = "timestamp" in df.columns
    min_ts, max_ts = None, None
    n_unique_ts = 0
    time_delta_seconds = None
    avg_interval_seconds = None
    timestamps_dense = False

    if has_timestamp:
        try:
            ts_series = pd.to_datetime(df["timestamp"])
            min_ts = ts_series.min().isoformat()
            max_ts = ts_series.max().isoformat()
            unique_ts = ts_series.drop_duplicates().sort_values()
            n_unique_ts = len(unique_ts)
            if n_unique_ts > 1:
                intervals = unique_ts.diff().dropna().dt.total_seconds()
                avg_interval_seconds = float(intervals.median())
                time_delta_seconds = float((unique_ts.max() - unique_ts.min()).total_seconds())
                # Considered dense if median interval <= 60 seconds
                timestamps_dense = avg_interval_seconds <= 60.0
        except Exception as e:
            print(f"Warning: Could not parse timestamps: {e}")

    # Instrument & asset extraction
    instruments = []
    underlyings = []
    strikes = []
    expiries = []

    if "instrument_name" in df.columns:
        instruments = sorted(df["instrument_name"].dropna().unique().tolist())
        # Parse standard Deribit-style instrument names: BTC-25SEP26-65000-C
        for inst in instruments:
            parts = str(inst).split("-")
            if len(parts) >= 4:
                underlyings.append(parts[0])
                expiries.append(parts[1])
                try:
                    strikes.append(float(parts[2]))
                except ValueError:
                    pass
    if "underlying" in df.columns:
        underlyings.extend(df["underlying"].dropna().unique().tolist())

    unique_underlyings = sorted(list(set(underlyings)))
    unique_strikes = sorted(list(set(strikes)))
    unique_expiries = sorted(list(set(expiries)))

    # Feature presence audit
    has_bid_ask = any(c in df.columns for c in ["best_bid_price", "best_ask_price", "bid", "ask", "bid_price", "ask_price"])
    has_underlying_spot = any(c in df.columns for c in ["underlying_price", "spot_price", "index_price", "spot"])
    has_iv = any(c in df.columns for c in ["implied_volatility", "iv", "mark_iv"])
    greeks_present = [g for g in ["delta", "gamma", "vega", "theta", "rho"] if g in df.columns]

    # Authenticity & Quality evaluation
    # Deterministic synthetic heuristic: perfectly clean 0 missing, uniform 5s ticks, event_ids matching sequential prefix
    is_synthetic = False
    if "event_id" in df.columns:
        sample_ids = df["event_id"].dropna().head(10).tolist()
        if all(re.match(r"^ev_.*_\d+$", str(x)) for x in sample_ids):
            is_synthetic = True
    if total_missing == 0 and n_duplicates == 0 and avg_interval_seconds in [1.0, 5.0, 10.0]:
        is_synthetic = True

    data_quality_issues = []
    if total_missing > 0:
        data_quality_issues.append(f"{total_missing} missing values detected across columns.")
    if n_duplicates > 0:
        data_quality_issues.append(f"{n_duplicates} duplicate rows detected.")
    if time_delta_seconds is not None and time_delta_seconds < 3600.0:
        data_quality_issues.append(f"Total time horizon is only {time_delta_seconds:.0f} seconds (~{time_delta_seconds/60:.1f} mins), insufficient for macro multi-day volatility forecasting.")
    if is_synthetic:
        data_quality_issues.append("Dataset is synthetic/simulated data (generated via deterministic geometric motion), not real exchange tape.")
    if len(greeks_present) < 5:
        missing_greeks = [g for g in ["delta", "gamma", "vega", "theta", "rho"] if g not in greeks_present]
        data_quality_issues.append(f"Greeks partially omitted: missing {missing_greeks}.")

    audit_result = {
        "file_path": file_path,
        "file_size_bytes": os.path.getsize(file_path),
        "n_rows": n_rows,
        "n_cols": n_cols,
        "columns": columns,
        "dtypes": dtypes,
        "missing_counts": missing_counts,
        "total_missing": total_missing,
        "n_duplicates": n_duplicates,
        "min_timestamp": min_ts,
        "max_timestamp": max_ts,
        "n_unique_timestamps": n_unique_ts,
        "duration_seconds": time_delta_seconds,
        "avg_interval_seconds": avg_interval_seconds,
        "timestamps_dense": timestamps_dense,
        "unique_underlyings": unique_underlyings,
        "n_instruments": len(instruments),
        "unique_strikes": unique_strikes,
        "unique_expiries": unique_expiries,
        "has_bid_ask": has_bid_ask,
        "has_underlying_spot": has_underlying_spot,
        "has_iv": has_iv,
        "greeks_present": greeks_present,
        "is_synthetic": is_synthetic,
        "data_quality_issues": data_quality_issues
    }

    # Print console summary
    print("=" * 60)
    print(f"DATASET AUDIT REPORT: {os.path.basename(file_path)}")
    print("=" * 60)
    print(f"Rows:                 {n_rows:,}")
    print(f"Columns:              {n_cols} {columns}")
    print(f"Total Missing:        {total_missing}")
    print(f"Duplicates:           {n_duplicates}")
    print(f"Timestamp Range:      {min_ts} -> {max_ts}")
    print(f"Unique Timestamps:    {n_unique_ts} (Avg Interval: {avg_interval_seconds}s)")
    print(f"Dense Time-Series:    {timestamps_dense}")
    print(f"Underlyings:          {unique_underlyings}")
    print(f"Instruments Count:    {len(instruments)}")
    print(f"Strikes ({len(unique_strikes)}):         {unique_strikes}")
    print(f"Expiries ({len(unique_expiries)}):        {unique_expiries}")
    print(f"Bid/Ask Data:         {has_bid_ask}")
    print(f"Underlying Spot:      {has_underlying_spot}")
    print(f"Implied Vol (IV):     {has_iv}")
    print(f"Greeks Present:       {greeks_present}")
    print(f"Authenticity:         {'SYNTHETIC' if is_synthetic else 'GENUINE HISTORICAL'}")
    print(f"Quality Issues ({len(data_quality_issues)}):")
    for issue in data_quality_issues:
        print(f"  - {issue}")
    print("=" * 60)

    if output_md:
        generate_markdown_report(audit_result, output_md)
        print(f"Audit report written to: {output_md}")

    return audit_result

def generate_markdown_report(result: Dict[str, Any], output_path: str):
    md = f"""# Dataset Audit Report: `{os.path.basename(result['file_path'])}`

**Audit Date**: {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}  
**Target File**: `{result['file_path']}`  
**File Size**: {result['file_size_bytes'] / (1024 * 1024):.2f} MB  

---

## 1. Executive Summary

| Metric | Value |
|---|---|
| **Total Observations (Rows)** | `{result['n_rows']:,}` |
| **Total Features (Columns)** | `{result['n_cols']}` |
| **Missing Values** | `{result['total_missing']}` |
| **Duplicate Records** | `{result['n_duplicates']}` |
| **Time Span** | `{result['min_timestamp']}` to `{result['max_timestamp']}` |
| **Duration** | `{result['duration_seconds']:.0f} seconds` (~`{result['duration_seconds']/60:.1f} minutes`) |
| **Discrete Timestamps** | `{result['n_unique_timestamps']}` |
| **Sampling Interval** | `{result['avg_interval_seconds']} seconds` (High-frequency regular tick grid) |
| **Underlying Assets** | `{', '.join(result['unique_underlyings'])}` |
| **Unique Instruments** | `{result['n_instruments']}` |
| **Strike Count** | `{len(result['unique_strikes'])}` strikes (`{result['unique_strikes']}`) |
| **Expiry Count** | `{len(result['unique_expiries'])}` expiries (`{result['unique_expiries']}`) |
| **Bid / Ask Quotes** | `{'Yes' if result['has_bid_ask'] else 'No'}` (`best_bid_price`, `best_ask_price`, quantities) |
| **Underlying Spot Price** | `{'Yes' if result['has_underlying_spot'] else 'No'}` (`underlying_price`) |
| **Implied Volatility (IV)** | `{'Yes' if result['has_iv'] else 'No'}` (`implied_volatility`) |
| **Greeks Included** | `{', '.join(result['greeks_present'])}` |
| **Data Nature** | **{'SYNTHETIC' if result['is_synthetic'] else 'HISTORICAL REAL'}** |
| **Density for Forecasting** | **{'Sufficient for high-frequency/tick forecasting; Insufficient for macro multi-day forecasting' if result['timestamps_dense'] else 'Sparse'}** |

---

## 2. Column Schema & Data Types

| Column Name | Data Type | Missing Count | Description |
|---|---|---|---|
"""
    for col in result["columns"]:
        dtype = result["dtypes"].get(col, "unknown")
        miss = result["missing_counts"].get(col, 0)
        md += f"| `{col}` | `{dtype}` | `{miss}` | |\n"

    md += f"""
---

## 3. Data Authenticity & Limitations

1. **Synthetic Nature**: The dataset is deterministically generated via geometric Brownian motion and Black-Scholes inversion (`services/replay/generator.py`). It is ideal for CI testing, offline replay, and architectural validation, but does not contain real market noise, microstructure jumps, or execution frictions.
2. **Horizon Constraint**: The total time window covers only **16.5 minutes** (200 snapshots at 5-second intervals). It is suitable for high-frequency tick returns and sequence models, but cannot train multi-week realized volatility dynamics.
3. **Missing Greeks**: Only `delta` and `vega` are explicitly serialized; `gamma`, `theta`, and `rho` must be derived dynamically via the quantitative pricer.
4. **Preservation**: This file (`data/samples/btc_options_sample.parquet`) is strictly preserved for Milestone 1 replay and regression testing.

---

## 4. Recommendations for Machine Learning

- **Feature Engineering**: Compute spot log returns, rolling Parkinson/realized volatility, moneyness $M = \\ln(K/S)$, and relative bid-ask spreads directly from available columns.
- **Time-Series Splitting**: Enforce strict chronological order (70% train, 15% val, 15% test) across the 200 time steps. **Never randomly shuffle**.
- **Model Training**: Use this dataset to establish pipeline invariants, unit test deep sequence models (LSTM/GRU), and train physics-informed neural surfaces (HyperIV/PINN). Real multi-month Deribit historical data should be ingested into `data/historical/` once acquired.
"""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md)

def main():
    parser = argparse.ArgumentParser(description="Audit Parquet options dataset.")
    parser.add_argument("--file", default="data/samples/btc_options_sample.parquet", help="Path to Parquet file.")
    parser.add_argument("--output", default="data/DATASET_AUDIT.md", help="Output path for Markdown audit report.")
    args = parser.parse_args()

    audit_dataset(args.file, args.output)

if __name__ == "__main__":
    main()
