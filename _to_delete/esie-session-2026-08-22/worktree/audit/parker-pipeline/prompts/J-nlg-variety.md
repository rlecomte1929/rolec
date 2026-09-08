## Task body — step J

**UI impact:** In-place updates only. Modifies the existing HR command center
exec summary card and adds a TL;DR panel inside the existing policy viewer. No
new pages, no new top-level routes, no new components — only swapping the
content source on existing surfaces. Does NOT require UI-PROPOSAL.md.

Diversify NLG. Today ReloPass produces markdown templates only; Parker enumerates
14 NLG approaches. Add three high-leverage ones: (1) **data-to-text** for executive
HR dashboards, (2) **frame-based NLG** for incident / case reports, (3) **extractive
summarisation** for long policy documents. Each serves a distinct buyer artefact
the LLM-only path cannot match for cost, auditability, or determinism.

### Prerequisites from prior steps
_None required._

If step I (translation) has shipped, the NLG outputs here should optionally route
through translation when the recipient's preferred_language ≠ source language.
Read `audit/parker-pipeline/runs/<RUN_ID>/I/RESULT.md` if present.

### Source material
- `backend/app/services/guidance_markdown.py` — current template-based NLG.
- `backend/app/services/policy_session_pdf.py` — PDF rendering path.
- `audit/parker-framework-audit.md` section 2 (W11) and section 4, Prompt J.

### Concrete deliverables

1. New package `backend/app/services/nlg/`:
   - `__init__.py` exports `data_to_text`, `frame_based`, `extractive_summarizer`.
   - `nlg/data_to_text.py`:
     - `summarise_kpis(kpis: KPISet, *, audience: Literal['exec', 'hr-ops']) -> str`
       — takes a structured dict of KPIs (current value, prior value, delta,
       target, anomaly flag) and produces a 3–5 sentence summary using
       deterministic templates plus sentence ordering by salience (largest
       absolute delta first; anomalies always lead).
     - No LLM call. No randomness. Same input → same output (assert with snapshot).
   - `nlg/frame_based.py`:
     - `Frame(event_type, slots)` dataclass.
     - Registered frames for: `passport_expiry_at_risk`, `assignment_milestone_missed`,
       `policy_change_required`, `supplier_unresponsive`.
     - `render(frame: Frame) -> str` fills slots into a pre-vetted template,
       respecting locale and number/date formatting (use `babel` if present;
       otherwise stdlib `datetime`+`locale`).
     - Localisation hooks: each frame has a translation key; if step I shipped,
       optionally route through translation_service.
   - `nlg/extractive_summarizer.py`:
     - `summarise(text: str, *, max_sentences: int = 5) -> str` — TextRank-style
       extractive summariser; **no LLM call**; pure Python with `networkx` for
       the graph + a simple TF-IDF sentence similarity.
     - Add `networkx>=3.0` to `backend/requirements.txt` (likely already a
       transitive dep; check before adding).
2. Wire into product surfaces:
   - HR command center exec summary card → use `data_to_text.summarise_kpis`
     with `audience='exec'`.
   - Case alerts feed → emit frame-based reports for the four registered event
     types.
   - Policy viewer → "TL;DR" panel using `extractive_summarizer.summarise` on the
     active policy document.
3. Frontend:
   - Update `frontend/src/features/hr/command-center/` to read the new NLG
     endpoints.
   - New endpoint: `GET /api/hr/{company_id}/exec-summary` returning the
     data-to-text output.
   - New endpoint: `GET /api/policies/{policy_id}/tldr` returning the extractive
     summary.
   - Register both in a new router `backend/app/routers/nlg.py`.
4. Tests:
   - `backend/tests/test_nlg_data_to_text.py` — snapshot test on a 6-KPI fixture
     for each audience; anomaly-leads-first ordering verified.
   - `backend/tests/test_nlg_frame_based.py` — each registered frame renders
     correctly; missing slot raises typed error; locale variants render.
   - `backend/tests/test_nlg_extractive.py` — known input/output on a small
     corpus; sentence ordering is preserved relative to source where ties.
   - `backend/tests/test_nlg_router.py` — endpoint auth + payload.
   - Determinism test: each function called twice on identical input returns
     identical bytes.

### Design notes
- **Three NLG approaches, three distinct guarantees:**
  - Data-to-text: deterministic, auditable, no model fees.
  - Frame-based: deterministic, schema-validated, ideal for incident reports
    where wording precision matters for legal / compliance reasons.
  - Extractive: deterministic, runs on CPU, no PII leak risk.
- All three are LLM-free by design. That is Parker's whole point on Page 2:
  classical NLG is often sufficient and is always cheaper.
- The exec summary today (if it exists at all) is likely either hardcoded or
  Claude-generated. The Claude-generated version is fine for now — gate the
  swap behind an env flag `NLG_EXEC_SUMMARY_PROVIDER=data_to_text|llm` so the
  rollback is one env change.

### Out of scope
- The other 11 NLG approaches Parker lists (template, rule, hybrid, grammar,
  decision-tree, abstractive, graph-based, ontology, chunk-and-merge,
  lexicon-driven, narrative-planning). They can be added later under the same
  `nlg/` package.

### Acceptance criteria
- pytest + tsc both pass.
- All three NLG functions are LLM-free (assert in tests: no openai/anthropic
  call is made during these unit tests, even with mocking).
- Snapshot tests pass and lock down the deterministic outputs.
- Frontend exec summary renders the data-to-text output behind the env flag.
- Policy TL;DR renders the extractive summary on a 40-page fixture policy.
