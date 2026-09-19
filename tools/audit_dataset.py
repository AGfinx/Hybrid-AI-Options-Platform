#!/usr/bin/env python3
"""
Dataset Audit Script for Hybrid AI Options Platform
Audits Parquet files and generates a comprehensive dataset audit report.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import pyarrow.parquet as pq


def audit_parquet_file(filepath: Path) -> Dict[str, Any]:
    """Audit a single Parquet file and return comprehensive statistics."""
    
    # Read with pyarrow for metadata
    pf = pq.ParquetFile(filepath)
    schema = pf.schema_arrow
    
    # Read full data with pandas for analysis
    df = pd.read_parquet(filepath)
    
    report = {
        "file": str(filepath),
        "file_size_bytes": filepath.stat().st_size,
        "num_rows": len(df),
        "num_columns": len(df.columns),
        "column_names": list(df.columns),
        "data_types": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "missing_values": df.isnull().sum().to_dict(),
        "duplicate_rows": int(df.duplicated().sum()),
        "memory_usage_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2),
    }
    
    # Timestamp analysis
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        report["min_timestamp"] = df["timestamp"].min().isoformat()
        report["max_timestamp"] = df["timestamp"].max().isoformat()
        report["num_unique_timestamps"] = int(df["timestamp"].nunique())
        report["time_span_hours"] = round((df["timestamp"].max() - df["timestamp"].min()).total_seconds() / 3600, 2)
        
        # Check timestamp density
        if report["num_unique_timestamps"] > 1:
            avg_interval_sec = (df["timestamp"].max() - df["timestamp"].min()).total_seconds() / (report["num_unique_timestamps"] - 1)
            report["avg_timestamp_interval_seconds"] = round(avg_interval_sec, 2)
    
    # Strike analysis - parse from instrument_name if not a direct column
    if "strike" in df.columns:
        report["num_unique_strikes"] = int(df["strike"].nunique())
        report["min_strike"] = float(df["strike"].min())
        report["max_strike"] = float(df["strike"].max())
        report["unique_strikes"] = sorted(df["strike"].unique().tolist())
    elif "instrument_name" in df.columns:
        # Parse strike from instrument_name (format: BTC-25SEP26-55000-C)
        try:
            strikes = df["instrument_name"].str.extract(r'-(\d+)-[CP]$')[0].astype(float)
            report["num_unique_strikes"] = int(strikes.nunique())
            report["min_strike"] = float(strikes.min())
            report["max_strike"] = float(strikes.max())
            report["unique_strikes"] = sorted(strikes.unique().tolist())
            report["strike_source"] = "parsed_from_instrument_name"
        except Exception:
            pass
    
    # Expiry analysis - parse from instrument_name if not a direct column
    expiry_col = None
    for col in ["expiry_years", "T", "time_to_expiry"]:
        if col in df.columns:
            expiry_col = col
            break
    if expiry_col:
        report["num_unique_expiries"] = int(df[expiry_col].nunique())
        report["min_expiry"] = float(df[expiry_col].min())
        report["max_expiry"] = float(df[expiry_col].max())
        report["unique_expiries"] = sorted(df[expiry_col].unique().tolist())
        report["expiry_column_used"] = expiry_col
    elif "instrument_name" in df.columns:
        # Parse expiry from instrument_name (format: BTC-25SEP26-55000-C)
        try:
            expiries = df["instrument_name"].str.extract(r'-(\d{2}[A-Z]{3}\d{2})-')[0]
            # Convert to approximate years from timestamp
            if "timestamp" in df.columns:
                df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
                # Parse expiry date
                expiry_dates = pd.to_datetime(expiries[0], format='%d%b%y', errors='coerce')
                # This is more complex - just count unique expiry codes
                report["num_unique_expiries"] = int(expiries.nunique())
                report["unique_expiry_codes"] = sorted(expiries.unique().tolist())
                report["expiry_source"] = "parsed_from_instrument_name"
        except Exception:
            pass
    
    # Instruments/Assets
    if "underlying" in df.columns:
        report["unique_underlyings"] = df["underlying"].unique().tolist()
    if "instrument_name" in df.columns:
        report["num_unique_instruments"] = int(df["instrument_name"].nunique())
    
    # Data quality checks
    report["has_bid_ask"] = "best_bid_price" in df.columns and "best_ask_price" in df.columns
    report["has_underlying_price"] = "underlying_price" in df.columns
    report["has_iv"] = "implied_volatility" in df.columns
    report["has_greeks"] = "delta" in df.columns and "vega" in df.columns
    report["has_volume"] = "best_bid_amount" in df.columns and "best_ask_amount" in df.columns
    report["has_mark_price"] = "mark_price" in df.columns
    
    # Check for negative prices/spreads
    if report["has_bid_ask"]:
        report["negative_spread_count"] = int((df["best_ask_price"] < df["best_bid_price"]).sum())
        report["zero_bid_count"] = int((df["best_bid_price"] <= 0).sum())
        report["zero_ask_count"] = int((df["best_ask_price"] <= 0).sum())
    
    if report["has_iv"]:
        report["iv_min"] = float(df["implied_volatility"].min())
        report["iv_max"] = float(df["implied_volatility"].max())
        report["iv_mean"] = float(df["implied_volatility"].mean())
        report["iv_std"] = float(df["implied_volatility"].std())
        report["negative_iv_count"] = int((df["implied_volatility"] < 0).sum())
    
    if "underlying_price" in df.columns:
        report["spot_min"] = float(df["underlying_price"].min())
        report["spot_max"] = float(df["underlying_price"].max())
        report["spot_mean"] = float(df["underlying_price"].mean())
    
    # Check if data appears synthetic
    report["is_likely_synthetic"] = _detect_synthetic_data(df)
    
    # Time-series density for forecasting
    if "timestamp" in df.columns and report["num_unique_timestamps"] > 10:
        report["suitable_for_ts_forecasting"] = True
        report["ts_density_note"] = f"{report['num_unique_timestamps']} unique timestamps over {report['time_span_hours']:.1f} hours"
    else:
        report["suitable_for_ts_forecasting"] = False
        report["ts_density_note"] = "Insufficient temporal resolution for time-series forecasting"
    
    return report


def _detect_synthetic_data(df: pd.DataFrame) -> bool:
    """Heuristic to detect if data is synthetically generated."""
    indicators = []
    
    # Check for perfectly regular time intervals
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        unique_ts = df["timestamp"].sort_values().unique()
        if len(unique_ts) > 10:
            intervals = pd.Series(unique_ts).diff().dt.total_seconds().dropna()
            # If all intervals are exactly the same (or very close), likely synthetic
            if intervals.std() < 0.01 and intervals.mean() > 0:
                indicators.append("perfectly_regular_timestamps")
    
    # Check for round-number patterns in strikes
    if "strike" in df.columns:
        strikes = df["strike"].unique()
        round_strikes = sum(1 for s in strikes if s % 1000 == 0 or s % 500 == 0)
        if round_strikes / len(strikes) > 0.8:
            indicators.append("round_number_strikes")
    
    # Check for deterministic patterns in IV
    if "implied_volatility" in df.columns:
        iv_vals = df["implied_volatility"].values
        # Check for too-perfect parametric smile
        unique_iv = len(pd.Series(iv_vals).round(4).unique())
        if unique_iv < len(iv_vals) * 0.1:
            indicators.append("low_iv_variety")
    
    return len(indicators) >= 2


def generate_markdown_report(audit_results: List[Dict[str, Any]], output_path: Path) -> str:
    """Generate a human-readable Markdown report from audit results."""
    
    lines = [
        "# Dataset Audit Report",
        f"Generated: {pd.Timestamp.now(tz='UTC').isoformat()}",
        "",
        "## Summary",
        ""
    ]
    
    for r in audit_results:
        lines.append(f"### {Path(r['file']).name}")
        lines.append(f"- **File size**: {r['file_size_bytes']:,} bytes ({r['file_size_bytes']/1024/1024:.2f} MB)")
        lines.append(f"- **Rows**: {r['num_rows']:,}")
        lines.append(f"- **Columns**: {r['num_columns']}")
        lines.append(f"- **Memory usage**: {r['memory_usage_mb']:.2f} MB")
        lines.append(f"- **Duplicate rows**: {r['duplicate_rows']}")
        lines.append("")
        
        # Time range
        if "min_timestamp" in r:
            lines.append(f"**Time Range**: {r['min_timestamp']} to {r['max_timestamp']}")
            lines.append(f"- Time span: {r['time_span_hours']:.2f} hours")
            lines.append(f"- Unique timestamps: {r['num_unique_timestamps']:,}")
            if "avg_timestamp_interval_seconds" in r:
                lines.append(f"- Avg interval: {r['avg_timestamp_interval_seconds']:.2f} seconds")
            lines.append("")
        
        # Strikes
        if "num_unique_strikes" in r:
            lines.append(f"**Strikes**: {r['num_unique_strikes']} unique ({r['min_strike']:.0f} to {r['max_strike']:.0f})")
            if "strike_source" in r:
                lines.append(f"- Source: {r['strike_source']}")
            lines.append("")
        
        # Expiries
        if "num_unique_expiries" in r:
            if "expiry_column_used" in r:
                lines.append(f"**Expiries**: {r['num_unique_expiries']} unique ({r['min_expiry']:.4f} to {r['max_expiry']:.4f} years)")
                lines.append(f"- Expiry column: {r['expiry_column_used']}")
            elif "unique_expiry_codes" in r:
                lines.append(f"**Expiries**: {r['num_unique_expiries']} unique expiry codes")
                lines.append(f"- Codes: {', '.join(r['unique_expiry_codes'])}")
                lines.append(f"- Source: {r['expiry_source']}")
            lines.append("")
        
        # Underlyings
        if "unique_underlyings" in r:
            lines.append(f"**Underlyings**: {', '.join(r['unique_underlyings'])}")
            lines.append("")
        
        # Data availability
        lines.append("**Available Data Fields**:")
        lines.append(f"- Bid/Ask: {'Yes' if r['has_bid_ask'] else 'No'}")
        lines.append(f"- Underlying spot price: {'Yes' if r['has_underlying_price'] else 'No'}")
        lines.append(f"- Implied volatility: {'Yes' if r['has_iv'] else 'No'}")
        lines.append(f"- Greeks (delta, vega): {'Yes' if r['has_greeks'] else 'No'}")
        lines.append(f"- Volume (bid/ask amount): {'Yes' if r['has_volume'] else 'No'}")
        lines.append(f"- Mark price: {'Yes' if r['has_mark_price'] else 'No'}")
        lines.append("")
        
        # IV stats
        if r["has_iv"]:
            lines.append("**Implied Volatility Stats**:")
            lines.append(f"- Range: {r['iv_min']:.4f} to {r['iv_max']:.4f}")
            lines.append(f"- Mean: {r['iv_mean']:.4f}, Std: {r['iv_std']:.4f}")
            lines.append(f"- Negative IV count: {r['negative_iv_count']}")
            lines.append("")
        
        # Spot stats
        if "spot_min" in r:
            lines.append(f"**Spot Price Range**: {r['spot_min']:.2f} to {r['spot_max']:.2f} (mean: {r['spot_mean']:.2f})")
            lines.append("")
        
        # Quality issues
        lines.append("**Data Quality Issues**:")
        if r["has_bid_ask"]:
            lines.append(f"- Negative spreads: {r['negative_spread_count']}")
            lines.append(f"- Zero/negative bids: {r['zero_bid_count']}")
            lines.append(f"- Zero/negative asks: {r['zero_ask_count']}")
        lines.append(f"- Missing values: {sum(r['missing_values'].values())} total across all columns")
        if r["duplicate_rows"] > 0:
            lines.append(f"- Duplicate rows: {r['duplicate_rows']}")
        lines.append("")
        
        # Synthetic detection
        lines.append(f"**Data Nature**: {'Likely Synthetic' if r['is_likely_synthetic'] else 'Appears Historical/Real'}")
        if r["is_likely_synthetic"]:
            lines.append("- Detected patterns consistent with synthetic generation (regular timestamps, round strikes, parametric IV)")
        lines.append("")
        
        # Forecasting suitability
        lines.append(f"**Time-Series Forecasting Suitability**: {'Suitable' if r['suitable_for_ts_forecasting'] else 'Not Suitable'}")
        lines.append(f"- {r['ts_density_note']}")
        lines.append("")
        
        # Column details
        lines.append("**Column Details**:")
        for col in r["column_names"]:
            dtype = r["data_types"][col]
            missing = r["missing_values"].get(col, 0)
            lines.append(f"- `{col}`: {dtype} (missing: {missing})")
        lines.append("")
        lines.append("---")
        lines.append("")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Audit Parquet dataset files")
    parser.add_argument("input", nargs="+", type=Path, help="Parquet file(s) to audit")
    parser.add_argument("-o", "--output", type=Path, default=Path("data/DATASET_AUDIT.md"), help="Output markdown report path")
    parser.add_argument("--json", type=Path, help="Output JSON report path")
    args = parser.parse_args()
    
    results = []
    for filepath in args.input:
        if not filepath.exists():
            print(f"Error: File not found: {filepath}", file=sys.stderr)
            sys.exit(1)
        
        print(f"Auditing {filepath}...")
        result = audit_parquet_file(filepath)
        results.append(result)
        
        # Print summary to console
        print(f"\n=== {filepath.name} ===")
        print(f"Rows: {result['num_rows']:,}")
        print(f"Columns: {result['num_columns']}")
        print(f"Time range: {result.get('min_timestamp', 'N/A')} to {result.get('max_timestamp', 'N/A')}")
        print(f"Unique timestamps: {result.get('num_unique_timestamps', 'N/A')}")
        print(f"Unique strikes: {result.get('num_unique_strikes', 'N/A')}")
        print(f"Unique expiries: {result.get('num_unique_expiries', 'N/A')}")
        print(f"Underlyings: {result.get('unique_underlyings', 'N/A')}")
        print(f"Has bid/ask: {result['has_bid_ask']}")
        print(f"Has IV: {result['has_iv']}")
        print(f"Has Greeks: {result['has_greeks']}")
        print(f"Likely synthetic: {result['is_likely_synthetic']}")
        print(f"Suitable for TS forecasting: {result['suitable_for_ts_forecasting']}")
        print()
    
    # Write markdown report
    args.output.parent.mkdir(parents=True, exist_ok=True)
    md_report = generate_markdown_report(results, args.output)
    args.output.write_text(md_report)
    print(f"Markdown report written to: {args.output}")
    
    # Write JSON report if requested
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(results, indent=2))
        print(f"JSON report written to: {args.json}")


if __name__ == "__main__":
    main()