"""
policy_versions.normalization_state — lifecycle for normalization persistence.

- normalization_in_progress: row created; Layer-2 + draft not committed yet (same DB transaction).
- normalization_failed: reserved for explicit failure markers (e.g. repair jobs); not set by atomic path.
- normalized_draft: persistence committed; readiness indicates draft / not auto-publishable bar.
- normalized_complete: persistence committed; structured normalization finished per readiness gate.
"""
from __future__ import annotations

NORMALIZATION_STATE_IN_PROGRESS = "normalization_in_progress"
NORMALIZATION_STATE_FAILED = "normalization_failed"
NORMALIZATION_STATE_DRAFT = "normalized_draft"
NORMALIZATION_STATE_COMPLETE = "normalized_complete"

NORMALIZATION_STATE_BLOCK_PUBLISH = frozenset(
    {
        NORMALIZATION_STATE_IN_PROGRESS,
        NORMALIZATION_STATE_FAILED,
    }
)
