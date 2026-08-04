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
    "EMPLOYMENT_CONTRACT": "agent not built — AIQ-1766. Prompt exists (prompts/extraction/employment_contract_{de,fr,no}_v1.txt); only the agent is missing.",
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
    # This is the AIQ-1774 blocker, recorded where it is discoverable.
    "TAX_CERT": (
        "outside Cohort-1, AND unresolved even if added: three country-specific agents "
        "(TaxCertDe/Fr/No) sit behind this one code and no country signal reaches the "
        "selection point. Recommended fix is to split this into TAX_CERT_DE/FR/NO so the "
        "flat registry handles them with no selector — see AIQ-1774."
    ),
}

# The runtime codes seeded in rce.document_types (prod, 2026-08-04). Kept here so
# the guard can compare without a live DB, and so drift in either direction shows
# up as a test failure rather than a silent skip in production.
RUNTIME_DOCUMENT_TYPES = frozenset(
    {
        "BIRTH_CERT",
        "DIPLOMA",
        "FOSTER_CARE_ORDER",
        "ID_CARD",
        "MARRIAGE_CERT",
        "PASSPORT_TD3",
        "TAX_CERT",
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
