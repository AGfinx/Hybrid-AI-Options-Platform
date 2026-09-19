"""
Data Validation for ML Pipeline

Validates data quality, checks for leakage, ensures consistency.
"""

import warnings
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


def check_data_quality(df: pd.DataFrame, verbose: bool = True) -> Dict:
    """
    Comprehensive data quality checks.
    
    Returns:
        Dict with check results and any warnings/errors
    """
    results = {
        "passed": True,
        "errors": [],
        "warnings": [],
        "checks": {}
    }
    
    # 1. No missing values in critical columns
    critical_cols = ["timestamp", "underlying_price", "implied_volatility"]
    for col in critical_cols:
        if col in df.columns:
            missing = df[col].isnull().sum()
            if missing > 0:
                results["errors"].append(f"Column '{col}' has {missing} missing values")
                results["passed"] = False
            results["checks"][f"missing_{col}"] = int(missing)
    
    # 2. No negative prices
    price_cols = ["underlying_price", "best_bid_price", "best_ask_price", "mark_price"]
    for col in price_cols:
        if col in df.columns:
            neg_count = (df[col] < 0).sum()
            if neg_count > 0:
                results["errors"].append(f"Column '{col}' has {neg_count} negative values")
                results["passed"] = False
            results["checks"][f"negative_{col}"] = int(neg_count)
    
    # 3. Bid <= Ask
    if "best_bid_price" in df.columns and "best_ask_price" in df.columns:
        crossed = (df["best_bid_price"] > df["best_ask_price"]).sum()
        if crossed > 0:
            results["warnings"].append(f"Bid > Ask on {crossed} rows (crossed market)")
        results["checks"]["crossed_market"] = int(crossed)
    
    # 4. IV in reasonable range
    if "implied_volatility" in df.columns:
        iv = df["implied_volatility"]
        too_low = (iv < 0.01).sum()
        too_high = (iv > 5.0).sum()
        if too_low > 0:
            results["warnings"].append(f"IV < 1% on {too_low} rows")
        if too_high > 0:
            results["warnings"].append(f"IV > 500% on {too_high} rows")
        results["checks"]["iv_out_of_range"] = {"too_low": int(too_low), "too_high": int(too_high)}
    
    # 5. Greeks in reasonable range
    if "delta" in df.columns:
        delta = df["delta"]
        invalid = ((delta < -2) | (delta > 2)).sum()
        if invalid > 0:
            results["warnings"].append(f"Delta outside [-2, 2] on {invalid} rows")
        results["checks"]["delta_range"] = int(invalid)
    
    # 6. Timestamp monotonicity
    if "timestamp" in df.columns:
        ts = pd.to_datetime(df["timestamp"])
        non_monotonic = (ts.diff().dt.total_seconds() < 0).sum()
        if non_monotonic > 0:
            results["warnings"].append(f"Non-monotonic timestamps: {non_monotonic} decreases")
        results["checks"]["non_monotonic_timestamps"] = int(non_monotonic)
    
    # 7. Duplicate rows
    dup = df.duplicated().sum()
    if dup > 0:
        results["warnings"].append(f"{dup} duplicate rows found")
    results["checks"]["duplicate_rows"] = int(dup)
    
    if verbose:
        if results["errors"]:
            for e in results["errors"]:
                print(f"ERROR: {e}")
        if results["warnings"]:
            for w in results["warnings"]:
                print(f"WARNING: {w}")
        if results["passed"] and not results["warnings"]:
            print("All data quality checks passed.")
    
    return results


def check_temporal_leakage(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    timestamp_col: str = "timestamp"
) -> Dict:
    """
    Verify no temporal leakage between splits.
    
    Training data must be strictly before validation, which must be before test.
    """
    results = {
        "passed": True,
        "errors": [],
        "warnings": [],
    }
    
    for name, df in [("train", train_df), ("val", val_df), ("test", test_df)]:
        if timestamp_col not in df.columns:
            results["errors"].append(f"{name} split missing '{timestamp_col}' column")
            results["passed"] = False
    
    if not results["passed"]:
        return results
    
    train_max = pd.to_datetime(train_df[timestamp_col]).max()
    val_min = pd.to_datetime(val_df[timestamp_col]).min()
    val_max = pd.to_datetime(val_df[timestamp_col]).max()
    test_min = pd.to_datetime(test_df[timestamp_col]).min()
    
    if train_max >= val_min:
        results["errors"].append(f"Train max ({train_max}) >= Val min ({val_min}) - LEAKAGE!")
        results["passed"] = False
    
    if val_max >= test_min:
        results["errors"].append(f"Val max ({val_max}) >= Test min ({test_min}) - LEAKAGE!")
        results["passed"] = False
    
    # Check for overlap
    train_set = set(pd.to_datetime(train_df[timestamp_col]).unique())
    val_set = set(pd.to_datetime(val_df[timestamp_col]).unique())
    test_set = set(pd.to_datetime(test_df[timestamp_col]).unique())
    
    train_val_overlap = train_set & val_set
    val_test_overlap = val_set & test_set
    train_test_overlap = train_set & test_set
    
    if train_val_overlap:
        results["errors"].append(f"Train/Val timestamp overlap: {len(train_val_overlap)} timestamps")
        results["passed"] = False
    
    if val_test_overlap:
        results["errors"].append(f"Val/Test timestamp overlap: {len(val_test_overlap)} timestamps")
        results["passed"] = False
    
    if train_test_overlap:
        results["errors"].append(f"Train/Test timestamp overlap: {len(train_test_overlap)} timestamps")
        results["passed"] = False
    
    results["checks"] = {
        "train_max": train_max.isoformat(),
        "val_min": val_min.isoformat(),
        "val_max": val_max.isoformat(),
        "test_min": test_min.isoformat(),
    }
    
    return results


def validate_features_no_lookahead(
    df: pd.DataFrame,
    feature_cols: List[str],
    target_col: str,
    timestamp_col: str = "timestamp"
) -> Dict:
    """
    Check that features don't use future information.
    
    This is a basic check - for full validation, inspect feature engineering code.
    """
    results = {
        "passed": True,
        "warnings": [],
    }
    
    # Check if any feature correlates too perfectly with future target
    # (This is a heuristic - real validation requires code review)
    if target_col in df.columns and len(feature_cols) > 0:
        df_sorted = df.sort_values(timestamp_col)
        target = df_sorted[target_col]
        
        for feat in feature_cols:
            if feat in df_sorted.columns:
                feat_vals = df_sorted[feat]
                # Check correlation with shifted target (future)
                if len(target) > 10:
                    corr_future = feat_vals.corr(target.shift(-1))
                    if abs(corr_future) > 0.95:
                        results["warnings"].append(
                            f"Feature '{feat}' has suspiciously high correlation "
                            f"with future target (r={corr_future:.4f}) - possible lookahead"
                        )
    
    return results


def assert_no_leakage(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    timestamp_col: str = "timestamp"
) -> None:
    """
    Raise exception if temporal leakage detected.
    Use in tests to enforce strict separation.
    """
    result = check_temporal_leakage(train_df, val_df, test_df, timestamp_col)
    if not result["passed"]:
        raise ValueError(f"Temporal leakage detected: {result['errors']}")