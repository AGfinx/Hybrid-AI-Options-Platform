# Hybrid AI Options Platform

A human-in-the-loop cryptocurrency options analytics, risk-management, recommendation, and paper-trading platform.

## System Overview

The Hybrid AI Options Platform enforces a strict **Recommendation Mode** by default. Live order routing and production exchange trading credentials remain **strictly disabled**.

Key platform capabilities:
- **Public Market Data Ingestion**: WebSocket & JSON-RPC public feed adapter for Deribit cryptocurrency options.
- **Deterministic Offline Replay**: Embedded DuckDB & Parquet event replay engine with 11,200 synthetic BTC ticks.
- **Quantitative Analytics (`packages/quant`)**:
  - Analytical Black-Scholes-Merton pricer & Greeks (Delta, Gamma, Vega, Theta, Rho).
  - Brent-solver implied volatility inversion.
  - Bilinear / Parametric volatility surface interpolation with calendar and butterfly non-arbitrage bounds.
  - Time-aware Realized Volatility forecaster with walk-forward cross-validation and uncertainty bands.
  - Transparent opportunity calculation with spread, fee, slippage, hedge cost, and uncertainty penalties.
- **Independent Risk Engine (`packages/risk`)**:
  - Isolated risk gatekeeper enforcing capital, margin, Greek limits, and data freshness.
  - 7x7 non-linear stress scenario matrix evaluating joint spot shocks (±20%) and volatility shocks (±15%).
  - Immediate fail-closed Emergency Stop circuit breaker.
- **Deterministic Paper Simulator (`services/simulator`)**:
  - Realistic order execution with spread crossing, exchange fee schedules (3 bps), dynamic slippage, and automated spot delta-hedging.
  - Real-time P&L factor attribution (Delta, Gamma, Vega, Theta, Fees, Slippage, Hedge, Residual).
- **Interactive Web Cockpit (`apps/web`)**:
  - Next.js 14 dashboard UI with operating mode toggles, interactive parameter adjustment modal, real-time recalculation of risk, and compliance audit trail.

---

## Monorepo Layout

```text
TSProject/
├── apps/
│   └── web/                 # Next.js 14 dashboard UI (React, TypeScript, CSS, Lucide icons)
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
│   ├── database.py          # PostgreSQL/SQLite database manager & session lifecycle
│   └── seed.py              # Seed script for default user, instruments, and risk limits
├── data/
│   └── samples/             # Synthetic BTC options parquet data slice
├── docs/
│   ├── IMPLEMENTATION_PLAN.md
│   └── DECISIONS.md
├── tests/
│   ├── unit/                # Math, risk invariants, domain entity unit tests
│   ├── integration/         # API endpoint and database integration tests
│   └── replay/              # Replay & paper trading simulator tests
├── infra/
│   ├── docker-compose.yml   # Multi-container stack (PostgreSQL, Redis, API, Web)
│   └── Dockerfile.api       # FastAPI Docker container specification
├── Makefile
├── pytest.ini
└── .env.example
```

---

## Quickstart & Local Setup

### 1. Prerequisites
- Python 3.11+
- Node.js 18+ and npm
- (Optional) Docker & Docker Compose

### 2. Backend Setup
```bash
# Activate virtual environment
.\.venv\Scripts\activate

# Install dependencies (if not already installed)
pip install -r requirements.txt

# Seed the database with 24 domain entities and synthetic BTC instruments
python -m db.seed

# Run the complete test suite (100% offline, 24/24 passing)
pytest tests/ -v

# Start the FastAPI core server on port 8000
python -m uvicorn services.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive OpenAPI docs will be available at [http://localhost:8000/docs](http://localhost:8000/docs).

### 3. Frontend Dashboard Setup
```bash
cd apps/web

# Start Next.js development server on port 3000
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Operating Modes

1. **`recommendation` (Default)**:
   Algorithmic opportunities are surfaced in the queue with transparent cost breakdowns and risk limits. Orders require explicit human approval and parameter review.
2. **`analytics`**:
   Market data, implied volatility surfaces, and risk metrics are computed and displayed; trade recommendations and order entries are disabled.
3. **`assisted`**:
   Allows guided execution within approved strategy mandate boundaries.
4. **`bounded_automation`**:
   Paper simulation only. Live execution remains strictly blocked by system circuit breakers.

---

## Safety Guarantees
- **No Exchange Credentials**: The platform does not request, store, or accept live API keys or private credentials.
- **Fail-Closed Gatekeeper**: If market data is stale (>15 seconds), if a circuit breaker is engaged, or if the risk engine rejects an action, new orders are blocked.
- **Emergency Stop Override**: One-click Emergency Stop halts all paper risk submission and writes an immutable audit record.
