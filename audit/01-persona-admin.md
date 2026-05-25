# Persona Input — Admin / Ops / Internal Operator

**Sources:** Internal-only persona (Romain + future ops team). No external interview signal. Evidence drawn from: codebase `frontend/src/pages/Hr*.tsx` + `Admin*.tsx` + `backend/app/routers/admin_*.py` patterns; AI Work Queue items in `Product Area = Infrastructure` and admin-tagged items; prior synthesis §10 ops/operational dependencies.

## Jobs to be done

1. **Curate the country/corridor catalog** — destinations, vendors, schools, neighborhoods, resources. Keep them fresh.
2. **Manage policy templates and form templates** as data, not Word docs.
3. **Configure suppliers** (vendor curation, preferred-supplier lists per company).
4. **Operate the prospect/sales funnel** (admin_prospects router).
5. **Triage ops/support tickets, A/B tests, and the dev loop autofix pipeline** — keep the platform self-improving.
6. **Run analytics**: ops dashboards, workflow analytics, freshness checks, review queues.

## Surface area (mapped from `backend/app/routers/admin_*.py`)

| Router | Concern |
|---|---|
| `admin.py` | Generic admin |
| `admin_catalog.py` | Country/destination catalog |
| `admin_collaboration.py` | Internal collaboration |
| `admin_form_templates.py` | Form Template Registry |
| `admin_freshness.py` | Data freshness checks |
| `admin_mobility.py` | Mobility-specific admin |
| `admin_notifications.py` | Notification config |
| `admin_ops_analytics.py` | Ops dashboards |
| `admin_prospects.py` | Sales prospects |
| `admin_resources.py` | Resource catalog (schools, neighborhoods, etc.) |
| `admin_review_queue.py` | Review-queue triage |
| `admin_staging.py` | Staging/preview |
| `admin_workflow_analytics.py` | Workflow analytics |

**Observation:** 13 admin routers but only **25 services**. Admin surface area has grown to dominate router count — Phase 2b must check whether routers correctly delegate to services or duplicate logic.

## Pain points (inferred, no interview evidence)

⚠ **No customer-interview signal for this persona.** All findings here are inferred from code + AI Work Queue items + author-known context. They are explicitly hypotheses, not validated pain.

Hypothesized pain:
- **Catalog freshness drift** — `admin_freshness.py` exists but if it's a manual UI for stale-row detection, it doesn't scale beyond Singapore.
- **Policy template editor ergonomics** — AI Work Queue items P1-2 (Form Template Registry admin UI), P1-3 (Policy Builder UI), P2-3 (Form Editor side-by-side) all "Ready for AI" — i.e., not shipped yet.
- **Review queue throughput** — P2-6 (HR document review queue UI) in queue; volume unclear without telemetry.
- **No unified ops dashboard** observed yet — analytics is split across `admin_ops_analytics.py` + `admin_workflow_analytics.py` + `hr_analytics.py`.

## Success criteria

- Adding a new destination corridor → one admin flow to seed vendors + schools + neighborhoods + watchouts + currency + resources, without writing migration SQL.
- Editing a policy template → diffs visible vs. live version, dry-run preview against existing cases.
- Review queue → ranked by SLA, one-click approve/reject with reason, audit-logged.
- Single ops dashboard surfacing: active cases, blocked cases, freshness, supplier health, exception count.

## Friction observed (already known)

- Prior synthesis flags **architectural concerns** around `Task.due_date` + date triggers (Spike 2) — these touch admin operability indirectly (alerting, freshness, SLA).
- Admin UIs may inherit the same jargon problem (W3) since they're authored by the same hands; needs live verification.

## Cross-reference: AI Work Queue items in Product Area = Infrastructure / UX

Items already in queue (i.e., "known" friction the team plans to fix):
- P1-2 Form Template Registry — admin UI to create, edit, version templates
- P2-3 Form Editor UI — side-by-side PDF + field panel
- P2-6 HR document review queue UI
- P3-1 PDF Service, P3-3 Form PDF download
- P5-3 Question tile system + guided assistant
- P5-5 Feedback collection → HR review queue
- Pets section design (367887c6-...8109) — flagged in May 2026 design review

This means: when Phase 3 synthesis lists admin pain, anything overlapping this list is **already known** (not a new finding); only what's NOT here is newly surfaced.

## Open questions for Phase 2

- Is there a single admin home that gives Romain a daily "what needs me" view?
- Do the 13 admin routers share auth/role-guard scaffolding, or each reimplement?
- Catalog editing: in-app or DB-direct? If DB-direct, that's a real operational risk.
- Is the dev-loop autofix pipeline (commit `4648944`) admin-visible? Should it be?

## Signal quality

- **Zero external interviews** for this persona. Phase 3 must explicitly mark all admin findings as "internal-inferred, not customer-validated."
- AI Work Queue + code surface area give a coarse map. Live UI walkthrough in Phase 2c will refine.
