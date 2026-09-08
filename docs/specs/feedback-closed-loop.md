# Feedback closed loop — design (2026-09-04)

**Status:** agreed direction for implementation. Supersedes `docs/specs/feedback-improvements.md` (stale widget-insert model). Extends, but does not replace, the shipped pieces of `docs/specs/feedback-pipeline-orchestration.md`.

**Plan:** `docs/superpowers/plans/2026-09-04-feedback-closed-loop.md`

## Problem

The widget → `feedback` → `feedback_status` → LLM spec → Notion AI Work Queue path exists. What is missing is an **efficient operator loop**:

1. Reporter symptom is treated as a spec too early.
2. PostHog identity and replay are captured on `client_context` but **dropped** from `format_diagnostics()`, so agents do not see them. Replay often starts only when the widget opens — after the bug.
3. “Trigger fix” does not propose a diff; it flips Notion to Ready for AI. Cursor is a paste, not a product step.
4. Tickets do not close on GitHub merge or PostHog evidence.

## Non-goals

- Auto-merge to `main`.
- Linear/Jira.
- Recording users who declined analytics.
- Replacing Notion as the work-queue system of record for agents.

## Target loop

```
symptom (immutable) → classify (Research | Bug | Idea | Not-a-bug)
  → spec (human-edited, evidence attached, PostHog links in the prompt)
  → admin approves spec
  → copy Cursor / relopass-dev-queue brief  (Phase A)
  → later: draft PR only  (Phase C)
  → verify (admin “seen on URL” and/or PostHog)  (Phase D)
  → done
```

Human approval sits in front of **code that can merge**. Automation drafts.

## PostHog — use what is already connected

Already shipped:

- EU PostHog project; `posthog-js` in the SPA; server `posthog_client.py`.
- `collectDiagnostics()` stores `posthog_id`, `posthog_session_id`, `posthog_replay_url`.
- Feedback widget calls `startBugReportRecording()` on **open** (consent-gated).
- Inbox Diagnostics panel can link to replay / person.
- Product metrics tab reads **mirrored** `analytics_events`, not live HogQL.
- Session replay is **off by default** except test-drive (`TestDriveReplayGate`) and the bug-widget start.

Gaps to close (in this programme):

| Gap | Why it feels unused |
|-----|---------------------|
| `format_diagnostics` omits all PostHog fields | Specs and agents never see the replay |
| Replay starts at widget open | The failure is usually already over |
| No `feedback_submitted` event with `report_id` | Cannot join tickets to product analytics |
| Distinct id may not equal ReloPass user id | Person page is the wrong human |
| Metrics tab is a warehouse mirror | Deep funnels stay only in PostHog UI |
| No post-deploy verify query | `done` is social, not measured |

Rules:

- Never start recording without `getAnalyticsConsent() === 'granted'`.
- Treat replay as **supporting evidence**, not proof the classified file is wrong.
- Label submit-time route vs navigation trail (already done for breadcrumbs; keep that honesty).

## Phases (each is shippable)

| Phase | Outcome | Auto-merge? |
|-------|---------|-------------|
| **A** | Inbox split; seed cannot silently fail; PostHog in spec + copyable agent brief | No |
| **B** | UI forces Research vs Implementation; force-dispatch needs a reason | No |
| **C** | Optional draft-PR / GitHub status on the ticket | No (draft PR) |
| **D** | Verify: admin confirm + optional PostHog query after deploy | No |

Phase A is the first implementation plan. B–D stay in the same plan as later tasks so the programme does not fragment.
