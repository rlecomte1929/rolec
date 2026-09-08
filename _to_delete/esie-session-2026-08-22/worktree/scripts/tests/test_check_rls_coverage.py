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


def _stub_query(policy_less, exposed=None, examined=369):
    """Stand in for the DB call: (policy_less, exposed_grants, tables_examined)."""
    return lambda _url: (policy_less, exposed or {}, examined)


def _run_main(monkeypatch, allowlist_path, query, argv=None):
    monkeypatch.setattr(crc, "ALLOWLIST_FILE", allowlist_path)
    monkeypatch.setattr(crc, "query_policy_less_tables", query)
    monkeypatch.setenv("DATABASE_URL", "postgresql://stub")
    monkeypatch.setattr(sys, "argv", argv or ["check_rls_coverage.py"])
    return crc.main()


def test_main_exits_1_on_unlisted_policyless_table(monkeypatch, tmp_path):
    """End-to-end: a policy-less table absent from the allowlist makes main()
    return 1 (CI fail), without touching a live DB."""
    allowlist = tmp_path / "rls_allowlist.txt"
    allowlist.write_text("# server-only\naudit_log\n")
    assert _run_main(monkeypatch, allowlist, _stub_query(["leaky_table"])) == 1


def test_main_exits_0_when_all_policyless_tables_allowlisted(monkeypatch, tmp_path):
    allowlist = tmp_path / "rls_allowlist.txt"
    allowlist.write_text("# server-only\nleaky_table  # internal ops table\n")
    assert _run_main(monkeypatch, allowlist, _stub_query(["leaky_table"])) == 0


# ── The allowlist justification is VERIFIED, not trusted (2026-08-11 sweep) ─────
#
# Every entry is excused by one claim: "server-role-only, unreachable through the anon
# key". PostgREST reaches the public schema as `anon` / `authenticated`, so that claim is
# checkable — and it can expire without anyone touching the allowlist. A later GRANT
# leaves the table policy-less AND reachable while the allowlist keeps the gate quiet.


def test_allowlisted_table_with_anon_grant_fails(monkeypatch, tmp_path):
    allowlist = tmp_path / "rls_allowlist.txt"
    allowlist.write_text("# server-only\nror_cities  # ops catalogue\n")
    exit_code = _run_main(
        monkeypatch,
        allowlist,
        _stub_query(["ror_cities"], exposed={"ror_cities": ["anon:SELECT"]}),
    )
    assert exit_code == 1, "an anon-granted allowlisted table must fail the gate"


def test_allowlisted_table_with_authenticated_grant_fails(monkeypatch, tmp_path):
    # `authenticated` is just as reachable — any logged-in user of any tenant.
    allowlist = tmp_path / "rls_allowlist.txt"
    allowlist.write_text("# server-only\nror_queue  # rollout queue\n")
    exit_code = _run_main(
        monkeypatch,
        allowlist,
        _stub_query(["ror_queue"], exposed={"ror_queue": ["authenticated:SELECT,UPDATE"]}),
    )
    assert exit_code == 1


def test_grant_on_a_non_allowlisted_table_is_not_the_expiry_check(monkeypatch, tmp_path):
    # A grant on a table that HAS policies is normal and must not fail: RLS is what
    # constrains it. This check is only about retired justifications.
    allowlist = tmp_path / "rls_allowlist.txt"
    allowlist.write_text("# server-only\nror_queue  # rollout queue\n")
    exit_code = _run_main(
        monkeypatch,
        allowlist,
        _stub_query(["ror_queue"], exposed={"cases": ["anon:SELECT"]}),
    )
    assert exit_code == 0


def test_json_pass_flag_agrees_with_exit_code(monkeypatch, tmp_path, capsys):
    """A JSON consumer reading `pass: true` while the process exits 1 is its own
    silent pass. The expired-justification failure must show up in both."""
    import json

    allowlist = tmp_path / "rls_allowlist.txt"
    allowlist.write_text("# server-only\nror_cities  # ops catalogue\n")
    exit_code = _run_main(
        monkeypatch,
        allowlist,
        _stub_query(["ror_cities"], exposed={"ror_cities": ["anon:SELECT"]}),
        argv=["check_rls_coverage.py", "--json"],
    )
    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["pass"] is False
    assert payload["expired_justifications"] == [
        {"table": "ror_cities", "grants": ["anon:SELECT"]}
    ]


# ── A guard that examined nothing has not passed ───────────────────────────────


def test_zero_tables_examined_fails(monkeypatch, tmp_path):
    """AUDIT_SQL returns only offenders, so "0 policy-less tables" looks identical
    whether coverage is complete or the query matched nothing (renamed schema, a
    read-only role that cannot read pg_tables, empty DB). Same failure shape as
    check_compliance_claims' `scanned == 0` and check_route_auth's `examined == 0`."""
    allowlist = tmp_path / "rls_allowlist.txt"
    allowlist.write_text("# fully drained\n")
    assert _run_main(monkeypatch, allowlist, _stub_query([], examined=0)) == 1


def test_zero_tables_examined_fails_even_for_update_allowlist(monkeypatch, tmp_path):
    # Seeding the allowlist from an empty result would write an empty file and read
    # as a drained allowlist.
    allowlist = tmp_path / "rls_allowlist.txt"
    allowlist.write_text("# fully drained\n")
    exit_code = _run_main(
        monkeypatch,
        allowlist,
        _stub_query([], examined=0),
        argv=["check_rls_coverage.py", "--update-allowlist"],
    )
    assert exit_code == 1
    assert allowlist.read_text() == "# fully drained\n", "must not have been rewritten"
