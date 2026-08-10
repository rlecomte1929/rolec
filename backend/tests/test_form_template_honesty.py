"""AIQ-1795b — the content-honesty guard, scored rather than asserted.

`scripts/check_form_template_honesty.py` encodes one invariant: a permit/visa template
must not be attachable by someone who needs no permit. This file measures it.

WHY SCORED. A checker that flagged every ungated template would catch all three known
defects and be worthless — it would condemn ANMELDUNG (§ 17 BMG applies to everyone) and
eight legitimate non-EEA templates, and would be switched off within a day. So precision
is measured explicitly against hand-labelled clean cases, not just recall against the
known bad ones.

WHY SELF-COVERAGE. The parser was silently wrong three times while being written, each
time dropping templates without a word — a `;` inside a `note`, `$$Dependant's Pass$$`
dollar-quoting whose apostrophe desynchronised the scanner, and a `--` comment sitting
between two values inside the INSERT. Each dropped template is a hole the guard cannot
see through, so coverage is asserted, not hoped for.
"""
from __future__ import annotations

import json
import os
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from scripts.check_form_template_honesty import (  # noqa: E402
    _EEA_VISA_TYPE,
    find_violations,
    is_permit_like,
    parse_templates,
    rule_is_eea_reachable,
    superseded_codes,
)

_CORPUS = os.path.join(os.path.dirname(__file__), "fixtures", "content_honesty",
                       "labelled_cases.json")


def _load_corpus():
    with open(_CORPUS, encoding="utf-8") as fh:
        return json.load(fh)["cases"]


class TestLabelledCorpus(unittest.TestCase):
    """Recall AND precision against cases labelled by hand, each with a legal reason."""

    def test_the_corpus_is_not_empty_or_one_sided(self):
        cases = _load_corpus()
        violations = [c for c in cases if c["label"] == "violation"]
        clean = [c for c in cases if c["label"] == "clean"]
        self.assertGreaterEqual(len(violations), 3, "need the known-real defects")
        self.assertGreaterEqual(len(clean), 4, "precision is the harder half; keep clean cases")
        for c in cases:
            self.assertTrue(c.get("reason"), f"{c['code']} needs a stated reason")

    def test_recall_every_known_violation_is_caught(self):
        missed = []
        for c in _load_corpus():
            if c["label"] != "violation":
                continue
            rows = [{"code": c["code"], "name": c["name"], "category": c["category"],
                     "rules": c["rules"], "file": "corpus"}]
            v, _ = find_violations(rows, {})
            if not v:
                missed.append(c["code"])
        self.assertEqual(missed, [], f"known-real defects the guard misses: {missed}")

    def test_precision_no_clean_case_is_flagged(self):
        false_positives = []
        for c in _load_corpus():
            if c["label"] != "clean":
                continue
            rows = [{"code": c["code"], "name": c["name"], "category": c["category"],
                     "rules": c["rules"], "file": "corpus"}]
            v, _ = find_violations(rows, {})
            if v:
                false_positives.append(f"{c['code']} ({c['reason']})")
        self.assertEqual(false_positives, [],
                         f"legitimate templates wrongly flagged: {false_positives}")


class TestTheShippedCorpusIsClean(unittest.TestCase):
    def test_no_violations_across_all_seed_migrations(self):
        rows = parse_templates()
        violations, _ = find_violations(rows, superseded_codes())
        self.assertEqual(
            [v["code"] for v in violations], [],
            "a permit/visa template attaches to EEA free-movement cases; run "
            "`python scripts/check_form_template_honesty.py` for the detail",
        )


class TestParserSelfCoverage(unittest.TestCase):
    """The parser must not silently drop a template. It did, three times."""

    def test_parses_a_plausible_number_of_templates(self):
        rows = parse_templates()
        self.assertGreater(len(rows), 60,
                           "parsed suspiciously few templates — a scan desync drops them "
                           "silently, which is a hole in the guard, not a pass")

    def test_every_code_literal_in_a_seed_is_actually_parsed(self):
        """Independent recount: scrape codes with a dumb regex over the INSERT regions and
        assert the real parser found each one. Catches a scanner desync, which is how
        RP-NO-DATASHEET and SG-DP-CHILD were invisible."""
        import re
        parsed = {r["code"] for r in parse_templates()}
        migrations = os.path.join(_REPO_ROOT, "supabase", "migrations")
        head_re = re.compile(r"INSERT\s+INTO\s+(?:public\.)?form_templates\s*\(",
                             re.IGNORECASE)
        # Scoped to form_templates INSERT spans. Without the scope this also picked up
        # the authority_code -> URL map in 20260612000000 (BZST, HMRC, UKVI, USCIS, ...),
        # which are not template codes. Deliberately does NOT reuse _statement_end or
        # _value_tuples — those are the functions that broke, so the recount stays
        # independent of them and ends the span at the next INSERT instead.
        scraped = set()
        for fname in sorted(os.listdir(migrations)):
            if not fname.endswith(".sql"):
                continue
            body = open(os.path.join(migrations, fname), encoding="utf-8").read()
            heads = [m.start() for m in head_re.finditer(body)]
            for n, start in enumerate(heads):
                end = heads[n + 1] if n + 1 < len(heads) else len(body)
                for m in re.finditer(r"\(\s*'([A-Z0-9][A-Z0-9\-\.]{2,})'\s*,",
                                     body[start:end]):
                    scraped.add(m.group(1))
        missing = sorted(scraped - parsed)
        self.assertEqual(missing, [],
                         f"codes present in a migration but not parsed: {missing}")
        self.assertGreater(len(scraped), 60, "the recount itself found nothing — check it")

    def test_known_awkward_templates_are_covered(self):
        """The three that exposed the parser bugs. Named so a regression is legible."""
        parsed = {r["code"] for r in parse_templates()}
        for code in ("RP-NO-DATASHEET",   # `;` in a note, and a `--` comment mid-statement
                     "SG-DP-CHILD",       # $$Dependant's Pass$$ dollar-quoting
                     "FAM-SPOUSE"):       # the defect this change fixes
            self.assertIn(code, parsed, f"{code} is not visible to the guard")


class TestInvariantEdges(unittest.TestCase):
    def test_omitted_visa_type_counts_as_eea_reachable(self):
        """The whole defect: an absent condition is never checked, so it matches."""
        self.assertTrue(rule_is_eea_reachable({"destination_country": "DE"}))

    def test_explicit_eea_registration_counts_too(self):
        self.assertTrue(rule_is_eea_reachable(
            {"destination_country": "DE", "visa_type": _EEA_VISA_TYPE}))

    def test_a_non_eea_visa_type_is_not_reachable(self):
        self.assertFalse(rule_is_eea_reachable(
            {"destination_country": "DE", "visa_type": "skilled_worker"}))

    def test_a_non_eea_destination_is_not_reachable(self):
        """visa_type is eea_registration only when BOTH countries are EEA."""
        for dest in ("US", "GB", "JP", "SG"):
            self.assertFalse(rule_is_eea_reachable({"destination_country": dest}), dest)

    def test_registration_steps_are_not_permit_like(self):
        self.assertFalse(is_permit_like("Address registration (Anmeldung beim Buergeramt)",
                                        "registration"))

    def test_a_data_sheet_is_not_permit_like(self):
        self.assertFalse(is_permit_like(
            "Personal Relocation Data Sheet (France to Norway)", "data_sheet"))

    def test_permits_are_permit_like_however_categorised(self):
        # RESID-PERMIT-DE is category 'registration'; FAM-SPOUSE is 'family'. Name matters.
        self.assertTrue(is_permit_like("Residence permit appointment (Auslaenderbehoerde)",
                                       "registration"))
        self.assertTrue(is_permit_like("Family reunion visa - spouse (Familiennachzug)",
                                       "family"))
        self.assertTrue(is_permit_like("Anything", "work_permit"))


class TestNoPrivateEeaCopy(unittest.TestCase):
    def test_the_checker_imports_eea_countries_rather_than_restating_them(self):
        """A second copy of _EEA_COUNTRIES is how these bugs start — the country-code
        defect (AIQ-1778) was 'FRANCE' not matching a pure-ISO-2 set."""
        src = open(os.path.join(_REPO_ROOT, "scripts",
                                "check_form_template_honesty.py"), encoding="utf-8").read()
        self.assertIn("from backend.app.services.trigger_engine import _EEA_COUNTRIES", src)
        self.assertNotIn('"AT", "BE"', src)
        self.assertNotIn("'AT', 'BE'", src)

    def test_the_eea_set_is_the_engines_and_is_populated(self):
        from backend.app.services.trigger_engine import _EEA_COUNTRIES
        self.assertIn("DE", _EEA_COUNTRIES)
        self.assertIn("FR", _EEA_COUNTRIES)
        self.assertNotIn("US", _EEA_COUNTRIES)
        self.assertGreater(len(_EEA_COUNTRIES), 25)


class TestPoisonDetection(unittest.TestCase):
    """Inject a synthetic defect and assert it is caught — the repo's existing
    non-vacuity pattern (test_triage_eval_guard.py:19-24)."""

    def test_a_planted_permit_template_is_caught(self):
        planted = [{
            "code": "PLANTED-PERMIT-NO", "name": "Residence permit collection",
            "category": "registration", "file": "synthetic",
            "rules": [{"event": "roadmap.arrival_confirmed",
                       "conditions": {"destination_country": "NO"}}],
        }]
        violations, _ = find_violations(planted, {})
        self.assertEqual([v["code"] for v in violations], ["PLANTED-PERMIT-NO"])

    def test_a_planted_clean_template_is_not_caught(self):
        planted = [{
            "code": "PLANTED-REGISTRATION", "name": "Address registration",
            "category": "registration", "file": "synthetic",
            "rules": [{"event": "roadmap.arrival_confirmed",
                       "conditions": {"destination_country": "NO"}}],
        }]
        violations, _ = find_violations(planted, {})
        self.assertEqual(violations, [])

    def test_a_superseded_violation_is_deferred_not_reported(self):
        """A forward migration may already have fixed a seeded rule — as
        20261023000000 did for RESID-PERMIT-DE. Reporting it again would be a false
        positive that never clears."""
        rows = [{
            "code": "OLD-PERMIT", "name": "Residence permit appointment",
            "category": "registration", "file": "seed.sql",
            "rules": [{"event": "roadmap.arrival_confirmed",
                       "conditions": {"destination_country": "DE"}}],
        }]
        violations, deferred = find_violations(rows, {"OLD-PERMIT": "later_fix.sql"})
        self.assertEqual(violations, [])
        self.assertEqual([d["code"] for d in deferred], ["OLD-PERMIT"])


if __name__ == "__main__":
    unittest.main()
