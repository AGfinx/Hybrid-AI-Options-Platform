# Antigravity Build Prompt

Copy and paste the prompt below into Antigravity from the root of this repository.

---

You are the lead engineer responsible for starting implementation of the **Hybrid AI Options Platform** described in this repository.

## 1. Mission

Build the first working version of a **hybrid human-in-the-loop cryptocurrency-options analytics and paper-trading platform**.

The platform must support:

1. Real-time public market-data ingestion.
2. Data validation and deterministic replay.
3. Implied-volatility surface analytics.
4. Realized-volatility forecasting baselines.
5. Volatility-arbitrage opportunity recommendations.
6. Portfolio Greeks, margin, stress, and risk checks.
7. Manual review, editing, approval, rejection, and watchlisting.
8. Paper trading with realistic fills, fees, spread, slippage, latency, and hedging.
9. Audit logs, observability, model/version tracking, and emergency stop controls.
10. A clear architecture for later assisted execution and bounded automation, while keeping live order entry disabled.

Do not build a completely autonomous trading system. The default operating mode must be **Recommendation mode**, and the first release must not submit live orders or access production exchange trading endpoints.

## 2. Read the repository documentation first

Before writing code, inspect and follow these documents:

- `README.md`
- `BRD.md`
- `PRD.md`
- `FRD.md`
- `TDD.md`
- `ARCHITECTURE.md`
- `RFC-001-technology-stack.md`
- `API.md`
- `RUNBOOK.md`

Treat these documents as the source of truth. If implementation details are missing, choose the simplest safe design consistent with them and document the decision in a new `docs/DECISIONS.md` file.

## 3. Required technology choices

Use the following initial stack unless a documented technical reason requires a change:

### Frontend

- Next.js
- React
- TypeScript
- A professional dashboard UI with tables, charts, forms, status badges, and clear risk indicators

### Backend and quantitative services

- Python 3.11+
- FastAPI
- Pydantic
- NumPy
- Polars and/or pandas
- SciPy
- QuantLib-Python where installation is practical
- PyArrow
- DuckDB

### Database and storage

- PostgreSQL for application state
- TimescaleDB-compatible schema where available
- Parquet for immutable historical market-data files
- DuckDB for replay and research queries
- Redis only for short-lived cache or realtime fan-out; never as the historical source of truth

### Modeling

- Transparent baseline models first
- scikit-learn for time-aware forecasting baselines
- PyTorch interfaces reserved for HyperIV, PINN, LSTM, and future models
- Stable-Baselines3 must not be implemented before the deterministic simulator and supervised baselines are working
- MLflow integration may begin as a lightweight experiment metadata interface, but model promotion must remain manual

### Optional later services

- Rust for deterministic market-data normalization and latency-sensitive services
- Kafka or Redpanda only after a durable event-log abstraction exists and real workload measurements justify it
- ClickHouse only after analytical volume justifies it
- Kubernetes, FPGA, DPDK, kernel bypass, co-location, and live order routing are explicitly deferred

## 4. Data-source safety rules

Use **Deribit public market data only** for the first implementation.

Use the native Deribit public WebSocket and JSON-RPC APIs for market data. Support:

- Instrument discovery.
- Option metadata.
- Ticker and order-book updates.
- Trades.
- Underlying/index data where available.
- Volatility-index data where available.
- Instrument lifecycle/state changes.

The market-data adapter must support:

- Heartbeat/test-request handling.
- Reconnect with exponential backoff.
- Resubscription after reconnect.
- Sequence/change-ID monitoring where available.
- Bounded queues and backpressure.
- Stale-data detection.
- Duplicate and out-of-order detection.
- Raw payload preservation.
- Snapshot reconciliation.
- Graceful shutdown.

Do not request, store, expose, or use exchange trading credentials. Do not implement production order submission. If a paper adapter is created, make it impossible to point it at a production order endpoint through the default configuration.

## 5. First release scope

Build a vertical slice that works end-to-end:

```text
Public market data
  -> normalized event
  -> stored event
  -> feature snapshot
  -> baseline IV surface
  -> baseline RV forecast
  -> recommendation
  -> independent risk check
  -> user approval/rejection
  -> paper order
  -> simulated fill
  -> position and P&L report
```

The first vertical slice must support one underlying, preferably BTC, and a limited number of option instruments. Keep the instrument universe configurable.

## 6. Product modes

Implement these modes in the domain model and UI:

- `analytics`: analysis only; no recommendations or orders.
- `recommendation`: recommendations require user approval.
- `assisted`: only a future mandate may enable assisted paper actions.
- `bounded_automation`: create the data model and UI state, but keep live execution disabled and use paper simulation only.

The user must be able to:

- View the active mode.
- Switch modes only if authorized.
- Approve a recommendation.
- Reject a recommendation with a reason.
- Edit quantity and price assumptions.
- Recalculate Greeks, margin, stress, and net edge after edits.
- Watchlist a recommendation.
- Pause a strategy.
- Trigger an emergency stop.

## 7. Core domain entities

Implement database models and migrations for at least:

- User
- Role
- Permission
- Venue
- Instrument
- InstrumentVersion
- MarketEvent
- QuoteSnapshot
- TradeEvent
- FeatureSnapshot
- SurfaceRun
- ForecastRun
- ModelVersion
- Recommendation
- RecommendationEdit
- Mandate
- Approval
- RiskLimit
- StressRun
- PaperOrder
- PaperFill
- Position
- HedgeAction
- PnLAttribution
- Alert
- CircuitBreaker
- AuditEvent

Every important entity must have an ID, timestamps, status, and version/reference fields where appropriate.

## 8. Quantitative requirements

### Implied-volatility surface

Start with a robust transparent baseline rather than the full HyperIV neural model. Implement:

- Quote filtering.
- Bid/ask and quote-age checks.
- Implied-volatility inversion.
- Strike and expiry normalization.
- Moneyness and time-to-expiry.
- A simple interpolation or parametric surface.
- Confidence/quality flags.
- Surface fallback or abstention.
- Structural validation hooks for calendar and butterfly checks.

The interface must later support HyperIV without changing the recommendation contract.

### Realized-volatility forecast

Start with simple rolling and lagged-feature baselines. Add a scikit-learn time-aware forecasting pipeline. Do not use shuffled train/test splits. Store forecast horizon, forecast value, uncertainty or confidence, feature snapshot, model version, and valid-until timestamp.

### Opportunity calculation

Calculate at minimum:

```text
estimated gross volatility edge
- spread cost
- exchange fee assumption
- slippage assumption
- hedge-cost assumption
- funding/carry assumption
- uncertainty penalty
= estimated net edge
```

Do not create a recommendation if data quality fails, the edge is below threshold, the surface is invalid, the forecast is unavailable, or the portfolio would violate risk limits.

## 9. Independent risk engine

The risk engine must be separate from the model/recommendation code and must be able to reject an action.

Implement checks for:

- Capital allocation.
- Margin usage.
- Maximum loss.
- Delta.
- Gamma.
- Vega.
- Theta.
- Short-option exposure.
- Position and maturity concentration.
- Liquidity.
- Quote age.
- Data health.
- Drawdown.
- Stress loss.
- Circuit-breaker status.

Implement a basic scenario grid for spot and implied-volatility shocks, then add extension points for skew, term structure, liquidity, partial fills, and outage scenarios.

If the risk service is unavailable, fail closed: no new recommendations may become actionable and no paper order may be created without an explicit test override.

## 10. Paper-trading simulator

Build a deterministic event-driven simulator. It must support:

- Market and limit-style paper orders.
- Bid/ask execution assumptions.
- Configurable fee and slippage assumptions.
- Partial fills.
- Latency assumptions.
- Cancellation and expiry.
- Position updates.
- Basic delta hedging simulation.
- Margin and stress recalculation.
- Complete P&L ledger.

All simulated orders must carry links to the recommendation, user decision, model versions, risk result, and market snapshot.

## 11. User interface requirements

Build the following pages or views:

1. Dashboard: operating mode, portfolio, active warnings, market/data health, margin, Greeks, and recent recommendations.
2. Market data: instrument list, quotes, freshness, and connection status.
3. Volatility surface: smile/skew/term-structure visualization with timestamps and confidence.
4. Opportunities: ranked recommendation queue with filters.
5. Recommendation detail: structure, rationale, costs, Greeks, margin, stress results, and approval controls.
6. Paper trading: orders, fills, positions, and simulated P&L.
7. Risk: limits, current utilization, stress scenarios, and circuit breakers.
8. Audit: user actions, model versions, risk decisions, and configuration changes.
9. Settings: mode, strategy permissions, risk limits, thresholds, and notification preferences.
10. Emergency control: visible stop-new-risk control with confirmation and audit logging.

Use clear language. Always display whether the data is live, delayed, replayed, or simulated. Always display the timestamp and freshness of prices and model outputs.

## 12. API requirements

Implement the API paths described in `API.md`, including:

- `/market/health`
- `/instruments`
- `/surfaces/{underlying}`
- `/forecasts/realized-volatility`
- `/recommendations`
- `/recommendations/{id}/approve`
- `/recommendations/{id}/reject`
- `/recommendations/{id}/edit`
- `/mandates`
- `/portfolio/risk`
- `/risk/stress-runs`
- `/controls/emergency-stop`
- `/paper/orders`
- `/paper/positions`
- `/reports/pnl`
- `/audit/events`

Use OpenAPI schemas, Pydantic validation, authentication placeholders, authorization checks, correlation IDs, idempotency keys for mutations, and safe error responses.

## 13. Repository structure

Create a clean monorepo structure similar to:

```text
/apps/web                 # Next.js dashboard
/services/api             # FastAPI application
/services/market-data     # public Deribit collector and normalizer
/services/replay          # deterministic event replay
/services/simulator       # paper trading and fill simulation
/packages/contracts       # OpenAPI/domain schemas if useful
/packages/quant            # pricing, IV, Greeks, features, forecasts
/packages/risk             # independent risk and stress logic
/db/migrations             # database migrations
/data/samples               # small synthetic/sample fixtures only
/tests/unit
/tests/integration
/tests/replay
/tests/e2e
docs                       # copy or link project documentation
infra/docker-compose.yml
.env.example
Makefile or justfile
```

Do not commit real market-data credentials, private keys, `.env` files, large raw datasets, or generated secrets.

## 14. Development sequence

Work in this order:

### Step 1: Inspect and plan

Read all repository documents. Produce a short implementation plan and a list of assumptions in `docs/IMPLEMENTATION_PLAN.md`.

### Step 2: Scaffold

Create the monorepo, local development instructions, environment template, Docker Compose services, health endpoints, logging, and test layout.

### Step 3: Database and contracts

Create migrations and Pydantic/domain schemas. Add seed data for one venue, BTC, synthetic instruments, roles, and safe default limits.

### Step 4: Synthetic-data vertical slice

Before connecting to Deribit, make the complete pipeline work on deterministic synthetic market events. This ensures the system can run in CI without network access.

### Step 5: Deribit public collector

Add the public WebSocket/HTTP adapter behind an interface. Add reconnect, heartbeat, validation, raw storage, and normalized events. Use feature flags to keep the network connector optional in tests.

### Step 6: Quant baseline

Implement features, IV inversion, baseline surface, Greeks, RV forecast, net-edge calculation, and quality flags. Add unit and regression tests.

### Step 7: Risk and paper simulator

Implement independent risk checks, stress scenarios, paper orders, fills, positions, hedges, and P&L attribution.

### Step 8: Dashboard and human approval

Implement recommendation review, editing, approval, rejection, watchlist, mandates, risk display, paper orders, reports, and emergency stop.

### Step 9: Observability and audit

Add structured logs, metrics, traces, audit events, request IDs, model IDs, and data-quality dashboards.

### Step 10: Validation

Run unit, integration, replay, API, end-to-end, security, and failure-mode tests. Update documentation and provide a final runbook.

## 15. Acceptance criteria for the first milestone

The first milestone is complete only when:

- The project starts locally with documented commands.
- The web app loads and authenticates a development user or uses a clearly marked local auth stub.
- Synthetic market data can be replayed deterministically.
- A public-data adapter exists behind a feature flag.
- The system creates a validated baseline volatility surface.
- The system produces a realized-volatility forecast with timestamp and model version.
- The system creates a cost-adjusted recommendation or explicitly returns no trade.
- The recommendation shows rationale, costs, Greeks, margin, stress loss, confidence, and expiry.
- A user can approve, reject, edit, or watchlist it.
- Editing recalculates risk and net edge.
- Risk checks can reject the action.
- Paper fills and P&L are recorded.
- Emergency stop prevents new paper risk.
- Audit records exist for all important decisions.
- Tests pass in an offline environment.
- No production trading endpoint or credential is used.

## 16. Engineering rules

- Prefer simple, testable implementations over premature optimization.
- Never hide assumptions about fees, slippage, funding, pricing, or forecast horizons.
- Use UTC timestamps and explicit units.
- Do not use random train/test splits for time-series evaluation.
- Keep model, data, feature, and configuration versions in all decisions.
- Use the no-trade outcome whenever quality or risk is insufficient.
- Treat all user approvals as expiring and state-dependent.
- Make risk checks independent from model recommendations.
- Fail closed when critical data, risk, or audit services are unavailable.
- Never implement autonomous live trading during this build.
- Do not claim that simulated profitability proves live profitability.

## 17. Required final response from you

When the first milestone is complete, report:

1. What was implemented.
2. Repository structure.
3. How to run it locally.
4. Which services require environment variables.
5. Test commands and results.
6. Known limitations.
7. Deferred work.
8. How to operate Analytics, Recommendation, and Paper Trading modes.
9. Confirmation that live order routing and production credentials remain disabled.

Start by inspecting the repository and producing `docs/IMPLEMENTATION_PLAN.md`. Then implement the first vertical slice incrementally. Do not wait for a perfect final architecture before producing a running, testable synthetic-data version.

---
