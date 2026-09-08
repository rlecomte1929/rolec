"""Canonical document-type vocabulary — the single mapping between classifier and runtime.

Three vocabularies exist in this codebase and, before this module, none of them agreed:

  1. the MVP heuristic  -- `document_extraction_queue.classify_document`, 4 values
  2. the C1-04a classifier -- `prompts/docs/classifier/v1.txt`, 10 codes
  3. the runtime        -- `rce.document_types.code` + `EXTRACTION_AGENT_REGISTRY`, 8 codes

Measured 2026-08-04, the classifier-runtime intersection was **exactly one code**:
`PASSPORT_TD3`. Every other classifier output resolved to no agent, and every other agent was
unreachable from real classification. The practical effect: of seven wired agents, only the
passport one could ever actually be selected once the real classifier lands.

`rce.document_types.code` is the source of truth. It is the FK target for `rce.documents`
(`documents_document_type_id_fkey`) and the key `EXTRACTION_AGENT_REGISTRY` is built on, so the
classifier must map onto it rather than the other way round.

Nothing here changes behaviour on its own. It makes the disagreement explicit, gives the
classifier swap (AIQ-1768) a target to map onto, and is enforced by
`backend/tests/test_document_type_vocabulary.py`, which fails when a code is added on either
side without a decision recorded here.
"""
from __future__ import annotations

from typing import Dict, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Classifier code -> runtime document-type code
# ─────────────────────────────────────────────────────────────────────────────
#
# Only entries where a runtime code AND a registered agent already exist. A
# mapping to a code with no agent would look like coverage while still skipping.

CLASSIFIER_TO_RUNTIME: Dict[str, str] = {
    # Identical on both sides.
    "PASSPORT_TD3": "PASSPORT_TD3",
    # An EU/EEA national identity card is what IdCardAgent reads (TD1 MRZ).
    "EU_NATIONAL_ID": "ID_CARD",
    # Reg. (EC) 1030/2002 residence permit. VisaPermitAgent already emits
    # visa_type / document_number / issue+expiry / issuing_country, which is
    # exactly this document's field set; DE Aufenthaltstitel and NO
    # oppholdstillatelse are listed as its own variants in the classifier prompt.
    "RESIDENCE_PERMIT_EU": "VISA_PERMIT",
    # COLLAPSED on purpose. The classifier splits ISCED 6 / 7 because that
    # distinction is visible in the document; the runtime has one DIPLOMA code and
    # DiplomaAgent infers the level itself (`infer_isced_level_from_title`). So the
    # split is preserved where it is observed and dropped where nothing consumes
    # it — collapsing here loses no information the agent uses.
    "DIPLOMA_BACHELOR": "DIPLOMA",
    "DIPLOMA_MASTER": "DIPLOMA",
    # [AIQ-1766] ONE code for all three locales, unlike the TAX_CERT split above.
    # The classifier emits exactly this one code and lists FR CDI/CDD, DE
    # Arbeitsvertrag and NO arbeidskontrakt as its variants; the three prompts
    # share an identical output schema, so the locales differ in language, not in
    # what they carry. EmploymentContractAgent reads the locale from the
    # document's own text, so no runtime selector has to be threaded through the
    # orchestrator — which is what made the old TAX_CERT arrangement unreachable.
    "EMPLOYMENT_CONTRACT": "EMPLOYMENT_CONTRACT",
}

# ─────────────────────────────────────────────────────────────────────────────
# Classifier codes with no runtime code yet, each with the reason
# ─────────────────────────────────────────────────────────────────────────────
#
# These classify fine; nothing downstream can act on them. Deliberately NOT
# seeded into rce.document_types: with no agent, a seeded code and an absent one
# behave identically (document_type_id ends up NULL either way, and the
# orchestrator records skipped_no_agent), so seeding would add rows that buy
# nothing and imply support that does not exist.

CLASSIFIER_PENDING_RUNTIME: Dict[str, str] = {
    # EMPLOYMENT_CONTRACT graduated to CLASSIFIER_TO_RUNTIME in AIQ-1766 — the
    # agent now exists and is registered.
    "PAYSLIP": "agent not built — AIQ-1767. Neither agent nor prompt exists; the payslip prompt was never merged.",
    "ANABIN_EVIDENCE": "DE credential-recognition printout. No agent, no extraction need identified yet.",
    "ZAB_STATEMENT_OF_COMPARABILITY": "DE Zeugnisbewertung. Feeds the IN_DE Blue Card runway as a milestone, not as extracted fields.",
    "HEALTH_INSURANCE_PROOF": "Proof of coverage. Presence matters; no structured fields consumed downstream.",
}

# ─────────────────────────────────────────────────────────────────────────────
# Runtime codes the classifier cannot produce, each with the reason
# ─────────────────────────────────────────────────────────────────────────────
#
# The classifier prompt states its own scope: "The 10 codes are the Cohort-1
# subset of the canonical Document Types catalog." These four sit outside that
# subset, so a document of these types classifies as UNKNOWN today.

RUNTIME_WITHOUT_CLASSIFIER: Dict[str, str] = {
    "BIRTH_CERT": "outside the classifier's Cohort-1 subset; family documents are a later cohort.",
    "MARRIAGE_CERT": "outside Cohort-1 — see BIRTH_CERT.",
    "FOSTER_CARE_ORDER": "outside Cohort-1 — see BIRTH_CERT.",
    # [AIQ-1774] The second half of this entry is now resolved; the first half is not.
    # The split shipped: each locale has its own code and its own registry entry, so
    # the selector problem is gone and all three agents are reachable. What remains is
    # purely the Cohort-1 scope boundary — the classifier prompt declares tax
    # certificates out of scope and its eval (prompts/docs/classifier/v1.eval.md, F10)
    # asserts a DE Lohnsteuerbescheinigung must return UNKNOWN. Expanding it is a
    # Cohort-2 scope change with its own eval, not part of the split.
    #
    # These are NOT unreachable in production: rce_document_ingest's filename
    # heuristic produces all three today (lohnsteuer→DE, avis→FR, skatte→NO).
    "TAX_CERT_DE": "outside Cohort-1; produced by the ingest filename heuristic (lohnsteuer/steuerbescheid), not the C1-04a classifier.",
    "TAX_CERT_FR": "outside Cohort-1; produced by the ingest filename heuristic (avis/imposition), not the C1-04a classifier.",
    "TAX_CERT_NO": "outside Cohort-1; produced by the ingest filename heuristic (skatte), not the C1-04a classifier.",
}

# The runtime codes rce.document_types is seeded with by the repo's migrations. Kept
# here so the guard can compare without a live DB, and so drift in either direction
# shows up as a test failure rather than a silent skip in production.
#
# This is the REPO's declared state, which prod reaches only after the out-of-band
# apply (CLAUDE.md — merging a migration PR does not create the rows). The three
# TAX_CERT_* codes come from 20261019000000_rce_tax_cert_split_by_locale.sql and are
# pending in prod until an operator applies it; the bare TAX_CERT they replace is
# deleted by that same migration.
RUNTIME_DOCUMENT_TYPES = frozenset(
    {
        "BIRTH_CERT",
        "DIPLOMA",
        # [AIQ-1766] Seeded by 20261020000000_rce_employment_contract_document_type.sql.
        "EMPLOYMENT_CONTRACT",
        "FOSTER_CARE_ORDER",
        "ID_CARD",
        "MARRIAGE_CERT",
        "PASSPORT_TD3",
        # [AIQ-1774] Replaced the bare TAX_CERT code, which routed to no agent.
        "TAX_CERT_DE",
        "TAX_CERT_FR",
        "TAX_CERT_NO",
        "VISA_PERMIT",
    }
)


def runtime_code_for(classifier_code: str) -> Optional[str]:
    """The runtime document-type code for a classifier output, or None.

    None means "classified, but nothing downstream handles it" — the caller must
    treat that as a fail-soft skip, exactly as an unregistered code is treated
    today. It must never fall back to a nearest-match: sending a payslip to the
    contract extractor produces confident, wrong fields, which is worse than not
    extracting at all.
    """
    return CLASSIFIER_TO_RUNTIME.get(classifier_code)
