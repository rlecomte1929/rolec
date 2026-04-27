#!/usr/bin/env python3
"""
Apply a Section C test fixture to a company's policy_config draft.

Reads a JSON fixture from backend/tests/fixtures/policy/ and writes it
through the same put_draft path the API uses, so the fixture exercises
real validation, real DB writes, and real override persistence. Lets you
demo NovoLike / RocheLike multi-region policies in a dev environment in
one command, without clicking through the editor.

Usage:
  scripts/apply_test_policy_fixture.py --company <company_id> --fixture novolike

Both the fixture name (without .json) and the company UUID are required.
The script prints the resulting effective_date + benefit count on success.

NOT for production. The fixture data is illustrative, not a real customer
policy. Skips publish — the draft stays unpublished so HR can review
before going live.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.database import Database  # noqa: E402
from backend.services.policy_config_matrix_service import (  # noqa: E402
    CONFIG_KEY,
    PolicyConfigMatrixService,
)


def _fixture_path(name: str) -> str:
    return os.path.join(
        _REPO_ROOT, "backend", "tests", "fixtures", "policy", f"{name}.json"
    )


def _ensure_draft(svc: PolicyConfigMatrixService, db: Database, company_id: str) -> str:
    """Return the draft policy_version_id for `company_id`, creating one
    if needed. Mirrors what the HR ensure_draft endpoint does."""
    cfg = db.ensure_policy_config(company_id, CONFIG_KEY)
    pid = str(cfg["id"])
    draft = db.get_policy_config_draft_for_config(pid)
    if draft:
        return str(draft["id"])
    # Use the service's ensure_draft path so version numbering matches
    # the API behavior. ensure_draft returns the working payload, not
    # the raw version id, so we re-fetch.
    svc.ensure_draft(company_id, created_by=None)
    draft = db.get_policy_config_draft_for_config(pid)
    if not draft:
        raise RuntimeError("ensure_draft did not produce a draft row")
    return str(draft["id"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company", required=True, help="company_id (UUID)")
    parser.add_argument(
        "--fixture",
        required=True,
        choices=["novolike", "rocheslike"],
        help="fixture name (without .json)",
    )
    parser.add_argument(
        "--effective-date",
        default=date.today().isoformat(),
        help="effective date for the draft (default: today)",
    )
    args = parser.parse_args()

    path = _fixture_path(args.fixture)
    if not os.path.exists(path):
        print(f"ERROR: fixture not found: {path}", file=sys.stderr)
        return 2
    with open(path, "r", encoding="utf-8") as f:
        fixture = json.load(f)

    db = Database()
    svc = PolicyConfigMatrixService(db)

    vid = _ensure_draft(svc, db, args.company)
    body = {
        "policy_version": vid,
        "effective_date": args.effective_date,
        "categories": fixture["categories"],
    }
    try:
        result = svc.put_draft(args.company, body)
    except ValueError as e:
        # Validation error — the structured payload is the error message.
        print(f"ERROR: validation failed:\n{e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: put_draft failed: {e}", file=sys.stderr)
        return 1

    benefit_count = sum(
        len(c.get("benefits") or []) for c in result.get("categories", [])
    )
    print(
        f"Applied fixture {args.fixture!r} to company {args.company} → "
        f"draft v{result.get('version_number')}, "
        f"effective {result.get('effective_date')}, "
        f"{benefit_count} benefit row(s)."
    )
    print("Draft is unpublished. Publish via /api/hr/policy-config/publish "
          "or the HR Policy page to make it live.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
