# ReloPass — Claude Code Run 1: Item 42 + Push B
**Generated 2026-08-16.** Open a Claude Code session at the `rolec` repo root and paste the **KICKOFF PROMPT** at the bottom. Full specs for every item are in `docs/plans/relopass_claude_code_plan.md` (Parts 1 & 3).

## Run order — one branch+PR each, recon-first, stop on any 🔴
| # | Task | Layer / Tier | Skill | One-line acceptance |
|---|------|--------------|-------|---------------------|
| 1 | **AIQ-1848** Sonnet 5 backbone | Backend · 🟢 | dev-queue | New model ID live, ≥30% cheaper on 30-day volume, E2E + coordinator regression green |
| 2 | **AIQ-1847** Fresh employee registration | Full-stack · 🟡 | dev-queue | AT3_FRESH Sentinel passes on a new account |
| 3 | **AIQ-1890** Documents "Upload" button | UI · 🟡 | fix-ui-bug | Header Upload opens a working picker via the existing `onUpload` path (or is removed) |
| 4 | **AIQ-1891** Documents "Outstanding" split | UI · 🟡 | fix-ui-bug | Uploading a required doc drops **Missing**, raises **In review** immediately |
| 5 | **AIQ-1892** Family/dependent CTA deep-link | UI · 🟡 | fix-ui-bug | CTA opens Dossier & Forms with `?form=<key>` expanded |
| 6 | **AIQ-1859** Passport extraction UI | UI · 🟡 | fix-ui-bug | Upload → editable extracted values; stored passport is **ciphertext** (vault key is live) |
| — | ~~AIQ-1889 Explain Prepay~~ | **HOLD** | — | Blocked on a tester screenshot/URL — do **not** start |

## Guardrails (all items)
- **Recon first, always.** Trust the code, not the task title (AT3 note). Follow the existing pattern the plan's *Specs* point at; no second code paths.
- **Validate:** run the task's validation command; frontend items also `npx tsc --noEmit`. Item 42 additionally needs the full E2E suite + a 10-prompt coordinator regression.
- **No corridor data changes this run**, so the §0.2 golden probes should stay unchanged — spot-check them after item 42 lands the new backbone.
- **Close out each:** Notion Status → Human Review + Execution Notes, then **commit (Phase 7)**. Stop and ask on any 🔴 gate or failed validation.
- **Item 42 is its own PR** and lands first so the rest build on the new backbone. Its savings gate is hard: if the live price isn't ≥30% cheaper on real volume, stop and report.

## Optional speed-up
Items 3–5 (the UI fixes) touch independent files and are safe to parallelize across **Conductor** worktrees. Run `relopass-conductor-check` first if you want the per-agent briefs; otherwise run them sequentially as listed.

---

## KICKOFF PROMPT (copy-paste into Claude Code)
```
Use relopass-dev-queue. Work these AI Work Queue tasks in THIS EXACT ORDER, one branch+PR each, recon-first, and STOP to ask me on any 🔴 Red gate or failed validation. Specs, files, and validation commands are in docs/plans/relopass_claude_code_plan.md (Parts 1 & 3).

1) AIQ-1848 — Upgrade the AI backbone to Claude Sonnet 5. First confirm the exact live model ID and that last-30-day token volume is >=30% cheaper at the new price; if not, STOP and tell me. Set thinking:{type:"disabled"} on any deterministic-output flow. Run the full E2E suite + a 10-prompt relocation-coordinator regression. Its own PR.
2) AIQ-1847 — Fresh employee registration. Open the NEWEST AT3_FRESH failing run artifact and quote the exact failure verbatim before diagnosing; fix the front-door registration path; re-run AT3_FRESH.
3) AIQ-1890 — Wire the Documents "Upload" button (relopass-fix-ui-bug).
4) AIQ-1891 — Split Documents "Outstanding" into Missing + In review (relopass-fix-ui-bug).
5) AIQ-1892 — Deep-link the family/dependent roadmap CTA (relopass-fix-ui-bug).
6) AIQ-1859 — Surface passport extraction in the UI; REUSE the shipped extraction pipeline (no new Vision path); the vault key is live, so verify the stored passport persists as ciphertext.

HOLD AIQ-1889 (Explain Prepay) — blocked on a tester URL; skip it.

For each task: follow its own Execution Prompt + Validation Criteria in Notion, run the validation command, set Notion Status to Human Review with execution notes, and COMMIT (Phase 7).
```
