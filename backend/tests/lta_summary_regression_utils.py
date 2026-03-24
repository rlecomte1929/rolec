"""Loaders and assertions for LTA policy summary regression fixtures."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Sequence, Tuple

_FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "lta_policy_summary_regression.json")


def load_lta_policy_summary_regression_fixture() -> Dict[str, Any]:
    with open(_FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


def fixture_policy_context_and_items(
    fixture: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    return dict(fixture["policy_context"]), list(fixture["items"])


def grouped_by_canonical_key(grouped: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for g in grouped:
        if not isinstance(g, dict):
            continue
        ck = g.get("canonical_key")
        if isinstance(ck, str) and ck:
            out[ck] = g
    return out


def assert_section_refs_not_leaked_as_numeric_values(
    clauses: Sequence[Dict[str, Any]],
    draft_rule_candidates: Sequence[Dict[str, Any]],
    section_refs: Sequence[str],
) -> None:
    """Section numbers like 2.1 must not appear as monetary/numeric hints (regression guard)."""
    ref_floats = set()
    for ref in section_refs:
        try:
            ref_floats.add(float(ref.strip()))
        except ValueError:
            continue

    for cl in clauses:
        if not isinstance(cl, dict):
            continue
        hints = cl.get("normalized_hint_json")
        if not isinstance(hints, dict):
            continue
        nums = hints.get("candidate_numeric_values")
        if not isinstance(nums, list):
            continue
        for n in nums:
            try:
                fn = float(n)
            except (TypeError, ValueError):
                continue
            if fn in ref_floats:
                raise AssertionError(
                    f"Section ref leaked into candidate_numeric_values: {fn!r} in clause hints"
                )

    for d in draft_rule_candidates:
        if not isinstance(d, dict):
            continue
        af = d.get("amount_fragments")
        if not isinstance(af, dict):
            continue
        av = af.get("amount_value")
        if av is None:
            continue
        try:
            fv = float(av)
        except (TypeError, ValueError):
            continue
        if fv in ref_floats:
            raise AssertionError(
                f"Section ref leaked into amount_fragments.amount_value: {fv!r}"
            )


def assert_section_refs_not_in_policy_text_bodies(
    clauses: Sequence[Dict[str, Any]],
    section_refs: Sequence[str],
) -> None:
    """Refs belong in provenance, not in the normalized row text used for mapping."""
    for cl in clauses:
        if not isinstance(cl, dict):
            continue
        raw = (cl.get("raw_text") or "").strip()
        for ref in section_refs:
            if ref in raw:
                raise AssertionError(
                    f"Section ref {ref!r} should not appear in clause raw_text body: {raw[:120]!r}..."
                )


def collect_amount_texts_from_grouped_values(gv: Any, out: List[str]) -> None:
    if not isinstance(gv, dict):
        return
    for t in gv.get("amount_tiers") or []:
        if isinstance(t, dict):
            at = t.get("amount_text")
            if isinstance(at, str):
                out.append(at)
    for k, v in gv.items():
        if isinstance(v, (dict, list)):
            collect_amount_texts_from_grouped_values(v, out)


def assert_section_refs_not_in_amount_tier_text(
    grouped: Sequence[Dict[str, Any]],
    section_refs: Sequence[str],
) -> None:
    texts: List[str] = []
    for g in grouped:
        if not isinstance(g, dict):
            continue
        collect_amount_texts_from_grouped_values(g.get("grouped_values"), texts)
    for t in texts:
        for ref in section_refs:
            if ref in t:
                raise AssertionError(f"Section ref {ref!r} appears in amount tier text: {t!r}")
