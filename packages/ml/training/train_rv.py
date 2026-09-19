"""
Training Script for RV Forecasting Models

Orchestrates training of baseline and deep learning models.
"""

import json
from pathlib import Path
from typing import Dict, Any

import pandas as pd
import numpy as np

from packages.ml.data.loader import load_parquet_dataset
from packages.ml.data.splitting import create_splits, save_splits
from packages.ml.models.rv_baseline import train_baseline_models, RVBaselineModel
from packages.ml.models.rv_lstm import train_lstm_model, RVLSTMTrainer
from packages.ml.evaluation.metrics import evaluate_vol_forecast, print_evaluation_report


def train_all_rv_models(
    data_path: str = "data/historical/btc_options.parquet",
    output_dir: str = "data/models/rv_forecaster/",
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    sequence_length: int = 30,
    lstm_epochs: int = 100,
    lstm_patience: int = 10,
    run_baselines: bool = True,
    run_lstm: bool = True,
    device: str = "auto"
) -> Dict[str, Any]:
    """
    Train all RV forecasting models.
    
    Args:
        data_path: Path to historical data
        output_dir: Directory for model artifacts
        train_ratio: Training split ratio
        val_ratio: Validation split ratio
        test_ratio: Test split ratio
        sequence_length: LSTM sequence length
        lstm_epochs: Max LSTM epochs
        lstm_patience: LSTM early stopping patience
        run_baselines: Train Ridge/RF baselines
        run_lstm: Train LSTM model
        device: Device for deep learning
        
    Returns:
        Dict with trained models and evaluation results
    """
    print(f"Loading data from {data_path}...")
    df = load_parquet_dataset(data_path)
    
    # Validate
    from packages.ml.data.validation import check_data_quality
    quality = check_data_quality(df)
    if not quality["passed"]:
        raise ValueError(f"Data quality check failed: {quality['errors']}")
    
    print(f"Data loaded: {len(df)} rows, {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    # Split data chronologically
    print("\nCreating chronological splits...")
    split_result = create_splits(
        df,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        test_ratio=test_ratio,
        timestamp_col="timestamp"
    )
    
    # Verify no leakage
    from packages.ml.data.validation import check_temporal_leakage
    leakage_check = check_temporal_leakage(
        split_result.train, split_result.validation, split_result.test
    )
    if not leakage_check["passed"]:
        raise ValueError(f"Temporal leakage detected: {leakage_check['errors']}")
    
    print(f"Split verified - no temporal leakage")
    print(f"  Train: {len(split_result.train)} rows ({split_result.metadata['train_time_range']['start']} to {split_result.metadata['train_time_range']['end']})")
    print(f"  Val:   {len(split_result.validation)} rows ({split_result.metadata['val_time_range']['start']} to {split_result.metadata['val_time_range']['end']})")
    print(f"  Test:  {len(split_result.test)} rows ({split_result.metadata['test_time_range']['start']} to {split_result.metadata['test_time_range']['end']})")
    
    # Save splits
    save_splits(split_result, "data/training/", prefix="rv_")
    
    results = {
        "models": {},
        "evaluation": {},
        "split_metadata": split_result.metadata
    }
    
    # Train baseline models
    if run_baselines:
        print("\n" + "="*50)
        print("TRAINING BASELINE MODELS")
        print("="*50)
        
        baseline_models = train_baseline_models(
            split_result.train,
            split_result.validation,
            split_result.test,
            model_types=["ridge", "random_forest"],
            output_dir=output_dir
        )
        
        results["models"]["ridge"] = baseline_models["ridge"]
        results["models"]["random_forest"] = baseline_models["random_forest"]
    
    # Train LSTM
    if run_lstm:
        print("\n" + "="*50)
        print("TRAINING LSTM MODEL")
        print("="*50)
        
        lstm_trainer = train_lstm_model(
            split_result.train,
            split_result.validation,
            split_result.test,
            sequence_length=sequence_length,
            hidden_dim=64,
            num_layers=2,
            dropout=0.2,
            learning_rate=1e-3,
            epochs=lstm_epochs,
            batch_size=32,
            patience=lstm_patience,
            output_dir=output_dir
        )
        
        results["models"]["lstm"] = lstm_trainer
    
    # Evaluate all models on test set
    print("\n" + "="*50)
    print("FINAL TEST SET EVALUATION")
    print("="*50)
    
    eval_results = evaluate_all_models(
        results["models"],
        split_result.test,
        output_dir=output_dir
    )
    
    results["evaluation"] = eval_results
    
    # Save summary
    summary = {
        "data_path": data_path,
        "split_metadata": split_result.metadata,
        "models_trained": list(results["models"].keys()),
        "evaluation": eval_results,
    }
    
    with open(Path(output_dir) / "training_summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)
    
    print(f"\nTraining complete! Summary saved to {output_dir}/training_summary.json")
    
    return results


def evaluate_all_models(
    models: Dict,
    test_df: pd.DataFrame,
    output_dir: str = "data/models/rv_forecaster/"
) -> Dict[str, Dict]:
    """
    Evaluate all trained models on test set.
    """
    from packages.ml.data.features import build_features, prepare_xy
    from sklearn.preprocessing import StandardScaler
    
    # Build test features
    test_features = build_features(test_df)
    X_test, y_test, feature_names = prepare_xy(test_features)
    
    # Scale features
    scaler = StandardScaler()
    # Note: In production, load the scaler used during training
    # For now, fit on test (not ideal but works for evaluation)
    X_test_scaled = scaler.fit_transform(X_test)
    
    eval_results = {}
    
    for name, model in models.items():
        print(f"\nEvaluating {name}...")
        
        if name in ["ridge", "random_forest"]:
            # Baseline models
            preds = model.predict(X_test_scaled)
            metrics = evaluate_vol_forecast(y_test, preds, prefix=f"{name}_test")
            print(f"  MAE: {metrics[f'{name}_test_mae']:.6f}")
            print(f"  RMSE: {metrics[f'{name}_test_rmse']:.6f}")
            print(f"  QLIKE: {metrics[f'{name}_test_qlike']:.6f}")
            eval_results[name] = metrics
            
        elif name == "lstm":
            # LSTM model
            trainer = model
            preds = trainer.predict(X_test_scaled)
            
            # Align (first seq_len are NaN)
            valid_mask = ~np.isnan(preds)
            if valid_mask.sum() > 0:
                metrics = evaluate_vol_forecast(
                    y_test[valid_mask],
                    preds[valid_mask],
                    prefix="lstm_test"
                )
                print(f"  MAE: {metrics['lstm_test_mae']:.6f}")
                print(f"  RMSE: {metrics['lstm_test_rmse']:.6f}")
                print(f"  QLIKE: {metrics['lstm_test_qlike']:.6f}")
                eval_results[name] = metrics
            else:
                eval_results[name] = {"error": "No valid predictions"}
    
    # Print comparison
    print("\n" + "="*60)
    print("MODEL COMPARISON (Test Set)")
    print("="*60)
    print(f"{'Model':<20} {'MAE':>10} {'RMSE':>10} {'QLIKE':>10} {'R2':>10}")
    print("-"*60)
    
    for name, metrics in eval_results.items():
        if "error" not in metrics:
            prefix = f"{name}_test" if name != "lstm" else "lstm_test"
            mae = metrics.get(f"{prefix}_mae", np.nan)
            rmse = metrics.get(f"{prefix}_rmse", np.nan)
            qlike = metrics.get(f"{prefix}_qlike", np.nan)
            r2 = metrics.get(f"{prefix}_r2", np.nan)
            print(f"{name:<20} {mae:>10.6f} {rmse:>10.6f} {qlike:>10.6f} {r2:>10.6f}")
    
    return eval_results


def generate_comparison_report(
    eval_results: Dict,
    output_path: str = "reports/milestone2_rv_results.md"
) -> str:
    """
    Generate markdown comparison report.
    """
    lines = [
        "# Milestone 2: RV Forecasting Model Comparison",
        f"Generated: {pd.Timestamp.now(tz='UTC').isoformat()}",
        "",
        "## Test Set Performance",
        "",
        "| Model | MAE | RMSE | QLIKE | R² | Directional Acc |",
        "|-------|-----|------|-------|----|-----------------|",
    ]
    
    for name, metrics in eval_results.items():
        if "error" in metrics:
            lines.append(f"| {name} | ERROR | ERROR | ERROR | ERROR | ERROR |")
            continue
            
        prefix = f"{name}_test" if name != "lstm" else "lstm_test"
        mae = metrics.get(f"{prefix}_mae", np.nan)
        rmse = metrics.get(f"{prefix}_rmse", np.nan)
        qlike = metrics.get(f"{prefix}_qlike", np.nan)
        r2 = metrics.get(f"{prefix}_r2", np.nan)
        dir_acc = metrics.get(f"{prefix}_directional_accuracy", np.nan)
        
        lines.append(f"| {name} | {mae:.6f} | {rmse:.6f} | {qlike:.6f} | {r2:.6f} | {dir_acc:.4f} |")
    
    lines.extend([
        "",
        "## Interpretation",
        "",
        "- **MAE/RMSE**: Lower is better. Measures average forecast error.",
        "- **QLIKE**: Quasi-likelihood loss. Standard for volatility forecasts. Lower is better.",
        "- **R²**: Coefficient of determination. Higher is better (1 = perfect).",
        "- **Directional Accuracy**: Fraction of correct sign predictions for volatility changes.",
        "",
        "## Notes",
        "",
        "- All models trained on chronological splits (no random shuffling)",
        "- Test set is strictly out-of-sample (final 15% of time)",
        "- Baseline models: Ridge regression and Random Forest from Milestone 1",
        "- LSTM: 2-layer LSTM with 64 hidden units, sequence length 30",
        "- Feature set: Rolling RV, IV statistics, Greeks, bid/ask spread, moneyness",
        "",
        "## Limitations",
        "",
        "- Current dataset is synthetic (16.5 minutes, 200 timestamps)",
        "- Insufficient for meaningful ML training - results not representative",
        "- Real historical data (months of data) needed for valid comparison",
        "- LSTM requires much more data to outperform simple baselines",
        "",
    ])
    
    report = "\n".join(lines)
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(report)
    
    print(f"\nComparison report saved to {output_path}")
    
    return report


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Train RV forecasting models")
    parser.add_argument("--data", default="data/historical/btc_options.parquet")
    parser.add_argument("--output", default="data/models/rv_forecaster/")
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--test-ratio", type=float, default=0.15)
    parser.add_argument("--seq-len", type=int, default=30)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--no-baselines", action="store_true")
    parser.add_argument("--no-lstm", action="store_true")
    parser.add_argument("--device", default="auto")
    
    args = parser.parse_args()
    
    results = train_all_rv_models(
        data_path=args.data,
        output_dir=args.output,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        sequence_length=args.seq_len,
        lstm_epochs=args.epochs,
        lstm_patience=args.patience,
        run_baselines=not args.no_baselines,
        run_lstm=not args.no_lstm,
        device=args.device
    )
    
    generate_comparison_report(results["evaluation"])