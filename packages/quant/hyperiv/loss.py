"""
HyperIV Loss Functions

Implements physics-informed losses for no-arbitrage constraints:
- Data loss (MSE on IV)
- Calendar arbitrage penalty
- Butterfly arbitrage penalty  
- Smoothness regularization
- Non-negative variance
- Weighted total loss
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Optional, Tuple


class HyperIVLoss(nn.Module):
    """
    Composite loss for HyperIV model.
    
    L_total = w_data * L_data + w_cal * L_calendar + w_bf * L_butterfly 
            + w_smooth * L_smooth + w_var * L_variance + w_reg * L_reg
    """
    
    def __init__(
        self,
        weight_data: float = 1.0,
        weight_calendar: float = 10.0,
        weight_butterfly: float = 10.0,
        weight_smooth: float = 1.0,
        weight_variance: float = 5.0,
        weight_reg: float = 0.01,
        calendar_margin: float = 1e-4,
        butterfly_margin: float = 1e-4,
    ):
        super().__init__()
        
        self.weight_data = weight_data
        self.weight_calendar = weight_calendar
        self.weight_butterfly = weight_butterfly
        self.weight_smooth = weight_smooth
        self.weight_variance = weight_variance
        self.weight_reg = weight_reg
        self.calendar_margin = calendar_margin
        self.butterfly_margin = butterfly_margin
        
        self.mse = nn.MSELoss()
    
    def forward(
        self,
        model: nn.Module,
        batch: Dict[str, torch.Tensor],
        iv_pred: torch.Tensor,
        uncertainty: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """
        Compute total loss and individual components.
        
        Args:
            model: HyperIV model
            batch: Input batch with keys:
                - moneyness, time_to_expiry, spot, atm_iv, expiry_idx
                - iv_true: Ground truth IV
            iv_pred: Model predictions
            uncertainty: Optional uncertainty predictions
            
        Returns:
            total_loss, loss_components_dict
        """
        iv_true = batch["iv_true"]
        
        # 1. Data loss
        if uncertainty is not None:
            # Heteroscedastic loss: NLL of Gaussian with predicted variance
            # L = 0.5 * (log(var) + (y - pred)^2 / var)
            var = uncertainty ** 2 + 1e-8
            data_loss = 0.5 * (torch.log(var) + (iv_true - iv_pred) ** 2 / var).mean()
        else:
            data_loss = self.mse(iv_pred, iv_true)
        
        # 2. Calendar arbitrage: variance should increase with time to expiry
        # For same strike, longer expiry should have >= variance
        calendar_loss = self._calendar_arbitrage_loss(
            model, batch, iv_pred
        )
        
        # 3. Butterfly arbitrage: convexity in strike
        # For same expiry, IV smile should be convex
        butterfly_loss = self._butterfly_arbitrage_loss(
            model, batch, iv_pred
        )
        
        # 4. Smoothness: penalize large second derivatives
        smoothness_loss = self._smoothness_loss(
            model, batch, iv_pred
        )
        
        # 5. Non-negative variance (already enforced by Softplus, but extra check)
        variance_loss = self._variance_positivity_loss(iv_pred, batch)
        
        # 6. Regularization (weight decay handled by optimizer, but can add extra)
        reg_loss = self._regularization_loss(model)
        
        # Weighted total
        total_loss = (
            self.weight_data * data_loss +
            self.weight_calendar * calendar_loss +
            self.weight_butterfly * butterfly_loss +
            self.weight_smooth * smoothness_loss +
            self.weight_variance * variance_loss +
            self.weight_reg * reg_loss
        )
        
        components = {
            "total": total_loss,
            "data": data_loss,
            "calendar": calendar_loss,
            "butterfly": butterfly_loss,
            "smoothness": smoothness_loss,
            "variance": variance_loss,
            "reg": reg_loss,
        }
        
        return total_loss, components
    
    def _calendar_arbitrage_loss(
        self,
        model: nn.Module,
        batch: Dict[str, torch.Tensor],
        iv_pred: torch.Tensor
    ) -> torch.Tensor:
        """
        Calendar spread arbitrage penalty.
        
        For European options, total variance w(k, T) = iv^2 * T
        should be non-decreasing in T for fixed k (moneyness).
        
        Penalty: max(0, w(T1) - w(T2) + margin) for T1 < T2
        """
        # Need to evaluate at multiple expiries for same strikes
        # This is approximate - in practice, sample strikes across expiries
        
        # Get unique expiries in batch
        expiries = batch["time_to_expiry"].unique()
        if len(expiries) < 2:
            return torch.tensor(0.0, device=iv_pred.device)
        
        expiries_sorted = torch.sort(expiries)[0]
        moneyness_vals = batch["moneyness"].unique()
        
        loss = 0.0
        count = 0
        
        # Sample a few moneyness levels
        for k in moneyness_vals[:5]:  # Limit for efficiency
            # Get spot and atm_iv for this moneyness
            mask = batch["moneyness"] == k
            if mask.sum() < 2:
                continue
            
            spot = batch["spot"][mask].mean()
            atm_iv = batch["atm_iv"][mask].mean()
            
            # Evaluate model at all expiries for this strike
            k_tensor = k.repeat(len(expiries_sorted))
            T_tensor = expiries_sorted
            spot_tensor = spot.repeat(len(expiries_sorted))
            atm_iv_tensor = atm_iv.repeat(len(expiries_sorted))
            
            with torch.enable_grad():
                w_pred, _ = model(k_tensor, T_tensor, spot_tensor, atm_iv_tensor)
            
            # Total variance should be non-decreasing in T
            w_diff = w_pred[:-1] - w_pred[1:] + self.calendar_margin
            loss += F.relu(w_diff).sum()
            count += len(w_diff)
        
        return loss / (count + 1e-8)
    
    def _butterfly_arbitrage_loss(
        self,
        model: nn.Module,
        batch: Dict[str, torch.Tensor],
        iv_pred: torch.Tensor
    ) -> torch.Tensor:
        """
        Butterfly arbitrage penalty (convexity in strike).
        
        For fixed expiry, call price should be convex in strike.
        Equivalent: implied variance should be convex in log-moneyness.
        
        Using Breeden-Litzenberger: d^2C/dK^2 = q(K) >= 0
        For implied vol: d^2w/dk^2 >= 0 where k = log(K/S)
        """
        expiries = batch["time_to_expiry"].unique()
        
        loss = 0.0
        count = 0
        
        for T in expiries:
            # Get data for this expiry
            mask = batch["time_to_expiry"] == T
            if mask.sum() < 3:
                continue
            
            # Sort by moneyness
            k_vals = batch["moneyness"][mask]
            sort_idx = torch.argsort(k_vals)
            k_sorted = k_vals[sort_idx]
            
            # Need at least 3 points for second derivative
            if len(k_sorted) < 3:
                continue
            
            spot = batch["spot"][mask].mean()
            atm_iv = batch["atm_iv"][mask].mean()
            
            # Evaluate model at sorted strikes
            k_tensor = k_sorted
            T_tensor = T.repeat(len(k_sorted))
            spot_tensor = spot.repeat(len(k_sorted))
            atm_iv_tensor = atm_iv.repeat(len(k_sorted))
            
            with torch.enable_grad():
                w_pred, _ = model(k_tensor, T_tensor, spot_tensor, atm_iv_tensor)
            
            # Second derivative penalty
            # Convexity: d^2w/dk^2 >= 0
            # Approximate with finite differences
            if len(w_pred) >= 3:
                # d^2w/dk^2 ≈ (w_{i+1} - 2w_i + w_{i-1}) / (dk)^2
                dk = k_sorted[1] - k_sorted[0]
                if dk > 1e-8:
                    second_deriv = (w_pred[2:] - 2*w_pred[1:-1] + w_pred[:-2]) / (dk ** 2)
                    # Penalize negative convexity
                    loss += F.relu(-second_deriv + self.butterfly_margin).sum()
                    count += len(second_deriv)
        
        return loss / (count + 1e-8)
    
    def _smoothness_loss(
        self,
        model: nn.Module,
        batch: Dict[str, torch.Tensor],
        iv_pred: torch.Tensor
    ) -> torch.Tensor:
        """
        Smoothness regularization: penalize large second derivatives in both k and T.
        """
        # Simple version: penalize gradient norm of predictions w.r.t inputs
        loss = 0.0
        count = 0
        
        for param in model.parameters():
            if param.requires_grad and param.grad is not None:
                loss += param.grad.norm(2).item()
                count += 1
        
        return torch.tensor(loss / (count + 1e-8), device=iv_pred.device)
    
    def _variance_positivity_loss(
        self,
        iv_pred: torch.Tensor,
        batch: Dict[str, torch.Tensor]
    ) -> torch.Tensor:
        """
        Ensure predicted variance is positive.
        (Already enforced by Softplus, but add soft penalty)
        """
        # Total variance = iv^2 * T
        T = batch["time_to_expiry"]
        total_var = iv_pred ** 2 * T
        
        # Penalize very small variance
        min_var = 1e-6
        loss = F.relu(min_var - total_var).mean()
        
        return loss
    
    def _regularization_loss(self, model: nn.Module) -> torch.Tensor:
        """L2 regularization on model weights."""
        loss = 0.0
        for param in model.parameters():
            if param.requires_grad:
                loss += param.norm(2)
        return loss


def compute_arbitrage_metrics(
    model: nn.Module,
    strikes: torch.Tensor,
    expiries: torch.Tensor,
    spot: float,
    atm_iv: float
) -> Dict[str, float]:
    """
    Compute arbitrage violation metrics for evaluation.
    
    Returns:
        Dict with calendar_violations, butterfly_violations, etc.
    """
    model.eval()
    
    with torch.no_grad():
        # Create grid
        K, T = torch.meshgrid(strikes, expiries, indexing='ij')
        k = torch.log(K / spot).flatten()
        T_flat = T.flatten()
        spot_tensor = torch.full_like(k, spot)
        atm_iv_tensor = torch.full_like(k, atm_iv)
        
        w_pred, _ = model(k, T_flat, spot_tensor, atm_iv_tensor)
        w_grid = w_pred.reshape(len(strikes), len(expiries))
        iv_grid = torch.sqrt(w_grid / (T.unsqueeze(0) + 1e-8))
    
    # Calendar arbitrage check
    calendar_violations = 0
    for i in range(len(strikes)):
        for j in range(len(expiries) - 1):
            if w_grid[i, j] > w_grid[i, j + 1] + 1e-4:
                calendar_violations += 1
    
    # Butterfly arbitrage check
    butterfly_violations = 0
    for j in range(len(expiries)):
        if len(strikes) >= 3:
            for i in range(1, len(strikes) - 1):
                k1, k2, k3 = strikes[i-1], strikes[i], strikes[i+1]
                w1, w2, w3 = w_grid[i-1, j], w_grid[i, j], w_grid[i+1, j]
                
                lambda_w = (k3 - k2) / (k3 - k1)
                convex_bound = lambda_w * w1 + (1 - lambda_w) * w3
                
                if w2 > convex_bound + 1e-4:
                    butterfly_violations += 1
    
    return {
        "calendar_violations": calendar_violations,
        "butterfly_violations": butterfly_violations,
        "total_violations": calendar_violations + butterfly_violations,
    }