"""
[AIQ-1258b] Lead-time config per roadmap track bucket / form category.

Consumed by AIQ-1258c to compute suggested roadmap due dates
(move_date − lead_time). Not yet wired.

The LIVE employee roadmap is projected at read time by ``project_tracks()`` in
``roadmap_projection.py``: each ``case_form`` becomes a step, bucketed into one
of four track keys (visa / civil / family / settlement) via
``CATEGORY_TO_TRACK`` (keyed on ``form_templates.category``).

This module supplies how many days *before the move date* a step should
ideally be started, so a later task can derive a suggested due date. Keys are
accepted at TWO granularities so the consumer can use whichever it has on hand:

  - the four projection track-bucket keys (``visa``, ``civil``, ``family``,
    ``settlement``), and
  - the underlying ``form_templates.category`` values that map into them
    (``work_permit``, ``registration``, ``civil_documents``, ``family``,
    ``tax``, ``health``, ``banking``).

Both kinds of key live in the same mapping; ``lead_time_days_for`` looks a key
up directly. Defaults are sensible starting points (immigration/visa earliest,
civil registration latest) and are expected to be tuned against real corridor
data later.
"""
from __future__ import annotations

# Days before the move/target-start date that a step should ideally begin.
# Track-bucket keys mirror roadmap_projection.TRACKS; category keys mirror
# roadmap_projection.CATEGORY_TO_TRACK.
LEAD_TIME_DAYS: dict[str, int] = {
    # ── Track-bucket keys (project_tracks output) ────────────────────────────
    "visa": 90,        # immigration / work permits — start earliest
    "family": 60,      # dependants' documents and permits
    "settlement": 45,  # housing, banking, tax, health on arrival
    "civil": 30,       # civil-document registration, typically after arrival prep
    # ── form_templates.category keys (inputs to the buckets) ─────────────────
    "work_permit": 90,
    "registration": 90,      # EEA residence scheme → visa bucket
    "civil_documents": 30,
    "tax": 45,
    "health": 45,
    "banking": 45,
}


def lead_time_days_for(bucket_or_category: str) -> int | None:
    """Return the lead time (days before move date) for a track bucket key or a
    form category, or ``None`` if the key is unknown."""
    return LEAD_TIME_DAYS.get(bucket_or_category)
