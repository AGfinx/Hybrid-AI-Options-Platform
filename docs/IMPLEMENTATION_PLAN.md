# Hybrid AI Options Platform - Implementation Plan (Milestone 1)

## System Overview
The Hybrid AI Options Platform is a human-in-the-loop cryptocurrency options analytics, risk-management, recommendation, and paper-trading platform. It enforces a strict Recommendation Mode by default, keeping live order submission disabled while delivering transparent IV analytics, realized volatility forecasts, independent risk filtering, human approval workflows, and deterministic paper execution.

---

## Component Architecture & Monorepo Layout

```text
c:\Users\manjr\Documents\TSProject\
├── apps/
│   └── web/                 # Next.js 14 dashboard UI (React, TypeScript, TailwindCSS, Recharts)
├── services/
│   ├── api/                 # FastAPI REST server implementing API.md spec
│   ├── market_data/         # Public Deribit WebSocket/HTTP ingestion and normalizer
│   ├── replay/              # Deterministic market event replay engine (DuckDB/Parquet)
│   └── simulator/           # Paper trading order execution and fill simulator
├── packages/
│   ├── quant/               # Black-Scholes pricing, IV surface, RV forecast, net edge calculation
│   └── risk/                # Independent risk engine, limits, stress scenario grid, circuit breakers
├── db/
│   ├── models/              # SQLAlchemy database ORM schemas (24 domain entities)
│   └── database.py          # PostgreSQL/SQLite database manager & session lifecycle
├── docs/
│   ├── IMPLEMENTATION_PLAN.md
│   └── DECISIONS.md
├── tests/
│   ├── unit/                # Math, risk invariants, domain entity unit tests
│   ├── integration/         # API endpoint and database integration tests
│   └── replay/              # Replay & paper trading simulator tests
├── infra/
│   └── docker-compose.yml   # Multi-container stack (PostgreSQL, Redis, API, Web)
├── Makefile
└── .env.example
```

---

## Planned Implementation Steps

### Phase 1: Architecture Scaffolding & Domain Entities
- Setup folder structure across `apps/web`, `services/`, `packages/`, `db/`, `tests/`.
- Implement SQLAlchemy database models for all 24 required core domain entities:
  `User`, `Role`, `Permission`, `Venue`, `Instrument`, `InstrumentVersion`, `MarketEvent`, `QuoteSnapshot`, `TradeEvent`, `FeatureSnapshot`, `SurfaceRun`, `ForecastRun`, `ModelVersion`, `Recommendation`, `RecommendationEdit`, `Mandate`, `Approval`, `RiskLimit`, `StressRun`, `PaperOrder`, `PaperFill`, `Position`, `HedgeAction`, `PnLAttribution`, `Alert`, `CircuitBreaker`, `AuditEvent`.
- Database initialization and seed script with synthetic BTC instruments, default user, roles, permissions, and initial risk limits.

### Phase 2: Synthetic Data Slice & Replay Engine
- Synthetic BTC market data generator creating realistic option tick streams (spot ~\$65,000, strike range \$50k-\$80k, expiries 7d/14d/30d/60d).
- Deterministic event replay engine to feed market snapshots through the pipeline offline without requiring network access.

### Phase 3: Quant Package (`packages/quant`)
- **Black-Scholes Option Pricing & IV Inversion**: Newton-Raphson / Brent root solver for implied volatility given market bid/ask prices.
- **IV Surface Analytics**: Parametric/Bilinear interpolation surface with structural validation checks (calendar spread arbitrage and butterfly spread non-negativity checks) and fallback/abstention states.
- **Realized Volatility Forecasting**: Lagged return feature calculator and scikit-learn Ridge/RandomForest time-aware forecasting baseline with uncertainty bounds.
- **Opportunity Calculator**: Calculates gross vol edge minus spread, fees, slippage, hedge cost, carry, and uncertainty penalty to yield `net_edge`.

### Phase 4: Independent Risk Engine (`packages/risk`)
- Isolated risk service that evaluates portfolio risk state and acts as an independent gatekeeper.
- Stress scenario grid evaluating spot shocks (-20% to +20%) and volatility shocks (-15% to +15%).
- Hard checks on portfolio delta, gamma, vega, theta, margin utilization, max loss, short option exposure, concentration, and data freshness.
- Circuit breaker triggers and Emergency Stop fail-closed override.

### Phase 5: Paper Trading Simulator (`services/simulator`)
- Deterministic event-driven simulator supporting Market and Limit paper orders.
- Execution model considering bid/ask spread, fee schedules, slippage model, latency delay, and partial fills.
- Automated delta-hedging simulation using BTC spot.
- Position ledger and real-time P&L attribution (Delta, Gamma, Vega, Theta, Fees, Slippage, Residual).

### Phase 6: Deribit Market Data Collector (`services/market_data`)
- Native Deribit JSON-RPC / WebSocket adapter behind feature flag (`DERIBIT_LIVE_ENABLED`).
- Reconnection with exponential backoff, sequence gap detection, heartbeat tracking, raw payload storage, and quality status tagging.

### Phase 7: FastAPI Core Server (`services/api`)
- Complete endpoint implementation covering all paths in `API.md`:
  - Operating Mode & Health: `/market/health`, `/controls/emergency-stop`
  - Instruments & Surfaces: `/instruments`, `/surfaces/{underlying}`, `/forecasts/realized-volatility`
  - Recommendations: `/recommendations`, `/recommendations/{id}`, `/recommendations/{id}/approve`, `/recommendations/{id}/reject`, `/recommendations/{id}/edit`
  - Mandates & Risk: `/mandates`, `/mandates/{id}/pause`, `/portfolio/risk`, `/risk/stress-runs`
  - Paper Trading & P&L: `/paper/orders`, `/paper/positions`, `/reports/pnl`
  - Audit: `/audit/events`
- Middleware for request correlation ID (`request_id`), authentication stub (`Bearer dev-token`), role-based authorization, idempotency validation, and audit event recording.

### Phase 8: Next.js Dashboard Frontend (`apps/web`)
- Financial dashboard UI with responsive dark theme, high contrast data display:
  - Header: Active mode indicator (`Recommendation` mode default), data freshness indicator, Emergency Stop button with confirmation.
  - Dashboard: Portfolio summary, greeks dial, active alerts, top recommendations, data health status.
  - Market Data View: Live/replayed quote ticker, orderbook depth, instrument list.
  - Volatility Surface View: Smile, skew, and term structure interactive visualization with confidence flags.
  - Recommendation Queue View: Ranked opportunities list, detailed breakdown modal showing rationale, costs, Greeks, margin, stress loss.
  - Recommendation Review & Edit View: Interactive input fields for quantity and limit price with real-time net-edge & risk re-computation, Approve, Reject (with mandatory reason), Watchlist controls.
  - Paper Trading View: Active paper orders, execution history, positions table, P&L attribution chart.
  - Risk & Stress Testing View: Risk limit gauges, spot/vol stress matrix heatmap, active circuit breakers.
  - Audit Trail View: Searchable, filterable event audit log.

### Phase 9: Testing & Verification
- Unit test suite for quant pricing, IV surface, RV forecast, risk engine, and simulator logic.
- End-to-end synthetic replay integration test proving full vertical slice execution.
- Verification that live order routing endpoints remain 100% disabled.

---

## Architectural Decision Log & Safety Rules
1. **Default Mode**: System defaults strictly to `recommendation` mode. No live order routing capability exists.
2. **Independent Risk Check**: Risk checks fail closed; if the risk service fails or is unreachable, no trade recommendations can be approved or executed in paper.
3. **Reproducibility**: All recommendations, forecasts, surface runs, and paper orders store exact `model_version`, `feature_snapshot_id`, `market_event_id`, and `timestamp`.
