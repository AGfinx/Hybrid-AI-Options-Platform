# Engineering / Technical Design Document (TDD)

## 1. Design goals

The system must be reproducible, modular, observable, secure, and human-controlled. Research flexibility and execution determinism are separate concerns. Every model and decision must be versioned and replayable.

## 2. Logical architecture

```text
Venue data adapters
      ↓
Raw event archive → Event normalizer → Durable event log
                                      ↓
                          Feature and surface services
                                      ↓
                          Forecast and signal services
                                      ↓
                             Recommendation service
                                      ↓
                              Independent risk engine
                                      ↓
                       User approval / mandate service
                                      ↓
                       Paper execution or permitted adapter
                                      ↓
                Position ledger, P&L, audit, alerts, monitoring
```

## 3. Service boundaries

| Service | Responsibility |
|---|---|
| Data adapter | WebSocket/HTTP connectivity, reconnect, subscription, raw capture |
| Normalizer | Canonical event schema, quality flags, sequence checks |
| Event store | Durable append-only history and replay |
| Feature service | Timestamp-valid features and volatility inputs |
| Surface service | IV surface, confidence, structural checks, fallback |
| Forecast service | RV forecasts, uncertainty, drift statistics |
| Recommendation service | Net edge, structures, rationale, expiry |
| Risk service | Limits, stress, margin, circuit breakers, independent decision |
| Mandate service | User permissions, mode, limits, approvals, expiry |
| Execution simulator | Realistic fills, fees, slippage, partial fills, hedges |
| Portfolio ledger | Orders, fills, positions, cash, Greeks, P&L |
| Audit service | Append-only decision and configuration history |
| Web application | Dashboard, user actions, reports, alerts |

## 4. Data architecture

Use Parquet and object storage for immutable historical events, DuckDB for replay and research, PostgreSQL/TimescaleDB for transactional application state and recent time series, Redis for short-lived latest-state cache, and later Kafka/Redpanda plus ClickHouse when throughput and analytical volume justify them.

The canonical event includes `event_id`, `venue`, `instrument_id`, `event_time`, `receive_time`, `sequence_id`, `event_type`, `payload_version`, `raw_reference`, and `quality_flags`.

## 5. Core data entities

- `users`, `roles`, `permissions`
- `venues`, `instruments`, `instrument_versions`
- `market_events`, `quote_snapshots`, `trades`
- `feature_snapshots`
- `surface_runs`, `forecast_runs`, `model_versions`
- `recommendations`, `recommendation_edits`, `watchlists`
- `mandates`, `approvals`, `risk_limits`
- `paper_orders`, `paper_fills`, `positions`, `hedges`
- `stress_runs`, `pnl_attributions`
- `alerts`, `circuit_breakers`, `audit_events`

All important objects must have a stable ID, creation timestamp, version, and status.

## 6. Model contract

A surface request shall include a timestamp, validated reference contracts, market-data version, model version, and requested coordinates. The response shall include predicted IV, option price, confidence, calibration status, structural violations, and fallback status.

A forecast request shall include feature snapshot ID, horizon, model version, and timestamp. The response shall include forecast, uncertainty, regime label, and validity interval.

## 7. Decision pipeline

A recommendation is created only when data quality passes, model outputs are valid, net edge exceeds threshold, portfolio constraints can be satisfied, and the user’s mode permits recommendations. Execution preparation additionally requires a valid user approval or mandate. Final action always requires independent risk approval.

## 8. Reliability and failure behavior

If market data is stale, stop new recommendations. If the surface fails, use a fallback or abstain. If the forecast fails, reduce confidence or abstain. If the risk engine is unavailable, fail closed. If execution simulation fails, keep the recommendation unexecuted. If the user interface is unavailable, no new manually approved action should be accepted through an alternate ungoverned path.

## 9. Security

Use separate environments, least-privilege identities, server-side secrets, encrypted transport, secure cookies, role-based authorization, audit logging, rate limits, backups, and MFA for privileged users. Production credentials must never be present in research notebooks or client bundles.

## 10. Testing strategy

Use unit tests for formulas and limits, contract tests for APIs, deterministic replay tests, property tests for risk invariants, stress tests for market and infrastructure failures, load tests for data throughput, and user-acceptance tests for approval and emergency controls.

## 11. Deployment strategy

Start with Docker Compose. Deploy the dashboard and APIs on managed infrastructure and run a persistent paper-trading worker. Introduce Rust services and distributed streaming only when measured workloads require them. Treat co-location, kernel bypass, and FPGA as later optimization projects.

## 12. Technical decisions

- Python is the research and model-development language.
- Rust is the preferred deterministic service language.
- Next.js/React/TypeScript is the dashboard stack.
- FastAPI is the quantitative API layer.
- PostgreSQL/TimescaleDB is the initial control-plane database.
- Parquet/DuckDB is the initial research/replay layer.
- No production order adapter is enabled in the research environment.

## References

[1]: file:///home/ubuntu/hybrid-options-platform-docs/PRD.md "Project product requirements"
[2]: file:///home/ubuntu/hybrid-options-platform-docs/FRD.md "Project functional requirements"
