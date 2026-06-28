# Epic C — SHARED brief (READ THIS FULLY before doing any task)

You are an autonomous engineer finishing **Epic C (accessibility)** of the ReloPass frontend lint
cleanup. Repo `rlecomte1929/rolec`; frontend is in `frontend/` (Vite + React + TypeScript). The
overall epic drives accessibility lint rules to **0** across `frontend/src` and re-promotes each
`warn` → `error` in `frontend/eslint.config.js` so CI enforces them. **You own ONE slice** — see your
TASK file. Do only that slice.

## NON-NEGOTIABLE DEFINITION OF DONE (all must hold before you report success)
1. Your task's **target rule = 0** across the files in scope (use the exact measure command in your task).
2. `npx eslint src` reports **0 ERRORS** (warnings are fine).
3. `npx tsc --noEmit` = **0 errors**.
4. `npm run build` **succeeds**.
5. `npx vitest run` = **all pass** (~1224 tests; you introduced **no** new failures).
6. A PR is open, the **"Frontend (build, types, lint, unit)"** check is green, and — unless your task
   says "DO NOT AUTO-MERGE" — it is squash-merged.
7. You changed **only** files in your scope (re-promotion tasks also touch `eslint.config.js`). These are
   a11y attribute/markup edits — **behavior is unchanged**, not logic changes.

## ENVIRONMENT & SETUP
- Work in a **dedicated worktree** (Conductor agents race HEAD):
  ```
  git fetch origin main && git worktree add /tmp/wt-$TASK origin/main && cd /tmp/wt-$TASK/frontend && npm ci
  git checkout -b fix/epic-c-$TASK
  ```
  Use **`npm ci`** (NOT `npm install` — it drifts versions and fakes ~380 test failures; a symlinked
  `node_modules` fakes "cannot find module zod/@tanstack" tsc errors).
- The blocking CI check is **"Frontend (build, types, lint, unit)"**. **Vercel / Cloudflare Pages /
  Supabase Preview are non-blocking noise — never wait on them.**
- **Never** `git stash` (shared repo). **Never** `git checkout main` (stale) — use `git reset --hard origin/main`.
- **Before pushing**, merge latest main and re-verify: `git fetch origin main && git merge origin/main`
  then `npx eslint src` = 0 errors (other agents' re-promotions may have flipped rules to `error`).

## HARD RULES (each has cost hours on this project — obey exactly)
1. **Commit messages** (commitlint / Conventional Commits): type ∈ `{feat fix chore docs style refactor
   perf test build ci revert}`. **`a11y:` is REJECTED → use `fix(a11y): …`.** **Subject ≤ 100 chars AND
   every body line ≤ 100 chars.** A bad message aborts the commit (tree intact) → fix + recommit. Use ASCII `-`.
2. **Measure eslint via a FILE, never a stream pipe to node** (piping races / under-reports):
   `npx eslint <path> --format json > /tmp/x.json 2>/dev/null` then read with node `require('/tmp/x.json')`.
3. Push with `git push --no-verify` (skips the local pre-push build; CI re-runs it). The commit-msg hook still runs.
4. Open the PR via REST if `gh pr create` 401s:
   `gh api -X POST repos/rlecomte1929/rolec/pulls -f title=… -f head=… -f base=main -f body=…`;
   poll `gh pr checks <n>` until **Frontend** = pass; `gh pr merge <n> --squash`.

## PER-FILE VERIFICATION RITUAL (every file, before commit)
- **Orphan check:** `grep -nE '^\s+id="' <file>` — no `id="…"` line may sit right after a line ending `/>`.
- That file's **target-rule residual = 0** (file-based measure).
- `npx tsc --noEmit` = 0.

## FIX PATTERNS (match the element's REAL role — NEVER blanket `role="button"`)
- **Modal / drawer backdrop** (`<div class="fixed inset-0 …" onClick={close}>` wrapping content):
  ```jsx
  onClick={(e) => { if (e.target === e.currentTarget) close(); }}   // target-check
  onKeyDown={(e) => { if (e.key === 'Escape') close(); }}
  role="button" tabIndex={-1} aria-label="Close …"
  ```
  AND **delete** the inner content div's `onClick={(e) => e.stopPropagation()}` (the target-check replaces it).
- **Clickable row / card** (`<tr|div onClick={fn}>`): add `role="button" tabIndex={0}` (+ `aria-expanded`
  when it expands) and
  `onKeyDown={(e)=>{ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); fn(); } }}`.
  **If `fn` is async, use `void fn()` inside onKeyDown** (`no-floating-promises` is an ERROR).
- **Conditionally clickable** (`onClick={cond ? fn : undefined}`): move ALL interactive props into a
  conditional **spread** so the linter sees no literal onClick and it is accessible only when active:
  ```jsx
  <tr {...(cond ? { onClick:()=>fn(), onKeyDown:(e: React.KeyboardEvent)=>{ if(e.key==='Enter'||e.key===' '){e.preventDefault(); fn();} }, role:'button' as const, tabIndex:0 } : {})} …>
  ```
  Add `import type * as React from 'react';` if you need the event type and React isn't imported.
- **`role="dialog"` / `"presentation"` / `"menu"` element WITH onClick** (the custom rule allowlists only
  button/link/tab → false positive): KEEP the correct ARIA role, add `onKeyDown(Escape)` for real keyboard
  dismiss, and add a **scoped disable** on the line before the element:
  ```
  // eslint-disable-next-line local/no-clickable-div, jsx-a11y/no-noninteractive-element-interactions -- role="dialog" is the correct ARIA role; backdrop-click + Escape are the standard dismiss interactions
  ```
  Use a `//` line comment when the element is the root of `return (`; use a `{/* … */}` JSX comment when
  it sits among JSX children/in a fragment. The disable MUST suppress something or
  `reportUnusedDisableDirectives` errors.
- **aria-hidden presentational dismiss overlay** (`<div aria-hidden onClick={close} />`, no content child):
  ```
  {/* eslint-disable-next-line local/no-clickable-div -- presentational mouse-dismiss overlay (aria-hidden); keyboard users dismiss via the panel's own controls */}
  ```
- **stopPropagation guard wrapper** (`<td|div onClick={e=>e.stopPropagation()}>` around interactive
  children): move the stopPropagation onto the actual interactive child (`<select>`/`<button>` —
  interactive elements aren't flagged) and drop the wrapper's onClick; OR use row-level target delegation.
- **Entities** (`react/no-unescaped-entities`, NOT autofixable): use the script below.

## ENTITIES SCRIPT (TASK ENT only) — write to `/tmp/fix_entities.py`
```python
import sys, json
from collections import defaultdict
ENT = {"'": "&apos;", '"': "&quot;", ">": "&gt;", "}": "&#125;"}
data = json.load(open(sys.argv[1]))                      # eslint --format json output
by_file = defaultdict(list)
for f in data:
    for m in f["messages"]:
        if m.get("ruleId") == "react/no-unescaped-entities":
            by_file[f["filePath"]].append((m["line"], m["column"]))
for path, locs in by_file.items():
    lines = open(path).read().split("\n")
    byline = defaultdict(list)
    for ln, col in locs: byline[ln].append(col)
    for ln, cols in byline.items():
        s = lines[ln-1]
        for col in sorted(set(cols), reverse=True):       # right-to-left so columns don't shift
            ch = s[col-1] if col-1 < len(s) else ""
            if ch in ENT: s = s[:col-1] + ENT[ch] + s[col:]
        lines[ln-1] = s
    open(path, "w").write("\n".join(lines))
    print(f"  {path}: {len(locs)}")
```
Run: `npx eslint src --format json > /tmp/e.json 2>/dev/null && python3 /tmp/fix_entities.py /tmp/e.json`
(loop 2–3× — fixing one entity can shift a sibling's column on the same line; re-measure until 0).
Use `&quot;`/`&apos;` (straight), NOT `&ldquo;`/`&rdquo;` (curly) — a test (CitationBlock) asserts straight quotes.

## REPORT WHEN DONE
The PR number + merge status, the before/after count of your target rule, and any element you intentionally
left as a scoped-disable (with the reason).
