from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def test_cvr_instances_validate():
    script = ROOT / "scripts/validate_cvr.py"
    proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    data = json.loads((ROOT / "docs/cvr/instances/fr-no-2026-07-15-founder.json").read_text())
    assert data["corridor_id"] == "FR-NO"
    assert data["cvr_version"] == "1.0"
