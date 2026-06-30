# D-Feedback — unified admin Feedback console

**Closes:** F-01, F-02, F-03, F-04. **Goal (G3):** every feedback stream is captured AND reaches an admin who can triage → act, with no write-only dead-ends.

## Problem
Five streams, one closes to a human:
- `public.feedback` (product widget) → `AdminFeedback`/`FeedbackTab` ✅ (but reads Supabase directly + buried).
- `ai_human_feedback` (AI thumbs/reviewer verdicts) → ML/eval only, **no admin view**.
- `policy_answer_helpfulness` (end-user policy thumbs) → endpoint exists but **no UI submits it**; admin sees only an aggregate.
- `policy_assistant_analytics` beacons + `policy_assistant_answer_audits` → admin dead-ends.

## Design
1. **Wire the missing producer (F-01, S):** add a 👍/👎 (+ optional comment) control to the policy-assistant answer UI → `POST /api/policy-assistant/helpfulness` (`routers/policy_helpfulness.py` already exists). Mirror the immigration thumbs in `features/immigration/ImmigrationAnswerPanel.tsx`.
2. **Read API (F-02/F-04):** add `GET /api/admin/feedback?stream=&status=&since=` returning a normalized item `{id, stream, source_ref, text|verdict, user/company, created_at, status, owner, resolution}` across `feedback` + `ai_human_feedback` + `policy_answer_helpfulness` (+ optional beacons summary). Replace `FeedbackTab`'s direct-Supabase read with this (standardizes the pattern).
3. **Triage state:** one `feedback_status` concept (`new → reviewed → acted_on → dismissed`) + `owner` + free-text resolution, persisted per item (reuse the existing `feedback` triage columns; add the same to a thin status table keyed by `(stream, source_id)` for the AI streams so we never mutate ML tables).
4. **Admin UI:** promote to a **sidebar item** "Feedback" with stream tabs (Product · AI answers · Helpfulness) + filters + the triage actions. Each AI-feedback row links to its trace (`policy_assistant_traces`) for context.
5. **Hook to D-BugRoutine:** a "Convert to ticket / dispatch" action on any item (see `11-design-bug-routine.md`).

## Reuse
`routers/feedback.py`, `components/admin/FeedbackTab.tsx`, `routers/policy_helpfulness.py` + `services/policy_helpfulness_service.py`, `services/ai_feedback_service.py`, `helpfulness_dataset_builder.py` (keep ML consumers untouched — this is read + status only), `policy_assistant_traces` for linkage.

## Acceptance metrics
Feedback streams with an admin view: 1 → ≥3. Policy-answer thumbs submittable (end-to-end test). No feedback stream is write-only. Feedback reachable ≤2 clicks (sidebar).
