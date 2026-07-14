"""The HR command center must not show synthetic e2e personas (Gap 6).

The E2E Sentinel provisions throwaway `…@testco.com` personas against PRODUCTION
by design (that is what makes it a live canary), and purges them afterwards. But
local and interrupted runs leave rows behind, so a one-time purge cannot hold —
which is exactly why the admin Companies list already filters them at read time.

The HR command center did NOT, so the test personas showed up in the case list
and in every portfolio count derived from it. At the time of writing that was 67
rows of `case_assignments` in prod.

This pins the SQL fragment, not the query, because the fragment is the thing that
must stay correct on both Postgres and SQLite.
"""
from __future__ import annotations

from backend.db.test_data_filter import exclude_test_people


class TestExcludeTestPeopleFragment:
    def test_it_targets_the_command_center_column(self):
        frag = exclude_test_people("ca.employee_identifier")
        assert "ca.employee_identifier" in frag
        assert "@testco.com" in frag

    def test_it_is_true_for_real_people_and_false_for_synthetic_ones(self):
        """Evaluate the fragment as real SQL, so a NULL-handling or dialect bug
        can't hide behind a string assertion."""
        import sqlite3

        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE ca (employee_identifier TEXT)")
        con.executemany(
            "INSERT INTO ca VALUES (?)",
            [
                ("romain@relopass.com",),      # real
                ("hr@testingapril.com",),      # real — must NOT be caught by a
                                               # naive 'test%' pattern
                ("emp_run_9f2@testco.com",),   # synthetic
                ("e2e_hr_a_abc@testco.com",),  # synthetic
                (None,),                       # NULL identifier — must survive
            ],
        )
        frag = exclude_test_people("ca.employee_identifier")
        rows = con.execute(f"SELECT employee_identifier FROM ca WHERE {frag}").fetchall()
        kept = {r[0] for r in rows}

        assert "romain@relopass.com" in kept
        assert "hr@testingapril.com" in kept, "a real tenant must never be hidden"
        assert None in kept, "a NULL identifier is not evidence of a test row"
        assert not any(e and "testco.com" in e for e in kept)
