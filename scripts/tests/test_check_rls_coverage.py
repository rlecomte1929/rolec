"""Unit tests for the SEC-RLSf allowlist-justification guard (AIQ-663).

Covers find_unjustified_allowlist_entries: every retained entry in
supabase/rls_allowlist.txt must carry a reason (inline `# ...` or a `#` section
header above it). Pure stdlib + tmp files — no DB.
"""
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import check_rls_coverage as crc  # noqa: E402


def _write(tmp_path, text):
    p = tmp_path / "rls_allowlist.txt"
    p.write_text(text)
    return p


def test_missing_file_is_ok(tmp_path):
    assert crc.find_unjustified_allowlist_entries(tmp_path / "nope.txt") == []


def test_empty_allowlist_passes(tmp_path):
    p = _write(tmp_path, "# header only\n# fully drained\n\n")
    assert crc.find_unjustified_allowlist_entries(p) == []


def test_inline_reason_passes(tmp_path):
    p = _write(tmp_path, "audit_log   # server-only internal audit trail\n")
    assert crc.find_unjustified_allowlist_entries(p) == []


def test_section_header_covers_block(tmp_path):
    p = _write(
        tmp_path,
        "# server-role-only ops tables\n"
        "ops_metrics\n"
        "ops_jobs\n",
    )
    assert crc.find_unjustified_allowlist_entries(p) == []


def test_bare_entry_fails(tmp_path):
    p = _write(tmp_path, "naked_table\n")
    offenders = crc.find_unjustified_allowlist_entries(p)
    assert offenders == [(1, "naked_table")]


def test_blank_line_resets_section(tmp_path):
    # The header covers ops_metrics, but the blank line ends the section so the
    # later bare entry is unjustified.
    p = _write(
        tmp_path,
        "# server-role-only\n"
        "ops_metrics\n"
        "\n"
        "stray_table\n",
    )
    offenders = crc.find_unjustified_allowlist_entries(p)
    assert offenders == [(4, "stray_table")]


def test_repo_allowlist_is_fully_justified():
    """The committed allowlist must always pass the guard."""
    repo_allowlist = SCRIPTS_DIR.parent / "supabase" / "rls_allowlist.txt"
    assert crc.find_unjustified_allowlist_entries(repo_allowlist) == []


# ── SEC-RLSh (AIQ-950): schema-aware audit (public + rce) ──────────────────────


def test_audited_schemas_include_public_and_rce():
    assert "public" in crc.AUDITED_SCHEMAS
    assert "rce" in crc.AUDITED_SCHEMAS


def test_audit_sql_scans_audited_schemas_not_just_public():
    # The query must parameterise the schema list (= ANY(%s)), not hardcode public.
    assert "schemaname = ANY(%s)" in crc.AUDIT_SQL
    assert "schemaname = 'public'" not in crc.AUDIT_SQL


def test_qualify_table_keeps_public_bare():
    # Public tables stay bare → existing public allowlist + behaviour unchanged.
    assert crc.qualify_table("public", "users") == "users"


def test_qualify_table_qualifies_non_public():
    # rce (and any non-public) tables are schema-qualified so a policy-less rce
    # table surfaces distinctly and needs an `rce.<name>` allowlist entry.
    assert crc.qualify_table("rce", "contradictions") == "rce.contradictions"


# ── SEC-01 (AIQ-1164): the core fail path — RLS-less table is caught ───────────


def test_policyless_table_not_on_allowlist_is_missing():
    # A new public table with no RLS policy and no allowlist entry MUST surface
    # as missing → the gate returns exit 1 and the PR fails.
    missing = crc.missing_from_allowlist(["new_pii_table"], {"audit_log"})
    assert missing == ["new_pii_table"]


def test_policyless_table_on_allowlist_passes():
    missing = crc.missing_from_allowlist(["audit_log"], {"audit_log"})
    assert missing == []


def test_policyless_rce_table_not_on_allowlist_is_missing():
    # Non-public schemas are schema-qualified; an unlisted rce table still fails.
    missing = crc.missing_from_allowlist(["rce.secrets"], {"rce.audit"})
    assert missing == ["rce.secrets"]


def test_main_exits_1_on_unlisted_policyless_table(monkeypatch, tmp_path):
    """End-to-end: a policy-less table absent from the allowlist makes main()
    return 1 (CI fail), without touching a live DB."""
    allowlist = tmp_path / "rls_allowlist.txt"
    allowlist.write_text("# server-only\naudit_log\n")
    monkeypatch.setattr(crc, "ALLOWLIST_FILE", allowlist)
    monkeypatch.setattr(crc, "query_policy_less_tables", lambda _url: ["leaky_table"])
    monkeypatch.setenv("DATABASE_URL", "postgresql://stub")
    monkeypatch.setattr(sys, "argv", ["check_rls_coverage.py"])
    assert crc.main() == 1


def test_main_exits_0_when_all_policyless_tables_allowlisted(monkeypatch, tmp_path):
    allowlist = tmp_path / "rls_allowlist.txt"
    allowlist.write_text("# server-only\nleaky_table  # internal ops table\n")
    monkeypatch.setattr(crc, "ALLOWLIST_FILE", allowlist)
    monkeypatch.setattr(crc, "query_policy_less_tables", lambda _url: ["leaky_table"])
    monkeypatch.setenv("DATABASE_URL", "postgresql://stub")
    monkeypatch.setattr(sys, "argv", ["check_rls_coverage.py"])
    assert crc.main() == 0
