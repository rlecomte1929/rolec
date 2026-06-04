"""
seed_immigration_form_templates.py — IMM-11

Generates synthetic AcroForm stand-in PDFs for the two reference immigration
forms and uploads them to the Supabase Storage "form-templates" bucket so the
pre-fill pipeline (form_prefill_service.generate_prefilled_pdf) has a template
to fill.

These are STAND-INS until the official government PDFs (German EU Blue Card,
French CERFA 14571) are obtained — the AcroForm field NAMES match
form_field_mappings.form_field_id, so swapping in the real templates requires no
code change.

Usage (from repo root, with SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY set):
    python -m backend.scripts.seed_immigration_form_templates           # upload
    python -m backend.scripts.seed_immigration_form_templates --dry-run # generate only

Field lists are kept in sync with supabase/migrations/20260605800000_imm11_form_field_mappings_seed.sql.
"""
from __future__ import annotations

import argparse
import sys

from backend.app.services.form_prefill_service import (
    TEMPLATE_BUCKET,
    build_synthetic_acroform,
)

# form_id -> (title, [form_field_id, ...]) — mirrors the seed migration.
FORMS = {
    "DE_blue_card_v2024": (
        "Germany — EU Blue Card application (synthetic stand-in)",
        [
            "family_name", "given_names", "date_of_birth", "place_of_birth",
            "nationality", "gender", "passport_number", "passport_issue_date",
            "passport_expiry", "passport_country", "marital_status",
            "employer_name", "job_title", "gross_annual_salary",
            "employment_start_date",
        ],
    ),
    "FR_cerfa_14571_v2024": (
        "France — Long-stay visa CERFA 14571*09 (synthetic stand-in)",
        [
            "nom", "prenoms", "date_naissance", "lieu_naissance", "nationalite",
            "sexe", "numero_passeport", "date_delivrance", "date_expiration",
            "situation_familiale", "profession", "employeur",
        ],
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed immigration form templates.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate the PDFs locally without uploading to Supabase Storage.",
    )
    args = parser.parse_args()

    pdfs = {
        form_id: build_synthetic_acroform(field_ids, title=title)
        for form_id, (title, field_ids) in FORMS.items()
    }
    for form_id, pdf in pdfs.items():
        print(f"generated {form_id}.pdf ({len(pdf)} bytes)")

    if args.dry_run:
        print("dry-run: skipping upload.")
        return 0

    from backend.app.services.supabase_client import get_supabase_admin_client

    sb = get_supabase_admin_client()
    for form_id, pdf in pdfs.items():
        path = f"{form_id}.pdf"
        sb.storage.from_(TEMPLATE_BUCKET).upload(
            path,
            pdf,
            {"content-type": "application/pdf", "upsert": "true"},
        )
        print(f"uploaded {TEMPLATE_BUCKET}/{path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
