# Optional policy PDF samples

The policy assistant audit script (`backend/scripts/audit_policy_assistant.py`) can load PDFs from here if they exist:

- `GOPS 12102.pdf`
- `Long Term Assignment Policy Summary.pdf`

These files are **not** committed to the repository. Obtain them from your policy library and place them in this folder, or set:

- `RELOPASS_AUDIT_POLICY_GOPS`
- `RELOPASS_AUDIT_POLICY_LTA`

to absolute paths, or pass `--gops-pdf` / `--lta-pdf`.

Before the audit, run once from the repo root: `PYTHONPATH=. python backend/scripts/bootstrap_backend_database.py` so the database and Alembic migrations are applied.

To generate **placeholder PDFs** for local testing (requires `reportlab`, listed in `backend/requirements.txt`):

```bash
PYTHONPATH=. python backend/scripts/generate_sample_audit_pdfs.py
```

See `docs/policy/canonical-policy-pipeline.md` for the full audit workflow.
