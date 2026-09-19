"""
Evaluation Metrics for Volatility Forecasting

Implements standard regression metrics and volatility-specific metrics.
"""

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats


def mean_absolute_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean Absolute Error."""
    return np.mean(np.abs(y_true - y_pred))


def mean_squared_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean Squared Error."""
    return np.mean((y_true - y_pred) ** 2)


def root_mean_squared_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Root Mean Squared Error."""
    return np.sqrt(mean_squared_error(y_true, y_pred))


def mean_absolute_percentage_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean Absolute Percentage Error (avoid division by zero)."""
    mask = y_true != 0
    if not mask.any():
        return np.nan
    return np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100


def median_absolute_error(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Median Absolute Error (robust to outliers)."""
    return np.median(np.abs(y_true - y_pred))


def r_squared(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """R-squared coefficient of determination."""
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    return 1 - (ss_res / ss_tot) if ss_tot != 0 else 0


def evaluate_regression(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    prefix: str = ""
) -> Dict[str, float]:
    """
    Comprehensive regression evaluation.
    
    Returns dict with all standard metrics.
    """
    metrics = {}
    
    p = f"{prefix}_" if prefix else ""
    
    metrics[f"{p}mae"] = mean_absolute_error(y_true, y_pred)
    metrics[f"{p}mse"] = mean_squared_error(y_true, y_pred)
    metrics[f"{p}rmse"] = root_mean_squared_error(y_true, y_pred)
    metrics[f"{p}mape"] = mean_absolute_percentage_error(y_true, y_pred)
    metrics[f"{p}medae"] = median_absolute_error(y_true, y_pred)
    metrics[f"{p}r2"] = r_squared(y_true, y_pred)
    
    # Additional metrics
    residuals = y_true - y_pred
    metrics[f"{p}residual_mean"] = np.mean(residuals)
    metrics[f"{p}residual_std"] = np.std(residuals)
    metrics[f"{p}bias"] = np.mean(residuals)  # Mean forecast error
    
    return metrics


def evaluate_vol_forecast(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_naive: Optional[np.ndarray] = None,
    prefix: str = ""
) -> Dict[str, float]:
    """
    Volatility-specific evaluation metrics.
    
    Args:
        y_true: True realized volatility
        y_pred: Predicted volatility
        y_naive: Naive benchmark predictions (e.g., lagged RV)
        prefix: Metric name prefix
        
    Returns:
        Dict with standard + volatility-specific metrics
    """
    metrics = evaluate_regression(y_true, y_pred, prefix)
    
    p = f"{prefix}_" if prefix else ""
    
    # Volatility-specific metrics
    
    # 1. QLIKE loss (common for volatility)
    # QLIKE = y_true/y_pred - log(y_true/y_pred) - 1
    ratio = y_true / (y_pred + 1e-10)
    qlike = np.mean(ratio - np.log(ratio) - 1)
    metrics[f"{p}qlike"] = qlike
    
    # 2. R^2 log (Mincer-Zarnowitz)
    # Regress log RV on log predicted RV
    log_true = np.log(y_true + 1e-10)
    log_pred = np.log(y_pred + 1e-10)
    
    slope, intercept, r_value, p_value, std_err = stats.linregress(log_pred, log_true)
    metrics[f"{p}mz_r2"] = r_value ** 2
    metrics[f"{p}mz_slope"] = slope
    metrics[f"{p}mz_intercept"] = intercept
    
    # 3. Directional accuracy (sign of change)
    if len(y_true) > 1:
        true_dir = np.sign(np.diff(y_true))
        pred_dir = np.sign(np.diff(y_pred))
        dir_acc = np.mean(true_dir == pred_dir)
        metrics[f"{p}directional_accuracy"] = dir_acc
    
    # 4. Hit rate for volatility regimes
    # Define regimes by quartiles
    try:
        true_quartiles = pd.qcut(y_true, 4, labels=False, duplicates='drop')
        pred_quartiles = pd.qcut(y_pred, 4, labels=False, duplicates='drop')
        regime_acc = np.mean(true_quartiles == pred_quartiles)
        metrics[f"{p}regime_accuracy"] = regime_acc
    except Exception:
        metrics[f"{p}regime_accuracy"] = np.nan
    
    # 5. Compare against naive benchmark
    if y_naive is not None:
        naive_metrics = evaluate_regression(y_true, y_naive, f"{prefix}_naive")
        metrics.update(naive_metrics)
        
        # Diebold-Mariano test for forecast comparison
        # Simplified: relative MAE
        rel_mae = metrics[f"{p}mae"] / (naive_metrics.get(f"{prefix}_naive_mae", 1) + 1e-10)
        metrics[f"{p}relative_mae_vs_naive"] = rel_mae
    
    return metrics


def evaluate_by_horizon(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    horizons: List[int],
    timestamps: Optional[np.ndarray] = None
) -> Dict[int, Dict[str, float]]:
    """
    Evaluate metrics at different forecast horizons.
    
    Assumes y_true/y_pred are aligned with horizons.
    """
    results = {}
    
    for h in horizons:
        # For each horizon, we'd need separate predictions
        # This is a placeholder for multi-horizon evaluation
        results[h] = evaluate_vol_forecast(y_true, y_pred, prefix=f"h{h}")
    
    return results


def evaluate_by_regime(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    regime_indicator: np.ndarray,
    regime_names: Optional[Dict[int, str]] = None
) -> Dict[str, Dict[str, float]]:
    """
    Evaluate metrics conditional on market regime.
    
    Args:
        y_true: True values
        y_pred: Predicted values
        regime_indicator: Regime labels for each observation
        regime_names: Optional mapping from label to name
        
    Returns:
        Dict mapping regime name to metrics dict
    """
    results = {}
    
    unique_regimes = np.unique(regime_indicator)
    
    for regime in unique_regimes:
        mask = regime_indicator == regime
        if mask.sum() < 10:
            continue
        
        name = regime_names.get(regime, f"regime_{regime}") if regime_names else f"regime_{regime}"
        results[name] = evaluate_vol_forecast(
            y_true[mask], y_pred[mask], prefix=name
        )
        results[name]["n_samples"] = int(mask.sum())
    
    return results


def format_metrics_table(metrics: Dict[str, float], precision: int = 4) -> str:
    """Format metrics dict as a readable table."""
    lines = []
    for k, v in sorted(metrics.items()):
        if isinstance(v, float):
            lines.append(f"  {k}: {v:.{precision}f}")
        else:
            lines.append(f"  {k}: {v}")
    return "\n".join(lines)


def print_evaluation_report(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_naive: Optional[np.ndarray] = None,
    model_name: str = "Model"
) -> None:
    """Print formatted evaluation report."""
    metrics = evaluate_vol_forecast(y_true, y_pred, y_naive, prefix=model_name.lower())
    
    print(f"\n{'='*50}")
    print(f"Evaluation Report: {model_name}")
    print(f"{'='*50}")
    print(f"Samples: {len(y_true)}")
    print(f"\nStandard Metrics:")
    for k in ["mae", "mse", "rmse", "mape", "medae", "r2", "bias"]:
        key = f"{model_name.lower()}_{k}"
        if key in metrics:
            print(f"  {key}: {metrics[key]:.6f}")
    
    print(f"\nVolatility-Specific Metrics:")
    for k in ["qlike", "mz_r2", "mz_slope", "mz_intercept", "directional_accuracy", "regime_accuracy"]:
        key = f"{model_name.lower()}_{k}"
        if key in metrics:
            print(f"  {key}: {metrics[key]:.6f}")
    
    if y_naive is not None:
        key = f"{model_name.lower()}_relative_mae_vs_naive"
        if key in metrics:
            print(f"\nRelative MAE vs Naive: {metrics[key]:.4f} ({'better' if metrics[key] < 1 else 'worse'})")
    
    print(f"{'='*50}\n")


def compute_prediction_intervals(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_std: np.ndarray,
    alpha: float = 0.05
) -> Dict[str, float]:
    """
    Evaluate prediction interval coverage.
    
    Args:
        y_true: True values
        y_pred: Point predictions
        y_std: Predicted standard deviation
        alpha: Significance level (0.05 = 95% interval)
        
    Returns:
        Coverage metrics
    """
    from scipy.stats import norm
    
    z = norm.ppf(1 - alpha / 2)
    lower = y_pred - z * y_std
    upper = y_pred + z * y_std
    
    coverage = np.mean((y_true >= lower) & (y_true <= upper))
    
    # Interval width
    width = np.mean(upper - lower)
    
    return {
        f"coverage_{int((1-alpha)*100)}": coverage,
        "interval_width": width,
        "expected_coverage": 1 - alpha,
    }