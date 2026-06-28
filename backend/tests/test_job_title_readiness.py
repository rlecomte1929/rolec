"""AIQ-1343 — HR 'Role / job title' readiness item.

Regression for the beta bug where the HR checklist item 'Role / job title' never
cleared even after the employee filled job title. Root cause:
`_draft_to_relocation_profile` emitted ``employer.roleTitle = None`` for a draft pass
without jobTitle, and `_merge_profiles` let that None overwrite a previously-saved
good roleTitle — so the persisted profile lost the value and the HR item stayed
outstanding. The wizard intentionally drops blank fields (intakeToCaseDraft.ts) so a
partial later save must never wipe earlier data.
"""
import os

# Skip the query-counter event.listen (which attaches to the conftest-mocked
# db.engine and would fail at import) — same as the app-mounted test harness.
os.environ.setdefault("RELOPASS_DISABLE_RATE_LIMITS", "1")
os.environ.setdefault("RELOPASS_QUERY_COUNTER_OFF", "1")

from backend.main import _draft_to_relocation_profile, _merge_profiles  # noqa: E402
from backend.hr_case_readiness_view import build_intake_checklist_items  # noqa: E402


def _role_title_item(profile):
    return next(
        i for i in build_intake_checklist_items(profile) if i["key"] == "role_title"
    )


def test_filled_job_title_maps_to_role_title_and_satisfies_readiness():
    draft = {"assignmentContext": {"jobTitle": "Senior SWE", "employerName": "Acme"}}
    profile = _draft_to_relocation_profile(draft, "aid-1")
    assert profile["primaryApplicant"]["employer"]["roleTitle"] == "Senior SWE"
    assert _role_title_item(profile)["satisfied"] is True


def test_empty_job_title_is_outstanding_and_not_emitted_as_none():
    profile = _draft_to_relocation_profile({"assignmentContext": {}}, "aid-2")
    employer = profile["primaryApplicant"]["employer"]
    # a blank must not be persisted as an explicit None (drop-blanks contract)
    assert "roleTitle" not in employer
    assert _role_title_item(profile)["satisfied"] is False


def test_blank_resubmit_does_not_clobber_saved_role_title():
    # An earlier submit persisted a good roleTitle...
    saved = _draft_to_relocation_profile(
        {"assignmentContext": {"jobTitle": "Senior SWE"}}, "aid-3"
    )
    assert _role_title_item(saved)["satisfied"] is True
    # ...a later partial save whose draft has no jobTitle must not wipe it.
    blank_pass = _draft_to_relocation_profile({"assignmentContext": {}}, "aid-3")
    merged = _merge_profiles(saved, blank_pass)
    assert merged["primaryApplicant"]["employer"]["roleTitle"] == "Senior SWE"
    assert _role_title_item(merged)["satisfied"] is True
