# Hybrid AI Options Platform - Web Dashboard

A financial-grade dashboard interface built with **Next.js 16**, **React 19**, **TypeScript**, and **TailwindCSS** for real-time cryptocurrency options analytics, independent risk monitoring, opportunity evaluation, and paper trading.

---

## Key Features & Views

1. **Cockpit View (`CockpitView.tsx`)**:
   - Live operating mode indicator (`Recommendation Mode` strictly enforced by default).
   - Real-time market data health, spot price tracker ($65,000 baseline), and quote freshness indicators.
   - Aggregate portfolio Greeks (Delta, Gamma, Vega, Theta) and margin utilization dials.
   - One-click Emergency Stop circuit-breaker trigger.

2. **Volatility Surface View (`SurfaceView.tsx`)**:
   - Interactive 2D/3D implied volatility smile and skew visualization.
   - **SVI (Stochastic Volatility Inspired)** parametric slice fitting and term structure across expiries.
   - Arbitrage violation flags (calendar and butterfly spread sanity checks) with confidence metrics.

3. **Opportunity Queue (`RecommendationsView.tsx`)**:
   - Algorithmic volatility arbitrage discovery across single-leg, delta-neutral straddles, and calendar spreads.
   - Transparent net edge computation deducting spread crossing, exchange fees (3 bps), dynamic slippage, delta-hedging drag, borrow/carry, and model uncertainty penalty.
   - Watchlist toggle and filtering.

4. **Human Review Modal (`ReviewModal.tsx`)**:
   - Interactive review dialogue enabling human traders to inspect pricing rationale and Greek exposures.
   - Dynamic quantity and limit price sliders that recalculate net edge and risk utilization in real time.
   - Mandatory rationale capture on rejection or approval before submission to the independent risk engine.

5. **Risk & Stress Engine (`RiskView.tsx`)**:
   - Independent gatekeeper evaluating Greek limits, capital concentration, and margin limits.
   - 2D Stress Testing Heatmap Matrix evaluating portfolio P&L under spot shocks (-20% to +20%) and implied volatility shocks (-15% to +15%).
   - Historical and Parametric Value-at-Risk (VaR 95%, 99%) and Expected Shortfall (CVaR).

6. **Paper Trading Simulator (`PaperTradingView.tsx`)**:
   - Deterministic paper execution model reflecting spread crossing, fee schedules, partial fills, and latency.
   - Automated delta-hedging simulation using BTC spot whenever portfolio delta drifts beyond limits.
   - Multi-factor P&L attribution decomposing returns into Delta, Gamma, Vega, Theta, Fees, Slippage, and Hedge components.

7. **Audit Trail (`AuditView.tsx`)**:
   - Immutable timeline of all system events, mode changes, reviews, approvals, risk rejections, and circuit breaker trips with correlated request IDs.

---

## Local Development Setup

### 1. Prerequisites
- Node.js 18+ (Node.js 20+ recommended)
- FastAPI backend server running on `http://localhost:8000`

### 2. Installation
```bash
# From within apps/web
npm install
```

### 3. Environment Variables
Create a `.env.local` file in `apps/web` (optional, defaults to `http://localhost:8000/api/v1`):
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

### 4. Running the Development Server
```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### 5. Production Build
```bash
npm run build
npm run start
```
