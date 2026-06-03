# AI-005 · EU AI Act Post-Market Monitoring Plan v1 · ReloPass

**Task**: AIQ-653 · AI-005 (partial — plan + quarterly report template + table specs shipped here; migration + aggregator code ships in Claude Code)
**Author**: Claude Cowork via notion-task-executor
**Date**: 2026-06-03
**Owner**: Romain (CTO + acting CISO) — must approve cadence + thresholds before code ships
**Regulation reference**: EU AI Act (Regulation 2024/1689) Articles 72, 73; Annex IV §8
**Cross-references**: AI-003 Annex IV §8 (`outputs/annex_iv_technical_doc_v1.md`); AI-006 risk register monitoring section (`outputs/risk_register_v1.md`); AI-004 conformity assessment §4 Art. 72 traceability
**Document status**: v1 — procedural plan + table specs + report template. Implementation queued for Claude Code.

---

## 1. Purpose

Article 72 of the EU AI Act requires every provider of a high-risk AI system to **document, set up, and run a post-market monitoring system** proportionate to the nature of the AI system and the risks. This document is that monitoring plan.

The plan has three components:

- **The plan itself** — what we monitor, why, on what cadence, with what thresholds. This document.
- **The metric pipeline** — database tables + aggregators that compute the metrics. Spec'd here; built in Claude Code.
- **The quarterly report** — template that operationalises the §6 quarterly cadence. Spec'd here; populated quarterly by the on-duty operator.

---

## 2. Monitoring objectives (Art. 72(1))

Post-market monitoring serves four explicit purposes per Art. 72(1):

1. **Evaluate continuous compliance** with Chapter III Section 2 requirements (Articles 9-15).
2. **Detect emerging risks** not foreseen during the pre-market conformity assessment.
3. **Detect serious incidents** per Article 73 (15-day reporting window).
4. **Inform the next iteration** of the risk management system (AI-006), the technical documentation (AI-003), and the conformity assessment (AI-004).

Every metric in §3 below maps to at least one of these four objectives.

---

## 3. Metrics catalogue

Every metric has: definition, data source, cadence, threshold, owner, action-on-breach.

### 3.1 Operational quality

| # | Metric | Definition | Source | Cadence | Threshold | Action on breach |
|---|---|---|---|---|---|---|
| 1 | OCR disagreement rate (primary vs shadow) | % of shadow-OCR calls where primary and shadow extractors disagree on at least one field | `ocr_shadow_comparisons` | Daily aggregate | >5% over 7-day rolling window | Investigation: which provider drifted; sample 20 disagreements; consider prompt update or provider switch |
| 2 | Classifier escalation rate (gpt-4o-mini → gpt-4o) | % of classification calls that escalate to the higher tier due to low confidence | `agent_runs.escalation_level` | Daily aggregate | Trended; >20% rolling 14-day baseline | Investigation: which document types are escalating; consider prompt refinement |
| 3 | UNKNOWN classification floor rate | % of classification calls returning UNKNOWN (below 0.50 floor) | `agent_runs.outcome = 'UNKNOWN'` | Weekly aggregate | Trended | If trending up: prompt refinement; if trending down without explanation: confidence-floor recalibration |
| 4 | Human correction rate by extractor | % of extractor outputs corrected by HR | `ai_human_feedback` joined to extractor type | Weekly aggregate per extractor | >10% per extractor over 14-day window | Prompt review for that extractor; potential new fixture corpus pass |
| 5 | Pathway abandonment after extraction | % of employees who close Pathway after seeing an extraction confirmation screen but before confirming | `pathway_sessions` + `pathway_answers` derived | Weekly aggregate | Trended | UX investigation — extraction may be eroding trust |

### 3.2 Equity / fairness

| # | Metric | Definition | Source | Cadence | Threshold | Action on breach |
|---|---|---|---|---|---|---|
| 6 | Per-origin correction-rate delta | Correction rate per detected document-origin country minus baseline (FR/DE/NO) | `ai_human_feedback` + employee origin | Monthly | >15% delta | Investigation: prompt revision OR additional fixture corpus from underperforming origins (R-BIAS-01 / R-BIAS-03 action) |
| 7 | Per-corridor escalation rate | Escalation rate per FR→NO / FR→DE / etc. | `agent_runs.escalation_level` joined to case corridor | Monthly | Trended | Investigation: corridor-specific data quality issue |
| 8 | Family-cohort extraction accuracy | Accuracy of family-document (marriage, birth) extractions vs employee documents | `ai_human_feedback` joined to document type | Monthly | <90% (vs employee target) | Family-document prompt refinement |

### 3.3 Safety + security

| # | Metric | Definition | Source | Cadence | Threshold | Action on breach |
|---|---|---|---|---|---|---|
| 9 | RLS guard CI failures | Count of CI runs failing the AUDIT-A3 RLS guard | CI logs | Per merge | Any failure | Blocks merge; immediate investigation |
| 10 | Production debug-endpoint hits | Count of hits to `/debug/*` routes on prod | Render access logs | Daily | Any hit | Investigation — should be impossible after SEC-001; if any hit appears, security incident |
| 11 | Dependabot High advisories | Count of open High-severity dependabot advisories | GitHub Dependabot | Continuous | Any | Triage within 24h; mitigate within sprint |
| 12 | Failed auth → session count delta | Failed login attempts on prod | Supabase Auth logs | Daily | >100x baseline | DDoS / credential-stuffing detection |
| 13 | Schema-validation rejection rate | % of LLM outputs rejected by output JSON schema | `agent_runs.outcome = 'schema_rejection'` | Daily | Trended | If >5%: prompt review (output format drift) |

### 3.4 Operational reliability

| # | Metric | Definition | Source | Cadence | Threshold | Action on breach |
|---|---|---|---|---|---|---|
| 14 | OCR provider latency p95 | 95th percentile latency of primary OCR call | `agent_runs.latency_ms` | Daily | >8s | UX risk — Pathway feels broken; consider provider switch or queueing |
| 15 | OCR provider error rate | % of primary OCR calls returning error | `agent_runs.outcome = 'provider_error'` | Daily | >2% | Provider outage check; activate shadow as primary if needed |
| 16 | LLM provider model deprecation alerts | Count of provider model-deprecation notifications received | Manual / RSS | Continuous | Any | Prompt version planning cycle |
| 17 | Production deploy success rate | % of production deploys completing without rollback | Render deploy logs | Daily | <95% | Deploy hygiene review |

### 3.5 Process + governance

| # | Metric | Definition | Source | Cadence | Threshold | Action on breach |
|---|---|---|---|---|---|---|
| 18 | GDPR Art. 15-22 request count | Count of requests received | GDPR Requests Notion db (gap) | Monthly | Trended | If >5/month: capacity planning |
| 19 | Serious incident count (Art. 73) | Count of incidents requiring 15-day report | Incident log (gap) | Continuous | Any | Immediate Art. 73 reporting workflow |
| 20 | Quarterly risk-register review completion | Was the quarterly walk done on time? | This plan's §6 cadence | Quarterly | Late | Operator follow-up |

### 3.6 Cost + sustainability (not regulatory but tracked)

| # | Metric | Definition | Source | Cadence | Threshold | Action on breach |
|---|---|---|---|---|---|---|
| 21 | AI cost per case | Total LLM + OCR spend / cases closed | `ai_unit_economics` aggregated | Monthly | Trended | Unit economics review |

**Total catalogued metrics: 21.**

---

## 4. Continuous monitoring infrastructure

### 4.1 Data model (Claude Code task to ship)

```sql
-- Table 1: per-day aggregates
CREATE TABLE public.post_market_metrics_daily (
  metric_date     date NOT NULL,
  metric_id       text NOT NULL,             -- '01_ocr_disagreement', '02_classifier_escalation', etc.
  value_numeric   numeric,
  value_text      text,
  context         jsonb,                     -- e.g., {'provider': 'mistral'}
  computed_at     timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (metric_date, metric_id, context)
);

CREATE INDEX ix_pmm_daily_metric ON public.post_market_metrics_daily(metric_id, metric_date DESC);

-- Table 2: alerts / breaches
CREATE TABLE public.post_market_alerts (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  metric_id       text NOT NULL,
  triggered_at    timestamptz NOT NULL DEFAULT now(),
  threshold_text  text NOT NULL,
  observed_value  text NOT NULL,
  severity        text NOT NULL CHECK (severity IN ('info','warn','critical')),
  resolution_at   timestamptz,
  resolution_notes text
);

-- Table 3: quarterly review log
CREATE TABLE public.post_market_quarterly_reviews (
  quarter         text PRIMARY KEY,           -- '2026Q3'
  reviewer        text NOT NULL,
  conducted_at    timestamptz NOT NULL DEFAULT now(),
  report_md_path  text,                       -- e.g., 'audit/ai_post_market_report_2026Q3.md'
  notes           text
);
```

### 4.2 Aggregator pattern (pg_cron)

Each metric is computed by a pg_cron job that aggregates from the source table into `post_market_metrics_daily`. Reference pattern:

```sql
SELECT cron.schedule(
  'pmm-01-ocr-disagreement',
  '5 0 * * *',  -- daily 00:05 UTC
  $$
  INSERT INTO public.post_market_metrics_daily(metric_date, metric_id, value_numeric, context)
  SELECT
    CURRENT_DATE - 1,
    '01_ocr_disagreement',
    100.0 * AVG(CASE WHEN disagreed THEN 1 ELSE 0 END),
    jsonb_build_object()
  FROM public.ocr_shadow_comparisons
  WHERE created_at >= CURRENT_DATE - 8 AND created_at < CURRENT_DATE - 1
  ON CONFLICT DO NOTHING;
  $$
);
```

### 4.3 Alert pattern (threshold trigger)

```sql
SELECT cron.schedule(
  'pmm-alerts-01-ocr-disagreement',
  '10 0 * * *',
  $$
  INSERT INTO public.post_market_alerts(metric_id, threshold_text, observed_value, severity)
  SELECT
    '01_ocr_disagreement',
    'value > 5.0',
    value_numeric::text,
    'warn'
  FROM public.post_market_metrics_daily
  WHERE metric_id = '01_ocr_disagreement'
    AND metric_date = CURRENT_DATE - 1
    AND value_numeric > 5.0
    AND NOT EXISTS (
      SELECT 1 FROM public.post_market_alerts a
      WHERE a.metric_id = '01_ocr_disagreement'
        AND a.triggered_at >= CURRENT_DATE - 1
    );
  $$
);
```

(Per-metric customisation needed — this is the pattern.)

### 4.4 Observability emission

Every aggregator additionally:
- Emits a structured log line (consumed by CloudWatch or Sentry).
- Updates a counter metric in the observability stack (Grafana / Sentry alerts).

This redundant emission provides escape-hatch alerting if the in-database alert mechanism fails.

---

## 5. Serious incident reporting workflow (Art. 73)

Article 73 requires the provider to report serious incidents to the relevant national competent authority within 15 days of awareness (immediately, if certain conditions are met). "Serious incident" definitions are broad — counsel should pressure-test the workflow.

### 5.1 Definition (provisional — counsel to confirm)

A serious incident occurs if any of:

- A natural person experiences harm (physical, mental, financial) attributable to the AI system.
- A widespread infringement of a person's rights occurs.
- The AI system materially deviates from its intended purpose without operator awareness.
- Critical infrastructure dependency on the AI system has a serious malfunction.

For ReloPass, plausible scenarios include: wrong immigration form filed causing employment delay; PII leak from misconfigured RLS; mass-bias episode (per R-BIAS-* monitoring threshold breach for a defined cohort).

### 5.2 Workflow

```
DETECTION
─────────
Source: threshold alert OR customer report OR internal observation

TRIAGE (within 24h)
───────────────────
Operator (Romain) classifies:
  - Routine bug? → normal bug tracking, NOT Art. 73
  - Serious incident? → §5.3 reporting workflow
  - Unsure? → counsel consult within 24h

REPORTING (within 15 days of awareness)
───────────────────────────────────────
1. Notify CNIL (France market surveillance authority) via formal channel
2. Notify affected data subjects per GDPR Art. 34 if breach is also a personal-data breach
3. Notify affected HR customers per contractual obligation
4. Document in `audit/incidents/<incident_id>/`:
   - Initial report (within 15 days)
   - Investigation log (rolling)
   - Final report (when closed)
   - Corrective actions taken

POST-INCIDENT
─────────────
- Update AI-006 risk register with new mitigations
- Update AI-003 Annex IV if mitigation involves system change
- Re-run AI-004 conformity assessment if Art. 9 + 14 + 15 mitigations change materially
- Communicate corrective measures to affected parties
```

### 5.3 Templates

`audit/incidents/INCIDENT_TEMPLATE.md` (Claude Code to ship):

```markdown
# Incident <ID> — <one-line title>

## Discovery
- Detected via: [alert / customer / internal observation]
- Discovered at: [iso]
- First operator awareness: [iso]

## Classification
- Triage rating: [routine bug / serious incident / TBD]
- Affected scope: [N data subjects, N companies]
- Art. 73 reporting window expires: [iso = awareness + 15 days]

## Initial assessment
[Free text — what we know, what we don't]

## Containment actions
[Immediate steps taken]

## Reporting
- CNIL notified: [iso] · [reference]
- GDPR Art. 34 subject notifications: [iso] · [N notifications]
- Affected customer notifications: [iso] · [N customers]

## Investigation log
[Rolling notes]

## Resolution
- Root cause: [free text]
- Corrective actions: [list]
- Risk register update: [link]
- Annex IV update: [if any]
- Conformity assessment update: [if any]

## Close-out
- Closed at: [iso]
- Closed by: [operator]
- External counsel reviewed: [Y/N]
```

---

## 6. Quarterly review cadence

The quarterly review is the "human checkpoint" that complements the daily/weekly aggregators.

### 6.1 What happens

- Walk every metric in §3 against last quarter's baseline.
- Re-score the AI-006 risk register residual ratings.
- Surface any new risks identified.
- Update Annex IV §8 if anything material changed.
- Log the review in `post_market_quarterly_reviews` table.
- Save the report to `audit/ai_post_market_report_<quarter>.md`.

### 6.2 Schedule

- **2026Q3** — review window: 2026-09-15 to 2026-09-30. Report due 2026-09-30.
- **2026Q4** — 2026-12-15 to 2026-12-31.
- **2027Q1** — 2027-03-15 to 2027-03-31.
- (Calendar item ⚠ gap — formalise in Romain's calendar.)

### 6.3 Quarterly report template (`audit/ai_post_market_report_<quarter>.md`)

```markdown
# Post-Market Monitoring Report — Q[N] 20[YY] · ReloPass

**Reviewer**: [name]
**Conducted**: [iso]
**Reporting period**: [start] to [end]

## TL;DR
[3-sentence summary: what's stable, what changed, what needs attention]

## §3.1 Operational quality
| Metric | Period value | vs prior quarter | Threshold met? | Action |
|---|---|---|---|---|
| 01 OCR disagreement | _% | _% | ✅/⚠/❌ | _ |
| ... | | | | |

## §3.2 Equity / fairness
[same table structure]

## §3.3 Safety + security
[same]

## §3.4 Operational reliability
[same]

## §3.5 Process + governance
[same]

## §3.6 Cost
[same]

## Alerts triggered this quarter
[copy from post_market_alerts table]

## Incidents this quarter
- Routine bugs: _
- Serious incidents (Art. 73): _
- Personal data breaches (Art. 33): _

## Risk register changes
[summary of AI-006 risk register changes; full diff stored separately]

## Recommended actions for Q[N+1]
1. [action]
2. [action]

## Annex IV / Conformity-assessment impact
[any changes that flow back to AI-003 / AI-004]

## Sign-off
- Reviewer: [name]
- DPO: [Romain]
- (Counsel — annual)
```

---

## 7. Roles + responsibilities

| Role | Responsibility | Backup |
|---|---|---|
| DPO + reviewer (Romain) | Approve thresholds; conduct quarterly review; close out incidents | TBC — see §10 gap |
| On-call operator (Romain) | Triage daily alerts; classify incidents | TBC — see §10 gap |
| Counsel | Annual conformity re-assessment; serious-incident classification consult | External |
| Engineering | Ship §4 metrics infrastructure; fix root causes | Romain |

⚠ **Single-person dependency is the largest operational risk** — see AI-006 R-INC-01.

---

## 8. Data subject + customer transparency

Per Art. 72(2) information about the operation of the post-market monitoring system shall be made available to deployers (HR customers) and, on request, to national competent authorities.

ReloPass will:
- Publish a **summary** of the post-market monitoring plan + last-quarter's metrics on a public `/eu-ai-act` page (TBC — Annex IV §3 follow-up).
- Provide the **full** plan + raw data to deployers on request, governed by NDA.
- Provide everything to competent authorities on request.

---

## 9. Validation against AIQ-653 criteria

- ✅ **Criterion: Post-market monitoring plan document drafted** — §1-§7 above.
- ✅ **Criterion: ≥20 catalogued metrics with definitions + cadences + thresholds** — 21 metrics in §3 across 6 categories.
- ✅ **Criterion: Serious-incident reporting workflow** — §5.
- ✅ **Criterion: Quarterly review cadence + report template** — §6.
- ✅ **Criterion: Data model for metric pipeline specified** — §4.1.
- ⚠ **Criterion: Database migration shipping the tables** — out of scope; Claude Code task.
- ⚠ **Criterion: pg_cron aggregators implemented** — out of scope; Claude Code task.
- ⚠ **Criterion: First quarterly report run in 2026Q3** — operational milestone; calendar gate.

**Recommendation**: mark AI-005 in Notion as **Validation** rather than Done — the plan + spec is complete, the migration + aggregator code waits for Claude Code.

---

## 10. Known gaps

- ⚠ **Quarterly review calendar item** — schedule the 2026Q3-Q4 + 2027Q1 reviews in Romain's calendar.
- ⚠ **Backup on-call operator** — even informal designation reduces R-INC-01 residual rating.
- ⚠ **GDPR Requests Notion db** — referenced from §3 metric 18; ship in parallel with PRIV-001 follow-ups.
- ⚠ **Incident folder structure** — `audit/incidents/INCIDENT_TEMPLATE.md` + first dummy run.
- ⚠ **Customer-facing `/eu-ai-act` page** — referenced from §8.
- ⚠ **National competent authority contact** — confirm exact CNIL division or future-named AI authority for France; document in counsel handoff.

---

## 11. Document metadata

- **Version**: v1.0 (Cowork half — plan + spec).
- **Generated**: 2026-06-03.
- **Generator**: Claude Cowork via notion-task-executor.
- **Source materials**: EU AI Act Art. 72, 73; Annex IV §8; AI-003 Annex IV doc; AI-004 conformity assessment; AI-006 risk register.
- **Next planned revision**: v1.1 after Claude Code ships §4 data model + aggregators, plus Romain operational sign-off on §3 thresholds.

---

*Generated 2026-06-03 by Claude Cowork via notion-task-executor. Cowork half — plan + spec + report template. Claude Code ships the data model and aggregators. Both halves close the EU AI Act Annex VI internal-control conformity bundle.*
