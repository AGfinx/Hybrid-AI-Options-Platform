"""
HyperIV Trainer

Training loop with validation, checkpointing, early stopping.
"""

import json
import torch
import torch.nn as nn
from pathlib import Path
from typing import Dict, List, Optional, Any

from torch.utils.data import DataLoader
from torch.optim import AdamW
from torch.optim.lr_scheduler import ReduceLROnPlateau

from packages.quant.hyperiv.model import HyperIVModel
from packages.quant.hyperiv.loss import HyperIVLoss, compute_arbitrage_metrics
from packages.quant.hyperiv.dataset import HyperIVDataset, collate_hyperiv


class HyperIVTrainer:
    """
    Trainer for HyperIV model.
    
    Features:
    - Mixed precision training
    - Gradient accumulation
    - Learning rate scheduling
    - Early stopping
    - Checkpoint saving
    - Arbitrage metric tracking
    """
    
    def __init__(
        self,
        model: HyperIVModel,
        loss_fn: HyperIVLoss,
        learning_rate: float = 1e-3,
        weight_decay: float = 1e-5,
        device: str = "auto",
        gradient_clip: float = 1.0,
        mixed_precision: bool = True,
        accumulation_steps: int = 1
    ):
        self.model = model
        self.loss_fn = loss_fn
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.gradient_clip = gradient_clip
        self.mixed_precision = mixed_precision
        self.accumulation_steps = accumulation_steps
        
        if device == "auto":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)
        
        self.model.to(self.device)
        self.loss_fn.to(self.device)
        
        # Optimizer
        self.optimizer = AdamW(
            model.parameters(),
            lr=learning_rate,
            weight_decay=weight_decay
        )
        
        # LR scheduler
        self.scheduler = ReduceLROnPlateau(
            self.optimizer, mode="min", factor=0.5, patience=5, verbose=True
        )
        
        # Mixed precision
        self.scaler = torch.cuda.amp.GradScaler(enabled=mixed_precision and self.device.type == "cuda")
        
        # History
        self.history = {
            "train_loss": [],
            "train_data_loss": [],
            "train_calendar_loss": [],
            "train_butterfly_loss": [],
            "val_loss": [],
            "val_data_loss": [],
            "val_calendar_loss": [],
            "val_butterfly_loss": [],
            "val_arbitrage": [],
            "lr": [],
        }
    
    def train_epoch(
        self,
        train_loader: DataLoader,
        epoch: int
    ) -> Dict[str, float]:
        """Train for one epoch."""
        self.model.train()
        
        total_losses = {k: 0.0 for k in ["total", "data", "calendar", "butterfly", "smoothness", "variance", "reg"]}
        n_batches = 0
        
        self.optimizer.zero_grad()
        
        for batch_idx, batch in enumerate(train_loader):
            # Move to device
            batch = {k: v.to(self.device) for k, v in batch.items()}
            
            # Forward with mixed precision
            with torch.cuda.amp.autocast(enabled=self.mixed_precision and self.device.type == "cuda"):
                iv_pred, uncertainty = self.model(
                    batch["moneyness"],
                    batch["time_to_expiry"],
                    batch["spot"],
                    batch["atm_iv"],
                    batch["expiry_idx"]
                )
                
                loss, components = self.loss_fn(self.model, batch, iv_pred, uncertainty)
            
            # Scale loss for accumulation
            loss = loss / self.accumulation_steps
            
            # Backward
            self.scaler.scale(loss).backward()
            
            # Accumulate
            for k, v in components.items():
                total_losses[k] += v.item()
            n_batches += 1
            
            # Step
            if (batch_idx + 1) % self.accumulation_steps == 0:
                self.scaler.unscale_(self.optimizer)
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.gradient_clip)
                self.scaler.step(self.optimizer)
                self.scaler.update()
                self.optimizer.zero_grad()
        
        # Average losses
        avg_losses = {k: v / n_batches for k, v in total_losses.items()}
        
        return avg_losses
    
    @torch.no_grad()
    def validate(
        self,
        val_loader: DataLoader,
        strikes_eval: Optional[torch.Tensor] = None,
        expiries_eval: Optional[torch.Tensor] = None,
        spot_eval: float = 65000.0,
        atm_iv_eval: float = 0.55
    ) -> Dict[str, float]:
        """Validate model."""
        self.model.eval()
        
        total_losses = {k: 0.0 for k in ["total", "data", "calendar", "butterfly", "smoothness", "variance", "reg"]}
        n_batches = 0
        
        all_preds = []
        all_true = []
        
        for batch in val_loader:
            batch = {k: v.to(self.device) for k, v in batch.items()}
            
            with torch.cuda.amp.autocast(enabled=self.mixed_precision and self.device.type == "cuda"):
                iv_pred, _ = self.model(
                    batch["moneyness"],
                    batch["time_to_expiry"],
                    batch["spot"],
                    batch["atm_iv"],
                    batch["expiry_idx"]
                )
                
                loss, components = self.loss_fn(self.model, batch, iv_pred)
            
            for k, v in components.items():
                total_losses[k] += v.item()
            n_batches += 1
            
            all_preds.append(iv_pred.cpu())
            all_true.append(batch["iv_true"].cpu())
        
        avg_losses = {k: v / n_batches for k, v in total_losses.items()}
        
        # Overall metrics
        all_preds = torch.cat(all_preds)
        all_true = torch.cat(all_true)
        
        mse = nn.functional.mse_loss(all_preds, all_true).item()
        mae = nn.functional.l1_loss(all_preds, all_true).item()
        
        # Arbitrage metrics
        if strikes_eval is not None and expiries_eval is not None:
            arb_metrics = compute_arbitrage_metrics(
                self.model, strikes_eval, expiries_eval, spot_eval, atm_iv_eval
            )
            avg_losses.update(arb_metrics)
        
        avg_losses["mse"] = mse
        avg_losses["mae"] = mae
        
        return avg_losses
    
    def fit(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader,
        epochs: int = 100,
        patience: int = 15,
        min_delta: float = 1e-4,
        strikes_eval: Optional[torch.Tensor] = None,
        expiries_eval: Optional[torch.Tensor] = None,
        spot_eval: float = 65000.0,
        atm_iv_eval: float = 0.55,
        verbose: bool = True
    ) -> Dict:
        """
        Train with early stopping.
        """
        best_val_loss = float('inf')
        patience_counter = 0
        best_state = None
        
        for epoch in range(epochs):
            # Train
            train_losses = self.train_epoch(train_loader, epoch)
            
            # Validate
            val_losses = self.validate(
                val_loader, strikes_eval, expiries_eval, spot_eval, atm_iv_eval
            )
            
            # Record
            for k, v in train_losses.items():
                self.history[f"train_{k}"].append(v)
            for k, v in val_losses.items():
                self.history[f"val_{k}"].append(v)
            self.history["lr"].append(self.optimizer.param_groups[0]["lr"])
            
            # LR scheduling
            self.scheduler.step(val_losses["total"])
            
            if verbose:
                print(f"Epoch {epoch:3d} | "
                      f"Train: {train_losses['total']:.6f} (data:{train_losses['data']:.4f} cal:{train_losses['calendar']:.4f} bf:{train_losses['butterfly']:.4f}) | "
                      f"Val: {val_losses['total']:.6f} (data:{val_losses['data']:.4f} cal:{val_losses['calendar']:.4f} bf:{val_losses['butterfly']:.4f}) | "
                      f"MAE: {val_losses.get('mae', 0):.6f} | "
                      f"Arb: {val_losses.get('total_violations', 0)}")
            
            # Early stopping
            val_loss = val_losses["total"]
            if val_loss < best_val_loss - min_delta:
                best_val_loss = val_loss
                patience_counter = 0
                best_state = {
                    "model": self.model.state_dict(),
                    "optimizer": self.optimizer.state_dict(),
                    "scheduler": self.scheduler.state_dict(),
                    "epoch": epoch,
                    "val_loss": val_loss,
                }
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    if verbose:
                        print(f"Early stopping at epoch {epoch}")
                    break
        
        # Restore best
        if best_state:
            self.model.load_state_dict(best_state["model"])
            self.optimizer.load_state_dict(best_state["optimizer"])
            self.scheduler.load_state_dict(best_state["scheduler"])
        
        return self.history
    
    @torch.no_grad()
    def predict(
        self,
        moneyness: torch.Tensor,
        time_to_expiry: torch.Tensor,
        spot: torch.Tensor,
        atm_iv: torch.Tensor,
        expiry_idx: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Generate predictions."""
        self.model.eval()
        
        moneyness = moneyness.to(self.device)
        time_to_expiry = time_to_expiry.to(self.device)
        spot = spot.to(self.device)
        atm_iv = atm_iv.to(self.device)
        if expiry_idx is not None:
            expiry_idx = expiry_idx.to(self.device)
        
        with torch.cuda.amp.autocast(enabled=self.mixed_precision and self.device.type == "cuda"):
            output, uncertainty = self.model(
                moneyness, time_to_expiry, spot, atm_iv, expiry_idx
            )
        
        return output.cpu(), uncertainty.cpu()
    
    def save(self, path: str | Path) -> None:
        """Save checkpoint."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        checkpoint = {
            "model_state": self.model.state_dict(),
            "optimizer_state": self.optimizer.state_dict(),
            "scheduler_state": self.scheduler.state_dict(),
            "model_config": self.model.get_config(),
            "loss_config": {
                "weight_data": self.loss_fn.weight_data,
                "weight_calendar": self.loss_fn.weight_calendar,
                "weight_butterfly": self.loss_fn.weight_butterfly,
                "weight_smooth": self.loss_fn.weight_smooth,
                "weight_variance": self.loss_fn.weight_variance,
                "weight_reg": self.loss_fn.weight_reg,
            },
            "trainer_config": {
                "learning_rate": self.learning_rate,
                "weight_decay": self.weight_decay,
                "gradient_clip": self.gradient_clip,
                "mixed_precision": self.mixed_precision,
                "accumulation_steps": self.accumulation_steps,
            },
            "history": {k: [float(v) for v in vals] for k, vals in self.history.items()},
        }
        
        torch.save(checkpoint, path)
        
        # Save config JSON
        with open(path.with_suffix(".json"), "w") as f:
            json.dump({
                "model_config": checkpoint["model_config"],
                "loss_config": checkpoint["loss_config"],
                "trainer_config": checkpoint["trainer_config"],
                "history": checkpoint["history"],
            }, f, indent=2)
    
    @classmethod
    def load(cls, path: str | Path, device: str = "auto") -> "HyperIVTrainer":
        """Load checkpoint."""
        path = Path(path)
        checkpoint = torch.load(path, map_location="cpu")
        
        model = HyperIVModel(**checkpoint["model_config"])
        model.load_state_dict(checkpoint["model_state"])
        
        loss_fn = HyperIVLoss(**checkpoint["loss_config"])
        
        trainer = cls(
            model=model,
            loss_fn=loss_fn,
            learning_rate=checkpoint["trainer_config"]["learning_rate"],
            weight_decay=checkpoint["trainer_config"]["weight_decay"],
            gradient_clip=checkpoint["trainer_config"]["gradient_clip"],
            mixed_precision=checkpoint["trainer_config"]["mixed_precision"],
            accumulation_steps=checkpoint["trainer_config"]["accumulation_steps"],
            device=device
        )
        
        trainer.optimizer.load_state_dict(checkpoint["optimizer_state"])
        trainer.scheduler.load_state_dict(checkpoint["scheduler_state"])
        trainer.history = checkpoint["history"]
        
        return trainer


def train_hyperiv_model(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    hidden_dim: int = 128,
    num_layers: int = 4,
    dropout: float = 0.1,
    learning_rate: float = 1e-3,
    weight_decay: float = 1e-5,
    batch_size: int = 256,
    epochs: int = 200,
    patience: int = 20,
    loss_weights: Dict[str, float] = None,
    output_dir: str = "data/models/hyperiv/",
    device: str = "auto"
) -> HyperIVTrainer:
    """
    Train HyperIV model.
    """
    print("Creating datasets...")
    train_loader, val_loader, test_loader, expiry_encoder = create_hyperiv_dataloaders(
        train_df, val_df, test_df, batch_size=batch_size
    )
    
    print(f"Train batches: {len(train_loader)}, Val: {len(val_loader)}, Test: {len(test_loader)}")
    print(f"Expiries: {expiry_encoder.classes_}")
    
    # Create model
    model = HyperIVModel(
        input_dim=4,
        hidden_dim=hidden_dim,
        num_layers=num_layers,
        dropout=dropout,
        output_param="total_variance",
        use_residual=True,
        max_expiries=len(expiry_encoder.classes_) + 5
    )
    
    # Loss
    if loss_weights is None:
        loss_weights = {
            "weight_data": 1.0,
            "weight_calendar": 10.0,
            "weight_butterfly": 10.0,
            "weight_smooth": 1.0,
            "weight_variance": 5.0,
            "weight_reg": 0.01,
        }
    
    loss_fn = HyperIVLoss(**loss_weights)
    
    # Trainer
    trainer = HyperIVTrainer(
        model=model,
        loss_fn=loss_fn,
        learning_rate=learning_rate,
        weight_decay=weight_decay,
        device=device,
        mixed_precision=True,
        accumulation_steps=1
    )
    
    # Evaluation grid for arbitrage metrics
    strikes_eval = torch.linspace(-0.5, 0.5, 20)
    expiries_eval = torch.tensor([0.05, 0.1, 0.25, 0.5, 1.0])
    
    print("\nTraining HyperIV...")
    history = trainer.fit(
        train_loader, val_loader,
        epochs=epochs,
        patience=patience,
        strikes_eval=strikes_eval,
        expiries_eval=expiries_eval,
        spot_eval=65000.0,
        atm_iv_eval=0.55
    )
    
    # Final test evaluation
    print("\nEvaluating on test set...")
    test_metrics = trainer.validate(
        test_loader, strikes_eval, expiries_eval, 65000.0, 0.55
    )
    print(f"Test MAE: {test_metrics.get('mae', 'N/A'):.6f}")
    print(f"Test MSE: {test_metrics.get('mse', 'N/A'):.6f}")
    print(f"Calendar violations: {test_metrics.get('calendar_violations', 'N/A')}")
    print(f"Butterfly violations: {test_metrics.get('butterfly_violations', 'N/A')}")
    
    # Save
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    trainer.save(output_path / "hyperiv_model.pt")
    
    # Save expiry encoder
    import joblib
    joblib.dump(expiry_encoder, output_path / "expiry_encoder.joblib")
    
    return trainer