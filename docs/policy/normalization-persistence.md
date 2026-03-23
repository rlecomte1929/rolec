# Normalization persistence guarantees

## Atomic attempt

A single `run_normalization` persistence phase runs in **one database transaction** (`Database.run_policy_normalization_transaction`). It includes, in order:

1. Optional `company_policies` insert (new shell only).
2. `policy_versions` insert with `normalization_state = normalization_in_progress` (overwritten before commit).
3. All Layer-2 inserts for that version (benefit rules, exclusions, evidence, conditions, applicability, source links).
4. `normalization_draft_json` update plus final `normalization_state` (`normalized_draft` or `normalized_complete`).

If any statement raises, the transaction **rolls back**. There is no orphaned `policy_versions` row without matching Layer-2/draft work from that attempt.

## Markers

| Value | Meaning |
|--------|--------|
| `normalization_in_progress` | Set only inside the open transaction before final update; not observable after successful commit. |
| `normalization_failed` | Reserved; not written by the atomic path (rollback leaves no row). |
| `normalized_draft` | Committed persistence; readiness did not meet auto-publish bar. |
| `normalized_complete` | Committed persistence; readiness met structured completion bar. |

Legacy rows with `normalization_state` **NULL** are treated as pre-feature data: publish gate does not block on NULL (existing behavior for Layer-2 checks still applies).

## Publish gate

Publishing for employees is blocked when `normalization_state` is `normalization_in_progress` or `normalization_failed` (see `PUBLISH_BLOCKED_NORMALIZATION_INCOMPLETE`), in addition to existing Layer-2 checks (`PUBLISH_BLOCKED_NO_LAYER2_RULES`), provenance (`PUBLISH_BLOCKED_INCOMPLETE_METADATA`), and failed source documents (`PUBLISH_BLOCKED_SOURCE_DOCUMENT_FAILED`).

## Non-atomic call sites

Other code paths that call `create_policy_version` / Layer-2 inserts without the transaction wrapper are unchanged but should migrate to the atomic helper for new work.
