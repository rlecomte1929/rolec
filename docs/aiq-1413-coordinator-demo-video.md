# AIQ-1413 — Mobility Coordinator demo video (production guide)

**Status:** Human-Only recording task. This doc gives you the honest, grounded plan.

## Reality check (read first)

The ticket imagines a single-prompt autonomous "superagent" running 7 relocation steps.
That capability is **not built**. The live **AI Mobility Coordinator** (AIQ-1414) is a
**per-case, read-only chat concierge** that answers questions grounded in an existing case
and can do two side-effecting actions: **flag a risk** and **add a note**. It does *not*
create cases from a prompt or orchestrate visa/housing/cost/vendor/onboarding.

**Chosen framing:** honest Coordinator-concierge video ("your AI mobility co-pilot").
Show what genuinely runs live; do **not** narrate the six unbuilt steps as if they exist.

- Model in use: `claude-sonnet-4-6` (Sonnet 5 is not wired — the ticket's "record after
  Sonnet 5" is a soft preference, not a blocker).
- Captions satisfy validation criterion 4 ("captioned for silent viewing"), so a silent,
  caption-burned clip is acceptable — TTS narration is optional.

## Demo data (this PR)

`backend/main.py` `_seed_demo_cases()` now seeds a hero case for the video:

- Employee: **Sarah Chen** (`sarah.chen@relopass.local`), French national, Senior Engineer
- Case: `demo-case-paris-london-schen` — **Paris → London**, start **2026-10-01**, standard international
- Flows through the same proven chain as the other demo cases (case → assignment →
  mobility-case link → person → passport document), so the Coordinator resolves it.

> This seed runs on the **local/demo SQLite stack only** (`uvicorn backend.main:app`).
> It is NOT applied to prod (prod `companies.id` is uuid and rejects the demo string ids).

## Setup for the recording

1. Run the backend on the demo stack so `_seed_demo_cases()` runs (SQLite):
   `uvicorn backend.main:app --reload --port 8000` (from repo root).
2. Enable the Coordinator flags in the recording env:
   - Frontend build/runtime: `VITE_FEATURE_COORDINATOR=true`
   - Backend: `RELOPASS_AI_COORDINATOR_ENABLED=1`
3. Start the frontend: `npm run dev` (proxies `/api` → :8000).
4. Log in as HR (`hr@testingapril.com` / `HrPass!1`) or the demo HR, and open Sarah Chen's
   case. The Coordinator hosts on:
   - HR: `/hr/command-center/cases/demo-case-paris-london-schen`
   - Employee: `/employee/case/demo-case-paris-london-schen/summary`
   The `<CoordinatorChatPanel>` appears on the case page (no dedicated `/coordinator` URL).

## 90-second shot script (silent + burned captions)

| t (s) | On screen | Caption |
|------:|-----------|---------|
| 0–6   | HR command center → open Sarah Chen's Paris→London case | "Sarah Chen · Paris → London · starts Oct 1" |
| 6–14  | Open the Coordinator chat panel on the case | "Meet your AI mobility co-pilot — grounded in this case" |
| 14–34 | Type: *"What's outstanding for Sarah's move and what should I watch?"* → it answers from the case (docs, requirements, timeline) | "Ask in plain English. It reads the live case." |
| 34–52 | Type: *"Any risks with the October 1 start date?"* → it reasons about timing; then click **Flag risk** | "Flags real risks to the case timeline" |
| 52–68 | Type: *"Add a note to follow up on the tenancy reference."* → it records the note | "Logs notes straight onto the case spine" |
| 68–84 | Show the case events updated with the new risk flag + note | "Every action is tracked — nothing lost" |
| 84–90 | ReloPass logo + tagline | "ReloPass — mobility, with an AI co-pilot" |

Keep prompts short and let the answers land. Pick the best take per exchange (LLM latency
and phrasing vary run to run).

## Tooling

The repo's TD-11 recorder (`frontend/scripts/record_test_drive_clips.mjs`) uses Playwright
`recordVideo` (1280×720 → `.webm`) with **burned-in DOM caption overlays**
(`window.__setCap`). It's the closest existing tool, but it:

- drives read-only prod screens today (would need to point at the local flagged stack and
  navigate to the case + open the Coordinator panel), and
- has **no TTS and no webm→mp4 transcode** in-repo.

Two viable paths:
- **Manual capture (recommended for the chat):** screen-record the live exchange (QuickTime/
  Loom) for natural pacing and best-take selection, then add captions in your editor.
- **Scripted capture:** extend `record_test_drive_clips.mjs` with a new clip that logs in,
  opens `demo-case-paris-london-schen`, and `waitForSelector` on each Coordinator reply
  bubble before advancing. More work; brittle to LLM latency.

## Validation criteria mapping

1. <90s — script is timed to 90. ✅ (edit to taste)
2. End-to-end from a single surface — the Coordinator answers + acts on the real case. ✅ (scoped honestly)
3. No broken states — use the seeded case; rehearse the prompts. ▶️ manual
4. Captioned for silent viewing — burned captions per the table. ✅
5. Posted / ready to post — export mp4, add to LinkedIn/landing. ▶️ manual
