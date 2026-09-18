# Decision Log (docs/DECISIONS.md)

This document records technical, operational, and architectural decisions made during the implementation of the Hybrid AI Options Platform.

---

## Decision 001: SQLite / In-Memory SQLite Fallback for Local Development & Testing
- **Context**: The specification calls for PostgreSQL/TimescaleDB for persistent state. For standalone offline developer experience and CI test execution without requiring a running PostgreSQL server container, a database abstraction is needed.
- **Decision**: Use SQLAlchemy with PostgreSQL as primary dialect, but with automatic fallback to SQLite (`sqlite:///./platform.db` or `:memory:`) when PostgreSQL environment variables are not supplied. Ensure JSON and Timestamp data types are portable.
- **Status**: Approved.

---

## Decision 002: Baseline Volatility Surface Model
- **Context**: Full HyperIV neural networks are planned for future releases. The platform requires an initial transparent baseline surface for v1.
- **Decision**: Implement a Bilinear / Parametric Smile Interpolation model in `packages/quant` using Black-Scholes inversion with SciPy optimizations. Support calendar and butterfly spread non-arbitrage constraints and flag structural violations.
- **Status**: Approved.

---

## Decision 003: Realized Volatility Forecasting Baseline
- **Context**: Deep learning models (LSTM, PINN) will be introduced in subsequent phases.
- **Decision**: Use a time-aware scikit-learn Ridge/RandomForest baseline combined with rolling realized volatility (7-day, 14-day, 30-day windows) without random data splits.
- **Status**: Approved.

---

## Decision 004: Hard-Disabled Live Execution Safety Boundary
- **Context**: Safety rules forbid live trading or order submission to exchange endpoints in the first release.
- **Decision**: Paper order execution engine is the sole execution target. Any configuration attempt to target live exchange endpoints will raise a hard `RuntimeError` and immediately trip the system circuit breaker.
- **Status**: Approved.

---

## Decision 005: Deterministic Paper Execution & Delta-Hedging Simulation
- **Context**: Realistic paper simulation must avoid phantom alpha from zero-cost execution or unhedged directional noise.
- **Decision**: In `services/simulator`, orders account for realistic bid/ask spread crossing, fee schedules (3 bps of contract value), dynamic slippage based on sizing, and automated spot delta-hedging whenever absolute position delta exceeds 0.5 BTC. Real-time P&L is attributed into Delta, Gamma, Vega, Theta, Fees, Slippage, and Hedge components.
- **Status**: Approved.

---

## Decision 006: Deterministic Offline Parquet/DuckDB Replay Architecture
- **Context**: Development, CI, and algorithm evaluation require reproducible testing without live network or external exchange downtime.
- **Decision**: Generated 11,200 synthetic BTC option quote events across 4 expiries and 7 strikes into `data/samples/btc_options_sample.parquet`. Built `ReplayEngine` querying via embedded DuckDB to step ticks deterministically into the database and pipeline.
- **Status**: Approved.
