"""The EEA member states, as ISO 3166-1 alpha-2 UPPERCASE codes. One copy.

Extracted from `trigger_engine` so a guard can import it without importing the engine.
`trigger_engine` pulls in SQLAlchemy at module level; `scripts/check_form_template_honesty.py`
runs in a CI job that installs no backend dependencies, and importing the engine there failed
with `ModuleNotFoundError: No module named 'sqlalchemy'`. The alternative — a second copy of the
set in the script — is exactly the pattern that produced AIQ-1778, where 'FRANCE' silently failed
to match a pure-ISO-2 set. So: one module, no dependencies, both callers import it.

Deliberately stdlib-only. Do not add an import to this file.

Note the repo carries other, differently-scoped EEA-ish sets —
`immigration_regime._EU_EEA_COUNTRIES` and `family_propagation._EU_EEA_COUNTRIES` both hold
country NAMES and answer a different question (is this destination in the EU/EEA, for a
nationality-vs-destination distinction documented in those modules). They are not
interchangeable with this one and are not consolidated here;
`backend/tests/test_nationality_cross_surface_consistency.py` is what keeps those honest.
"""
from __future__ import annotations

from typing import FrozenSet

# EU/EEA member states. An EEA national relocating to another EEA country follows the
# registration scheme rather than a work permit, which is what makes this set load-bearing:
# `trigger_engine._build_context` resolves visa_type 'eea_registration' exactly when BOTH the
# origin and the destination are in here.
EEA_COUNTRIES: FrozenSet[str] = frozenset({
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR",
    "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK",
    "SI", "ES", "SE", "IS", "LI", "NO",
})
