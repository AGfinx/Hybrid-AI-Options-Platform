# Hybrid AI Options Platform Documentation

This directory contains the product, business, functional, technical, architecture, API, operations, and developer documentation for the hybrid human-in-the-loop cryptocurrency-options platform.

## Documentation map

| Document | Purpose | Primary audience |
|---|---|---|
| [BRD](BRD.md) | Business goals, users, scope, value, and business success measures | Business owners, product leadership, risk owners |
| [PRD](PRD.md) | Product vision, features, user stories, modes, and product success criteria | Product, design, engineering, users |
| [FRD](FRD.md) | Testable functional requirements and system behaviors | Engineering, QA, product |
| [TDD](TDD.md) | Detailed technical design, services, data entities, reliability, security, and testing | Developers, architects, SRE |
| [System Architecture](ARCHITECTURE.md) | High-level components, data flow, integrations, deployment, and security boundaries | Architects, engineering leadership |
| [RFC-001](RFC-001-technology-stack.md) | Proposed technology stack and staged architecture decision | Engineering team, reviewers |
| [API Reference](API.md) | Versioned API conventions, endpoints, payloads, response codes, and safety rules | Backend and frontend developers, integrators |
| [Runbook](RUNBOOK.md) | Deployment, monitoring, incident response, restart, rollback, and emergency procedures | SRE, operations, on-call engineers |

## Recommended reading order

1. Read the BRD to understand business value, scope, target users, and financial impact.
2. Read the PRD to understand product capabilities and the hybrid operating model.
3. Read the FRD to understand testable behaviors.
4. Read the architecture and TDD to understand implementation boundaries.
5. Read RFC-001 to review technology choices and deferred complexity.
6. Read the API reference when implementing services or integrations.
7. Read the runbook before deploying or operating any environment.

## Operating principle

The platform may automate analysis broadly, recommendations selectively, execution narrowly, and risk reduction decisively. The user controls the authority granted to each strategy.

## Environment policy

Development, research, paper, test, shadow, and production-candidate environments must be separated. Production order-entry capability must remain disabled until quantitative validation, security review, operational testing, compliance review, and explicit approval are complete.

## Local documentation preview

These files are standard Markdown and can be viewed in any Git repository or Markdown editor. For a local preview, use any Markdown-capable editor or static documentation generator.

## Contribution rules

Changes to requirements, APIs, risk limits, data schemas, model contracts, or operating modes require a document update and review. Code changes that affect a documented contract must update the relevant document in the same change.

## Versioning

Each document should acquire a version, owner, status, and last-reviewed date when adopted into a repository. The current documents are a coherent initial baseline derived from the platform concept and hybrid workflow.
