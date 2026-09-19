"""
ML Package for Hybrid AI Options Platform

Provides:
- Data loading and validation
- Feature engineering for volatility modeling
- Time-series aware train/val/test splitting
- Model training and evaluation pipelines
- RV forecasting (baseline + deep learning)
- HyperIV/PINN volatility surface modeling
"""

from packages.ml.data.loader import load_parquet_dataset, validate_schema
from packages.ml.data.features import build_features
from packages.ml.data.splitting import TimeSeriesSplitter, create_splits
from packages.ml.evaluation.metrics import evaluate_regression, evaluate_vol_forecast

__all__ = [
    "load_parquet_dataset",
    "validate_schema",
    "build_features",
    "TimeSeriesSplitter",
    "create_splits",
    "evaluate_regression",
    "evaluate_vol_forecast",
]