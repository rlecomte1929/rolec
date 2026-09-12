#!/usr/bin/env python3
"""Validate CVR JSON instances against the unified v1.0 required-field contract.

Does not pull in jsonschema: CI already has a heavy Python graph. This checks the
fields the serving catalog must not duplicate and that verdict/relief_moment exist.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs/cvr/cvr.schema.json"
INSTANCES = ROOT / "docs/cvr/instances"

REQUIRED_ROOT = (
    "cvr_version",
    "cvr_uid",
    "corridor_id",
    "session",
    "outcomes",
    "relief_moment",
)
REQUIRED_OUTCOMES = (
    "requirements_correct_ids",
    "requirements_wrong_ids",
    "requirements_missed_ids",
    "non_obvious_confirmed_ids",
)


def _fail(path: Path, msg: str) -> str:
    return f"{path}: {msg}"


def validate_instance(path: Path, data: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return [_fail(path, "root must be an object")]
    for key in REQUIRED_ROOT:
        if key not in data:
            errors.append(_fail(path, f"missing {key}"))
    if data.get("cvr_version") != "1.0":
        errors.append(_fail(path, "cvr_version must be '1.0'"))
    session = data.get("session")
    if not isinstance(session, dict) or "session_date" not in session:
        errors.append(_fail(path, "session.session_date required"))
    outcomes = data.get("outcomes")
    if isinstance(outcomes, dict):
        for key in REQUIRED_OUTCOMES:
            if key not in outcomes or not isinstance(outcomes[key], list):
                errors.append(_fail(path, f"outcomes.{key} must be an array"))
    else:
        errors.append(_fail(path, "outcomes must be an object"))
    relief = data.get("relief_moment")
    if not isinstance(relief, dict) or "response" not in relief:
        errors.append(_fail(path, "relief_moment.response required (bool or null)"))
    per = data.get("per_requirement") or []
    if isinstance(per, list):
        for i, row in enumerate(per):
            if not isinstance(row, dict) or "requirement_id" not in row or "judgment" not in row:
                errors.append(_fail(path, f"per_requirement[{i}] needs requirement_id and judgment"))
    return errors


def main() -> int:
    schema = json.loads(SCHEMA_PATH.read_text())
    if schema.get("$schema") != "http://json-schema.org/draft-07/schema#":
        print("schema $schema must be Draft-07", file=sys.stderr)
        return 1
    errors: list[str] = []
    paths = sorted(INSTANCES.glob("*.json"))
    if not paths:
        print("no instances under docs/cvr/instances", file=sys.stderr)
        return 1
    for path in paths:
        data = json.loads(path.read_text())
        errors.extend(validate_instance(path, data))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"ok: {len(paths)} CVR instance(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
