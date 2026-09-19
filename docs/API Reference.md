# API Reference

## 1. API conventions

Base URL: `/api/v1`

All responses use JSON. Every response should include `request_id`. Timestamps use UTC ISO-8601. IDs are opaque strings. Mutating endpoints require authentication and authorization. All user actions create audit events.

## 2. Authentication

`Authorization: Bearer <token>`

The API must validate identity, role, portfolio scope, strategy scope, and action permissions. Authentication does not grant execution authority; authority comes from the active operating mode and mandate.

## 3. Market and analytics endpoints

### `GET /market/health`

Returns venue connectivity, latest event time, quote freshness, sequence status, and data-quality state.

### `GET /instruments`

Query parameters: `venue`, `underlying`, `expiry`, `state`.

Returns supported instruments and metadata versions.

### `GET /surfaces/{underlying}`

Query parameters: `timestamp`, `expiry`, `model_version`.

Returns surface points containing strike, expiry, implied volatility, option price, confidence, quote timestamp, structural status, and fallback status.

### `POST /forecasts/realized-volatility`

Request:

```json
{
  "underlying": "BTC",
  "horizon_seconds": 3600,
  "feature_snapshot_id": "fs_123",
  "model_version": "rv_2026_01"
}
```

Response:

```json
{
  "forecast_id": "fc_123",
  "forecast": 0.62,
  "uncertainty": 0.08,
  "regime": "elevated",
  "valid_until": "2026-09-17T15:00:00Z",
  "model_version": "rv_2026_01"
}
```

## 4. Recommendation endpoints

### `GET /recommendations`

Filters: `status`, `underlying`, `strategy`, `min_edge`, `created_after`.

### `GET /recommendations/{id}`

Returns structure, legs, prices, implied volatility, forecast volatility, net edge, costs, Greeks, margin, stress results, confidence, rationale, expiry, and current status.

### `POST /recommendations/{id}/approve`

Request:

```json
{
  "mode": "paper",
  "quantity_override": 2,
  "price_limit_override": null,
  "hedge_permission": "within_mandate",
  "comment": "Approved after liquidity review"
}
```

### `POST /recommendations/{id}/reject`

Request: `{ "reason": "Spread too wide" }`

### `POST /recommendations/{id}/edit`

Request contains changed quantity, price, structure, or hedge parameters. The API must recalculate costs, Greeks, margin, and stress before returning an actionable status.

## 5. Mandate endpoints

### `POST /mandates`

Creates a versioned, expiring strategy mandate. Required fields include strategy, instruments, venues, mode, capital limit, exposure limits, loss limits, hedge permissions, start time, and expiry.

### `GET /mandates`

Returns active and historical mandates within the user’s permission scope.

### `POST /mandates/{id}/pause`

Stops new actions under the mandate while preserving audit history.

### `POST /mandates/{id}/terminate`

Terminates the mandate and blocks further new risk.

## 6. Risk endpoints

### `GET /portfolio/risk`

Returns delta, gamma, vega, theta, margin, available capital, drawdown, concentration, short-option exposure, and current limit utilization.

### `POST /risk/stress-runs`

Request contains portfolio or recommendation ID and scenario grid. Response returns maximum loss, margin impact, and scenario-level results.

### `POST /controls/emergency-stop`

Requires privileged authorization and reason. Disables new risk and records an immutable audit event.

## 7. Paper-trading endpoints

### `POST /paper/orders`

Creates a paper order only after recommendation, mandate, and risk checks pass.

### `GET /paper/orders/{id}`

Returns order status, fill assumptions, timestamps, and linked recommendation.

### `GET /paper/positions`

Returns positions, Greeks, margin, P&L, and hedge state.

## 8. Reports and audit

### `GET /reports/pnl`

Returns P&L attribution by delta, theta, vega, realized gamma, unrealized gamma, fees, slippage, hedge cost, and residual.

### `GET /audit/events`

Returns authorized audit events with actor, action, object, timestamp, request ID, before state, and after state.

## 9. Response codes

| Code | Meaning |
|---|---|
| 200 | Success |
| 201 | Created |
| 400 | Invalid request |
| 401 | Unauthenticated |
| 403 | Not authorized by role, mode, or mandate |
| 404 | Resource not found |
| 409 | State conflict or stale recommendation |
| 422 | Validation or risk failure |
| 429 | Rate limit exceeded |
| 503 | Critical dependency unavailable; fail closed |

## 10. API safety requirements

The API must use idempotency keys for mutating requests, reject stale recommendations, enforce server-side authorization, redact secrets from logs, and attach correlation IDs to all downstream model, risk, and audit calls.
