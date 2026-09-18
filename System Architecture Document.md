# System Architecture Document

## 1. Purpose

This document describes the high-level architecture for the hybrid human-in-the-loop cryptocurrency-options platform.

## 2. Architecture principles

The architecture is event-driven, replayable, modular, permissioned, observable, and fail-closed. Research, recommendation, risk, and execution concerns are separated. The user interface cannot bypass the risk engine or mandate service.

## 3. Context diagram

```text
┌──────────────┐   market data   ┌──────────────────────┐
│ Option Venue │ ───────────────> │ Data Adapter         │
└──────────────┘                  └──────────┬───────────┘
                                             ↓
                                   ┌──────────────────────┐
                                   │ Normalize / Validate │
                                   └──────────┬───────────┘
                                             ↓
                         ┌───────────────────┴───────────────────┐
                         ↓                                       ↓
                ┌────────────────┐                    ┌────────────────┐
                │ Event Archive  │                    │ Live Features  │
                └───────┬────────┘                    └───────┬────────┘
                        ↓                                     ↓
                ┌───────────────┐                    ┌───────────────┐
                │ Replay/DuckDB │                    │ Model Services│
                └───────────────┘                    └───────┬───────┘
                                                              ↓
                                                   ┌────────────────────┐
                                                   │ Recommendations    │
                                                   └─────────┬──────────┘
                                                             ↓
┌──────────────┐      approval / control      ┌─────────────┴──────────┐
│ User Browser │ <──────────────────────────> │ API + Mandate Service  │
└──────────────┘                              └─────────────┬───────────┘
                                                           ↓
                                                   ┌────────────────────┐
                                                   │ Independent Risk    │
                                                   └─────────┬──────────┘
                                                             ↓
                                                   ┌────────────────────┐
                                                   │ Paper Execution     │
                                                   └────────────────────┘
```

## 4. Deployment view

The dashboard and API may run on managed web hosting. Persistent market-data, replay, and paper-trading workers require an always-on process. PostgreSQL/TimescaleDB stores application state; object storage stores historical events; monitoring runs separately from the strategy services.

A future production candidate should separate control-plane services from latency-sensitive services and use dedicated infrastructure only after profiling proves it necessary.

## 5. Integration points

- Venue market-data WebSocket and HTTP APIs.
- Authentication provider.
- PostgreSQL/TimescaleDB.
- Object storage.
- Optional Kafka/Redpanda.
- Optional ClickHouse.
- MLflow model registry.
- Prometheus/Grafana/OpenTelemetry.
- Notification provider.

No production order-entry integration is part of the initial architecture.

## 6. Data flow

Raw events are captured first, normalized second, quality-checked third, and only then made available to features and models. Every downstream object carries source timestamps and version references. Model outputs feed recommendations; recommendations pass through user mode and mandate checks; all executable or simulated actions pass through independent risk validation.

## 7. Security boundaries

The browser can request analytics and submit user decisions but cannot access secrets or directly connect to venue APIs. Service credentials are server-side. The risk service has authority to reject actions but cannot generate a new user mandate. The audit store receives events from all critical services.

## 8. Availability and recovery

The system should tolerate data reconnects, worker restarts, delayed events, and model-service restarts. Recovery uses event replay and persisted application state. Critical failure behavior is to stop new risk, preserve auditability, alert the user, and permit only explicitly authorized risk-reducing actions.

## 9. Scaling path

Begin with a modular monolith or small number of services. Add event streaming, ClickHouse, service separation, dedicated hosts, and specialized networking only when measured throughput, latency, or availability requirements justify the complexity.
