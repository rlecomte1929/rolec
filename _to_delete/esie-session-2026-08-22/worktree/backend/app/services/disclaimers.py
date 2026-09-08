"""AIQ-1349 — non-liability disclaimer for immigration guidance.

Single source of truth (backend) for the recommend-not-liable disclaimer attached
to requirement / roadmap responses. Mirrors the frontend copy in
frontend/src/features/immigration/immigrationDisclaimerContent.ts — keep in sync.
"""

IMMIGRATION_DISCLAIMER_VERSION = "2026-06-29-v1.0"

IMMIGRATION_DISCLAIMER = (
    "ReloPass surfaces indicative immigration guidance to help you prepare. It is a "
    "recommendation, not legal advice, and ReloPass accepts no liability for it. "
    "Immigration requirements change and depend on your personal circumstances — you "
    "remain responsible for validating every requirement and document with the relevant "
    "authority or a licensed immigration professional before you act."
)

# Current platform-wide provenance level of the requirement catalog. Items are
# curated + cited ("representative") but not yet signed off by a licensed
# immigration lawyer ("expert_verified").
DEFAULT_VERIFICATION_STATUS = "representative"
