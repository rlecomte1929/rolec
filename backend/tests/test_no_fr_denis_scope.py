"""Denis, and the label that silently switched the nationality gate off.

Every record in the NO→FR batch was tagged `nationality: "EEA"` or `"non-EEA"` with no
`nationality_scope_basis`. Denis — a FRENCH national returning Oslo → Paris — is an
OWN_NATIONAL, which matches neither, so he was served ZERO of the 17.

Tagging alone was not enough. The patch that added the scope tags also changed `nationality` to
`"EEA/EU/Swiss"`, a label the matcher did not know. An unrecognised label FAILS OPEN — the
anti-silence contract, and right for a label we cannot interpret — so six `nationality_determined`
records reached EVERY mover, Denis included, and he was told to obtain a residence card a French
citizen in France does not need. The count looked like progress (0 → 11) while the gate was off.

Both halves are pinned here: the alias resolves, and the served sets per persona are asserted.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from backend.app.services.applies_to_matcher import apply_applies_to, nationality_applies
from backend.app.services.nationality_class import EU_EEA, classify_best

BATCH = (Path(__file__).resolve().parents[2]
         / "docs/imports/no-fr-general-curated-2026-08-22/no-fr-general-curated-2026-08-22.ndjson")

DENIS = {"nationality": "France", "origin_country": "NO", "destination_country": "FR"}
EEA_CONTROL = {"nationality": "Spain", "origin_country": "NO", "destination_country": "FR"}
THIRD_COUNTRY = {"nationality": "Venezuela", "origin_country": "NO", "destination_country": "FR"}


def _rows():
    return [json.loads(l) for l in BATCH.read_text().splitlines() if l.strip()]


def _served(rows, profile):
    return {r["fact_key"] for r in rows if apply_applies_to(r["applies_to"], profile)}


class SpelledOutNationalityLabelTest(unittest.TestCase):
    def test_the_spelled_out_label_resolves_instead_of_failing_open(self):
        """`EEA/EU/Swiss` plainly means EU_EEA. Leaving it unmapped does not make the matcher
        cautious — it makes it permissive, which is the opposite of what the tag is for."""
        rule = {"nationality_scope_basis": "nationality_determined", "nationality": "EEA/EU/Swiss"}
        self.assertTrue(nationality_applies(rule, EEA_CONTROL))
        self.assertFalse(nationality_applies(rule, DENIS))
        self.assertFalse(nationality_applies(rule, THIRD_COUNTRY))

    def test_a_genuinely_unknown_label_still_fails_open(self):
        """The anti-silence contract is unchanged: we suppress only what we positively know
        does not apply."""
        rule = {"nationality_scope_basis": "nationality_determined", "nationality": "Ruritanian"}
        self.assertTrue(nationality_applies(rule, DENIS))

    def test_denis_is_an_own_national_not_an_eea_mover(self):
        self.assertNotEqual(classify_best(("France", None), "FR"), EU_EEA)


class DenisServedSetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _rows()

    def test_denis_is_served_the_corridor_wide_rules(self):
        served = _served(self.rows, DENIS)
        self.assertTrue(served, "a returning national must not be served nothing")
        for key in ("no_fr_urssaf_posted_worker_a1_certificate",
                    "no_fr_france_numero_secu_ss_number_assignment",
                    "no_fr_eu_eea_single_state_principle_reg_883_2004"):
            self.assertIn(key, served)

    def test_denis_is_not_told_to_obtain_a_residence_card(self):
        """A French citizen in France needs no carte de séjour. The burden never existed, so a
        rule about an EEA residence card is not an exemption he has — it is not his rule."""
        leaked = {k for k in _served(self.rows, DENIS) if "sejour_card" in k}
        self.assertEqual(leaked, set(), f"carte de séjour rules reached an own-national: {sorted(leaked)}")

    def test_denis_is_not_served_the_non_eea_work_permit_rule(self):
        self.assertNotIn("no_fr_non_eea_worker_work_permit_required", _served(self.rows, DENIS))

    def test_the_eea_control_still_gets_the_residence_card_rules(self):
        """The opposite failure: over-correcting until the EEA mover loses rules that are hers."""
        served = _served(self.rows, EEA_CONTROL)
        self.assertTrue({k for k in served if "sejour_card" in k})
        self.assertNotIn("no_fr_non_eea_worker_work_permit_required", served)

    def test_every_persona_gets_the_audience_scope_rules(self):
        audience = {r["fact_key"] for r in self.rows
                    if r["applies_to"].get("nationality_scope_basis") == "audience_scope"}
        self.assertTrue(audience)
        for profile in (DENIS, EEA_CONTROL, THIRD_COUNTRY):
            self.assertTrue(audience <= _served(self.rows, profile))


if __name__ == "__main__":
    unittest.main()
