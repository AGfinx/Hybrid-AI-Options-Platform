"""
Data Loader for ML Pipeline

Loads and validates Parquet datasets for training.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd


REQUIRED_COLUMNS = [
    "timestamp",
    "underlying",
    "underlying_price",
    "implied_volatility",
    "best_bid_price",
    "best_ask_price",
]

OPTIONAL_COLUMNS = [
    "event_id",
    "event_type",
    "instrument_name",
    "best_bid_amount",
    "best_ask_amount",
    "mark_price",
    "delta",
    "vega",
    "gamma",
    "theta",
    "rho",
    "open_interest",
    "volume_24h",
]


def load_parquet_dataset(path: str | Path) -> pd.DataFrame:
    """
    Load a Parquet dataset.
    
    Args:
        path: Path to Parquet file or directory
        
    Returns:
        DataFrame with parsed timestamps
    """
    df = pd.read_parquet(path)
    
    # Parse timestamps
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.sort_values("timestamp").reset_index(drop=True)
    
    return df


def validate_schema(df: pd.DataFrame, required: Optional[List[str]] = None) -> Tuple[bool, List[str]]:
    """
    Validate that DataFrame has required columns.
    
    Args:
        df: DataFrame to validate
        required: List of required column names (uses default if None)
        
    Returns:
        (is_valid, list_of_missing_columns)
    """
    if required is None:
        required = REQUIRED_COLUMNS
    
    missing = [col for col in required if col not in df.columns]
    return len(missing) == 0, missing


def get_data_summary(df: pd.DataFrame) -> Dict:
    """Get summary statistics for the dataset."""
    summary = {
        "num_rows": len(df),
        "num_columns": len(df.columns),
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "missing_values": df.isnull().sum().to_dict(),
        "memory_mb": round(df.memory_usage(deep=True).sum() / 1024 / 1024, 2),
    }
    
    if "timestamp" in df.columns:
        summary["time_range"] = {
            "min": df["timestamp"].min().isoformat(),
            "max": df["timestamp"].max().isoformat(),
            "span_hours": round((df["timestamp"].max() - df["timestamp"].min()).total_seconds() / 3600, 2),
            "unique_timestamps": int(df["timestamp"].nunique()),
        }
    
    if "underlying" in df.columns:
        summary["underlyings"] = df["underlying"].unique().tolist()
    
    return summary


def parse_instrument_name(instrument_name: str) -> Dict:
    """
    Parse Deribit-style instrument name.
    Format: BTC-25SEP26-65000-C
    """
    import re
    
    pattern = r"^([A-Z]+)-(\d{2}[A-Z]{3}\d{2})-(\d+)-([CP])$"
    match = re.match(pattern, instrument_name)
    
    if not match:
        return {}
    
    underlying, expiry_code, strike_str, opt_type = match.groups()
    
    return {
        "underlying": underlying,
        "expiry_code": expiry_code,
        "strike": float(strike_str),
        "option_type": "call" if opt_type == "C" else "put",
    }


def enrich_with_parsed_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Add parsed strike, expiry, option_type from instrument_name."""
    if "instrument_name" not in df.columns:
        return df
    
    parsed = df["instrument_name"].apply(parse_instrument_name)
    parsed_df = pd.DataFrame(parsed.tolist(), index=df.index)
    
    # Only add columns that don't exist
    for col in ["strike", "expiry_code", "option_type"]:
        if col not in df.columns and col in parsed_df.columns:
            df[col] = parsed_df[col]
    
    return df