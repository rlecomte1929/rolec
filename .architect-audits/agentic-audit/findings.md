# Agentic Audit — Findings

# Layer 0 Diagnostic Snapshot

- Repository: rolec (ReloPass) — Run: 2026-06-25
- Project shape: hybrid monorepo (Node/React frontend + Python/FastAPI backend + Supabase)
- AI surface detected: true — backend pins openai==1.51.2 and anthropic==0.39.0

### Detected agentic instruction files (in scope)

| Path | Lines | Last modified | Tool family |
| --- | --- | --- | --- |
| CLAUDE.md (root, primary) | 301 | 2026-06-14 | claude |
| backend/CLAUDE.md | 51 | 2026-05-26 | claude |

- Total in-scope line count: 352 · file count: 2
- .claude/settings.json: present, valid JSON, keys [enabledPlugins], 0 permission entries
- .claude/settings.local.json: present, valid JSON, 21 allow / 0 deny — TRACKED & not gitignored
- Hooks: none (Claude) · MCP-server blocks: none · statusLine: none · model override: none
- ~30 .claude/worktrees/**/CLAUDE.md copies excluded as out of scope

Thresholds applied — instruction min 25, max 400, permission-broadness 5, context-coverage 60%.

---

## Summary

| Layer | present | partial | missing | violation |
| --- | --- | --- | --- | --- |
| L1 Project context coverage | 5 | 3 | 0 | 0 |
| L2 Operational guidance & conventions | 3 | 3 | 0 | 0 |
| L3 Claude Code settings hygiene | 4 | 1 | 0 | 1 |
| L4 Multi-agent consistency & drift | 6 | 0 | 0 | 1 |
| Total | 18 | 7 | 0 | 2 |

---

## Layer 1 — Project context coverage

- Primary instruction file present — present. Root CLAUDE.md is canonical primary (301 lines).
- Primary instruction file is substantive — present. 301 lines, richly headed structure.
- Primary instruction file is not bloated — present. 301 <= 400 ceiling. (Pre-run hypothesis of >400 lines NOT borne out; actual 301.)
- Project purpose documented — partial. File opens at "## Commands"; never states in prose what ReloPass is / who it is for. Purpose only inferable from architecture (Employee/HR/Admin personas, relocation/immigration/policy).
- Tech stack documented — present. React/TS/Vite/Tailwind/RR6/Axios/Supabase + FastAPI/SQLAlchemy/Python 3.11 all named; matches deps.
- Architectural mental model documented — present. Repo tree, dual-layer pattern (main.py vs app/), services/agents/recommendations, frontend routing/state, three-persona trees.
- Domain glossary present where appropriate — partial. Heavy domain terms (corridors, dossier, roadmap, RLS tenant-scoping, intake wizard, policy_config) with no glossary/link.
- Links to canonical human-facing docs — partial. Links DESIGN.md, backend/MIGRATION_PLAN.md, audit/REMEDIATION_PLAN.md, audit/STAGES.md, docs/security/PRIV-004 (all resolve); but README.md (exists) not linked; CONTRIBUTING.md/ARCHITECTURE.md absent.

## Layer 2 — Operational guidance & conventions

- Build, test, run commands documented — present. Frontend + backend + Supabase command block; cross-ref to package.json passes.
- Code-style and naming conventions documented — partial. Has strict-tsc + antigravity-first + navy/accent Tailwind rules; lacks naming/import-order/abbreviations policy.
- Commit and branching conventions documented — present. audit/stage-N branch convention + feature-branch->PR->CI->merge + pre-push build hygiene.
- Testing philosophy or approach documented — partial. Names runners (vitest/pytest) + "tsc --noEmit before PR" gate; no behaviour-over-implementation / query-priority / snapshot policy.
- "What to do" and "What NOT to do" guidance present — present. Strong bidirectional: register routers in BOTH apps; never apply schema via MCP; don't touch engine config; PII must never leave platform in LLM payload; Karpathy guidelines.
- Tone or response-style guidance present — partial. Real AI surface (Policy Assistant, extraction, roadmap gen). Extensive data-handling rules (pii_masker, safe_log_text, sub-processor register) but no response-style/persona/tone guidance.
- Imperative-present rule signal — skipped (Conventional Commits not formally required).

## Layer 3 — Claude Code settings hygiene

- settings.json is valid JSON — present. Only enabledPlugins (security-guidance@claude-plugins-official).
- settings.local.json is gitignored — VIOLATION. File is git-tracked and .gitignore excludes only .claude/worktrees/. Local overrides leak into shared repo; future inline secret would be committed. ALREADY ADDRESSED IN-FLIGHT in PR #858 (chore/gitignore-settings-local) which adds the ignore entry + untracks the file; current branch working-tree .gitignore does not yet carry it, so the finding stands until that PR merges.
- No secrets in settings.json — present. No secret-shaped values.
- No secrets in settings.local.json — present. All 21 allow-entries + Notion MCP ids scanned; no sk-/ghp_/xoxb-/JWT/AWS/long-hex; Notion ids are server UUIDs, not credentials.
- Permissions are appropriately scoped — present. 21 allow-entries, ZERO match-all broad patterns (Bash(*)/Edit(*)/Write(*)) — under tolerance 5. Broadest are Bash(git add *), Bash(git commit -m ' *), Bash(npx tsc *) — subcommand-scoped, not match-all. Bash(rm -rf /tmp/rolec-intake) is destructive but pinned to a tmp path.
- permissions.deny is non-empty in security-sensitive projects — partial. Deployable (Render auto-deploys main) but no deny-list anywhere; no guardrail against rm -rf /, git push --force, destructive DB ops.
- Hooks reference scripts that exist — skipped (no hooks block).
- Environment variables do not contain secrets — skipped (no env block).
- Status-line and model overrides are intentional — skipped (none set).
- MCP-server entries are auditable — skipped (no mcpServers block; Notion MCP only as permission entries).

## Layer 4 — Multi-agent consistency & drift

- Single source of truth for shared rules — present. backend/CLAUDE.md opens "Supplements the root CLAUDE.md. Backend-specific rules…" — explicit scoped supplement, no conflict.
- Tech-stack mentions match dependencies — present. React/Vite/Vitest/TS in frontend/package.json; FastAPI/Python/SQLAlchemy + OpenAI/Anthropic in backend/requirements.txt. No stale refs.
- Commands documented match package.json scripts — present. npm run dev/build resolve (root proxies to frontend); build/dev/preview/test/lint exist. Non-script commands not-applicable. No missing-script refs.
- Cross-references resolve — present. All checked files exist: DESIGN.md, backend/MIGRATION_PLAN.md, audit/REMEDIATION_PLAN.md, audit/STAGES.md, docs/security/PRIV-004…, backend/app/services/pii_masker.py, .githooks/pre-push, .github/workflows/ci.yml, scripts/check_migration_drift.py, backend/main.py, backend/app/main.py.
- No retired-model identifiers — present. No retired ids; CLAUDE.md references no model ids. Current ids (claude-opus-4-8 etc.) are not retired and not in CLAUDE.md.
- Instruction-file freshness — present. Active project (latest commit 2026-06-19); root CLAUDE.md modified 2026-06-14, within 180-day threshold.
- Process drift — "main-push migration workflow" does not exist — VIOLATION. CLAUDE.md lines 132 & 180 instruct agents to "let the main-push workflow apply [the migration] on merge" / "applies the file to production on merge". No such workflow exists — .github/workflows/ has 15 workflows but none applies migrations to prod; ci.yml is PR-only/validate-only. Reality: migrations applied manually / via MCP apply_migration. An agent following this commits + merges and assumes prod is updated when it is not — silent schema-drift hazard. Fix: reword to the real manual/MCP process, or build the workflow the docs promise.
- No abbreviations in agentic prose — skipped (no abbreviations policy declared).
