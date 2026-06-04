"""
[P1-6 / AIQ-800] Roadmap read-time projection (Option B).

The persisted ``roadmap_tracks`` / ``roadmap_steps`` tables are never written in
production (nothing materialises them), so the employee RoadmapScreen rendered an
empty placeholder and the dossier form-card "Roadmap step" label was always blank.

Rather than build a writer + sync engine for those tables, this module *projects*
a roadmap from the case's real ``case_forms``: each form becomes a step, grouped
into one of the four track buckets the UI already renders
(Visa & Permit / Civil Documents / Family / Settlement). The projection is a pure
function of the form list — no DB access, no persistence — so it is trivially
unit-testable and inherits the (already-correct) case-id handling of whatever
loaded the forms.

Consumed by:
  - ``GET /api/cases/{id}/roadmap/tracks`` (cases_read) → RoadmapScreen
  - ``cases_read._row_to_summary`` → form-card ``roadmap_step_title`` label
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Track buckets — names/icons mirror roadmap_builder.derive_roadmap so the UI is
# visually consistent whichever surface a user came from.
# ─────────────────────────────────────────────────────────────────────────────

TRACKS = {
    "visa":       {"name": "Visa & Permit",   "icon": "passport", "sort_order": 0},
    "civil":      {"name": "Civil Documents", "icon": "document", "sort_order": 1},
    "family":     {"name": "Family",          "icon": "family",   "sort_order": 2},
    "settlement": {"name": "Settlement",      "icon": "home",     "sort_order": 3},
}

# Primary mapping: form_templates.category → track key.
CATEGORY_TO_TRACK = {
    "work_permit":     "visa",
    "registration":    "visa",        # EEA registration scheme = residence/right-to-work
    "civil_documents": "civil",
    "family":          "family",
    "tax":             "settlement",
    "health":          "settlement",
    "banking":         "settlement",
}

# Per-code overrides for categories that are overloaded. ``registration`` covers
# both the EEA residence scheme (→ visa) and address registration (→ settlement);
# pin the settlement cases here so they don't land under Visa & Permit.
CODE_TO_TRACK = {
    "RF-1234": "settlement",          # Norway address registration (folkeregister)
}

# Catch-all for ad-hoc forms / unknown categories. Settlement is the most generic
# "everything else" bucket in the existing UX.
DEFAULT_TRACK = "settlement"


# ─────────────────────────────────────────────────────────────────────────────
# Form status → RoadmapStepV2 status enum
# (frontend enum: pending | in_progress | awaiting_employee | awaiting_vendor |
#  awaiting_hr | blocked | completed | skipped)
# ─────────────────────────────────────────────────────────────────────────────

_FORM_STATUS_TO_STEP_STATUS = {
    "approved":    "completed",
    "submitted":   "completed",       # submitted to the authority = done from the user's side
    "rejected":    "blocked",         # needs rework
    "pending_doc": "awaiting_employee",
    "in_progress": "in_progress",
    "auto_filled": "in_progress",
    "ready":       "in_progress",
    "not_started": "pending",
}

_COMPLETED_STEP_STATUSES = {"completed", "skipped"}


@dataclass
class ProjectedStep:
    id: str
    title: str
    status: str
    owner: str
    due_date: Optional[str]
    sort_order: int


@dataclass
class ProjectedTrack:
    key: str
    name: str
    icon: str
    sort_order: int
    progress_pct: int
    steps: List[ProjectedStep] = field(default_factory=list)


def track_key_for_form(category: Optional[str], code: Optional[str]) -> str:
    """Resolve the track bucket key for a form. Per-code override wins, then
    category, then the catch-all default."""
    if code and code in CODE_TO_TRACK:
        return CODE_TO_TRACK[code]
    if category and category in CATEGORY_TO_TRACK:
        return CATEGORY_TO_TRACK[category]
    return DEFAULT_TRACK


def track_label_for_form(category: Optional[str], code: Optional[str]) -> str:
    """Human-readable track name for the form-card 'Roadmap step' label."""
    return TRACKS[track_key_for_form(category, code)]["name"]


def _step_status_for_form(form: Any) -> str:
    if getattr(form, "is_blocked", False):
        return "blocked"
    return _FORM_STATUS_TO_STEP_STATUS.get(str(getattr(form, "status", "") or ""), "pending")


def project_tracks(forms: List[Any]) -> List[ProjectedTrack]:
    """Project a list of CaseFormSummary-like objects into roadmap tracks.

    Each form becomes one step in its track bucket. Tracks with no forms are
    omitted. Per-track progress = completed steps / total steps. Input order is
    preserved as step sort_order (the caller already sorts by status/blocker).

    Duck-typed on: ``.id``, ``.status``, ``.is_blocked``, ``.deadline`` and
    ``.template.code`` / ``.template.category`` / ``.template.name``.
    """
    by_key: dict[str, ProjectedTrack] = {}

    for idx, form in enumerate(forms):
        template = getattr(form, "template", None)
        category = getattr(template, "category", None)
        code = getattr(template, "code", None)
        key = track_key_for_form(category, code)

        track = by_key.get(key)
        if track is None:
            meta = TRACKS[key]
            track = ProjectedTrack(
                key=key,
                name=meta["name"],
                icon=meta["icon"],
                sort_order=meta["sort_order"],
                progress_pct=0,
            )
            by_key[key] = track

        title = getattr(template, "name", None) or "Document"
        track.steps.append(ProjectedStep(
            id=str(getattr(form, "id", "")),
            title=str(title),
            status=_step_status_for_form(form),
            owner="employee",
            due_date=getattr(form, "deadline", None),
            sort_order=len(track.steps),
        ))

    # Compute per-track progress and return ordered tracks.
    tracks = sorted(by_key.values(), key=lambda t: t.sort_order)
    for track in tracks:
        total = len(track.steps)
        done = sum(1 for s in track.steps if s.status in _COMPLETED_STEP_STATUSES)
        track.progress_pct = round(100 * done / total) if total else 0
    return tracks
