import os
import math
import datetime
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from packages.quant.black_scholes import bs_price, bs_greeks

def generate_synthetic_options_data(
    underlying: str = "BTC",
    output_path: str = "data/samples/btc_options_sample.parquet",
    num_ticks: int = 200,
    initial_spot: float = 65000.0,
    spot_vol: float = 0.55,
    strikes: list = None
):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if strikes is None:
        strikes = [55000.0, 60000.0, 62500.0, 65000.0, 67500.0, 70000.0, 75000.0]

    # 1. Simulate spot price path using Geometric Brownian Motion
    dt = 1.0 / (365.0 * 24.0 * 60.0) # 1-minute steps
    np.random.seed(42 if underlying == "BTC" else 101)
    shocks = np.random.normal(0, np.sqrt(dt), num_ticks)
    spot_path = [initial_spot]
    for shock in shocks:
        s_next = spot_path[-1] * math.exp(-0.5 * (spot_vol ** 2) * dt + spot_vol * shock)
        spot_path.append(s_next)

    # 2. Options universe
    expiry_days = [7, 14, 30, 60]
    opt_types = ["call", "put"]

    start_time = datetime.datetime(2026, 9, 18, 10, 0, 0, tzinfo=datetime.timezone.utc)

    records = {
        "event_id": [],
        "timestamp": [],
        "event_type": [],
        "instrument_name": [],
        "underlying": [],
        "underlying_price": [],
        "best_bid_price": [],
        "best_bid_amount": [],
        "best_ask_price": [],
        "best_ask_amount": [],
        "mark_price": [],
        "implied_volatility": [],
        "delta": [],
        "vega": []
    }

    event_counter = 0

    for i in range(num_ticks):
        current_spot = spot_path[i]
        tick_time = start_time + datetime.timedelta(seconds=i * 5)
        tick_time_str = tick_time.isoformat()

        # Volatility smile skew: OTM puts higher IV, OTM calls lower/slight smile
        for exp_d in expiry_days:
            T = exp_d / 365.0
            exp_date = (tick_time + datetime.timedelta(days=exp_d)).strftime("%d%b%y").upper()

            for strike in strikes:
                for opt_type in opt_types:
                    event_counter += 1
                    flag = "C" if opt_type == "call" else "P"
                    symbol = f"{underlying}-{exp_date}-{int(strike)}-{flag}"

                    moneyness = math.log(strike / current_spot)
                    # Parametric smile formula
                    base_iv = spot_vol + 0.15 * (moneyness ** 2) - 0.08 * moneyness + 0.02 * math.sin(i / 10.0)
                    base_iv = max(0.20, min(1.80, base_iv))

                    greeks = bs_greeks(current_spot, strike, T, 0.0, base_iv, opt_type)
                    fair_price = greeks["price"]

                    # Realistic spread: 1% to 2% of price or min $5 for BTC, $1 for ETH
                    min_spread = 2.5 if underlying == "BTC" else 0.5
                    half_spread = max(min_spread, fair_price * 0.015)
                    bid = max(0.1, round(fair_price - half_spread, 1))
                    ask = round(fair_price + half_spread, 1)

                    records["event_id"].append(f"ev_{underlying.lower()}_{event_counter:08d}")
                    records["timestamp"].append(tick_time_str)
                    records["event_type"].append("quote")
                    records["instrument_name"].append(symbol)
                    records["underlying"].append(underlying)
                    records["underlying_price"].append(round(current_spot, 2))
                    records["best_bid_price"].append(bid)
                    records["best_bid_amount"].append(round(np.random.uniform(2.0, 20.0), 1))
                    records["best_ask_price"].append(ask)
                    records["best_ask_amount"].append(round(np.random.uniform(2.0, 20.0), 1))
                    records["mark_price"].append(round(fair_price, 2))
                    records["implied_volatility"].append(round(base_iv, 4))
                    records["delta"].append(round(float(greeks["delta"]), 4))
                    records["vega"].append(round(float(greeks["vega"]), 4))

    table = pa.Table.from_pydict(records)
    pq.write_table(table, output_path)
    print(f"Generated {len(records['event_id'])} synthetic {underlying} option events into {output_path}")

def generate_all():
    generate_synthetic_options_data(
        underlying="BTC",
        output_path="data/samples/btc_options_sample.parquet",
        initial_spot=65000.0,
        spot_vol=0.55,
        strikes=[55000.0, 60000.0, 62500.0, 65000.0, 67500.0, 70000.0, 75000.0]
    )
    generate_synthetic_options_data(
        underlying="ETH",
        output_path="data/samples/eth_options_sample.parquet",
        initial_spot=3500.0,
        spot_vol=0.65,
        strikes=[2800.0, 3000.0, 3200.0, 3500.0, 3800.0, 4000.0, 4200.0]
    )

if __name__ == "__main__":
    generate_all()
