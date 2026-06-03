# Execution Prompt — SEC-006 · File Upload Validation + Private Bucket Audit

**Notion:** AIQ-478 — `https://www.notion.so/36d887c64d48816993bce6303eb2c0a7`
**Priority:** P1 · **Complexity:** Medium · **Estimated effort:** ~3 hr.
**Branch:** `feature/sec-006-upload-validation`

## Role
Backend security engineer. Goal: every employee/HR document upload is server-side type-validated, size-capped, filename-sanitized, and lives in a private bucket accessed only via short-lived signed URLs.

## Read first
- `backend/main.py:10556` — `POST /api/hr/policies/upload`.
- `backend/main.py:10778` — `POST /api/hr/policy-documents/upload`.
- `backend/main.py:11816` — `POST /api/admin/policies/upload`.
- `backend/main.py:3737` — older upload endpoint (verify scope).
- Bucket-scoped storage calls: `grep -rn "storage.from_" backend/` returns 3 buckets in use:
  - `case-forms` (cases_read.py, cases.py)
  - `form-templates` (case_form_pdf.py)
  - `hr-policies` (via `BUCKET_HR_POLICIES` in services)
- Migrations: `supabase/migrations/20260301022000_hr_policies_bucket.sql`, `20260521040000_form_template_pdfs_bucket.sql`.

## Step 1 — Bucket audit (do this before touching code)
Run, against the live Supabase project:
```sql
SELECT id, name, public, file_size_limit, allowed_mime_types, created_at
FROM storage.buckets
ORDER BY name;
```
For every bucket holding employee/HR documents:
- `public` must be **false**. If any are `true`, flip them to `false` immediately via Supabase MCP migration (do NOT do this through the dashboard — commit a migration so the change is in source control).
- Note current `allowed_mime_types` — if NULL, the bucket accepts anything. Tighten to the SEC-006 allowlist below.
- Note `file_size_limit` — set to 20 MB (`20 * 1024 * 1024 = 20971520` bytes) if NULL or higher.

Migration file to commit: `supabase/migrations/<NEW-TS>_bucket_hardening.sql` setting `public=false`, `allowed_mime_types`, `file_size_limit` on every relevant bucket.

## Step 2 — Server-side validation middleware
Create `backend/app/services/upload_validator.py`:

```python
import magic                       # add to backend/requirements.txt: python-magic==0.4.27
from werkzeug.utils import secure_filename
from fastapi import HTTPException, UploadFile

ALLOWED_MIME = {
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'image/png',
    'image/jpeg',
}
MAX_BYTES = 20 * 1024 * 1024  # 20 MB

async def read_and_validate(file: UploadFile) -> tuple[bytes, str, str]:
    """Returns (content, sanitized_name, detected_mime). Raises HTTPException on policy violation."""
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="file_too_large")
    mime = magic.from_buffer(content, mime=True)
    if mime not in ALLOWED_MIME:
        raise HTTPException(status_code=415, detail=f"unsupported_type:{mime}")
    safe = secure_filename(file.filename or "upload.bin")
    if not safe:
        raise HTTPException(status_code=400, detail="invalid_filename")
    return content, safe, mime
```

Add `python-magic==0.4.27` + `Werkzeug==3.0.4` (only for `secure_filename`) to `backend/requirements.txt`. **Note:** `python-magic` requires the system `libmagic` library; document in `backend/README.md` and verify Render's Python build image has it (it does — `python:3.11-slim` includes it via apt).

## Step 3 — Wire validator into every upload endpoint
Each of the 3+ upload endpoints listed above must:
1. Call `read_and_validate(file)` at the top.
2. Use the returned `safe` filename, not `file.filename`.
3. Build the storage path as `f"{tenant_scope_id}/{uuid4()}/{safe}"` — never trust client-supplied paths.
4. Upload to a **private** bucket.
5. Return a **signed URL** with `expiry=900` (15 min), not a direct public URL.

For routes that previously stored a `file_url` that's a direct storage path: change to store the bucket-relative `path` only, and generate the signed URL on read via `sb.storage.from_(bucket).create_signed_url(path, 900)`.

## Step 4 — Frontend changes (minimal)
Any place that previously rendered `file_url` directly: change to call a new backend endpoint `GET /api/files/signed-url?bucket=...&path=...` (admin-only, RLS-scoped) that returns a fresh 15-min URL. Or inline-fetch from the existing endpoint that owns the row. **Do not** persist signed URLs longer than their TTL.

## Step 5 — Tests
`backend/tests/test_upload_validator.py`:
1. `.exe` content → 415.
2. `.js` content with JS bytes → 415 (verify python-magic actually detects `application/javascript`).
3. 21 MB PDF → 413.
4. Filename `../../etc/passwd.pdf` → `secure_filename` returns `etc_passwd.pdf` (or empty → 400).
5. Valid PDF → returns `(content, safe_name, 'application/pdf')`.

`backend/tests/integration/test_upload_endpoints.py`:
6. POST to each of the 3 upload routes with valid PDF → 200; returned URL is signed and resolves within 15 min, then 403 after expiry.
7. POST to each with `.exe` → 415.

## Step 6 — Bucket visibility regression check
Add to `scripts/rls_coverage_check.py` (or a sibling `scripts/storage_bucket_check.py`) a CI check: query `storage.buckets`, fail if any bucket containing case/HR/employee data has `public = true`. Wire into `.github/workflows/ci.yml` mirroring the `rls-coverage-check` job.

## Constraints
- Server-side validation only — never trust client `Content-Type` or file extension.
- Path traversal must be impossible — every stored path is server-generated (`uuid4()` + `secure_filename`).
- Virus scanning is out of scope this PR (note as known gap, file a follow-up task suggesting ClamAV or Cloudmersive).
- Do not break any existing upload flow — confirm the 3 routes still work end-to-end after the change.

## Test commands
```
cd backend && pytest backend/tests/test_upload_validator.py -v
cd backend && pytest backend/tests/integration/test_upload_endpoints.py -v
cd backend && RELOPASS_DISABLE_RATE_LIMITS=1 pytest -q   # full suite green
python scripts/storage_bucket_check.py
```

## Definition of done
- Bucket migration committed setting `public=false`, `allowed_mime_types`, `file_size_limit` on every relevant bucket.
- `upload_validator.py` shipped + python-magic + Werkzeug in requirements.
- All 3+ upload endpoints route through the validator and return signed URLs.
- Tests prove 415/413/path-traversal handling.
- `storage_bucket_check.py` runs in CI and fails on public-bucket regressions.
- Notion AIQ-478 → Human Review with bucket-audit query output (pre + post) and sample 415 response in Execution Notes.
- Commit per CLAUDE.md Build Hygiene rules.
