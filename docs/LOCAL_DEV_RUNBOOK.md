# Local Development Runbook & Verification Playbook

This runbook provides complete instructions for setting up, running, testing, and verifying the **Hybrid AI Options Platform** locally.

---

## 1. System Requirements & Architecture

- **OS**: Windows / macOS / Linux
- **Python**: 3.11+ (virtual environment located in `.venv`)
- **Node.js**: 18+ (tested on Node.js 20+)
- **Ports Used**:
  - `8000`: FastAPI Backend Server
  - `3000`: Next.js Web Frontend
- **Database**: SQLite default (`platform.db`), TimescaleDB/PostgreSQL compatible.

---

## 2. Quickstart: Launching the Services

### Terminal 1: FastAPI Backend
```powershell
# From the repository root
.venv\Scripts\uvicorn services.api.main:app --host 127.0.0.1 --port 8000 --reload
```
- API root: `http://localhost:8000/`
- Interactive OpenAPI Docs: `http://localhost:8000/docs`
- Default Auth Header: `Authorization: Bearer dev-token`

### Terminal 2: Next.js Frontend Dashboard
```powershell
# From the repository root
cd apps/web
npm run dev
```
- Dashboard URL: `http://localhost:3000`

---

## 3. Automated Test Suites

### Unit & Integration Tests (pytest)
Runs 34 tests covering quant pricing, SVI surface fitting, RV forecasting, independent risk limits, paper simulator execution, and REST endpoints:
```powershell
.venv\Scripts\pytest
```

### Full End-to-End Lifecycle Verification Script
Executes all 12 stages of the options workflow against the live running backend (market health $\to$ surface & SVI $\to$ opportunity generation $\to$ dynamic edit $\to$ watchlist toggle $\to$ risk check $\to$ atomic paper fill $\to$ delta hedging $\to$ P&L attribution $\to$ stress test $\to$ emergency stop fail-closed test $\to$ audit log):
```powershell
.venv\Scripts\python tests/verify_e2e.py
```

### Frontend Build Verification
Verifies TypeScript typing, static page generation, and bundle compilation:
```powershell
cd apps/web
npm run build
```

---

## 4. Operating Procedures & Safety Invariants

### Operating Modes
1. **`recommendation` (Default)**:
   - Automated opportunity generation and risk calculation.
   - Requires explicit human approval before any order is submitted to the paper simulator.
   - Live exchange trading is strictly disabled.
2. **`analytics`**:
   - Market data and volatility surface analytics only. No trade recommendations are actionable.
3. **`assisted` / `bounded_automation`**:
   - Reserved for future assisted execution mandates under strict risk boundaries; live execution endpoints remain disabled.

### Emergency Stop Procedures
- **Trigger**: Click **"EMERGENCY STOP"** in the UI header, or send:
  ```http
  POST /api/v1/controls/emergency-stop
  Content-Type: application/json
  Authorization: Bearer dev-token

  { "reason": "Immediate risk freeze", "confirmed": true }
  ```
- **Behavior**: Trips the `emergency_stop` circuit breaker. The risk engine immediately **fails closed**, rejecting any subsequent order approvals with `HTTP 422`.
- **Reset**:
  ```http
  POST /api/v1/controls/emergency-stop/reset
  Authorization: Bearer dev-token
  ```
