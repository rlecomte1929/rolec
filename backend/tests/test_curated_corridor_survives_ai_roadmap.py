"""A generated roadmap must never delete an authored corridor pathway.

THE BUG. `persist_generated_milestones` calls
`delete_case_milestones(exclude_source="service")` before writing its AI steps, so every
non-Services row goes — including the `{phase}_corridor_{NN}` milestones
`timeline_service._corridor_milestones` seeds from the corridor's authored pathway. On
intake submit `_async_seed_and_generate_roadmap` runs seed-then-generate, so the AI steps
replace the seeded ones by design. For a corridor nobody has authored that is fine. For a
curated one it destroys sequenced, cited, human-reviewed content and replaces it with
generated text.

MEASURED IN PRODUCTION 2026-08-22, before the fix:

    corridor   corpus chunks   cases w/ AI steps   cases w/ corridor steps
    FR_NO           46               265                    0
    IN_DE           19                 6                    0
    ES_IE            8                 0                    8

All 272 cases holding AI steps held NOTHING but source='ai' and source='service' rows.
FR→NO has an authored pathway — one case still carries its corridor rows — so the other
265 lost theirs. ES→IE had not fired only because the retriever short-circuits to
RULE_NOT_FOUND on an empty corpus, and ES_IE's corpus was indexed that same day. The next
ES→IE intake submit would have deleted Andrea's CSEP pathway.

WHY THE TESTS LOOK THE WAY THEY DO. The discriminator is the milestone_type NAME, not the
`source` column: all 455 corridor rows in production carry `source IS NULL`, so a guard
written against `source='deterministic'` — the obvious guess, and the value that does not
exist; the real one is 'deterministic_seed' — matches nothing and protects nothing.
`test_the_guard_keys_on_the_name_not_the_source_column` is the test that fails against
that version.
"""
from __future__ import annotations

import os
import sys

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services.case_roadmap_profile import (  # noqa: E402
    curated_corridor_milestones,
    persist_generated_milestones,
)

AI_STEPS = [
    {"order": 1, "title": "Generated step one", "phase": "immigration"},
    {"order": 2, "title": "Generated step two", "phase": "post_arrival"},
]

# Shaped like timeline_service._corridor_milestones output: note source is None, which is
# what every corridor row in production actually carries.
CSEP_ROWS = [
    {"milestone_type": "immigration_corridor_01", "title": "Employer applies for CSEP", "source": None},
    {"milestone_type": "immigration_corridor_02", "title": "Receive permit decision", "source": None},
    {"milestone_type": "post_arrival_corridor_03", "title": "Register with immigration", "source": None},
]

GENERIC_ROWS = [
    {"milestone_type": "task_visa_docs_prep", "title": "Prepare visa pack", "source": "deterministic_seed"},
    {"milestone_type": "task_biometrics", "title": "Biometrics", "source": "deterministic_seed"},
]


class _Db:
    """Records whether the destructive delete was reached."""

    def __init__(self, existing, raise_on_list=False):
        self._existing = list(existing)
        self._raise_on_list = raise_on_list
        self.deleted = False
        self.upserted = []

    def list_case_milestones(self, case_id, request_id=None):
        if self._raise_on_list:
            raise RuntimeError("simulated database blip")
        return list(self._existing)

    def delete_case_milestones(self, case_id, request_id=None, exclude_source=None):
        self.deleted = True
        self._existing = [m for m in self._existing if m.get("source") == exclude_source]

    def upsert_case_milestone(self, case_id=None, request_id=None, source=None, **row):
        self.upserted.append(row)


def test_a_curated_corridor_pathway_is_never_deleted():
    """The Andrea case: CSEP steps present, generated steps arrive, pathway survives."""
    db = _Db(CSEP_ROWS)
    written = persist_generated_milestones(db, "case-es-ie", AI_STEPS, "ES_IE")
    assert written == 0
    assert db.deleted is False, "delete_case_milestones must not be reached"
    assert db.upserted == []
    assert len(curated_corridor_milestones(db, "case-es-ie")) == 3


def test_the_guard_keys_on_the_name_not_the_source_column():
    """Corridor rows carry source=None in production.

    A guard written against source='deterministic' (or 'deterministic_seed') sees nothing
    here and lets the delete through. This fixture deliberately gives every corridor row a
    NULL source so that version cannot pass.
    """
    assert all(m["source"] is None for m in CSEP_ROWS)
    db = _Db(CSEP_ROWS)
    persist_generated_milestones(db, "case-es-ie", AI_STEPS, "ES_IE")
    assert db.deleted is False


def test_an_uncurated_corridor_still_gets_its_generated_roadmap():
    """The guard must not become a blanket refusal.

    A corridor nobody has authored has only generic seed rows; replacing those with
    generated steps is the existing, intended behaviour and must be preserved.
    """
    db = _Db(GENERIC_ROWS)
    written = persist_generated_milestones(db, "case-xx-yy", AI_STEPS, "XX_YY")
    assert written == 2
    assert db.deleted is True
    assert [r["milestone_type"] for r in db.upserted] == [
        "immigration_ai_01", "post_arrival_ai_02",
    ]


def test_a_case_with_no_milestones_at_all_still_gets_generated_steps():
    db = _Db([])
    assert persist_generated_milestones(db, "case-empty", AI_STEPS, "XX_YY") == 2
    assert db.deleted is True


def test_an_unreadable_milestone_list_fails_CLOSED():
    """A transient read failure must never authorise the delete.

    The natural implementation returns [] on error, which reads as "no curated steps" and
    destroys the pathway on exactly the runs where the database is already unhappy. The
    helper returns None for "unknown" and the caller refuses.
    """
    db = _Db(CSEP_ROWS, raise_on_list=True)
    assert curated_corridor_milestones(db, "case-es-ie") is None
    written = persist_generated_milestones(db, "case-es-ie", AI_STEPS, "ES_IE")
    assert written == 0
    assert db.deleted is False, "an unknown state must not permit deletion"


def test_no_usable_steps_is_still_a_no_op():
    """Pre-existing contract: empty generation leaves everything alone."""
    db = _Db(GENERIC_ROWS)
    assert persist_generated_milestones(db, "case-xx-yy", [{"title": ""}], "XX_YY") == 0
    assert db.deleted is False


@pytest.mark.parametrize(
    "milestone_type",
    ["immigration_corridor_01", "post_arrival_corridor_07", "logistics_corridor_02",
     "pre_departure_corridor_01"],
)
def test_every_corridor_phase_prefix_is_recognised(milestone_type):
    """All four phase prefixes observed in production must match the marker."""
    db = _Db([{"milestone_type": milestone_type, "source": None}])
    assert len(curated_corridor_milestones(db, "c")) == 1
    persist_generated_milestones(db, "c", AI_STEPS, "ES_IE")
    assert db.deleted is False


@pytest.mark.parametrize("milestone_type", ["task_visa_submit", "immigration_ai_01", "corridor", "_corridor"])
def test_non_corridor_types_do_not_trip_the_guard(milestone_type):
    """Anti-false-positive: the marker is `_corridor_`, so a bare 'corridor' must not match."""
    db = _Db([{"milestone_type": milestone_type, "source": None}])
    assert curated_corridor_milestones(db, "c") == []
