# Canonical Policy Pipeline

This pipeline adds a canonical policy extraction flow alongside the existing policy assistant import path.

## What It Adds

- Canonical SQLAlchemy models and matching API/LLM schemas
- Alembic migration files for the canonical policy tables
- Ingestion from local files or existing `policy_documents` rows
- Context-aware chunking based on structural parse output
- LLM-backed fact extraction with deterministic fallback
- Validation error logging and audit summaries
- Admin API routes under `/api/admin/policy-canonical`
- Company-scoped read/query routes under `/api/policy-canonical`
- Query audit logging for chunk retrieval traceability

## Environment

- `OPENAI_API_KEY`: required for live LLM extraction
- `OPENAI_POLICY_EXTRACTION_MODEL`: optional model override
- `RELOPASS_POLICY_DEFAULT_CURRENCY`: fallback currency for ingestion
- `RELOPASS_POLICY_CHUNK_WORDS`: max words per chunk, default `800`
- `RELOPASS_POLICY_CHUNK_OVERLAP`: overlap ratio, default `0.2`

## Alembic

From `backend/`:

```bash
alembic -c alembic.ini upgrade head
```

This migration tree is scoped to the canonical policy schema only. Legacy schema bootstrapping still comes from the repo’s existing database initialization flow.

## API Flow

1. `POST /api/admin/policy-canonical/ingest`
2. `POST /api/admin/policy-canonical/{canonical_document_id}/chunk`
3. `POST /api/admin/policy-canonical/{canonical_document_id}/extract`
4. Inspect:
   - `/api/admin/policy-canonical/documents/{id}/facts`
   - `/api/admin/policy-canonical/documents/{id}/validation-errors`
   - `/api/admin/policy-canonical/documents/{id}/audit`

For an existing uploaded policy document, use:

```text
POST /api/admin/policy-canonical/from-existing/{policy_document_id}
```

## Company Scoping and Roles

- Every canonical policy document, chunk, fact, validation error, and query audit row is stored with `company_id`.
- HR and Admin users can ingest, update, chunk, extract, and delete canonical policies.
- Employees cannot mutate policies. Admin routes return `403` for employee callers.
- Employee and HR read/query flows are company-scoped:
  - `GET /api/policy-canonical/render/current`
  - `POST /api/policy-canonical/query`
  - `GET /api/policy-canonical/query-audit`
- Query retrieval is filtered by `company_id` before any chunk ranking, so chunks from another company are excluded from consideration.

## Structured Rendering

Use:

```bash
GET /api/policy-canonical/render/current
```

The response returns Markdown grouped by phase and benefit category, including eligibility notes and source chunk identifiers.

## Query Answering and Citations

- Queries are redacted for simple PII patterns before retrieval.
- The retrieval path resolves the active canonical policy document for the user’s company.
- Answers are constrained to retrieved policy chunks and should include chunk-based citations.
- Each query writes an audit record with:
  - `company_id`
  - `user_id`
  - `user_role`
  - `canonical_policy_document_id`
  - redacted query text
  - retrieved chunk ids
  - answer preview

## Manual Audit Script (canonical extraction)

Run the full pipeline against the named source PDFs:

```bash
python backend/scripts/audit_policy_canonical_pipeline.py \
  "/absolute/path/GOPS 12102.pdf" \
  "/absolute/path/Long Term Assignment Policy Summary.pdf"
```

Use `--use-fallback` if you want deterministic extraction instead of the OpenAI path.

The script writes:

- `audit_report.json`
- `audit_report.md`

## Policy assistant audit harness (`audit_policy_assistant.py`)

This script validates **company-scoped retrieval**, **RBAC** (employees cannot mutate policies; HR cannot touch another tenant), and **query answering with citations** against the canonical policy pipeline. Enterprise deployments rely on tenant isolation and audit logs so policy text never bleeds across companies.

### Prerequisites

1. Python virtual environment with backend dependencies installed:

   ```bash
   cd rolec
   python -m venv .venv
   source .venv/bin/activate
   pip install -r backend/requirements.txt
   ```

2. **Bootstrap the database** (required on a fresh machine). Alembic’s canonical revisions expect legacy tables such as `policy_documents` to exist. Run once from the **repository root**:

   ```bash
   PYTHONPATH=. python backend/scripts/bootstrap_backend_database.py
   ```

   This runs `database.init_db()` (runtime SQLite DDL including `policy_documents`, `companies`, and canonical policy tables) and then aligns Alembic: on **SQLite** it usually runs `alembic stamp head` when no `alembic_version` row exists (because `init_db()` already created the same objects Alembic would create). On **Postgres** it runs `alembic upgrade head`. The same `DATABASE_URL` is used throughout. If you do not set `DATABASE_URL`, the script defaults to an **absolute** path: `<repo>/backend/relopass.db`.

   If you prefer manual steps: run `PYTHONPATH=. python -c "from backend.database import db; db.init_db()"` then align Alembic as above (SQLite: `alembic stamp head` if fresh; otherwise `alembic upgrade head`), with a consistent `DATABASE_URL`.

3. **Source PDFs** (not shipped in the repo). Either export paths:

   ```bash
   export RELOPASS_AUDIT_POLICY_GOPS="/absolute/path/GOPS 12102.pdf"
   export RELOPASS_AUDIT_POLICY_LTA="/absolute/path/Long Term Assignment Policy Summary.pdf"
   ```

   or pass `--gops-pdf` / `--lta-pdf`. The script also checks optional repo-relative fallbacks `docs/samples/` and `samples/` if present.

4. Optional: `OPENAI_API_KEY` for LLM-based fact extraction and answers. Without it, the script defaults to deterministic extraction and non-LLM fallback answers (still citation-backed).

If the audit script exits with “Canonical policy tables are missing”, run the bootstrap command in step 2 again (or confirm `DATABASE_URL` points at the same database file you migrated).

### Invocation

From the **repository root** (so `PYTHONPATH` and imports resolve):

```bash
python backend/scripts/audit_policy_assistant.py
```

This creates two companies (`company_acme` and `company_beta` by default), seeds HR and employee profiles per company, ingests the GOPS PDF for Acme and the LTA summary for Beta (chunk + extract), sets them as the active canonical policy per company (latest ingested document wins), runs a representative **(role, company_id, question)** matrix, runs RBAC checks, and writes **`audit_report.json`** in the current working directory.

**Common options**

| Flag | Purpose |
|------|---------|
| `--company-acme` / `--company-beta` | Override tenant ids (must match your DB if reusing rows). |
| `--queries-json path.json` | Custom queries: JSON array of `{"role","company_id","question"}` or `[role, company_id, question]` tuples. |
| `--output-json path` | Report file location (default `audit_report.json`). |
| `--use-openai-extraction` | Use OpenAI for extraction instead of the deterministic fallback. |
| `--no-seed` | Skip company creation, user seeding, and ingestion; requires existing active canonical documents for both company ids (PDF env args not required). |

### Interpreting the output

The script prints a short summary and writes JSON including:

- **`companies`**: Canonical document metadata and a **structured Markdown preview** from `render_canonical_policy_markdown` (phase/category grouping).
- **`rbac`**: Results of `ensure_company_scope_for_write` (employee write blocked, HR other-company blocked, HR own-company allowed).
- **`queries`**: Per query: role, company, answer preview, citation labels, `retrieved_chunk_ids`, and **`cross_tenant_leakage`**: any chunk whose stored `company_id` does not match the user’s company (empty list means no leakage detected).

Exit codes: **0** success; **1** if any query raised an error; **2** if cross-tenant validation failed.

### Automated tests (opt-in)

Unit/integration tests for the audit helpers live in `backend/tests/test_policy_assistant_audit.py`. They are **skipped by default** so normal `pytest` runs stay fast. Run them with:

```bash
cd backend
pytest -m policy_assistant_audit tests/test_policy_assistant_audit.py
```

or set `RUN_POLICY_ASSISTANT_AUDIT=1` to allow the same tests without `-m`.

## Compatibility Notes

- Existing `/api/admin/policies/...` endpoints remain unchanged.
- The canonical extractor can project facts into the legacy assistant-friendly fact shape for bridge scenarios.
- Invalid canonical facts are logged to `canonical_policy_fact_validation_errors` and are excluded from canonical fact inserts.

## Extending The Schema

- Add enum values in both `backend/app/models.py` and `backend/app/schemas.py`
- Extend validation rules in `backend/services/policy_canonical_validation.py`
- Update the extractor prompt/schema in `backend/services/policy_canonical_extraction.py`
- Add migration steps in a new Alembic revision for any table or column change
