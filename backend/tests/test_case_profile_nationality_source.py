"""`build_case_profile` read nationality from two paths production never writes.

WHAT WAS MEASURED (prod, 2026-08-23, 1,948 wizard_cases with a draft):

    draft_json path                      cases   read by build_case_profile?
    employeeProfile.nationality          1,435   NO
    primaryApplicant.nationality             0   NO
    relocationBasics.nationality             0   YES
    personalInfo.nationality                 0   YES

Both paths it read are populated in ZERO cases. So the third branch of its `or`
chain — `or origin_raw`, "an EEA-corridor mover is typically a national of the
origin" — fired for 100% of cases, and every AI roadmap was built from the
mover's ORIGIN COUNTRY in place of their nationality.

That is invisible most of the time, because people usually move from their own
country: of the 1,434 cases carrying a nationality, the substitution agreed with
the truth 1,385 times. It is the other 49 that matter. Running the product's own
`immigration_regime._is_eu_national` over both values:

    42 cases were WRONGLY GRANTED free movement   (a third-country national
                                                   read as an EU/EEA one)
     7 cases were wrongly denied it

Stripping junk nationalities ("asdas", "123" — `nationality` is unvalidated free
text) leaves 23 real ones, and **14 of those are on ES->IE**: 13 Indian nationals
and 1 Venezuelan national relocating Spain -> Ireland. Ireland publishes no
EU/EEA free-mover requirements at all — an EU national gets a single notice where
a third-country national gets 14 requirements — so those 14 movers were served a
free-movement roadmap for a journey that needs an employment permit and an
immigration permission.

The failure direction is the dangerous one: it UNDER-serves requirements. A
missing permit step is a person who cannot legally start work.

WHY IT SURVIVED. `wizard_draft_mapper` — whose whole job is reading this draft —
has known all four paths since P2. `build_case_profile` grew its own shorter
chain. `test_nationality_cross_surface_consistency` already warns that a surface
growing its own copy of nationality logic is the recurring defect here; this is
that defect one layer earlier, in where the value is READ rather than how it is
classified. The fix therefore extracts the mapper's chain into
`employee_nationality()` and calls it from both, instead of adding a fourth copy.

SCOPE. This pins where nationality is READ. What to do when a case genuinely
records none (514 prod cases) is a separate decision, deliberately not made here
— see `test_absent_nationality_still_falls_back_to_origin_UNCHANGED`.
"""
from __future__ import annotations

import unittest

from backend.app.services.case_roadmap_profile import build_case_profile


def _case(draft_extra: dict, origin: str = "ES", dest: str = "IE") -> dict:
    """A case dict shaped exactly as backend/main.py builds it before calling
    generate_ai_roadmap_for_case: {"id", "status", "draft": json.loads(draft_json)}."""
    draft = {"relocationBasics": {"originCountry": origin, "destCountry": dest}}
    draft.update(draft_extra)
    return {"id": "c1", "status": "submitted", "draft": draft}


class NationalityIsReadFromWhereProductionWritesIt(unittest.TestCase):

    def test_wizard_path_employeeProfile_is_read(self):
        """1,435 of 1,948 prod cases store it here. This is the whole bug."""
        profile, _ = build_case_profile(_case({"employeeProfile": {"nationality": "IN"}}))
        self.assertEqual(profile.nationality, "IN")

    def test_orchestrator_path_primaryApplicant_is_read(self):
        profile, _ = build_case_profile(_case({"primaryApplicant": {"nationality": "IN"}}))
        self.assertEqual(profile.nationality, "IN")

    def test_nationalityCountry_alias_is_read(self):
        profile, _ = build_case_profile(
            _case({"employeeProfile": {"nationalityCountry": "IN"}})
        )
        self.assertEqual(profile.nationality, "IN")

    def test_primaryApplicant_wins_over_employeeProfile(self):
        """Precedence must match wizard_draft_mapper's, not be re-invented."""
        profile, _ = build_case_profile(
            _case({
                "primaryApplicant": {"nationality": "IN"},
                "employeeProfile": {"nationality": "ES"},
            })
        )
        self.assertEqual(profile.nationality, "IN")


class TheIrishFreeMovementFlip(unittest.TestCase):
    """The 14 real ES->IE cases, as an executable regression."""

    def test_indian_national_moving_ES_to_IE_is_not_an_EU_free_mover(self):
        profile, _ = build_case_profile(_case({"employeeProfile": {"nationality": "IN"}}))
        self.assertFalse(
            profile.is_eea,
            "an Indian national was classified as an EU/EEA free mover into Ireland "
            "because the origin country (ES) was substituted for their nationality",
        )

    def test_venezuelan_national_moving_ES_to_IE_is_not_an_EU_free_mover(self):
        profile, _ = build_case_profile(_case({"employeeProfile": {"nationality": "VE"}}))
        self.assertFalse(profile.is_eea)

    def test_a_spanish_national_on_the_same_corridor_still_IS_a_free_mover(self):
        """The gate must DISCRIMINATE. If this passed while the two above failed,
        the fix would just be 'always false' — which breaks the 13 genuine ES
        nationals on this very corridor."""
        profile, _ = build_case_profile(_case({"employeeProfile": {"nationality": "ES"}}))
        self.assertTrue(profile.is_eea)


class AnUnknownNationalityFailsSafe(unittest.TestCase):
    """Was `ScopeBoundary`, which pinned the origin fallback and recorded the
    decision as deliberately unmade. It is now made: unknown fails safe.

    MEASURED (prod, 2026-08-23) before deciding. 513 drafts record no nationality
    at any of the four paths. Only 419 carry BOTH an origin and a destination, and
    `build_case_profile` returns None without both — so 419 is the real reach, not
    513. Of those, 410 have an EEA origin and therefore flipped: France 384, FR 19,
    ES 3, and one each of NL / Norway / Spain / Germany. The remaining 9 already
    classified third-country and do not move. 403 of the 410 are French-origin,
    i.e. the seeded France corridor bulk rather than 403 distinct real movers.

    WHY THIS DIRECTION. The two errors are not symmetric. Wrongly granting free
    movement DROPS required steps — an Irish employment permit, a residence
    permission — and the mover discovers it when they cannot legally start work.
    Wrongly denying it ADDS steps that turn out to be unnecessary. Only one of
    those is recoverable by the person reading the roadmap.

    It also stops being an invention. `nationality_class.classify` already returns
    None on an unknown nationality and keeps the full requirement list rather than
    fabricating "nothing required"; `detect_regime` documents that an incomplete
    profile returns "unknown" rather than raising. Substituting the origin country
    was the one place that answered an unknown with a guess, and it is the same
    class of inference PR #2021 removed one layer up.
    """

    def test_absent_nationality_is_NOT_replaced_by_the_origin_country(self):
        profile, _ = build_case_profile(_case({}, origin="FR", dest="DE"))
        self.assertEqual(
            profile.nationality, "",
            "a case that records no nationality must report no nationality, not 'FR'",
        )

    def test_absent_nationality_is_not_free_movement(self):
        """The 410. A French-origin case with no nationality no longer reads as an
        EU free mover on the strength of its origin alone."""
        profile, _ = build_case_profile(_case({}, origin="FR", dest="DE"))
        self.assertFalse(profile.is_eea)

    def test_a_non_EEA_origin_with_no_nationality_is_unchanged(self):
        """The other 9 — already third-country, and they must stay put. Without
        this the suite could not tell 'fails safe' from 'flipped everything'."""
        profile, _ = build_case_profile(_case({}, origin="IN", dest="DE"))
        self.assertFalse(profile.is_eea)

    def test_a_RECORDED_nationality_still_decides_and_can_still_be_free_movement(self):
        """The discriminator for this change. If failing safe were implemented as
        `is_eea = False`, this would fail — and it would silently strip free
        movement from the 1,385 cases that correctly have it."""
        profile, _ = build_case_profile(
            _case({"employeeProfile": {"nationality": "FR"}}, origin="FR", dest="DE")
        )
        self.assertEqual(profile.nationality, "FR")
        self.assertTrue(profile.is_eea)

    def test_the_corridor_is_still_built_so_the_roadmap_still_generates(self):
        """Failing safe must not fail CLOSED. Dropping the fallback must not make
        `build_case_profile` return None and silently disable roadmap generation
        for all 419."""
        mapping = build_case_profile(_case({}, origin="FR", dest="DE"))
        self.assertIsNotNone(mapping)
        _, classification = mapping
        self.assertEqual(classification.corridor, "FR→DE")

    def test_junk_nationality_is_NOT_treated_as_the_origin_country(self):
        """`nationality` is unvalidated free text and prod holds ~19 junk values
        ("asdas", "123", "dfgd"). Before this change they were invisible: the
        chain matched nothing and the origin country was substituted, so a case
        reading "asdas" out of Norway was served as a Norwegian free mover.

        Now junk reads as an unknown nationality, and an unknown nationality is
        NOT free movement — which is the direction `nationality_class` already
        takes ("an unknown nationality keeps the full requirement list"). These
        ~19 cases therefore move from a free-movement roadmap to the fuller
        third-country one. That is a real behavioural change and it is the safe
        direction, but it is a change, so it is pinned here rather than left to
        be discovered.
        """
        profile, _ = build_case_profile(
            _case({"employeeProfile": {"nationality": "asdas"}}, origin="Norway",
                  dest="Singapore")
        )
        self.assertEqual(profile.nationality, "asdas")
        self.assertFalse(profile.is_eea)

    def test_whitespace_only_nationality_counts_as_absent(self):
        """A form or an LLM that "fills in" the field with a space must not read as
        a recorded nationality. `.strip()` is client-side for exactly this — the
        server-side `is_empty` would call "   " populated."""
        profile, _ = build_case_profile(
            _case({"employeeProfile": {"nationality": "   "}}, origin="FR", dest="DE")
        )
        self.assertEqual(profile.nationality, "")
        self.assertFalse(profile.is_eea)


if __name__ == "__main__":
    unittest.main()
