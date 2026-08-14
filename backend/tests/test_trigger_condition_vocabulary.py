"""
Guard: every trigger-rule condition key must exist in the matching context.

WHY THIS EXISTS — a real, shipped failure (2026-08-04)

`_matches_conditions` fails CLOSED on an unknown key:

    actual = context.get(key)
    if actual is None:
        return False

So a condition naming a key that `_build_context` does not produce does not raise,
does not warn, and does not appear in any log — the rule simply never matches, for
any case, ever, and the template is silently unattachable.

That is exactly what happened to `RP-NO-DATASHEET`: its rule required
`movement_basis: "eea_free_movement"`, which is not a context key. The template was
seeded, correct in every other respect, and could never reach a case. The bug was
invisible to the seed's own tests, to CI, and to a direct DB inspection of the row.

The correct key was `visa_type`, which `_build_context` sets to `eea_registration`
exactly when origin and destination are both EEA — the same vocabulary the
already-firing `POL-EEA-REG` rule uses.

This test scans EVERY seeded template in `supabase/migrations/` and asserts its
condition keys are ones the engine can actually resolve. It is deliberately static
(no DB) so it runs everywhere and covers templates that no environment has applied
yet — the previous failure mode.
"""
from __future__ import annotations

import json
import os
import re
import sys
import unittest
from typing import Dict, List, Set, Tuple

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_MIGRATIONS = os.path.join(_REPO_ROOT, "supabase", "migrations")

# The keys `trigger_engine._build_context` returns. Mirrors the dict it builds —
# if you add a key there, add it here and the new key becomes usable in rules.
# Kept as a literal on purpose: _build_context needs a live DB, and this guard
# must run with no database at all.
CONTEXT_KEYS: Set[str] = {
    "case_uuid",
    "employee_id",
    "destination_country",
    "origin_country",
    "visa_type",
    "has_spouse",
    "has_children",
}


def _iter_trigger_rule_blobs() -> List[Tuple[str, str]]:
    """(filename, json_text) for every JSON array in a migration that looks like
    a trigger_rules payload. Matched on the `event` key rather than on SQL
    position, so it survives reformatting."""
    out: List[Tuple[str, str]] = []
    if not os.path.isdir(_MIGRATIONS):
        return out
    for fname in sorted(os.listdir(_MIGRATIONS)):
        if not fname.endswith(".sql"):
            continue
        with open(os.path.join(_MIGRATIONS, fname), encoding="utf-8") as fh:
            body = fh.read()
        if '"event"' not in body or "conditions" not in body:
            continue
        # Any bracketed block containing an "event" + "conditions" pair.
        for match in re.finditer(r"\[\s*\{.*?\}\s*\]", body, re.DOTALL):
            blob = match.group(0)
            if '"event"' in blob and '"conditions"' in blob:
                out.append((fname, blob))
    return out


def _parsed_rules() -> List[Tuple[str, Dict]]:
    """(filename, rule) for every parseable trigger rule found in migrations."""
    rules: List[Tuple[str, Dict]] = []
    for fname, blob in _iter_trigger_rule_blobs():
        try:
            parsed = json.loads(blob)
        except (json.JSONDecodeError, TypeError):
            # Not a trigger_rules payload (or contains SQL interpolation) — the
            # dedicated malformed-JSON test below reports genuinely broken ones.
            continue
        if isinstance(parsed, list):
            for rule in parsed:
                if isinstance(rule, dict) and "conditions" in rule:
                    rules.append((fname, rule))
    return rules


class TriggerConditionVocabularyTests(unittest.TestCase):
    def test_migrations_contain_trigger_rules_to_check(self) -> None:
        # Guards the guard: a regex that silently matches nothing would make every
        # assertion below vacuously true.
        self.assertGreater(
            len(_parsed_rules()), 0,
            "found no trigger rules in supabase/migrations — the scanner is broken, "
            "not the migrations",
        )

    def test_every_condition_key_exists_in_the_matching_context(self) -> None:
        offenders: List[str] = []
        for fname, rule in _parsed_rules():
            for key in (rule.get("conditions") or {}):
                if key not in CONTEXT_KEYS:
                    offenders.append(f"{fname}: condition key {key!r}")

        self.assertEqual(
            offenders, [],
            "These trigger rules name a key that _build_context does not produce. "
            "_matches_conditions fails closed on an unknown key, so each of these "
            "templates is SILENTLY UNATTACHABLE — it will never reach a case and "
            "nothing will report an error.\n  "
            + "\n  ".join(offenders)
            + f"\n\nValid keys: {sorted(CONTEXT_KEYS)}",
        )

    def test_frno_datasheet_uses_the_resolvable_eea_key(self) -> None:
        # The specific regression: RP-NO-DATASHEET shipped with
        # `movement_basis: eea_free_movement`, which never matches.
        seed = os.path.join(_MIGRATIONS, "20261015000000_seed_frno_data_sheet.sql")
        if not os.path.isfile(seed):
            self.skipTest("FR->NO data-sheet seed not present in this checkout")
        with open(seed, encoding="utf-8") as fh:
            body = fh.read()

        self.assertNotIn(
            '"movement_basis"', body,
            "movement_basis is not a trigger-context key — the data-sheet would be "
            "unattachable. Use visa_type: eea_registration.",
        )
        self.assertIn(
            '"visa_type":"eea_registration"', body.replace(" ", ""),
            "the FR->NO data-sheet must key off visa_type=eea_registration, the same "
            "vocabulary POL-EEA-REG uses",
        )

    def test_context_keys_match_build_context_source(self) -> None:
        # Keeps CONTEXT_KEYS honest: if _build_context's returned dict gains or
        # loses a key, this fails and forces the literal above to be updated,
        # rather than letting the guard drift into approving an invalid key.
        src_path = os.path.join(
            _REPO_ROOT, "backend", "app", "services", "trigger_engine.py"
        )
        with open(src_path, encoding="utf-8") as fh:
            src = fh.read()

        # The single `return { ... }` block at the end of _build_context.
        start = src.index("def _build_context")
        segment = src[start : src.index("\ndef ", start + 10)]
        ret = segment[segment.rindex("return {") : ]
        found = set(re.findall(r'"([a-z_]+)":', ret))

        self.assertEqual(
            found, CONTEXT_KEYS,
            "trigger_engine._build_context's returned keys have changed. Update "
            "CONTEXT_KEYS in this file to match, then re-check every seeded "
            f"trigger rule.\n  in source: {sorted(found)}\n  in guard:  {sorted(CONTEXT_KEYS)}",
        )


if __name__ == "__main__":
    unittest.main()
