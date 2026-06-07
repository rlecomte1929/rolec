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
