# Generator–Relay–Applier: a code-artifact bridge (Cursor → Otto → Claude)

**Date:** 2026-08-22 · **Author:** Claude (Cowork) · **Owner:** Romain
**Problem:** Cursor has LLM/code capacity we want to use, but it isn't wired to the rolec repo, prod Supabase, or `gh` — and wiring it with prod *write* access is risky. How do we still get it doing the heavy lifting?

## The insight

Cursor doesn't need to *apply* changes — it needs to *generate* them. **Generation is a pure, read-only function** with no side effects: `(context bundle) → (artifact + prediction)`. So we never give Cursor write access to anything. It produces patches, SQL, tests, and a *prediction of the result*; a thin trusted agent applies them; the bridge moves artifacts between the two. The constraint stops being a blocker and becomes the architecture.

## Roles

- **Cursor = Generator.** Given a read-only context bundle, it emits: unified diffs (code), transactional SQL (data), tests, and a **prediction** (exactly what applying should produce — row counts, titles, pillars, test pass/fail, "must-not-touch" rows). Sandboxed; needs no prod. Runs as a **fleet** — Otto can fan out N `cursor_delegation` jobs in parallel (this is where your capacity goes).
- **Otto = Orchestrator + Relay + Researcher.** Builds the `cursor_delegation` jobs, carries context in and artifacts out, moves them on/off the `otto_claude_bridge`. Still does the research heavy-lifting (Denis).
- **Applier = the one thin wired agent** (local Claude Code for repo+DB; or Cowork-Claude for DB-only). It never trusts the generator: **dry-run → diff against Cursor's prediction → apply only on match → verify against prod.** Write access stays concentrated here, audited.
- **Cowork-Claude (me) = context-exporter + independent auditor.** I can read the repo (device bridge) and read prod (Supabase), so I build the read-only bundles Cursor needs and verify the applied result independently.

## The artifact contract (extend the existing bridge — no new infra)

Add three `kind: record` subtypes to `otto_claude_bridge`:

| subtype | direction | payload |
|---|---|---|
| `context_bundle` | wired → Otto → Cursor | repo files needed + schema DDL + a JSON snapshot of the relevant staged/live rows + the task + the rules |
| `artifact` | Cursor → Otto → wired | unified diff / SQL (transactional) / tests + a **prediction** {expected_inserts, counts, pillars, must_not_touch} |
| `apply_report` | wired → Otto/Cursor | dry-run diff, prediction match yes/no, applied result, prod verification |

## The trust model (the hacker discipline)

1. **Generation is read-only → safe by construction.** Cursor can't break prod; it has no handle to it.
2. **Application is dry-run-then-verify → safe by procedure.** Postgres `BEGIN … <inserts> … SELECT counts … ROLLBACK` (or `import_otto_facts` dry-run, which is already the default) lets the applier *see* the effect before committing. It compares actual vs Cursor's **prediction**; mismatch → reject, don't apply.
3. **Snapshot-based generation handles the no-access problem.** Cursor generates against a frozen snapshot; the applier reconciles against *live* at apply time (drift-aware). Cursor never needs live access.
4. **Least privilege if you wire Cursor at all: read-only only.** A fine-grained *read-only* GitHub token + a *read-only* DB role let Cursor generate with real context, while write stays with the one audited applier. Never hand a broad agent the service-role key.
5. **Every artifact ships with its own test/prediction** — the applier has an objective pass/fail before touching prod. This is generator–verifier, applied to code and data ops.

## Data path — two variants

- **First test (manual relay, 2 hops):** I build the bundle → you paste it to Otto → Cursor generates → Otto returns it → you paste to me → I dry-run/verify/apply. Proves the *generation quality* before we automate transport.
- **Automated (target):** local Claude Code (bridge-wired) pushes `context_bundle` → Otto pulls, delegates to Cursor → Otto pushes `artifact` → Claude Code pulls, dry-runs, applies, verifies. **No human relay, and the heavy lifting is all on Cursor/Otto** — Claude Code shrinks to a thin apply/verify gate, exactly the split you want.

## Where it pays — and where it doesn't

- **Pays:** bulk / parallel codegen — promotion SQL for *many* corridors, the serving-layer wiring (CT-4), Denis's engine logic, whole test suites. Cursor's fleet generates while the applier serializes safely.
- **Doesn't pay:** a single 3-row insert. Routing that through Cursor is overkill — the wired agent just does it. Use the bridge where scale justifies the hops.

## The proof test (small, real, safe)

Generate the promotion for **one** topic and apply it through the loop:
1. **I export a `context_bundle`:** `requirement_items` schema + `create_requirement_item` mapping rules (from `mappings.py`, incl. the #1973 pillar logic) + a JSON snapshot of the 3 `immigration_work_authorization` staged facts + the existing live rows for that concept.
2. **Cursor generates:** transactional promotion SQL (append-only, dedup on `(country_code, purpose, title)`, pillar-honoring, promote-to-pending) **+ a prediction**: the 3 rows it will insert (titles, pillars) and the reviewed rows it must NOT touch.
3. **I apply as dry-run:** `BEGIN … inserts … SELECT … ROLLBACK`; confirm actual == prediction, confirm zero UPDATEs on reviewed rows, confirm nothing served.
4. **Verdict:** if the dry-run matches Cursor's prediction and violates no gate → the loop works; scale to the full promotion and the CT-4 serving patch. If not → we see exactly where the generator drifted, cheaply, with no prod impact.

## What this makes the whole workflow

Every remaining task — promotions, serving-layer wiring, the Denis engine, tests — becomes a **generated artifact**: Cursor generates (heavy, parallel), the bridge relays, one thin wired agent applies + verifies, Otto orchestrates, I audit. Cursor does the lifting without ever touching prod; risk stays concentrated and verified in one place.
