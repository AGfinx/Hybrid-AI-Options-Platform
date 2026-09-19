# RFC-001: Technology Stack and Hybrid Execution Architecture

## Status

Proposed.

## Summary

This RFC proposes Python for quantitative research, Next.js/React/TypeScript for the user dashboard, FastAPI for quantitative APIs, PostgreSQL/TimescaleDB plus Parquet/DuckDB for initial storage, Rust for later deterministic real-time services, and a human-in-the-loop operating model with paper trading before any live execution consideration.

## Motivation

The product requires both rapid quantitative experimentation and reliable, observable user-controlled workflows. A single language or platform would either slow research or weaken deterministic service design. Separating these concerns provides a practical path from research to production candidate.

## Options considered

### Python-only

Fast for research and simple to operate, but less suitable for deterministic high-throughput data and latency-sensitive services.

### TypeScript-only

Strong for application development, but weaker for the project’s numerical modeling and scientific ecosystem.

### C++ from the beginning

Potentially fast, but expensive for research iteration and more exposed to memory-safety errors.

### Proposed hybrid

Python for research and models; TypeScript for dashboard; FastAPI for APIs; Rust for deterministic services; managed infrastructure first; specialized hardware later.

## Decision

Adopt the proposed hybrid stack. Begin with public market data, local simulation, human review, and paper trading. Do not enable production order entry in the initial environment.

## Consequences

The team must maintain API contracts and model artifact compatibility across Python and Rust/TypeScript boundaries. It must also prevent duplicated business logic. The positive consequence is that quantitative experimentation remains fast while production-critical paths can become deterministic later.

## Rejected premature complexity

Kubernetes, Kafka, FPGA, kernel bypass, co-location, online reinforcement learning, and multi-venue execution are deferred until measured needs and validated paper-trading economics exist.

## Review questions

1. Does the team agree that recommendation mode is the default?
2. Are all live capabilities explicitly disabled in the research environment?
3. Which venue and instrument universe are approved for v1?
4. What evidence will justify moving from Python services to Rust?
5. Who owns risk-limit approval and model promotion?

## Rollback plan

The architecture can revert to a Python modular monolith and local Parquet/DuckDB replay if service decomposition creates operational burden. No rollback may bypass audit, mandate, or risk checks.
