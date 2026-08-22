"""Generator/verifier separation for ``requirement_items.verification_status``.

``verification_status`` is the provenance ladder — ``representative`` →
``corpus_grounded`` → ``expert_verified`` (AIQ-1349). The top rung is defined as
"signed off by a licensed immigration professional (human-only)", but until this
guard existed nothing enforced that: ``crud.create_requirement_item`` wrote
whatever status its payload carried, and every caller of that funnel is an
automated producer — the Otto promotion pipeline (``backend/imports/otto``), the
YAML seeder (``backend/scripts/seed_requirements.py``) and the research stub
(``services/research.py``). A seed file or promotion payload claiming
``expert_verified`` would have been recorded as a human signature that never
happened. That is the exact overclaim the provenance model exists to prevent.

The invariant, enforced fail-closed at the write path:

1. **A generator is structurally unable to write ``expert_verified``.**
   ``crud.create_requirement_item`` routes every ``verification_status`` (and the
   guard-owned ``verified_by`` / ``verified_at`` columns) through
   ``assert_generator_verification_write`` — a payload that claims
   ``expert_verified``, smuggles the actor columns, or carries a status outside
   the canonical ladder is REJECTED with ``VerificationWriteError``. Nothing is
   written, nothing is silently downgraded.

2. **Only a human can flip representative/corpus_grounded → expert_verified.**
   The single write path into ``expert_verified`` is ``mark_expert_verified``,
   which refuses to run without an explicit human actor: ``verified_by`` must be
   a non-empty identifier that does not look like an automated/LLM/service
   identity, and ``verified_at`` is stamped alongside it. The admin router's
   verify endpoint is the only production caller, behind ``require_admin``.

3. **A human signature cannot be silently overwritten.** Once a row is
   ``expert_verified``, a generator upsert that would change its
   ``verification_status`` (a YAML re-seed, a re-promotion) is rejected loudly
   instead of downgrading the row. Revoking a human verification is itself a
   human act and has no automated path.

This mirrors the two-key design on the counsel-attestation axis (only the admin
promote endpoint may write ``attested`` — see ``routers/attestation.py``) and the
``review_status`` publication gate (stamped ``reviewed_by``/``reviewed_at``).
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Iterable, Mapping, Optional

#: The canonical provenance ladder. Anything else is a label-consistency defect —
#: ``draft`` exists only in ``draft_requirements.py`` output files, which by
#: contract never reach the database.
#:
#: ``verified`` was missing here and PRODUCTION USES IT. Measured 2026-08-22:
#: ``representative`` 163 / ``corpus_grounded`` 19 / ``verified`` 11 — and all 11
#: ``verified`` rows are SERVED (``review_status='approved'``). The frontend has
#: rendered it since #1922, as "Reviewed" (info), deliberately distinct from
#: "Expert-verified" because no lawyer has seen those rows.
#:
#: So this tuple described a ladder the database does not have, and
#: ``assert_generator_verification_write`` would have rejected a legitimate
#: ``verified`` write through ``crud.create_requirement_item`` as "outside the
#: canonical ladder". Latent only because the rows that use it were written by
#: direct SQL during founder review (AIQ-1845), which does not pass through here.
VERIFICATION_STATUSES = ("representative", "corpus_grounded", "verified", "expert_verified")

EXPERT_VERIFIED = "expert_verified"

#: What an automated producer may write. ``None`` is also accepted (legacy rows
#: and the research stub carry no provenance claim at all).
#:
#: ``verified`` is NOT here, and that is the point of adding it above rather than
#: below: it is a claim that a human read the source and confirmed the row, so a
#: generator must not be able to mint it. It sits on the ladder so the value is
#: legal and renderable; it stays off this set so only a human review path writes
#: it — the same two-key split ``expert_verified`` already has, one rung down.
GENERATOR_WRITABLE_STATUSES = frozenset({"representative", "corpus_grounded"})

#: Columns only ``mark_expert_verified`` may set. A generator payload that
#: carries them is trying to forge the human signature and is rejected outright.
GUARD_OWNED_COLUMNS = ("verified_by", "verified_at")

#: Identity tokens that mark an actor as automated. Matched against the
#: identifier split on non-alphanumerics, so ``otto-research``, ``service:promo``
#: and ``ci_pipeline`` all fail while a human name that merely contains a token
#: as a substring (e.g. "Agathe") does not.
_AUTOMATED_ACTOR_TOKENS = frozenset({
    "agent", "ai", "assistant", "auto", "automated", "automation", "bot",
    "claude", "cron", "daemon", "gpt", "import", "importer", "job", "llm",
    "machine", "model", "noreply", "otto", "pipeline", "promoter", "robot",
    "scheduler", "script", "seed", "seeder", "service", "svc", "system",
    "worker",
})

_TOKEN_SPLIT = re.compile(r"[^a-z0-9]+")


class VerificationWriteError(ValueError):
    """A write that would break generator/verifier separation. Nothing was written."""


def is_human_actor(identifier: Optional[str]) -> bool:
    """True when ``identifier`` plausibly names a real human, not an automated identity.

    This is deliberately a deny-list, not proof of humanity — real authentication
    is the admin router's job (``require_admin``). What this closes is the honest
    mistake and the lazy forgery: a pipeline stamping ``verified_by='otto-research'``
    or ``'service:catalog-promotion'`` must fail loudly, not land as a signature.
    """
    if not isinstance(identifier, str):
        return False
    ident = identifier.strip()
    if not ident:
        return False
    tokens = {t for t in _TOKEN_SPLIT.split(ident.lower()) if t}
    return not (tokens & _AUTOMATED_ACTOR_TOKENS)


def assert_generator_verification_write(
    payload: Mapping[str, Any],
    *,
    existing_status: Optional[str] = None,
    context: str = "create_requirement_item",
) -> None:
    """Validate one generator-path write of a requirement item. Raises; never mutates.

    Called by ``crud.create_requirement_item`` on BOTH branches of its upsert, so
    every automated producer (Otto promote, YAML seed, research stub) passes
    through it. Fail-closed: any violation raises ``VerificationWriteError`` and
    the caller must not write the row.
    """
    for column in GUARD_OWNED_COLUMNS:
        if column in payload:
            raise VerificationWriteError(
                f"{context}: '{column}' is guard-owned and cannot be written through the "
                "generator path. Only services/verification_guard.mark_expert_verified "
                "records the human signature."
            )

    has_claim = "verification_status" in payload
    new_status = payload.get("verification_status")

    if has_claim and new_status is not None:
        if new_status not in VERIFICATION_STATUSES:
            raise VerificationWriteError(
                f"{context}: verification_status={new_status!r} is not in the canonical "
                f"ladder {VERIFICATION_STATUSES}. Refusing to write an inconsistent label."
            )
        if new_status not in GENERATOR_WRITABLE_STATUSES:
            raise VerificationWriteError(
                f"{context}: verification_status={new_status!r} is a human signature and "
                "cannot be written by a generator/import/seed path. Promotion into "
                f"'{EXPERT_VERIFIED}' happens only through mark_expert_verified with a "
                "recorded human actor."
            )

    if existing_status == EXPERT_VERIFIED and has_claim and new_status != EXPERT_VERIFIED:
        raise VerificationWriteError(
            f"{context}: the existing row is '{EXPERT_VERIFIED}' — a recorded human "
            f"signature. Rewriting its verification_status to {new_status!r} from an "
            "automated path would silently revoke it. Rejecting the write; revocation "
            "is a human decision."
        )


def assert_generator_statuses(statuses: Iterable[Optional[str]], *, context: str) -> None:
    """Batch form for pure expansion steps (e.g. the YAML seeder), same rules."""
    for status in statuses:
        assert_generator_verification_write(
            {"verification_status": status} if status is not None else {},
            context=context,
        )


def mark_expert_verified(
    item: Any,
    *,
    verified_by: Optional[str],
    verified_at: Optional[datetime] = None,
) -> Any:
    """The ONLY write path into ``verification_status='expert_verified'``.

    Stamps ``verified_by`` + ``verified_at`` alongside the flip so the signature
    is auditable. Raises ``VerificationWriteError`` (nothing mutated) when the
    actor is missing or looks automated. The caller owns the transaction.
    """
    if not isinstance(verified_by, str) or not verified_by.strip():
        raise VerificationWriteError(
            "mark_expert_verified: verified_by is required — 'expert_verified' is a human "
            "signature and cannot be recorded without naming the human."
        )
    if not is_human_actor(verified_by):
        raise VerificationWriteError(
            f"mark_expert_verified: verified_by={verified_by!r} looks like an "
            "automated/LLM/service identity. A generator cannot sign off content as "
            "expert-verified."
        )
    item.verification_status = EXPERT_VERIFIED
    item.verified_by = verified_by.strip()
    item.verified_at = verified_at or datetime.utcnow()
    return item
