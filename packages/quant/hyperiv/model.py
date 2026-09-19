"""
HyperIV Model Architecture

Physics-Informed Neural Network for implied volatility surface.
Inputs: moneyness, time to expiry, spot, market observables
Output: Implied volatility or total implied variance
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple


class HyperIVModel(nn.Module):
    """
    HyperIV: Neural Volatility Surface with Physics Constraints.
    
    Architecture:
    - Input embedding layer
    - Multiple hidden layers with residual connections
    - Output head for implied variance (ensures positivity)
    - Optional: Separate heads for different expiries (mixture of experts)
    
    Physics constraints enforced via loss:
    - Non-negative variance
    - Calendar spread arbitrage (variance increases with time)
    - Butterfly arbitrage (convexity in strike)
    - Smoothness regularization
    """
    
    def __init__(
        self,
        input_dim: int = 4,           # moneyness, T, spot, atm_iv
        hidden_dim: int = 128,
        num_layers: int = 4,
        dropout: float = 0.1,
        activation: str = "gelu",
        output_param: str = "total_variance",  # or "implied_vol"
        use_residual: bool = True,
        expiry_embedding_dim: int = 8,
        max_expiries: int = 20
    ):
        super().__init__()
        
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.output_param = output_param
        self.use_residual = use_residual
        
        # Activation
        act_map = {
            "relu": nn.ReLU,
            "gelu": nn.GELU,
            "silu": nn.SiLU,
            "tanh": nn.Tanh,
        }
        self.activation = act_map.get(activation, nn.GELU)()
        
        # Input projection
        self.input_proj = nn.Linear(input_dim, hidden_dim)
        
        # Expiry embedding (for calendar consistency)
        self.expiry_embedding = nn.Embedding(max_expiries, expiry_embedding_dim)
        self.expiry_proj = nn.Linear(expiry_embedding_dim, hidden_dim)
        
        # Hidden layers with residual connections
        self.layers = nn.ModuleList()
        self.layer_norms = nn.ModuleList()
        
        for i in range(num_layers):
            self.layers.append(nn.Linear(hidden_dim, hidden_dim))
            self.layer_norms.append(nn.LayerNorm(hidden_dim))
        
        # Output head
        if output_param == "total_variance":
            # Predict total variance (ensures positivity via softplus)
            self.output_head = nn.Sequential(
                nn.Linear(hidden_dim, hidden_dim // 2),
                self.activation,
                nn.Dropout(dropout),
                nn.Linear(hidden_dim // 2, 1),
                nn.Softplus()  # > 0
            )
        else:
            # Predict implied volatility directly
            self.output_head = nn.Sequential(
                nn.Linear(hidden_dim, hidden_dim // 2),
                self.activation,
                nn.Dropout(dropout),
                nn.Linear(hidden_dim // 2, 1),
                nn.Softplus()  # > 0
            )
        
        # Uncertainty head (optional)
        self.uncertainty_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            self.activation,
            nn.Linear(hidden_dim // 2, 1),
            nn.Softplus()
        )
        
        # Initialize weights
        self.apply(self._init_weights)
    
    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            nn.init.xavier_uniform_(module.weight)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.LayerNorm):
            nn.init.ones_(module.weight)
            nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            nn.init.normal_(module.weight, mean=0, std=0.02)
    
    def forward(
        self,
        moneyness: torch.Tensor,
        time_to_expiry: torch.Tensor,
        spot: torch.Tensor,
        atm_iv: torch.Tensor,
        expiry_idx: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass.
        
        Args:
            moneyness: log(K/S) - (batch,)
            time_to_expiry: T in years - (batch,)
            spot: Spot price - (batch,)
            atm_iv: ATM implied vol - (batch,)
            expiry_idx: Optional expiry index for embedding - (batch,)
            
        Returns:
            total_variance: (batch,) or implied_vol
            uncertainty: (batch,)
        """
        # Stack inputs
        x = torch.stack([moneyness, time_to_expiry, spot, atm_iv], dim=-1)  # (batch, 4)
        
        # Input projection
        h = self.input_proj(x)  # (batch, hidden_dim)
        
        # Add expiry embedding if provided
        if expiry_idx is not None:
            expiry_emb = self.expiry_embedding(expiry_idx)  # (batch, expiry_emb_dim)
            h = h + self.expiry_proj(expiry_emb)
        
        # Hidden layers with residual connections
        for i, (layer, ln) in enumerate(zip(self.layers, self.layer_norms)):
            residual = h
            h = layer(h)
            h = ln(h)
            h = self.activation(h)
            if self.use_residual:
                h = h + residual
        
        # Output
        output = self.output_head(h).squeeze(-1)  # (batch,)
        uncertainty = self.uncertainty_head(h).squeeze(-1)
        
        return output, uncertainty
    
    def implied_vol(
        self,
        moneyness: torch.Tensor,
        time_to_expiry: torch.Tensor,
        spot: torch.Tensor,
        atm_iv: torch.Tensor,
        expiry_idx: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """
        Get implied volatility directly.
        
        If output_param is total_variance: iv = sqrt(w / T)
        """
        total_var, _ = self.forward(moneyness, time_to_expiry, spot, atm_iv, expiry_idx)
        
        if self.output_param == "total_variance":
            # w = total_variance = iv^2 * T
            iv = torch.sqrt(total_var / (time_to_expiry + 1e-8))
        else:
            iv = total_var
        
        return iv
    
    def get_config(self) -> Dict:
        return {
            "input_dim": self.input_dim,
            "hidden_dim": self.hidden_dim,
            "num_layers": self.num_layers,
            "output_param": self.output_param,
            "use_residual": self.use_residual,
        }


class HyperIVMixture(nn.Module):
    """
    Mixture of HyperIV experts per expiry bucket.
    
    Useful for capturing term structure variations.
    """
    
    def __init__(
        self,
        num_experts: int = 4,
        input_dim: int = 4,
        hidden_dim: int = 128,
        num_layers: int = 3,
        **kwargs
    ):
        super().__init__()
        
        self.num_experts = num_experts
        self.experts = nn.ModuleList([
            HyperIVModel(
                input_dim=input_dim,
                hidden_dim=hidden_dim,
                num_layers=num_layers,
                **kwargs
            )
            for _ in range(num_experts)
        ])
        
        # Gating network
        self.gate = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, num_experts),
            nn.Softmax(dim=-1)
        )
    
    def forward(
        self,
        moneyness: torch.Tensor,
        time_to_expiry: torch.Tensor,
        spot: torch.Tensor,
        atm_iv: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        x = torch.stack([moneyness, time_to_expiry, spot, atm_iv], dim=-1)
        
        # Gating weights
        gate_weights = self.gate(x)  # (batch, num_experts)
        
        # Expert outputs
        expert_outputs = []
        expert_uncertainties = []
        
        for expert in self.experts:
            out, unc = expert(moneyness, time_to_expiry, spot, atm_iv)
            expert_outputs.append(out)
            expert_uncertainties.append(unc)
        
        expert_outputs = torch.stack(expert_outputs, dim=1)  # (batch, num_experts)
        expert_uncertainties = torch.stack(expert_uncertainties, dim=1)
        
        # Weighted combination
        output = (gate_weights * expert_outputs).sum(dim=1)
        uncertainty = (gate_weights * expert_uncertainties).sum(dim=1)
        
        return output, uncertainty