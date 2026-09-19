"""
Baseline RV Forecasting Models

Wraps the existing scikit-learn Ridge/RandomForest implementation
from Milestone 1 for comparison with deep learning models.
"""

import joblib
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Any

import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from packages.quant.rv_forecast import RealizedVolForecaster


class RVBaselineModel:
    """
    Wrapper for Milestone 1 baseline RV forecasters.
    
    Provides consistent interface with deep learning models.
    """
    
    def __init__(
        self,
        model_type: str = "ridge",
        horizon_seconds: int = 3600,
        **model_kwargs
    ):
        """
        Initialize baseline model.
        
        Args:
            model_type: "ridge" or "random_forest"
            horizon_seconds: Forecast horizon
            **model_kwargs: Additional model parameters
        """
        self.model_type = model_type
        self.horizon_seconds = horizon_seconds
        self.model_kwargs = model_kwargs
        self.model = None
        self.scaler = StandardScaler()
        self.is_fitted = False
        self.feature_names = None
        self.training_history = {}
    
    def _create_model(self):
        """Create the underlying sklearn model."""
        if self.model_type == "ridge":
            alpha = self.model_kwargs.get("alpha", 1.0)
            return Ridge(alpha=alpha, random_state=42)
        elif self.model_type == "random_forest":
            n_estimators = self.model_kwargs.get("n_estimators", 100)
            max_depth = self.model_kwargs.get("max_depth", 10)
            return RandomForestRegressor(
                n_estimators=n_estimators,
                max_depth=max_depth,
                random_state=42,
                n_jobs=-1
            )
        else:
            raise ValueError(f"Unknown model_type: {self.model_type}")
    
    def prepare_features(self, df: pd.DataFrame) -> tuple:
        """
        Prepare features using the existing RealizedVolForecaster logic.
        
        Returns:
            X: Feature matrix
            y: Target vector
            feature_names: List of feature names
        """
        forecaster = RealizedVolForecaster()
        
        # Group by underlying and timestamp to get spot series
        X_list = []
        y_list = []
        
        for underlying in df["underlying"].unique():
            mask = df["underlying"] == underlying
            sub_df = df[mask].sort_values("timestamp")
            
            if len(sub_df) < 30:
                continue
            
            spot_series = sub_df["underlying_price"].values
            features = forecaster.extract_features(spot_series.tolist())
            
            # Target: future RV at horizon
            # We need to compute this from the data
            # For now, use the existing logic
            X_list.append([features[name] for name in forecaster.feature_names])
            
            # Use the next period's RV as target (approximate)
            # In practice, this should be computed from actual future data
            y_list.append(features.get("rv_30d", 0.55))  # placeholder
        
        if not X_list:
            raise ValueError("Insufficient data for feature preparation")
        
        X = np.array(X_list)
        y = np.array(y_list)
        
        self.feature_names = forecaster.feature_names
        return X, y, self.feature_names
    
    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: Optional[List[str]] = None,
        validation_split: float = 0.15
    ) -> Dict:
        """
        Train the model with time-series cross-validation.
        
        Args:
            X: Feature matrix
            y: Target vector
            feature_names: Names of features
            validation_split: Fraction for validation
            
        Returns:
            Training history dict
        """
        self.feature_names = feature_names
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Create model
        self.model = self._create_model()
        
        # Time-series cross-validation
        tscv = TimeSeriesSplit(n_splits=3)
        cv_scores = []
        
        for train_idx, val_idx in tscv.split(X_scaled):
            X_tr, X_val = X_scaled[train_idx], X_scaled[val_idx]
            y_tr, y_val = y[train_idx], y[val_idx]
            
            self.model.fit(X_tr, y_tr)
            val_pred = self.model.predict(X_val)
            
            from packages.ml.evaluation.metrics import mean_absolute_error
            cv_scores.append(mean_absolute_error(y_val, val_pred))
        
        # Final fit on all data
        self.model.fit(X_scaled, y)
        self.is_fitted = True
        
        self.training_history = {
            "cv_mae_scores": cv_scores,
            "cv_mae_mean": np.mean(cv_scores),
            "cv_mae_std": np.std(cv_scores),
            "model_type": self.model_type,
            "n_samples": len(X),
            "n_features": X.shape[1],
        }
        
        return self.training_history
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Generate predictions."""
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)
    
    def predict_with_uncertainty(self, X: np.ndarray) -> tuple:
        """
        Predict with uncertainty estimate.
        
        For Ridge: uses residual std from CV
        For RF: uses prediction std across trees
        """
        preds = self.predict(X)
        
        if self.model_type == "random_forest" and hasattr(self.model, "estimators_"):
            # Use tree variance for RF
            tree_preds = np.array([tree.predict(self.scaler.transform(X)) for tree in self.model.estimators_])
            uncertainty = np.std(tree_preds, axis=0)
        else:
            # Use CV residual std for Ridge
            cv_std = self.training_history.get("cv_mae_std", 0.04)
            uncertainty = np.full_like(preds, cv_std)
        
        return preds, uncertainty
    
    def save(self, path: str | Path) -> None:
        """Save model artifact."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        artifact = {
            "model_type": self.model_type,
            "horizon_seconds": self.horizon_seconds,
            "model_kwargs": self.model_kwargs,
            "model": self.model,
            "scaler": self.scaler,
            "is_fitted": self.is_fitted,
            "feature_names": self.feature_names,
            "training_history": self.training_history,
        }
        joblib.dump(artifact, path)
    
    @classmethod
    def load(cls, path: str | Path) -> "RVBaselineModel":
        """Load model artifact."""
        artifact = joblib.load(path)
        
        model = cls(
            model_type=artifact["model_type"],
            horizon_seconds=artifact["horizon_seconds"],
            **artifact["model_kwargs"]
        )
        model.model = artifact["model"]
        model.scaler = artifact["scaler"]
        model.is_fitted = artifact["is_fitted"]
        model.feature_names = artifact["feature_names"]
        model.training_history = artifact["training_history"]
        
        return model


def train_baseline_models(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    model_types: List[str] = ["ridge", "random_forest"],
    output_dir: str = "data/models/rv_forecaster/"
) -> Dict[str, RVBaselineModel]:
    """
    Train all baseline models and return them.
    
    Args:
        train_df: Training data
        val_df: Validation data
        test_df: Test data
        model_types: List of model types to train
        output_dir: Directory to save artifacts
        
    Returns:
        Dict mapping model_type to trained model
    """
    from packages.ml.data.features import build_features, prepare_xy
    
    # Build features for each split
    train_features = build_features(train_df)
    val_features = build_features(val_df)
    test_features = build_features(test_df)
    
    X_train, y_train, feature_names = prepare_xy(train_features)
    X_val, y_val, _ = prepare_xy(val_features)
    X_test, y_test, _ = prepare_xy(test_features)
    
    models = {}
    
    for model_type in model_types:
        print(f"\nTraining {model_type} baseline...")
        
        model = RVBaselineModel(model_type=model_type)
        history = model.fit(X_train, y_train, feature_names)
        
        print(f"  CV MAE: {history['cv_mae_mean']:.6f} ± {history['cv_mae_std']:.6f}")
        
        # Evaluate on validation
        val_pred = model.predict(X_val)
        from packages.ml.evaluation.metrics import evaluate_vol_forecast
        val_metrics = evaluate_vol_forecast(y_val, val_pred, prefix=f"{model_type}_val")
        print(f"  Val MAE: {val_metrics[f'{model_type}_val_mae']:.6f}")
        
        # Evaluate on test
        test_pred = model.predict(X_test)
        test_metrics = evaluate_vol_forecast(y_test, test_pred, prefix=f"{model_type}_test")
        print(f"  Test MAE: {test_metrics[f'{model_type}_test_mae']:.6f}")
        
        # Save
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        model.save(output_path / f"{model_type}_baseline.joblib")
        
        models[model_type] = model
    
    return models