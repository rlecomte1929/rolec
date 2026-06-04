# AIQ-614 — CLI validator for AI-W dossier ground-truth files
"""
Usage:
    cd backend && python -m eval.validate_dossier <dossier_dir>

Loads ground_truth.json from <dossier_dir>, validates it against the Dossier
schema, prints PASS/FAIL with any validation errors, and exits 0 on success or
1 on failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import ValidationError

from eval.schemas.dossier import Dossier


def validate(dossier_dir: str) -> bool:
    gt_path = Path(dossier_dir) / "ground_truth.json"
    if not gt_path.exists():
        print(f"FAIL: ground_truth.json not found in {dossier_dir}")
        return False

    with gt_path.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)

    try:
        Dossier.model_validate(raw)
    except ValidationError as exc:
        print("FAIL")
        for err in exc.errors():
            loc = " -> ".join(str(p) for p in err["loc"])
            print(f"  [{loc}] {err['msg']}")
        return False

    print("PASS")
    return True


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python -m eval.validate_dossier <dossier_dir>")
        sys.exit(1)

    ok = validate(sys.argv[1])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
