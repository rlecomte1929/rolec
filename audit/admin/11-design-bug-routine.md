# D-BugRoutine — in-app report → triage → agent routine → status-back

**Closes:** B-01, B-02, B-03. **Goal (G4):** a reported bug can be triaged and routed to an (agent-assisted) routine from inside the platform, with status back to the reporter.

## Problem
`routers/feedback.py::submit_feedback` only `INSERT`s a row and returns a `report_id`. All triage/fix automation is **external** (Notion AI Work Queue + Claude skills `relopass-bug-triage`/`autopilot`/`fix-*`) or **scheduled** (GH Actions cron). There is no bridge from an in-app report to that machinery, and the reporter never hears back.

## Design (3 layers; build incrementally)
1. **Ticket lifecycle (B-02, M):** promote feedback/error rows into first-class tickets with `{status: new→triaged→dispatched→in_progress→resolved→wontfix, severity, area (UI/API/Isolation/Feature), owner, dispatch_ref, reporter_id}`. Reporter sees status on their submission; admin sees the board (extends D-Feedback).
2. **Auto-triage (M):** on submit, classify severity + area (reuse the existing guardrail/classifier patterns; deterministic first, optional LLM-assist with `mask_pii` on the report text). Pre-fill the ticket so the admin triages, not transcribes.
3. **Dispatch bridge (B-01, L):** an admin "Dispatch routine" action that hands a triaged ticket to the execution layer. Two safe options (HITL by default):
   - **Notion path:** create an AI Work Queue task from the ticket (the skills already consume that queue). The app writes the task; a human/`autopilot` runs it; status syncs back via `dispatch_ref`.
   - **Scheduled-agent path:** for known classes, enqueue to an existing routine (e.g. an `e2e-campaign`/`fix-*` flow). Dispatch is **gated** — admin approves; 🔴-tier (isolation/security) never auto-dispatches (mirror the autopilot Red rule).
4. **Visibility (B-03, S):** an admin "Routines" view showing the cron/automation inventory + last-run status (read GH Actions run status) so external automation isn't invisible.

## Safeguards / HITL
Dispatch is human-approved by default; destructive or 🔴-tier fixes require explicit admin confirm + are audited (`audit_logs`, `new_value.event='ticket_dispatched'`). No auto-merge of agent fixes — they land as PRs gated by the normal review (and, presently, the held-PR + CI-budget reality).

## Reuse
`routers/feedback.py`, `components/admin/{FeedbackTab,ErrorTicketsTab}.tsx`, the Notion MCP / Work Queue (external), `.github/workflows/*` (run-status reads), the autonomy-tier rubric from `relopass-autopilot`, `pii_masker.mask_pii` for any LLM triage.

## Acceptance metrics
In-app report → ticket with status visible to reporter (e2e). At least one dispatch path live (Notion task creation) behind an admin gate + audit. Routines/automation visible in-app with last-run status. 🔴-tier never auto-dispatches (test).
