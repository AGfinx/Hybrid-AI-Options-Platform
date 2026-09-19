"""
Feature Engineering for Volatility Modeling

Builds reusable features from market data.
Only uses fields that actually exist in the dataset.
"""

from typing import List, Optional

import numpy as np
import pandas as pd


def compute_log_returns(series: pd.Series) -> pd.Series:
    """Compute log returns from price series."""
    return np.log(series / series.shift(1))


def compute_realized_vol(
    returns: pd.Series,
    window: int,
    annualize: bool = True,
    trading_periods: int = 365 * 24 * 60  # minute data
) -> pd.Series:
    """
    Compute rolling realized volatility from returns.
    
    Args:
        returns: Series of log returns
        window: Rolling window size
        annualize: Whether to annualize the volatility
        trading_periods: Periods per year for annualization
        
    Returns:
        Rolling realized volatility
    """
    rv = returns.rolling(window=window, min_periods=window//2).std()
    if annualize:
        rv = rv * np.sqrt(trading_periods)
    return rv


def compute_parkinson_vol(
    high: pd.Series,
    low: pd.Series,
    window: int,
    annualize: bool = True,
    trading_periods: int = 365 * 24 * 60
) -> pd.Series:
    """
    Compute Parkinson volatility estimator (requires OHLC).
    
    Note: Only works if high/low data is available.
    """
    if high is None or low is None:
        return pd.Series(index=high.index if high is not None else low.index, dtype=float)
    
    # Parkinson: sigma = sqrt(1/(4*ln(2)*N) * sum(ln(H/L)^2))
    rs = np.log(high / low) ** 2
    pv = rs.rolling(window=window, min_periods=window//2).mean()
    pv = np.sqrt(pv / (4 * np.log(2)))
    
    if annualize:
        pv = pv * np.sqrt(trading_periods)
    
    return pv


def compute_moneyness(
    strike: pd.Series,
    spot: pd.Series
) -> pd.Series:
    """Compute log moneyness: ln(K/S)."""
    return np.log(strike / spot)


def compute_time_to_expiry(
    expiry_timestamp: pd.Series,
    current_timestamp: pd.Series
) -> pd.Series:
    """Compute time to expiry in years."""
    return (expiry_timestamp - current_timestamp).dt.total_seconds() / (365 * 24 * 3600)


def compute_bid_ask_spread(
    bid: pd.Series,
    ask: pd.Series,
    mid: Optional[pd.Series] = None
) -> pd.Series:
    """Compute bid-ask spread in absolute and relative terms."""
    abs_spread = ask - bid
    if mid is None:
        mid = (bid + ask) / 2
    rel_spread = abs_spread / mid
    return abs_spread, rel_spread


def compute_iv_features(
    iv: pd.Series,
    windows: List[int] = [10, 30, 60]
) -> pd.DataFrame:
    """Compute rolling IV statistics."""
    features = pd.DataFrame(index=iv.index)
    
    for w in windows:
        features[f"iv_rolling_mean_{w}"] = iv.rolling(w, min_periods=w//2).mean()
        features[f"iv_rolling_std_{w}"] = iv.rolling(w, min_periods=w//2).std()
        features[f"iv_rolling_min_{w}"] = iv.rolling(w, min_periods=w//2).min()
        features[f"iv_rolling_max_{w}"] = iv.rolling(w, min_periods=w//2).max()
    
    # IV rank (percentile within rolling window)
    for w in windows:
        features[f"iv_rank_{w}"] = iv.rolling(w, min_periods=w//2).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1] if len(x) == w else np.nan
        )
    
    return features


def compute_greeks_features(
    delta: pd.Series,
    vega: pd.Series,
    gamma: Optional[pd.Series] = None,
    theta: Optional[pd.Series] = None,
    windows: List[int] = [10, 30]
) -> pd.DataFrame:
    """Compute rolling Greeks statistics."""
    features = pd.DataFrame(index=delta.index)
    
    for w in windows:
        features[f"delta_rolling_mean_{w}"] = delta.rolling(w, min_periods=w//2).mean()
        features[f"vega_rolling_mean_{w}"] = vega.rolling(w, min_periods=w//2).mean()
        
        if gamma is not None:
            features[f"gamma_rolling_mean_{w}"] = gamma.rolling(w, min_periods=w//2).mean()
        if theta is not None:
            features[f"theta_rolling_mean_{w}"] = theta.rolling(w, min_periods=w//2).mean()
    
    return features


def build_features(
    df: pd.DataFrame,
    target_horizon: int = 1,
    include_iv_features: bool = True,
    include_greeks_features: bool = True,
    return_windows: List[int] = [5, 15, 30, 60],
    iv_windows: List[int] = [10, 30, 60],
) -> pd.DataFrame:
    """
    Build feature matrix from raw market data.
    
    Args:
        df: DataFrame with required columns
        target_horizon: Forward horizon for target (in timestamps)
        include_iv_features: Whether to include IV rolling stats
        include_greeks_features: Whether to include Greeks rolling stats
        return_windows: Windows for realized vol computation
        iv_windows: Windows for IV rolling stats
        
    Returns:
        DataFrame with features and target column
    """
    df = df.copy()
    df = df.sort_values("timestamp").reset_index(drop=True)
    
    features = pd.DataFrame(index=df.index)
    
    # Parse instrument fields if available
    if "instrument_name" in df.columns:
        from packages.ml.data.loader import enrich_with_parsed_fields
        df = enrich_with_parsed_fields(df)
    
    # === Target: Future Realized Volatility ===
    # We need to compute RV from underlying price returns
    if "underlying_price" in df.columns:
        # Compute returns per underlying
        for underlying in df["underlying"].unique():
            mask = df["underlying"] == underlying
            spot = df.loc[mask, "underlying_price"]
            returns = compute_log_returns(spot)
            
            # Compute RV at different windows
            for w in return_windows:
                rv = compute_realized_vol(returns, w)
                features.loc[mask, f"rv_{w}"] = rv.values
            
            # Target: RV at target_horizon (forward-looking)
            # This is what we want to predict
            rv_target = compute_realized_vol(returns, target_horizon)
            # Shift back so target aligns with current features
            features.loc[mask, "target_rv"] = rv_target.shift(-target_horizon).values
    
    # === Spot Features ===
    if "underlying_price" in df.columns:
        features["spot"] = df["underlying_price"]
        features["log_spot"] = np.log(df["underlying_price"])
        features["spot_returns"] = df.groupby("underlying")["underlying_price"].transform(
            lambda x: compute_log_returns(x)
        )
    
    # === Moneyness ===
    if "strike" in df.columns and "underlying_price" in df.columns:
        features["moneyness"] = compute_moneyness(df["strike"], df["underlying_price"])
        features["moneyness_abs"] = features["moneyness"].abs()
    
    # === Time to Expiry ===
    if "expiry_code" in df.columns and "timestamp" in df.columns:
        # Parse expiry code to approximate date
        # This is approximate - real implementation would use proper expiry dates
        pass  # Requires proper date parsing
    
    # === Bid/Ask Spread ===
    if "best_bid_price" in df.columns and "best_ask_price" in df.columns:
        abs_spread, rel_spread = compute_bid_ask_spread(
            df["best_bid_price"], df["best_ask_price"]
        )
        features["bid_ask_spread_abs"] = abs_spread
        features["bid_ask_spread_rel"] = rel_spread
        features["mid_price"] = (df["best_bid_price"] + df["best_ask_price"]) / 2
    
    # === IV Features ===
    if include_iv_features and "implied_volatility" in df.columns:
        iv_feats = compute_iv_features(df["implied_volatility"], iv_windows)
        features = pd.concat([features, iv_feats], axis=1)
        features["iv"] = df["implied_volatility"]
        features["iv_term_structure"] = df.groupby("expiry_code")["implied_volatility"].transform("mean") \
            if "expiry_code" in df.columns else np.nan
    
    # === Greeks Features ===
    if include_greeks_features:
        greeks_feats = compute_greeks_features(
            df.get("delta"),
            df.get("vega"),
            df.get("gamma"),
            df.get("theta"),
            windows=[10, 30]
        )
        features = pd.concat([features, greeks_feats], axis=1)
        
        if "delta" in df.columns:
            features["delta"] = df["delta"]
        if "vega" in df.columns:
            features["vega"] = df["vega"]
        if "gamma" in df.columns:
            features["gamma"] = df["gamma"]
        if "theta" in df.columns:
            features["theta"] = df["theta"]
    
    # === Volume/OI if available ===
    if "best_bid_amount" in df.columns and "best_ask_amount" in df.columns:
        features["bid_size"] = df["best_bid_amount"]
        features["ask_size"] = df["best_ask_amount"]
        features["total_size"] = df["best_bid_amount"] + df["best_ask_amount"]
    
    if "open_interest" in df.columns:
        features["open_interest"] = df["open_interest"]
    if "volume_24h" in df.columns:
        features["volume_24h"] = df["volume_24h"]
    
    # === Categorical ===
    if "option_type" in df.columns:
        features["is_call"] = (df["option_type"] == "call").astype(int)
    if "underlying" in df.columns:
        features["underlying"] = df["underlying"]
    
    # Drop rows where target is NaN (last rows of each series)
    if "target_rv" in features.columns:
        features = features.dropna(subset=["target_rv"])
    
    return features


def get_feature_columns(features: pd.DataFrame, exclude: List[str] = None) -> List[str]:
    """Get list of feature column names, excluding target and metadata."""
    if exclude is None:
        exclude = ["target_rv", "target", "timestamp", "underlying", "expiry_code", "option_type"]
    
    return [c for c in features.columns if c not in exclude]


def prepare_xy(
    features: pd.DataFrame,
    target_col: str = "target_rv",
    exclude_cols: List[str] = None
) -> tuple:
    """
    Split features into X (features) and y (target).
    
    Returns:
        X: Feature matrix (numpy array)
        y: Target vector (numpy array)
        feature_names: List of feature column names
    """
    if target_col not in features.columns:
        raise ValueError(f"Target column '{target_col}' not in features")
    
    feature_names = get_feature_columns(features, exclude_cols)
    
    # Only use numeric features
    X_df = features[feature_names].select_dtypes(include=[np.number])
    feature_names = X_df.columns.tolist()
    
    X = X_df.values
    y = features[target_col].values
    
    # Remove rows with NaN
    valid = ~(np.isnan(X).any(axis=1) | np.isnan(y))
    X = X[valid]
    y = y[valid]
    
    return X, y, feature_names