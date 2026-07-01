# AUDOS.md — ReloPass

> **Auto-generated manifest.** Do not edit manually — this file is regenerated on every push from Audos.

## File Structure

All workspace files live inside `audos-workspace-776786/`. Files outside this folder are ignored during inbound sync.

```
audos-workspace-776786/
  Desktop.tsx              ← Space shell / desktop entry point (dock, windows, launcher, Otto)
  SpaceRuntimeContext.tsx  ← Shared Space runtime context + logic
  config.json              ← Workspace manifest (apps, branding, theme, layout — source of truth)
  *.generated.ts/.css      ← Platform-managed (theme/branding) — regenerated, do not edit
  apps/<AppName>/App.tsx   ← Code-first Space apps (each registered via config.json)
  landing-pages/    ← Landing page TSX files (compiled to DB app records)
  mini-apps/        ← Mini-app TSX files (compiled to DB app records)
  components/       ← Shared React components (stored in GCS space files)
  hooks/            ← Custom React hooks
  lib/              ← Utility libraries
  data/             ← JSON data files
  assets/           ← Static assets
  tools/            ← Agent tools (Otto capabilities)
```

## Repo directory → Audos UI map

| Repo path | Audos UI surface |
| --- | --- |
| `Desktop.tsx` | Your Space (the desktop shell) |
| `config.json` | Space settings + app list (manifest) |
| `apps/<AppName>/App.tsx` | Apps in your Space (dock + app launcher) |
| `landing-pages/*.tsx` | Product Studio → Landing Pages (microsites) |
| `mini-apps/*.tsx` | Product Studio → Mini Apps |
| `components/`, `hooks/`, `lib/`, `data/`, `assets/` | Shared building blocks |
| `tools/` | Otto's capabilities |

## Editable vs. platform-managed

- **Editable (round-trips through sync):** `Desktop.tsx`, `config.json`, `SpaceRuntimeContext.tsx`, and files under `apps/`, `components/`, `hooks/`, `lib/`, `data/`, `assets/`, `landing-pages/`, `mini-apps/`.
- **Platform-managed (regenerated — don't edit):** `README.md`, `AUDOS.md`, `*.generated.ts` / `*.generated.css`, and anything under `.published-source/`.

## Current Apps

### Landing Pages
  - `landing.tsx`

### Mini Apps
  - _(none yet)_

## Compilation Rules

- **Bundler**: ESBuild with JSX automatic runtime
- **Target**: ES2020, ESM format
- **External deps**: React, ReactDOM, Lucide React (resolved via CDN importmap)
- **Single-file TSX**: Each landing page and mini-app is a single `.tsx` file
- **Space files**: Components, hooks, lib, data are stored in GCS and bundled during space compilation
- **`Desktop.tsx`**: the entry point for the Space, compiled on the backend together with the files it imports
- **Config-driven app registry**: a Space app only renders if it has an entry in `config.json` (its `component` field points at `apps/<AppName>/App.tsx`). Dropping a file under `apps/` *without* a matching `config.json` entry will not surface it.
- **`components/` are not auto-wired**: editing a file under `components/` does NOT automatically manifest inside `Desktop.tsx` or any app — something must `import` it first. It only affects screens that already import it.

## Sync Behavior

### Inbound (GitHub → Audos)
- Every push triggers a full-tree sync
- `landing-pages/*.tsx` → matched to DB app records by filename → ESBuild compile
- `mini-apps/*.tsx` → matched to DB app records by filename → ESBuild compile
- Other files → written to GCS space storage
- Post-sync: compilation cache cleared + fresh build triggered

### Outbound (Audos → GitHub)
- Manual push from Developer Window
- Commits tagged with `[audos-sync]` to prevent infinite loops
- AUDOS.md regenerated on each push

### Loop Prevention
- Commits containing `[audos-sync]` in the message are skipped during inbound sync

## WorkspaceDB SDK

Each app in this workspace has access to a built-in database SDK — no import needed.

### `useWorkspaceDB(tableName, options?)` — React hook

```tsx
const { data, loading, error, total, refresh } = useWorkspaceDB('orders', {
  filters: [{ column: 'status', operator: 'eq', value: 'active' }],
  orderBy: { column: 'created_at', direction: 'desc' },
  limit: 50,
  offset: 0,
  shared: false, // true = bypass per-session scoping
});
```

**Options:** `filters` (eq, neq, gt, gte, lt, lte, like, ilike) · `orderBy` · `limit` (default 50) · `offset` (default 0) · `shared` (default false)

> By default, each visitor only sees their own rows. Use `shared: true` for reference/catalog data seeded via Otto or MCP tools.

### `window.__workspaceDb` — Imperative API

```ts
// Query
const { data, total } = await window.__workspaceDb.from('orders')
  .eq('status', 'active').orderBy('created_at', 'desc').limit(50).get();

// Insert / Bulk insert
await window.__workspaceDb.from('orders').insert({ customer_name: 'Alice', total: 99.99 });
await window.__workspaceDb.from('orders').bulkInsert([{ ... }, { ... }]);

// Update / Delete
await window.__workspaceDb.from('orders').update(rowId, { status: 'shipped' });
await window.__workspaceDb.from('orders').delete(rowId);

// Aggregate
const revenue = await window.__workspaceDb.from('orders').eq('status', 'completed').aggregate('total', 'sum');

// Shared (cross-session) access
const { data } = await window.__workspaceDb.from('articles', { shared: true }).get();
```

### Standard columns (auto-added to every table)

`id` (serial PK) · `session_id` (text) · `created_at` · `updated_at`

## Direct Database Access

Workspace owners can generate scoped PostgreSQL credentials for local development via the Developer Window. These credentials grant direct read-write access to the workspace's database schema and work with any standard PostgreSQL client (pgAdmin, TablePlus, psql, ORMs, etc.). Credentials can be regenerated or revoked at any time from the Developer Window.

## Tips for AI Agents

- Each app file must be self-contained (single TSX file with all imports)
- Use `useWorkspaceDB` or `window.__workspaceDb` for data persistence (not localStorage)
- CDN dependencies are resolved via importmap — don't bundle React
- Test compilation locally with ESBuild before pushing
- MCP-seeded data has `session_id=NULL`; always use `{ shared: true }` in apps that read it
