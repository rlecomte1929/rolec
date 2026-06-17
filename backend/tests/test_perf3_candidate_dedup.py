"""
[AIQ-1014/PERF-3] Prove the N+1 dedup in collect_company_id_candidates_for_assignment:
passing the already-fetched HR company + employee profile yields a BYTE-IDENTICAL
candidate list while issuing ZERO redundant DB lookups (vs. one get_hr_company_id +
one get_profile_record on the query-on-demand path).
"""
from __future__ import annotations

import unittest

from backend.app.services.policy_resolution import (
    collect_company_id_candidates_for_assignment as collect,
)


class _CountingDb:
    def __init__(self, hr_company, profile):
        self._hr = hr_company
        self._profile = profile
        self.hr_calls = 0
        self.profile_calls = 0

    def get_hr_company_id(self, uid):
        self.hr_calls += 1
        return self._hr

    def get_profile_record(self, uid):
        self.profile_calls += 1
        return self._profile


_ASSIGN = {"hr_user_id": "hr-1", "employee_user_id": "emp-1"}
_CASE = {"company_id": "co-case"}


class CandidateDedupTests(unittest.TestCase):
    def test_query_on_demand_path_unchanged(self):
        db = _CountingDb("co-hr", {"company_id": "co-prof"})
        out = collect(db, _ASSIGN, _CASE)
        self.assertEqual(out, ["co-case", "co-hr", "co-prof"])
        self.assertEqual((db.hr_calls, db.profile_calls), (1, 1))  # original behaviour

    def test_prefetched_path_is_identical_with_zero_queries(self):
        db = _CountingDb("co-hr", {"company_id": "co-prof"})
        out = collect(
            db, _ASSIGN, _CASE,
            hr_company_id="co-hr",
            employee_profile={"company_id": "co-prof"},
        )
        self.assertEqual(out, ["co-case", "co-hr", "co-prof"])  # byte-identical
        self.assertEqual((db.hr_calls, db.profile_calls), (0, 0))  # 2 queries saved

    def test_equivalence_across_edge_cases(self):
        # (case_company, hr_company, profile) → expected deduped candidates
        cases = [
            ("co-1", "co-1", {"company_id": "co-1"}, ["co-1"]),          # all same → 1
            ("co-1", "co-2", {"company_id": "co-3"}, ["co-1", "co-2", "co-3"]),
            (None, "co-2", {"company_id": "co-3"}, ["co-2", "co-3"]),     # no case co
            ("co-1", None, None, ["co-1"]),                              # no hr/profile
            ("co-1", "co-2", None, ["co-1", "co-2"]),                    # profile None
        ]
        for case_co, hr_co, prof, expected in cases:
            case = {"company_id": case_co} if case_co is not None else {}
            db_a = _CountingDb(hr_co, prof)
            db_b = _CountingDb(hr_co, prof)
            on_demand = collect(db_a, _ASSIGN, case)
            prefetched = collect(db_b, _ASSIGN, case, hr_company_id=hr_co, employee_profile=prof)
            self.assertEqual(on_demand, expected, f"on-demand {case_co}/{hr_co}/{prof}")
            self.assertEqual(prefetched, on_demand, f"prefetched != on-demand for {case_co}/{hr_co}/{prof}")
            self.assertEqual((db_b.hr_calls, db_b.profile_calls), (0, 0))


if __name__ == "__main__":
    unittest.main()
