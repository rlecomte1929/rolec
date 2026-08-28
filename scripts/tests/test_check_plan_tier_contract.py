"""CI coverage for the plan-tier contract guard.

Loads the guard by file path — `scripts/` has no `__init__.py`, so `from scripts.x import`
raises ModuleNotFoundError under CI's full-suite discovery. Same idiom as
test_check_workflow_base_sha.py.

The planted-drift case is the point. This guard exists because two vocabularies coexisted in
production for months without either test suite noticing, so a guard that has only ever passed
would prove nothing. These pin that it FAILS on the shape that actually shipped.
"""
import importlib.util
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _guard():
    spec = importlib.util.spec_from_file_location(
        "check_plan_tier_contract", os.path.join(ROOT, "scripts/check_plan_tier_contract.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _clone(tmp_path):
    """Copy just the files the guard reads, preserving relative layout."""
    for rel in (
        "backend/db/companies.py",
        "frontend/src/types.ts",
        "frontend/src/features/platform-v2/companies/adapter.ts",
    ):
        dst = tmp_path / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(os.path.join(ROOT, rel), dst)
    return tmp_path


def test_the_repo_agrees_today():
    assert _guard().main(["--root", ROOT]) == 0, (
        "company plan_tier vocabulary has drifted between Python and TypeScript — the UI will "
        "silently coerce every unrecognised tier and display one the database does not hold"
    )


def test_it_fails_on_the_drift_that_shipped(tmp_path):
    """The exact shape found in production: Python writes starter/growth/enterprise,
    TypeScript accepts only low/medium/premium."""
    root = _clone(tmp_path)
    p = root / "frontend/src/features/platform-v2/companies/adapter.ts"
    p.write_text(
        p.read_text()
        .replace("'starter' | 'growth' | 'enterprise'", "'low' | 'medium' | 'premium'")
        .replace("['starter', 'growth', 'enterprise']", "['low', 'medium', 'premium']")
    )
    assert _guard().main(["--root", str(root)]) == 1


def test_it_fails_when_only_the_update_path_drifts(tmp_path):
    """The subtler half: create_company and the UI agree, but update_company silently
    writes nothing because its whitelist rejects every legitimate value."""
    root = _clone(tmp_path)
    p = root / "backend/db/companies.py"
    p.write_text(
        p.read_text().replace(
            'if pt in ("starter", "growth", "enterprise")',
            'if pt in ("low", "medium", "premium")',
        )
    )
    assert _guard().main(["--root", str(root)]) == 1


def test_a_missing_source_file_is_exit_2_not_a_pass(tmp_path):
    root = _clone(tmp_path)
    (root / "backend/db/companies.py").unlink()
    assert _guard().main(["--root", str(root)]) == 2


def test_an_unparseable_declaration_is_exit_2_not_a_pass(tmp_path):
    """A pattern that matches nothing must not be read as agreement."""
    root = _clone(tmp_path)
    p = root / "frontend/src/types.ts"
    p.write_text(p.read_text().replace("export type CompanyPlanTier", "export type RenamedAway"))
    assert _guard().main(["--root", str(root)]) == 2
