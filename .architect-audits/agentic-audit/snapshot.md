# Agentic Audit — Layer 0 Diagnostic Snapshot

- **Repository:** rolec (ReloPass)
- **Run:** 2026-06-25
- **Project shape:** hybrid monorepo (Node/React frontend + Python/FastAPI backend + Supabase)
- **AI surface detected:** true — backend `requirements.txt` pins `openai==1.51.2` and `anthropic==0.39.0` (frontend Node deps carry no AI SDK)

## Detected agentic instruction files (in scope)

| Path | Lines | Last modified | Tool family |
| --- | --- | --- | --- |
| `CLAUDE.md` (root, **primary**) | 301 | 2026-06-14 | claude |
| `backend/CLAUDE.md` | 51 | 2026-05-26 | claude |

> `.claude/worktrees/**/CLAUDE.md` copies (≈30 stale worktree checkouts) are out of scope and excluded. Home-dir `~/.claude/*` files are out of scope per the baseline.

- **Total agentic-instruction line count (in scope):** 352
- **Agentic instruction file count:** 2
- **No other tool families present:** no `AGENTS.md`, `.cursorrules`, `.cursor/rules/*.mdc`, `.github/copilot-instructions.md`, `.windsurfrules`, `CONVENTIONS.md`, or Aider config.

## Claude Code settings

- **`.claude/` directory:** present (also contains `skills/`, `worktrees/`).
- **`.claude/settings.json`:** present. Valid JSON. Top-level keys: `enabledPlugins`. Permission entries: 0.
- **`.claude/settings.local.json`:** present. Valid JSON. `permissions.allow` entries: 21. `permissions.deny` entries: 0.
  - **Git status:** TRACKED (`git ls-files` returns it) and NOT gitignored — `.gitignore` excludes only `.claude/worktrees/`.
- **Hooks (Claude settings):** none. (A separate `.githooks/pre-push` exists but is a Git hook, not a Claude Code hook.)
- **MCP servers:** no `mcpServers` block in either settings file (Notion MCP appears only as permission allow-entries by server id).
- **Status-line override:** none.
- **Model override:** none.

## Project shape signals

- Deployable (Render Web Service + Static Site, auto-deploy on `main`).
- Monorepo (`frontend/` Node workspace + `backend/` Python package + `supabase/` migrations) → classified **hybrid**.
