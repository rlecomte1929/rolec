# backend/CLAUDE.md

Supplements the root `CLAUDE.md`. Backend-specific rules that apply whenever you are
working inside the `backend/` directory.

---

## Service module location — canonical rule (AUDIT-A9.2)

**`backend/app/services/` is the one and only canonical location for all service modules.**

| Tree | Status |
|------|--------|
| `backend/app/services/` | **Canonical. All new service files go here.** |
| `backend/services/` | **Being migrated — do not add new files here.** |

### What this means in practice

- **New service modules:** create them in `backend/app/services/<module>.py`. Never
  create new files under `backend/services/`.
- **Imports:** use `from backend.app.services.<module> import ...`. If you find an
  import like `from backend.services.<module>` or `from services.<module>`, that is a
  pre-migration import — rewrite it to the canonical form when you touch the file.
- **Migration in progress:** 155 files in `backend/services/` are being moved to
  `backend/app/services/` as part of AUDIT-A9.3 (see below). Until that PR lands,
  both trees exist but only `backend/app/services/` is canonical.

### Background and decision record

The two-tree situation is documented in full in:

```
backend/docs/adr-001-service-tree-consolidation.md   ← ADR-001 (Status: Accepted)
backend/docs/services-migration-matrix.md            ← Per-file inventory + all 85 import sites
```

The migration (AUDIT-A9.3) will:
1. Copy all 155 files from `backend/services/` into `backend/app/services/`
2. Rewrite all 85 cross-import lines
3. Delete `backend/services/`

This will land as a single atomic PR on `audit/stage-1-security`. Do not attempt a
partial migration — the ADR requires atomicity.

---

## Other backend conventions

See the root `CLAUDE.md` for the full backend architecture description
(dual-layer pattern, database access rules, authentication, environment variables,
deployment, and the audit remediation workflow).
