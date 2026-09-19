# Operations Runbook / Playbook

## 1. Operating modes

The system supports Analytics, Recommendation, Assisted Execution, and Bounded Automation. Recommendation mode is the default. Operators must verify the active mode before investigating any event.

## 2. Daily start checklist

1. Confirm service versions and deployment status.
2. Confirm venue connectivity and data freshness.
3. Check sequence gaps and reconnect history.
4. Confirm model and feature versions are approved.
5. Confirm risk limits and mandates are current.
6. Confirm emergency stop is available.
7. Confirm audit logging is healthy.
8. Confirm paper or approved execution mode.

## 3. Data outage procedure

Symptoms include stale quotes, sequence gaps, disconnected WebSocket, or invalid books.

Actions:

1. Confirm the affected venue and time of last valid event.
2. Stop new recommendations and new risk.
3. Preserve raw logs and connection diagnostics.
4. Attempt controlled reconnect and resubscription.
5. Reconcile snapshots and sequence continuity.
6. Keep the system in analytics-only mode until freshness is restored.
7. Notify the user and record an incident.

## 4. Model failure procedure

Symptoms include surface structural violations, extreme forecast uncertainty, inference errors, or drift alerts.

Actions:

1. Disable the affected model version.
2. Switch to approved fallback or abstain.
3. Preserve input snapshot and model logs.
4. Compare with the last approved model.
5. Do not promote a replacement automatically.
6. Require research and risk-owner review before reactivation.

## 5. Risk-limit breach procedure

Actions:

1. Stop new exposure.
2. Cancel pending paper or permitted orders as configured.
3. Recalculate portfolio Greeks and stress loss.
4. Permit only explicitly authorized risk reduction.
5. Notify the user and risk owner.
6. Record the trigger, actions, and final state.
7. Require manual restart after severe breaches.

## 6. Emergency stop

The emergency stop disables new risk immediately. It must be available from the dashboard and an independent operator path. Activation requires a reason and creates an immutable audit event. Restart requires review of data, model, risk, and mandate status.

## 7. Service restart

Restart services in dependency order: data adapter, normalizer, event consumer, model services, risk service, API, dashboard. After restart, verify state reconciliation from the durable event log and database. Do not resume recommendations until the system confirms current data and risk state.

## 8. Deployment procedure

1. Build immutable artifact.
2. Run unit, integration, replay, and security tests.
3. Deploy to development.
4. Run smoke tests.
5. Deploy to paper environment.
6. Observe shadow results.
7. Obtain model/configuration approval.
8. Deploy with rollback version available.
9. Verify dashboards, audit events, and health checks.
10. Announce completion and record release ID.

## 9. Rollback procedure

Rollback the application, model, or configuration to the previous approved version. Verify schema compatibility, replay a recent window, confirm risk limits, and keep new risk disabled until validation passes.

## 10. Incident severity

| Severity | Example | Response |
|---|---|---|
| Sev 1 | Uncontrolled risk, audit loss, emergency stop failure | Immediate shutdown and escalation |
| Sev 2 | Data outage, risk service unavailable, repeated model failure | Stop new risk; restore service urgently |
| Sev 3 | Degraded latency, stale recommendations, report delay | Investigate and correct during operating window |
| Sev 4 | Cosmetic dashboard or non-critical alert issue | Schedule correction |

## 11. Recovery objectives

Define and approve RTO/RPO before production candidate deployment. Historical raw data and audit records must be recoverable. Application state must reconcile from durable events and database backups.

## 12. Post-incident review

Every Sev 1 or Sev 2 incident requires a timeline, trigger, detection quality, user impact, risk impact, root cause, corrective action, test addition, and owner. Corrective actions must be tracked to closure.
