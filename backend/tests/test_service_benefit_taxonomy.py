"""[F14] Guard: the Services-catalog vocabulary and the HR Policy Builder
vocabulary MUST intersect through the ONE shared taxonomy.

Historically the two sides spoke disjoint vocabularies bridged by three
inconsistent ad-hoc alias maps, so the caps/compare bridge always answered
``no_cap_for_benefit_in_context`` and over-cap — the trigger of the Policy
Exception → HR notification path — could never fire. These tests fail the build
if the mismatch is ever re-introduced:

  1. every benefit_key the shared taxonomy maps to must exist in the policy
     matrix's canonical vocabulary (_CANONICAL_KEYS);
  2. every Services-catalog category (serviceConfig.ts) must be declared in the
     shared taxonomy (mapped, or explicitly uncapped);
  3. a service-keyed estimate over the mapped cap must actually produce an
     over-cap result through evaluate_estimates_against_caps.
"""
from __future__ import annotations

import os
import re
import sys
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.app.services import service_benefit_taxonomy as tax
from backend.app.services.policy_config_cap_compare import (
    NORMALIZED_CURRENCY_AMOUNT,
    evaluate_estimates_against_caps,
)
from backend.app.services.policy_config_matrix_service import (
    SERVICE_MODULE_BENEFIT_KEYS,
    _CANONICAL_KEYS,
)

_CANONICAL = {bk for bk, _lbl, _cat in _CANONICAL_KEYS}

_SERVICE_CONFIG_TS = os.path.join(
    _REPO_ROOT, "frontend", "src", "features", "services", "serviceConfig.ts"
)


def _catalog_service_keys() -> set:
    """Service keys of the Employee Services catalog, read from the catalog's own
    source of truth (SERVICE_CONFIG in serviceConfig.ts). A regex tripwire on
    purpose: if the catalog gains a service the taxonomy doesn't know, this file
    changes and the coverage test below goes red."""
    with open(_SERVICE_CONFIG_TS, "r", encoding="utf-8") as fh:
        src = fh.read()
    keys = set(re.findall(r"\{\s*key:\s*'([a-z_]+)'", src))
    if not keys:
        raise AssertionError(
            "could not parse any SERVICE_CONFIG keys out of serviceConfig.ts — "
            "update the regex in this test if the catalog file format changed"
        )
    return keys


class TaxonomyVocabularyIntersectionTests(unittest.TestCase):
    def test_every_mapped_benefit_key_is_canonical_in_the_policy_matrix(self) -> None:
        """The core F14 guard: the taxonomy may only speak the matrix vocabulary."""
        unknown = set(tax.all_mapped_benefit_keys()) - _CANONICAL
        self.assertFalse(
            unknown,
            f"shared/service_benefit_taxonomy.json maps to benefit_keys that do not "
            f"exist in policy_config_matrix_service._CANONICAL_KEYS: {sorted(unknown)}. "
            f"Fix the taxonomy (or extend _CANONICAL_KEYS if the benefit is real).",
        )

    def test_every_catalog_service_is_declared_in_the_taxonomy(self) -> None:
        """No Services-catalog category may silently fall outside the taxonomy."""
        declared = set(tax.declared_service_keys()) | set(tax.service_aliases())
        missing = _catalog_service_keys() - declared
        self.assertFalse(
            missing,
            f"Services-catalog categories missing from shared/service_benefit_taxonomy.json: "
            f"{sorted(missing)}. Declare each one — map it to canonical benefit_keys, or "
            f"declare it explicitly uncapped with [].",
        )

    def test_the_vocabulary_intersection_is_not_empty(self) -> None:
        """At least the core purchasable services must map to a real cap, otherwise
        over-cap (and the Policy Exception path) is unreachable again."""
        for service in ("housing", "movers", "schools", "banks", "visa"):
            self.assertTrue(
                tax.benefit_keys_for_service(service),
                f"catalog service {service!r} no longer maps to any policy benefit_key",
            )

    def test_aliases_resolve_to_declared_services(self) -> None:
        declared = set(tax.declared_service_keys())
        for alias, target in tax.service_aliases().items():
            self.assertIn(
                target,
                declared,
                f"alias {alias!r} points at {target!r}, which is not a declared service",
            )
            self.assertNotIn(alias, declared, f"{alias!r} is both an alias and a service")

    def test_module_map_is_served_from_the_shared_taxonomy(self) -> None:
        self.assertEqual(SERVICE_MODULE_BENEFIT_KEYS, tax.module_benefit_keys())
        for module, keys in SERVICE_MODULE_BENEFIT_KEYS.items():
            unknown = set(keys) - _CANONICAL
            self.assertFalse(unknown, f"module {module!r} maps to unknown keys {sorted(unknown)}")

    def test_alias_and_normalization_resolution(self) -> None:
        self.assertEqual(tax.normalize_service_key("living_areas"), "housing")
        self.assertEqual(tax.normalize_service_key("MOVING"), "movers")
        self.assertEqual(tax.normalize_service_key("temp-accommodation"), "temp_accommodation")
        self.assertEqual(
            tax.benefit_keys_for_service("moving"),
            ["shipment_of_goods", "removal_expenses", "storage"],
        )
        self.assertEqual(tax.benefit_keys_for_service("pets"), [])
        self.assertEqual(tax.benefit_keys_for_service("totally_unknown"), [])


def _cap(benefit_key: str, amount: float, currency: str = "EUR") -> dict:
    return {
        "benefit_key": benefit_key,
        "normalized_cap_type": NORMALIZED_CURRENCY_AMOUNT,
        "normalized_amount": amount,
        "currency_code": currency,
    }


class ServiceKeyedCapCompareTests(unittest.TestCase):
    """The bridge itself: a Services-catalog-keyed estimate must land on a real
    cap so over-cap can fire (this used to be unreachable — F14)."""

    def test_over_cap_fires_for_a_service_keyed_estimate(self) -> None:
        caps = [
            _cap("shipment_of_goods", 500.0),
            _cap("removal_expenses", 300.0),
            _cap("storage", 200.0),
        ]
        out = evaluate_estimates_against_caps(
            [{"benefit_key": "movers", "amount": 1500.0, "currency": "EUR"}],
            caps,
            service_key_resolver=tax.benefit_keys_for_service,
        )
        row = out[0]
        self.assertTrue(row["matched_cap"])
        self.assertTrue(row["supported_comparison"])
        self.assertFalse(row["within_cap"])
        self.assertEqual(row["cap_amount"], 1000.0)
        self.assertEqual(row["difference_direction"], "over")
        self.assertEqual(
            sorted(row["matched_benefit_keys"]),
            ["removal_expenses", "shipment_of_goods", "storage"],
        )

    def test_within_cap_for_a_service_keyed_estimate(self) -> None:
        out = evaluate_estimates_against_caps(
            [{"benefit_key": "banks", "amount": 400.0, "currency": "EUR"}],
            [_cap("banking_assistance", 800.0)],
            service_key_resolver=tax.benefit_keys_for_service,
        )
        self.assertTrue(out[0]["matched_cap"])
        self.assertTrue(out[0]["within_cap"])

    def test_alias_keyed_estimate_resolves_too(self) -> None:
        # Legacy intake vocabulary ('moving') and backendKeys ('living_areas').
        out = evaluate_estimates_against_caps(
            [
                {"benefit_key": "moving", "amount": 1200.0, "currency": "EUR"},
                {"benefit_key": "living_areas", "amount": 2500.0, "currency": "EUR"},
            ],
            [_cap("shipment_of_goods", 1000.0), _cap("host_housing_cap", 2000.0)],
            service_key_resolver=tax.benefit_keys_for_service,
        )
        self.assertTrue(all(r["matched_cap"] for r in out))
        self.assertFalse(out[0]["within_cap"])
        self.assertFalse(out[1]["within_cap"])

    def test_direct_canonical_benefit_key_still_wins(self) -> None:
        # Back-compat: an estimate already speaking the matrix vocabulary matches
        # its own cap directly, without taxonomy aggregation.
        out = evaluate_estimates_against_caps(
            [{"benefit_key": "host_housing_cap", "amount": 1800.0, "currency": "EUR"}],
            [_cap("host_housing_cap", 2000.0)],
            service_key_resolver=tax.benefit_keys_for_service,
        )
        self.assertTrue(out[0]["matched_cap"])
        self.assertTrue(out[0]["within_cap"])
        self.assertNotIn("matched_benefit_keys", out[0])

    def test_uncapped_service_stays_an_honest_no_cap(self) -> None:
        out = evaluate_estimates_against_caps(
            [{"benefit_key": "pets", "amount": 50.0, "currency": "EUR"}],
            [_cap("host_housing_cap", 2000.0)],
            service_key_resolver=tax.benefit_keys_for_service,
        )
        self.assertFalse(out[0]["matched_cap"])
        self.assertEqual(out[0]["reason_unsupported"], "no_cap_for_benefit_in_context")

    def test_mixed_currency_caps_refuse_rather_than_invent_fx(self) -> None:
        out = evaluate_estimates_against_caps(
            [{"benefit_key": "movers", "amount": 900.0, "currency": "EUR"}],
            [_cap("shipment_of_goods", 500.0, "EUR"), _cap("storage", 200.0, "USD")],
            service_key_resolver=tax.benefit_keys_for_service,
        )
        self.assertTrue(out[0]["matched_cap"])
        self.assertFalse(out[0]["supported_comparison"])
        self.assertEqual(out[0]["reason_unsupported"], "mixed_currency_caps_for_service")

    def test_without_a_resolver_behavior_is_unchanged(self) -> None:
        out = evaluate_estimates_against_caps(
            [{"benefit_key": "movers", "amount": 900.0, "currency": "EUR"}],
            [_cap("shipment_of_goods", 500.0)],
        )
        self.assertFalse(out[0]["matched_cap"])
        self.assertEqual(out[0]["reason_unsupported"], "no_cap_for_benefit_in_context")


if __name__ == "__main__":
    unittest.main()
