"""
Time-Series Aware Data Splitting

Implements chronological splits and walk-forward evaluation
to prevent data leakage in financial time-series.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class SplitResult:
    """Result of a time-series split."""
    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame
    metadata: Dict


class TimeSeriesSplitter:
    """
    Chronological train/validation/test splitter.
    
    Splits by time, not randomly. Ensures:
    - Train < Validation < Test in time
    - No overlapping timestamps
    - Configurable ratios
    """
    
    def __init__(
        self,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
        timestamp_col: str = "timestamp",
        gap: int = 0  # Gap between splits in timestamps
    ):
        assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-6, "Ratios must sum to 1.0"
        
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        self.timestamp_col = timestamp_col
        self.gap = gap
    
    def split(self, df: pd.DataFrame) -> SplitResult:
        """
        Split DataFrame chronologically.
        
        Args:
            df: DataFrame sorted by timestamp
            
        Returns:
            SplitResult with train/val/test DataFrames and metadata
        """
        df = df.sort_values(self.timestamp_col).reset_index(drop=True)
        n = len(df)
        
        train_end = int(n * self.train_ratio)
        val_end = train_end + int(n * self.val_ratio)
        
        # Apply gap
        train_df = df.iloc[:train_end].copy()
        val_df = df.iloc[train_end + self.gap:val_end].copy()
        test_df = df.iloc[val_end + self.gap:].copy()
        
        metadata = {
            "n_total": n,
            "n_train": len(train_df),
            "n_val": len(val_df),
            "n_test": len(test_df),
            "train_ratio": self.train_ratio,
            "val_ratio": self.val_ratio,
            "test_ratio": self.test_ratio,
            "gap": self.gap,
            "train_time_range": {
                "start": train_df[self.timestamp_col].min().isoformat() if len(train_df) > 0 else None,
                "end": train_df[self.timestamp_col].max().isoformat() if len(train_df) > 0 else None,
            },
            "val_time_range": {
                "start": val_df[self.timestamp_col].min().isoformat() if len(val_df) > 0 else None,
                "end": val_df[self.timestamp_col].max().isoformat() if len(val_df) > 0 else None,
            },
            "test_time_range": {
                "start": test_df[self.timestamp_col].min().isoformat() if len(test_df) > 0 else None,
                "end": test_df[self.timestamp_col].max().isoformat() if len(test_df) > 0 else None,
            },
        }
        
        return SplitResult(
            train=train_df,
            validation=val_df,
            test=test_df,
            metadata=metadata
        )
    
    def walk_forward_splits(
        self,
        df: pd.DataFrame,
        n_splits: int = 5,
        min_train_size: Optional[int] = None
    ) -> List[SplitResult]:
        """
        Generate walk-forward (expanding window) splits.
        
        Each split:
        - Train: Expanding window from start
        - Validation: Fixed window after train
        - Test: Fixed window after validation
        
        Args:
            df: DataFrame sorted by timestamp
            n_splits: Number of splits to generate
            min_train_size: Minimum training size (rows)
            
        Returns:
            List of SplitResult objects
        """
        df = df.sort_values(self.timestamp_col).reset_index(drop=True)
        n = len(df)
        
        if min_train_size is None:
            min_train_size = int(n * self.train_ratio)
        
        # Calculate test and val sizes
        test_size = int(n * self.test_ratio)
        val_size = int(n * self.val_ratio)
        
        splits = []
        
        for i in range(n_splits):
            # Calculate split points
            train_end = min_train_size + i * (test_size + val_size) // n_splits
            val_end = train_end + val_size
            test_end = val_end + test_size
            
            if test_end > n:
                break
            
            train_df = df.iloc[:train_end].copy()
            val_df = df.iloc[train_end + self.gap:val_end].copy()
            test_df = df.iloc[val_end + self.gap:test_end].copy()
            
            metadata = {
                "split_index": i,
                "n_train": len(train_df),
                "n_val": len(val_df),
                "n_test": len(test_df),
                "train_time_range": {
                    "start": train_df[self.timestamp_col].min().isoformat(),
                    "end": train_df[self.timestamp_col].max().isoformat(),
                },
                "val_time_range": {
                    "start": val_df[self.timestamp_col].min().isoformat(),
                    "end": val_df[self.timestamp_col].max().isoformat(),
                },
                "test_time_range": {
                    "start": test_df[self.timestamp_col].min().isoformat(),
                    "end": test_df[self.timestamp_col].max().isoformat(),
                },
            }
            
            splits.append(SplitResult(
                train=train_df,
                validation=val_df,
                test=test_df,
                metadata=metadata
            ))
        
        return splits


def create_splits(
    df: pd.DataFrame,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    timestamp_col: str = "timestamp",
    gap: int = 0,
    walk_forward: bool = False,
    n_splits: int = 5
) -> SplitResult | List[SplitResult]:
    """
    Convenience function to create time-series splits.
    
    Args:
        df: Input DataFrame
        train_ratio: Training set ratio
        val_ratio: Validation set ratio
        test_ratio: Test set ratio
        timestamp_col: Timestamp column name
        gap: Gap between splits (rows)
        walk_forward: Whether to generate walk-forward splits
        n_splits: Number of walk-forward splits
        
    Returns:
        Single SplitResult or list for walk-forward
    """
    splitter = TimeSeriesSplitter(
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        test_ratio=test_ratio,
        timestamp_col=timestamp_col,
        gap=gap
    )
    
    if walk_forward:
        return splitter.walk_forward_splits(df, n_splits=n_splits)
    else:
        return splitter.split(df)


def split_by_underlying(
    df: pd.DataFrame,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    timestamp_col: str = "timestamp",
    underlying_col: str = "underlying"
) -> Dict[str, SplitResult]:
    """
    Split each underlying independently, then combine.
    
    Useful when different assets have different time ranges.
    """
    results = {}
    
    for underlying in df[underlying_col].unique():
        mask = df[underlying_col] == underlying
        sub_df = df[mask].copy()
        
        splitter = TimeSeriesSplitter(
            train_ratio=train_ratio,
            val_ratio=val_ratio,
            test_ratio=test_ratio,
            timestamp_col=timestamp_col
        )
        
        results[underlying] = splitter.split(sub_df)
    
    return results


def save_splits(
    result: SplitResult,
    output_dir: str,
    prefix: str = ""
) -> None:
    """Save split DataFrames to Parquet and metadata to JSON."""
    import json
    from pathlib import Path
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    prefix = f"{prefix}_" if prefix else ""
    
    result.train.to_parquet(output_path / f"{prefix}train.parquet", index=False)
    result.validation.to_parquet(output_path / f"{prefix}validation.parquet", index=False)
    result.test.to_parquet(output_path / f"{prefix}test.parquet", index=False)
    
    with open(output_path / f"{prefix}metadata.json", "w") as f:
        json.dump(result.metadata, f, indent=2)


def load_splits(
    input_dir: str,
    prefix: str = ""
) -> SplitResult:
    """Load saved splits from Parquet and JSON."""
    import json
    from pathlib import Path
    
    input_path = Path(input_dir)
    prefix = f"{prefix}_" if prefix else ""
    
    train = pd.read_parquet(input_path / f"{prefix}train.parquet")
    val = pd.read_parquet(input_path / f"{prefix}validation.parquet")
    test = pd.read_parquet(input_path / f"{prefix}test.parquet")
    
    with open(input_path / f"{prefix}metadata.json", "r") as f:
        metadata = json.load(f)
    
    # Parse timestamps
    for df in [train, val, test]:
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    
    return SplitResult(train=train, validation=val, test=test, metadata=metadata)