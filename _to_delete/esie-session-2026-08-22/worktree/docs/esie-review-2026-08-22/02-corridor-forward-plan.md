# ReloPass corridor-facts — recommendations & forward plan

*Full-stack engineer's read, 2026-08-22. Grounded in the read-only audit plus an end-to-end trace of the corridor lifecycle (research → gate → seed → attest → serve).*

---

## The objective, stated plainly

ReloPass wins on **trust**: it serves relocation obligations as *verified, cited, human-attested fact*, not LLM guesses. So the goal is not "more facts" — it's **a small set of corridors that are genuinely sellable end-to-end**, where *sellable* means all three of: provenance-gated ✅, counsel-attested, **and actually served to the customer**.

Your repo makes the near-term objective concrete for me: two design partners, each tied to your two strongest corridors.

- **Andrea → ES→IE.** Your `ReloPass_ES-IE_Andrea_GoLive_Assessment_2026-08-20.md` says she can go live **within a week**, and the blocker is **5 already-built PRs awaiting merge** (vendors done; empty housing/schools recs, disabled geocoding, and `example.com` advisor URLs are *all built but unmerged*).
- **Denis → NO→FR.** The gap-analysis build spec frames NO→FR as "close the gap between what ReloPass *demos* and what it *does today*, authored against a real validation case."

Everything below is ordered by how directly it moves those two corridors to live.

## Current state — the map (what I verified)

| Layer | State | Evidence |
|---|---|---|
| Provenance gate | **PASS**, 36/36 tests green, zero drift | `scripts/check_corridor_facts.py`; audit 2026-08-22 |
| Gated fact corpus (`backend/seeds/facts/`) | 25 facts, clean & dated — but **17/21 are `representative` (unattested)**, only 4 `active` | pack YAMLs |
| Fact → served-table bridge (`seed_corridor_facts.py`, path #3) | **Built + tested (PR #1916)** — but `DATA-PATHS.md` still says "not yet built", and it's unclear it's been *applied to prod* | commit `c6f2189b`; `docs/corridors/DATA-PATHS.md` |
| Served table (`requirement_items`) | Fed by **4 authoring paths, 2 id conventions**; fuzzy-match dedup hazard where they overlap | `docs/corridors/DATA-PATHS.md` (114 prod rows, 2026-08-20) |
| Serving engine (`public_corridor.py`) | **Destination-only** — origin obligations (exit tax, home-country A1) are structurally dropped; NO shows ~3 items, missing tax-card/police/EEA | router docstring |
| Attestation | Full system exists (admin-gated promote + tokenized counsel signing), largely **unused so far** | `backend/app/routers/attestation.py` |
| Coverage | 4 of 12 corridors fact-bound (ES_IE, FR_NO, NO_FR, GB_NO); GB_NO missing its pathway | `corridors/*/` |
| Knowledge/dev debt | Stale Otto docs describe a phantom `tools/corridor-facts/` TS pipeline; local venvs broken; 148 pending migrations + jammed applier | audit; CLAUDE.md |

**The one-sentence diagnosis:** you have a verified fact corpus and a working gate, but the *last mile* — landing those facts into the served table (#3) and surfacing origin-side obligations — is unfinished or unverified, so the trust you've built isn't yet reaching the customer. And your nearest customer (Andrea) is blocked on merges, not on new code.

## Recommendations, in priority order

**1. Ship Andrea (ES→IE) first — it's a merge problem, not a build problem.** The go-live assessment says the fixes are built. Triage the 5 PRs against your own merge discipline (both required CI checks green; router dual-registration; no back-to-back migration merges), merge the clean ones, and verify live (Render auto-deploys `main`): recs populate, geocoding on, zero `example.com`. This is the highest ROI on the board — days to a real validated corridor.

**2. Verify and finish the fact→serving bridge (path #3).** This is the structural keystone: until `seeds/facts` reliably lands in `requirement_items`, your gate PASS is cosmetic — the verified facts don't render. Confirm ES-IE and NO-FR facts are actually in `requirement_items` (run `seed_corridor_facts.py --apply` in a controlled window if not), add a **served == gated-corpus** regression test, and refresh `DATA-PATHS.md` (the "not built" note is now false).

**3. Ship Denis (NO→FR) — and close the origin-side serving gap.** NO→FR's value *is* the origin obligations (Norwegian exit tax, A1/home social security) that the destination-only engine currently drops. Decide the smallest fix that surfaces origin facts in the roadmap (the `roadmap_corridor_overlay` is the likely home — don't rebuild the engine), then author/attest the rest against Denis's validation case.

**4. Run the attestation drive.** 17/21 facts sit `representative` — nothing is *sellable* until counsel signs. The workflow exists; feed it. I can generate per-corridor attestation packets (fact + quote + source, legal-scope only) and verify the admin promote path so a signature actually flips a row to `active`.

**5. Expand coverage — controlled, quality over count.** Land the two staged Otto batches (`B3-corridor-facts`, `ve-ie-entry-family`) via `import_otto_facts.py` dry-run → source-check → stage (never blind-import); fix GB_NO's missing pathway; add corridors only as gated research arrives.

**6. Pay down the tax on every future pass.** Consolidate the 4 authoring paths (path #4's divergent `ES:IE-ES:*` id convention is the outlier); retire the stale Otto docs and point to `DATA-PATHS.md` + the gate (this drift has already cost whole agent passes, per your own CLAUDE.md); fix the local venvs (a documented `uv` bootstrap so `pytest` runs); and flag the 148-pending migration ledger for the pre-launch data reset (don't touch it now).

## Phased roadmap

| Phase | Work | Effort | Risk | Definition of done |
|---|---|---|---|---|
| **0 — Unblock Andrea** | Triage + merge the 5 ES-IE PRs; fix last-mile (recs/geocoding/`example.com`); E2E-verify | S (days) | Prod-affecting — follow merge discipline | ES→IE renders complete live; no `example.com`; go-live checklist green |
| **1 — Finish bridge #3** | Verify/apply `seed_corridor_facts.py`; served==corpus test; refresh `DATA-PATHS.md` | S–M | Idempotence + fuzzy-match dedup | Gated ES-IE/NO-FR facts served; re-run = 0 changes; doc current |
| **2 — Ship Denis + origin gap** | Surface origin obligations in NO→FR roadmap; author + attest remaining facts | M | Engine change scope creep | NO→FR renders origin+destination, cited + attested |
| **3 — Attestation drive** | Packets for the 4 corridors; verify promote flow; drive representative→active | M (process-gated) | Needs counsel availability | ≥1 corridor fully attested → `active` → sellable |
| **4 — Coverage** | Land 2 staged Otto batches; fix GB_NO pathway; add corridors as researched | M, ongoing | Never blind-import | Each new corridor gate-PASS + provenance-clean before promote |
| **5 — Debt paydown** | Consolidate authoring paths; retire stale docs; fix venvs; flag migration ledger | M, ongoing | — | One authoring convention; docs match reality; local tests run |

Phases 0 and 1 can run in parallel (both are "finish/verify what exists"). 3 runs alongside 2. 5 is continuous.

## Where I'd start Monday

**Phase 0 + the Phase 1 verification, together.** Concretely, my first session would: (a) read the Andrea go-live assessment in full and pull the actual PR/merge-queue state, produce a triage (merge / hold / needs-fix per PR); and (b) confirm whether the gated ES-IE facts are already in `requirement_items` — if not, that's the single change that connects your verified corpus to Andrea's live corridor. Both are low-build, high-signal, and directly serve the one-week go-live.

## What I'd need from you

- Confirm Andrea (ES→IE) and Denis (NO→FR) are still the two live targets, and which is first. (I'm reading that from repo docs dated 2026-08-20 — correct me if it's moved.)
- A green light before anything that touches `main`/production (merges, `--apply`, prod DB) — Phases 0–1 are production-affecting; everything up to that point is read-only analysis I can do unattended.

---

*Companion to the read-only audit (`corridor-facts-audit-2026-08-22.md`). This is a recommendation, not executed work — no code changed, nothing merged, no production contact.*
