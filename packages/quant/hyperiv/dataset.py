"""
HyperIV Dataset Preparation

Converts market data to training format for PINN.
"""

import torch
from torch.utils.data import Dataset, DataLoader
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from sklearn.preprocessing import StandardScaler, LabelEncoder


class HyperIVDataset(Dataset):
    """
    Dataset for HyperIV training.
    
    Each sample: (moneyness, T, spot, atm_iv, expiry_idx) -> iv_true
    """
    
    def __init__(
        self,
        df: pd.DataFrame,
        expiry_encoder: Optional[LabelEncoder] = None,
        fit_encoder: bool = True
    ):
        """
        Args:
            df: DataFrame with option quotes
            expiry_encoder: Pre-fitted LabelEncoder for expiry indices
            fit_encoder: Whether to fit encoder on this data
        """
        self.df = df.copy()
        self.df = self.df.sort_values(["timestamp", "expiry_code", "strike"]).reset_index(drop=True)
        
        # Parse instrument fields if needed
        if "instrument_name" in self.df.columns:
            from packages.ml.data.loader import enrich_with_parsed_fields
            self.df = enrich_with_parsed_fields(self.df)
        
        # Compute moneyness
        if "strike" in self.df.columns and "underlying_price" in self.df.columns:
            self.df["moneyness"] = np.log(self.df["strike"] / self.df["underlying_price"])
        else:
            raise ValueError("Need strike and underlying_price columns")
        
        # Time to expiry - approximate from expiry_code
        if "expiry_code" in self.df.columns and "timestamp" in self.df.columns:
            self.df["time_to_expiry"] = self._compute_tte(
                self.df["expiry_code"], self.df["timestamp"]
            )
        elif "T" in self.df.columns:
            self.df["time_to_expiry"] = self.df["T"]
        else:
            raise ValueError("Need expiry information")
        
        # ATM IV per timestamp/expiry
        atm_iv = self._compute_atm_iv()
        self.df = self.df.merge(atm_iv, on=["timestamp", "expiry_code"], how="left")
        self.df["atm_iv"] = self.df["atm_iv"].fillna(self.df["implied_volatility"].median())
        
        # Encode expiry
        if expiry_encoder is None:
            self.expiry_encoder = LabelEncoder()
            if fit_encoder:
                self.df["expiry_idx"] = self.expiry_encoder.fit_transform(self.df["expiry_code"])
            else:
                raise ValueError("Need fitted expiry_encoder if fit_encoder=False")
        else:
            self.expiry_encoder = expiry_encoder
            self.df["expiry_idx"] = self.expiry_encoder.transform(self.df["expiry_code"])
        
        # Spot
        if "underlying_price" in self.df.columns:
            self.df["spot"] = self.df["underlying_price"]
        else:
            raise ValueError("Need underlying_price")
        
        # Target
        self.df["iv_true"] = self.df["implied_volatility"]
        
        # Clean
        self.df = self.df.dropna(subset=["moneyness", "time_to_expiry", "spot", "atm_iv", "iv_true"])
        self.df = self.df.reset_index(drop=True)
    
    def _compute_tte(self, expiry_codes: pd.Series, timestamps: pd.Series) -> pd.Series:
        """Compute time to expiry in years from expiry code and timestamp."""
        # Parse expiry code: 25SEP26 -> 2026-09-25
        def parse_expiry(code):
            try:
                day = int(code[:2])
                month_str = code[2:5]
                year = 2000 + int(code[5:])
                month_map = {"JAN":1, "FEB":2, "MAR":3, "APR":4, "MAY":5, "JUN":6,
                           "JUL":7, "AUG":8, "SEP":9, "OCT":10, "NOV":11, "DEC":12}
                month = month_map[month_str.upper()]
                return pd.Timestamp(year=year, month=month, day=day, tz="UTC")
            except:
                return pd.NaT
        
        expiry_dates = expiry_codes.apply(parse_expiry)
        tte = (expiry_dates - timestamps).dt.total_seconds() / (365.25 * 24 * 3600)
        return tte.clip(lower=1e-4)
    
    def _compute_atm_iv(self) -> pd.DataFrame:
        """Compute ATM IV per timestamp/expiry (IV at strike closest to spot)."""
        atm_rows = []
        
        for (ts, exp), group in self.df.groupby(["timestamp", "expiry_code"]):
            spot = group["underlying_price"].iloc[0]
            # Find closest to ATM
            idx = (group["strike"] - spot).abs().idxmin()
            atm_row = group.loc[idx]
            atm_rows.append({
                "timestamp": ts,
                "expiry_code": exp,
                "atm_iv": atm_row["implied_volatility"]
            })
        
        return pd.DataFrame(atm_rows)
    
    def __len__(self) -> int:
        return len(self.df)
    
    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        row = self.df.iloc[idx]
        
        return {
            "moneyness": torch.tensor(row["moneyness"], dtype=torch.float32),
            "time_to_expiry": torch.tensor(row["time_to_expiry"], dtype=torch.float32),
            "spot": torch.tensor(row["spot"], dtype=torch.float32),
            "atm_iv": torch.tensor(row["atm_iv"], dtype=torch.float32),
            "expiry_idx": torch.tensor(row["expiry_idx"], dtype=torch.long),
            "iv_true": torch.tensor(row["iv_true"], dtype=torch.float32),
        }
    
    @property
    def num_expiries(self) -> int:
        return len(self.expiry_encoder.classes_)
    
    @property
    def expiry_classes(self) -> np.ndarray:
        return self.expiry_encoder.classes_


def create_hyperiv_dataloaders(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    batch_size: int = 256,
    num_workers: int = 0
) -> Tuple[DataLoader, DataLoader, DataLoader, LabelEncoder]:
    """
    Create train/val/test dataloaders with shared expiry encoder.
    """
    # Fit encoder on training data
    train_dataset = HyperIVDataset(train_df, fit_encoder=True)
    expiry_encoder = train_dataset.expiry_encoder
    
    val_dataset = HyperIVDataset(val_df, expiry_encoder=expiry_encoder, fit_encoder=False)
    test_dataset = HyperIVDataset(test_df, expiry_encoder=expiry_encoder, fit_encoder=False)
    
    train_loader = DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True, num_workers=num_workers
    )
    val_loader = DataLoader(
        val_dataset, batch_size=batch_size, shuffle=False, num_workers=num_workers
    )
    test_loader = DataLoader(
        test_dataset, batch_size=batch_size, shuffle=False, num_workers=num_workers
    )
    
    return train_loader, val_loader, test_loader, expiry_encoder


def collate_hyperiv(batch: List[Dict]) -> Dict[str, torch.Tensor]:
    """Custom collate function for HyperIV batches."""
    return {
        "moneyness": torch.stack([b["moneyness"] for b in batch]),
        "time_to_expiry": torch.stack([b["time_to_expiry"] for b in batch]),
        "spot": torch.stack([b["spot"] for b in batch]),
        "atm_iv": torch.stack([b["atm_iv"] for b in batch]),
        "expiry_idx": torch.stack([b["expiry_idx"] for b in batch]),
        "iv_true": torch.stack([b["iv_true"] for b in batch]),
    }