"""
Deep Learning RV Forecasting Models

Implements LSTM/GRU for realized volatility forecasting.
Designed to be extensible to PatchTST/Transformer later.
"""

import json
import joblib
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

from packages.ml.evaluation.metrics import evaluate_vol_forecast


class RVLSTMModel(nn.Module):
    """
    LSTM-based Realized Volatility Forecaster.
    
    Architecture:
    - Input: Sequence of features (returns, IV, Greeks, etc.)
    - LSTM layers
    - Fully connected output head
    - Optional: prediction interval head
    
    Designed so PatchTST can be swapped in later.
    """
    
    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 64,
        num_layers: int = 2,
        dropout: float = 0.2,
        bidirectional: bool = False,
        output_dim: int = 1,
        predict_interval: bool = False,
        sequence_length: int = 30
    ):
        super().__init__()
        
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.dropout = dropout
        self.bidirectional = bidirectional
        self.output_dim = output_dim
        self.predict_interval = predict_interval
        self.sequence_length = sequence_length
        
        # LSTM layer
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=bidirectional,
            batch_first=True
        )
        
        # Output dimension accounting for bidirectionality
        lstm_output_dim = hidden_dim * (2 if bidirectional else 1)
        
        # Point prediction head
        self.point_head = nn.Sequential(
            nn.Linear(lstm_output_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, output_dim),
            nn.Softplus()  # Ensure positive volatility
        )
        
        # Optional: prediction interval head (predicts log-variance)
        if predict_interval:
            self.interval_head = nn.Sequential(
                nn.Linear(lstm_output_dim, hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
                nn.Linear(hidden_dim, output_dim)
            )
        
        # Store config for saving/loading
        self.config = {
            "input_dim": input_dim,
            "hidden_dim": hidden_dim,
            "num_layers": num_layers,
            "dropout": dropout,
            "bidirectional": bidirectional,
            "output_dim": output_dim,
            "predict_interval": predict_interval,
            "sequence_length": sequence_length,
        }
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        """
        Forward pass.
        
        Args:
            x: (batch, sequence_length, input_dim)
            
        Returns:
            point_pred: (batch, output_dim)
            interval_pred: (batch, output_dim) or None
        """
        # LSTM forward
        lstm_out, (h_n, c_n) = self.lstm(x)
        
        # Use last hidden state
        if self.bidirectional:
            # Concatenate forward and backward last hidden states
            last_hidden = torch.cat([h_n[-2], h_n[-1]], dim=1)
        else:
            last_hidden = h_n[-1]
        
        # Point prediction
        point_pred = self.point_head(last_hidden)
        
        # Interval prediction
        interval_pred = None
        if self.predict_interval:
            interval_pred = self.interval_head(last_hidden)
        
        return point_pred, interval_pred
    
    def get_config(self) -> Dict:
        return self.config.copy()


class RVLSTMTrainer:
    """
    Trainer for RVLSTMModel.
    
    Handles:
    - Data preparation (sequences)
    - Training loop with early stopping
    - Validation
    - Checkpoint saving
    """
    
    def __init__(
        self,
        model: RVLSTMModel,
        learning_rate: float = 1e-3,
        weight_decay: float = 1e-5,
        device: str = "auto",
        gradient_clip: float = 1.0
    ):
        self.model = model
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.gradient_clip = gradient_clip
        
        if device == "auto":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)
        
        self.model.to(self.device)
        
        # Optimizer
        self.optimizer = optim.AdamW(
            model.parameters(),
            lr=learning_rate,
            weight_decay=weight_decay
        )
        
        # Loss functions
        self.point_loss_fn = nn.MSELoss()
        self.interval_loss_fn = nn.MSELoss()  # For log-variance
        
        # History
        self.history = {
            "train_loss": [],
            "val_loss": [],
            "train_mae": [],
            "val_mae": [],
        }
    
    def create_sequences(
        self,
        X: np.ndarray,
        y: np.ndarray,
        sequence_length: int
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Create sliding window sequences for LSTM.
        
        Args:
            X: (n_samples, n_features)
            y: (n_samples,)
            sequence_length: Lookback window
            
        Returns:
            X_seq: (n_sequences, sequence_length, n_features)
            y_seq: (n_sequences,)
        """
        n_samples, n_features = X.shape
        n_sequences = n_samples - sequence_length
        
        if n_sequences <= 0:
            raise ValueError(f"Sequence length {sequence_length} > samples {n_samples}")
        
        X_seq = np.zeros((n_sequences, sequence_length, n_features))
        y_seq = np.zeros(n_sequences)
        
        for i in range(n_sequences):
            X_seq[i] = X[i:i+sequence_length]
            y_seq[i] = y[i+sequence_length-1]  # Predict next step
        
        return X_seq, y_seq
    
    def train_epoch(
        self,
        train_loader: DataLoader,
        epoch: int
    ) -> Dict[str, float]:
        """Train for one epoch."""
        self.model.train()
        
        total_loss = 0.0
        total_mae = 0.0
        n_batches = 0
        
        for X_batch, y_batch in train_loader:
            X_batch = X_batch.to(self.device)
            y_batch = y_batch.to(self.device).unsqueeze(1)  # (batch, 1)
            
            self.optimizer.zero_grad()
            
            point_pred, interval_pred = self.model(X_batch)
            
            # Point prediction loss
            loss = self.point_loss_fn(point_pred, y_batch)
            
            # Add interval loss if applicable
            if interval_pred is not None:
                # Target: squared residuals
                with torch.no_grad():
                    residuals = (y_batch - point_pred.detach()) ** 2
                    log_var_target = torch.log(residuals + 1e-8)
                interval_loss = self.interval_loss_fn(interval_pred, log_var_target)
                loss = loss + 0.1 * interval_loss
            
            loss.backward()
            
            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.gradient_clip)
            
            self.optimizer.step()
            
            total_loss += loss.item()
            total_mae += torch.mean(torch.abs(point_pred - y_batch)).item()
            n_batches += 1
        
        return {
            "loss": total_loss / n_batches,
            "mae": total_mae / n_batches
        }
    
    def validate(
        self,
        val_loader: DataLoader
    ) -> Dict[str, float]:
        """Validate model."""
        self.model.eval()
        
        total_loss = 0.0
        total_mae = 0.0
        n_batches = 0
        
        all_preds = []
        all_true = []
        
        with torch.no_grad():
            for X_batch, y_batch in val_loader:
                X_batch = X_batch.to(self.device)
                y_batch = y_batch.to(self.device).unsqueeze(1)
                
                point_pred, _ = self.model(X_batch)
                
                loss = self.point_loss_fn(point_pred, y_batch)
                
                total_loss += loss.item()
                total_mae += torch.mean(torch.abs(point_pred - y_batch)).item()
                
                all_preds.append(point_pred.cpu().numpy())
                all_true.append(y_batch.cpu().numpy())
                
                n_batches += 1
        
        all_preds = np.concatenate(all_preds).flatten()
        all_true = np.concatenate(all_true).flatten()
        
        metrics = evaluate_vol_forecast(all_true, all_preds, prefix="val")
        
        return {
            "loss": total_loss / n_batches,
            "mae": total_mae / n_batches,
            **metrics
        }
    
    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        epochs: int = 100,
        batch_size: int = 32,
        patience: int = 10,
        min_delta: float = 1e-4,
        verbose: bool = True
    ) -> Dict:
        """
        Train model with early stopping.
        
        Args:
            X_train, y_train: Training data
            X_val, y_val: Validation data
            epochs: Max epochs
            batch_size: Batch size
            patience: Early stopping patience
            min_delta: Minimum improvement
            verbose: Print progress
            
        Returns:
            Training history
        """
        # Create sequences
        seq_len = self.model.sequence_length
        X_train_seq, y_train_seq = self.create_sequences(X_train, y_train, seq_len)
        X_val_seq, y_val_seq = self.create_sequences(X_val, y_val, seq_len)
        
        # Create dataloaders
        train_dataset = TensorDataset(
            torch.FloatTensor(X_train_seq),
            torch.FloatTensor(y_train_seq)
        )
        val_dataset = TensorDataset(
            torch.FloatTensor(X_val_seq),
            torch.FloatTensor(y_val_seq)
        )
        
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
        
        best_val_loss = float('inf')
        patience_counter = 0
        best_state = None
        
        for epoch in range(epochs):
            # Train
            train_metrics = self.train_epoch(train_loader, epoch)
            
            # Validate
            val_metrics = self.validate(val_loader)
            
            # Record history
            self.history["train_loss"].append(train_metrics["loss"])
            self.history["val_loss"].append(val_metrics["loss"])
            self.history["train_mae"].append(train_metrics["mae"])
            self.history["val_mae"].append(val_metrics["mae"])
            
            if verbose and (epoch % 10 == 0 or epoch == epochs - 1):
                print(f"Epoch {epoch:3d} | "
                      f"Train Loss: {train_metrics['loss']:.6f} | "
                      f"Val Loss: {val_metrics['loss']:.6f} | "
                      f"Val MAE: {val_metrics['mae']:.6f}")
            
            # Early stopping
            val_loss = val_metrics["loss"]
            if val_loss < best_val_loss - min_delta:
                best_val_loss = val_loss
                patience_counter = 0
                best_state = {
                    "model": self.model.state_dict(),
                    "optimizer": self.optimizer.state_dict(),
                    "epoch": epoch,
                    "val_loss": val_loss,
                }
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    if verbose:
                        print(f"Early stopping at epoch {epoch}")
                    break
        
        # Restore best model
        if best_state:
            self.model.load_state_dict(best_state["model"])
            self.optimizer.load_state_dict(best_state["optimizer"])
        
        return self.history
    
    def predict(
        self,
        X: np.ndarray,
        return_uncertainty: bool = False
    ) -> np.ndarray | Tuple[np.ndarray, np.ndarray]:
        """
        Generate predictions.
        
        Args:
            X: Input features (n_samples, n_features)
            return_uncertainty: Also return prediction intervals
            
        Returns:
            Predictions (and optionally uncertainty)
        """
        self.model.eval()
        
        # Create sequences (use last sequence_length samples for each prediction)
        seq_len = self.model.sequence_length
        n_samples = X.shape[0]
        
        if n_samples <= seq_len:
            raise ValueError(f"Need at least {seq_len + 1} samples, got {n_samples}")
        
        # Create sequences ending at each prediction point
        X_seq = np.zeros((n_samples - seq_len, seq_len, X.shape[1]))
        for i in range(n_samples - seq_len):
            X_seq[i] = X[i:i+seq_len]
        
        dataset = TensorDataset(torch.FloatTensor(X_seq))
        loader = DataLoader(dataset, batch_size=64, shuffle=False)
        
        all_preds = []
        all_uncertainty = []
        
        with torch.no_grad():
            for (X_batch,) in loader:
                X_batch = X_batch.to(self.device)
                point_pred, interval_pred = self.model(X_batch)
                all_preds.append(point_pred.cpu().numpy())
                
                if return_uncertainty and interval_pred is not None:
                    # Convert log-variance to std
                    uncertainty = torch.exp(0.5 * interval_pred).cpu().numpy()
                    all_uncertainty.append(uncertainty)
        
        preds = np.concatenate(all_preds).flatten()
        
        # Pad beginning with NaN (no prediction for first seq_len samples)
        preds_full = np.full(n_samples, np.nan)
        preds_full[seq_len:] = preds
        
        if return_uncertainty and all_uncertainty:
            unc = np.concatenate(all_uncertainty).flatten()
            unc_full = np.full(n_samples, np.nan)
            unc_full[seq_len:] = unc
            return preds_full, unc_full
        
        return preds_full
    
    def save(self, path: str | Path) -> None:
        """Save model checkpoint."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        checkpoint = {
            "model_state": self.model.state_dict(),
            "optimizer_state": self.optimizer.state_dict(),
            "model_config": self.model.get_config(),
            "trainer_config": {
                "learning_rate": self.learning_rate,
                "weight_decay": self.weight_decay,
                "gradient_clip": self.gradient_clip,
            },
            "history": self.history,
        }
        
        torch.save(checkpoint, path)
        
        # Also save config as JSON for inspection
        with open(path.with_suffix(".json"), "w") as f:
            json.dump({
                "model_config": checkpoint["model_config"],
                "trainer_config": checkpoint["trainer_config"],
                "history": {k: [float(v) for v in vals] for k, vals in self.history.items()},
            }, f, indent=2)
    
    @classmethod
    def load(cls, path: str | Path, device: str = "auto") -> "RVLSTMTrainer":
        """Load model checkpoint."""
        path = Path(path)
        checkpoint = torch.load(path, map_location="cpu")
        
        # Recreate model
        model = RVLSTMModel(**checkpoint["model_config"])
        model.load_state_dict(checkpoint["model_state"])
        
        # Recreate trainer
        trainer = cls(
            model=model,
            learning_rate=checkpoint["trainer_config"]["learning_rate"],
            weight_decay=checkpoint["trainer_config"]["weight_decay"],
            gradient_clip=checkpoint["trainer_config"]["gradient_clip"],
            device=device
        )
        trainer.optimizer.load_state_dict(checkpoint["optimizer_state"])
        trainer.history = checkpoint["history"]
        
        return trainer


def train_lstm_model(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    sequence_length: int = 30,
    hidden_dim: int = 64,
    num_layers: int = 2,
    dropout: float = 0.2,
    learning_rate: float = 1e-3,
    epochs: int = 100,
    batch_size: int = 32,
    patience: int = 10,
    output_dir: str = "data/models/rv_forecaster/"
) -> RVLSTMTrainer:
    """
    Train LSTM model on RV forecasting task.
    
    Returns trained trainer with history and best model.
    """
    from packages.ml.data.features import build_features, prepare_xy
    
    print("\nBuilding features for LSTM...")
    train_features = build_features(train_df)
    val_features = build_features(val_df)
    test_features = build_features(test_df)
    
    X_train, y_train, feature_names = prepare_xy(train_features)
    X_val, y_val, _ = prepare_xy(val_features)
    X_test, y_test, _ = prepare_xy(test_features)
    
    print(f"Features: {len(feature_names)}")
    print(f"Train: {X_train.shape}, Val: {X_val.shape}, Test: {X_test.shape}")
    
    # Standardize features (fit on train only)
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    X_test_scaled = scaler.transform(X_test)
    
    # Create model
    model = RVLSTMModel(
        input_dim=X_train.shape[1],
        hidden_dim=hidden_dim,
        num_layers=num_layers,
        dropout=dropout,
        sequence_length=sequence_length
    )
    
    trainer = RVLSTMTrainer(
        model=model,
        learning_rate=learning_rate,
        weight_decay=1e-5
    )
    
    print("\nTraining LSTM...")
    history = trainer.fit(
        X_train_scaled, y_train,
        X_val_scaled, y_val,
        epochs=epochs,
        batch_size=batch_size,
        patience=patience
    )
    
    # Evaluate on test
    test_preds = trainer.predict(X_test_scaled)
    # Align (first seq_len are NaN)
    valid_mask = ~np.isnan(test_preds)
    if valid_mask.sum() > 0:
        test_metrics = evaluate_vol_forecast(
            y_test[valid_mask],
            test_preds[valid_mask],
            prefix="lstm_test"
        )
        print(f"\nTest MAE: {test_metrics['lstm_test_mae']:.6f}")
        print(f"Test RMSE: {test_metrics['lstm_test_rmse']:.6f}")
        print(f"Test QLIKE: {test_metrics['lstm_test_qlike']:.6f}")
    
    # Save
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    trainer.save(output_path / "lstm_model.pt")
    
    # Save scaler
    joblib.dump(scaler, output_path / "lstm_scaler.joblib")
    
    # Save feature names
    with open(output_path / "lstm_features.json", "w") as f:
        json.dump(feature_names, f)
    
    return trainer