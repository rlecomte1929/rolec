"""Regenerating a case's roadmap picks up the corridor overlay, idempotently.

#1938 wired `roadmap_corridor_overlay` into `timeline_service.compute_default_milestones`,
so an ES→IE third-country national now gets the CSEP journey. Milestones are only written at
case creation/submit, so cases created before it keep the generic pack. Andrea's 6ecadafe,
measured in production 2026-08-22: 16 `task_*` rows, 0 corridor steps, every one `pending`
with `source` NULL — including task_visa_docs_prep / task_visa_submit / task_biometrics.

THE HAZARD THESE TESTS EXIST FOR. `db.upsert_case_milestone` is an upsert only when given a
`milestone_id`; without one it unconditionally INSERTs. So "run the generator again" — the
obvious implementation — silently doubles every row. The idempotency tests below are the
point of the file, not a formality.
"""
from __future__ import annotations

import os
import sys
import unittest
import uuid

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.roadmap_regeneration_service import (  # noqa: E402
    PROTECTED_STATUSES,
    milestone_inputs_from_draft,
    plan_regeneration,
    regenerate_case_milestones,
)
from backend.app.services.timeline_service import compute_default_milestones  # noqa: E402

CSEP_MARKERS = (
    "Critical Skills Employment Permit",
    "'D' Employment visa",
    "IRP",
    "PPSN",
    "RPN",
)
GENERIC_VISA = {"task_visa_docs_prep", "task_visa_submit", "task_biometrics"}


def _draft(nationality: str, origin: str = "ES", destination: str = "IE"):
    return {
        "relocationBasics": {
            "originCountry": origin,
            "destCountry": destination,
            "nationality": nationality,
        }
    }


def _generated(nationality: str, **kw):
    return compute_default_milestones(
        case_id="case-under-test", **milestone_inputs_from_draft(_draft(nationality, **kw))
    )


# Andrea's 16 rows, as production holds them.
def _andrea_existing():
    types = [
        "task_profile_core", "task_family_dependents", "task_passport_upload",
        "task_employment_letter", "task_route_verify", "task_hr_case_review",
        "task_immigration_review", "task_visa_docs_prep", "task_visa_submit",
        "task_biometrics", "task_temp_housing", "task_movers_shipment",
        "task_travel_plan", "task_arrival_registration", "task_tax_local_registration",
        "task_settling_in",
    ]
    return [
        {"id": f"m-{i}", "milestone_type": t, "title": t.replace("_", " ").title(),
         "status": "pending", "source": None, "sort_order": (i + 1) * 5,
         "description": None, "target_date": None, "owner": "joint", "criticality": "normal"}
        for i, t in enumerate(types)
    ]


class GeneratorProducesTheCorridorJourney(unittest.TestCase):
    def test_a_venezuelan_on_es_ie_gets_the_csep_steps(self) -> None:
        blob = " | ".join(m["title"] for m in _generated("VE"))
        for marker in CSEP_MARKERS:
            self.assertIn(marker, blob, f"CSEP journey is missing {marker!r}")

    def test_an_eu_national_on_es_ie_gets_no_visa_or_permit_steps(self) -> None:
        rows = _generated("ES")
        blob = " | ".join(m["title"] for m in rows)
        for forbidden in ("Critical Skills Employment Permit", "'D' Employment visa", "IRP card"):
            self.assertNotIn(forbidden, blob, f"an EU/EEA national was served {forbidden!r}")
        self.assertFalse([m for m in rows if m["milestone_type"] in GENERIC_VISA])

    def test_the_eu_national_still_gets_the_shared_post_arrival_steps(self) -> None:
        """Free movement removes the permit, not the PPSN and the Revenue registration —
        an empty roadmap would be its own bug."""
        blob = " | ".join(m["title"] for m in _generated("ES"))
        self.assertIn("PPSN", blob)
        self.assertIn("RPN", blob)


class PlanReconciliationTests(unittest.TestCase):
    def test_andrea_s_case_gains_the_corridor_steps_and_loses_the_generic_visa_pack(self) -> None:
        plan = plan_regeneration(_andrea_existing(), _generated("VE"))
        inserted = " | ".join(p["title"] for p in plan.inserts)
        for marker in CSEP_MARKERS:
            self.assertIn(marker, inserted, f"regeneration did not add {marker!r}")

        existing_by_id = {m["id"]: m for m in _andrea_existing()}
        deleted_types = {existing_by_id[i]["milestone_type"] for i in plan.delete_ids}
        self.assertTrue(
            GENERIC_VISA <= deleted_types,
            f"the superseded generic visa pack survived: {GENERIC_VISA - deleted_types}",
        )

    def test_a_second_run_is_a_no_op(self) -> None:
        """The whole idempotency contract, and the one `upsert_case_milestone` cannot give
        us on its own."""
        generated = _generated("VE")
        # Materialise the state a first run would leave behind.
        settled = [
            {"id": f"s-{i}", "status": "pending", "source": None, **m}
            for i, m in enumerate(generated)
        ]
        plan = plan_regeneration(settled, generated)
        self.assertTrue(plan.is_noop, f"second run would change: {plan.summary()}")
        self.assertEqual([], plan.inserts)
        self.assertEqual([], plan.delete_ids)
        self.assertEqual([], plan.updates)

    def test_completed_work_is_never_deleted_even_when_superseded(self) -> None:
        """A generic step the employee already ticked off is evidence. The generator moving
        on is not a reason to unremember that somebody did something."""
        existing = _andrea_existing()
        for row in existing:
            if row["milestone_type"] == "task_visa_submit":
                row["status"] = "completed"
        plan = plan_regeneration(existing, _generated("VE"))
        by_id = {m["id"]: m for m in existing}
        deleted = {by_id[i]["milestone_type"] for i in plan.delete_ids}
        self.assertNotIn("task_visa_submit", deleted)
        self.assertIn("task_visa_submit", plan.kept_protected)

    def test_every_protected_status_is_honoured(self) -> None:
        for status in PROTECTED_STATUSES:
            with self.subTest(status):
                existing = _andrea_existing()
                for row in existing:
                    if row["milestone_type"] == "task_biometrics":
                        row["status"] = status
                plan = plan_regeneration(existing, _generated("VE"))
                by_id = {m["id"]: m for m in existing}
                self.assertNotIn(
                    "task_biometrics", {by_id[i]["milestone_type"] for i in plan.delete_ids}
                )

    def test_service_owned_rows_are_never_touched(self) -> None:
        existing = _andrea_existing() + [{
            "id": "svc-1", "milestone_type": "service_movers_quote", "title": "Movers quote",
            "status": "pending", "source": "service", "sort_order": 500,
            "description": None, "target_date": None, "owner": "joint", "criticality": "normal",
        }]
        plan = plan_regeneration(existing, _generated("VE"))
        self.assertNotIn("svc-1", plan.delete_ids)
        self.assertIn("service_movers_quote", plan.kept_protected)

    def test_progress_survives_an_update_to_a_still_generated_step(self) -> None:
        """Wording/timing refresh, status untouched."""
        generated = _generated("VE")
        target = generated[0]
        existing = [{
            "id": "keep-1", "milestone_type": target["milestone_type"],
            "title": "an old title", "status": "in_progress", "source": None,
            "sort_order": 999, "description": None, "target_date": None,
            "owner": "joint", "criticality": "normal",
        }]
        plan = plan_regeneration(existing, generated)
        updates = {mid: payload for mid, payload in plan.updates}
        self.assertIn("keep-1", updates)
        self.assertEqual("in_progress", updates["keep-1"]["status"])
        self.assertEqual(target["title"], updates["keep-1"]["title"])

    def test_a_pre_existing_duplicate_is_not_adopted_twice(self) -> None:
        rows = _andrea_existing()
        dupe = dict(rows[0]); dupe["id"] = "dupe-1"
        plan = plan_regeneration(rows + [dupe], _generated("VE"))
        self.assertIn("dupe-1", plan.delete_ids)


class _FakeDb:
    """Records calls; enough to prove the service drives the DB seam correctly."""

    def __init__(self, existing):
        self.rows = {m["id"]: dict(m) for m in existing}
        self.inserted, self.updated, self.deleted = [], [], []
        self._n = 0

    def list_case_milestones(self, case_id, request_id=None):
        return [dict(r) for r in self.rows.values()]

    def upsert_case_milestone(self, case_id, milestone_type=None, title=None,
                              milestone_id=None, request_id=None, **kw):
        if milestone_id:
            self.updated.append(milestone_id)
            self.rows[milestone_id].update({"title": title, **kw})
            return self.rows[milestone_id]
        self._n += 1
        new_id = f"new-{self._n}"
        self.rows[new_id] = {"id": new_id, "milestone_type": milestone_type, "title": title,
                             "source": None, "status": kw.get("status", "pending"), **kw}
        self.inserted.append(new_id)
        return self.rows[new_id]

    def delete_case_milestone(self, milestone_id, case_id=None, request_id=None):
        self.deleted.append(milestone_id)
        self.rows.pop(milestone_id, None)
        return 1


class ServiceDrivesTheDatabaseTests(unittest.TestCase):
    def test_applying_then_reapplying_does_not_duplicate(self) -> None:
        """End-to-end idempotency against the real reconcile + a recording DB."""
        db = _FakeDb(_andrea_existing())
        first = regenerate_case_milestones(db, "case-1", draft=_draft("VE"), apply=True)
        self.assertTrue(first.inserts, "first run added nothing")

        before = len(db.rows)
        second = regenerate_case_milestones(db, "case-1", draft=_draft("VE"), apply=True)
        self.assertTrue(second.is_noop, f"second run was not a no-op: {second.summary()}")
        self.assertEqual(before, len(db.rows), "a second run changed the row count")

        types = [r["milestone_type"] for r in db.rows.values()]
        self.assertEqual(len(types), len(set(types)), "duplicate milestone_type after re-run")

    def test_the_result_contains_the_csep_journey_after_applying(self) -> None:
        db = _FakeDb(_andrea_existing())
        regenerate_case_milestones(db, "case-1", draft=_draft("VE"), apply=True)
        blob = " | ".join(r["title"] for r in db.rows.values())
        for marker in CSEP_MARKERS:
            self.assertIn(marker, blob)
        remaining = {r["milestone_type"] for r in db.rows.values()}
        self.assertFalse(GENERIC_VISA & remaining, "generic visa pack shown beside the CSEP one")

    def test_dry_run_writes_nothing(self) -> None:
        db = _FakeDb(_andrea_existing())
        plan = regenerate_case_milestones(db, "case-1", draft=_draft("VE"), apply=False)
        self.assertTrue(plan.inserts, "dry run computed no change to report")
        self.assertEqual([], db.inserted)
        self.assertEqual([], db.updated)
        self.assertEqual([], db.deleted)

    def test_an_eu_case_regenerates_without_visa_steps(self) -> None:
        db = _FakeDb(_andrea_existing())
        regenerate_case_milestones(db, "case-eu", draft=_draft("ES"), apply=True)
        blob = " | ".join(r["title"] for r in db.rows.values())
        self.assertNotIn("Critical Skills Employment Permit", blob)
        self.assertNotIn("'D' Employment visa", blob)
        self.assertFalse(GENERIC_VISA & {r["milestone_type"] for r in db.rows.values()})


class DraftInputTests(unittest.TestCase):
    def test_nationality_precedence_matches_the_seeding_sites(self) -> None:
        draft = {
            "relocationBasics": {"nationality": "XX", "originCountry": "ES", "destCountry": "IE"},
            "employeeProfile": {"nationality": "YY"},
            "primaryApplicant": {"nationality": "VE"},
        }
        self.assertEqual("VE", milestone_inputs_from_draft(draft)["nationality"])

    def test_an_empty_draft_degrades_rather_than_raising(self) -> None:
        for draft in (None, {}, {"relocationBasics": None}):
            inputs = milestone_inputs_from_draft(draft)
            self.assertIsNone(inputs["nationality"])
            self.assertIsNone(inputs["destination_country"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
