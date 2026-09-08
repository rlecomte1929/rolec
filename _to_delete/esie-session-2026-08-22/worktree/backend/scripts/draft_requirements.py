#!/usr/bin/env python3
"""AIQ-1349 — LLM-assisted requirement drafter (the country-coverage learning tool).

For a destination country + purpose, retrieve the immigration RAG corpus and ask a
citation-bound LLM (Anthropic tool-use, `emit_requirements`) to DRAFT candidate
requirement-catalog entries — each grounded in a corpus chunk, with inferred
assignment-type applicability and an expert-review flag. Writes a DRAFT seed YAML
(`verification_status: draft`) for human review; it NEVER writes the database.

Pipeline: corpus (grown by the immigration-indexer) → this drafter → human review
(edit YAML / review queue) → `seed_requirements.py` loader → prod.

Core logic (context build, citation validation, YAML) is decoupled from the LLM
transport via a `complete_fn(context) -> dict` callable, so it is fully unit-tested.
The CLI wires `complete_fn` to the real Anthropic client (mirrors roadmap_generator).

Usage:
    python backend/scripts/draft_requirements.py --country GERMANY --purpose employment --out drafts/de.yaml
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Callable, Dict, List, Optional

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_PROMPT_PATH = os.path.join(_REPO_ROOT, "prompts", "emit_requirements_v1.txt")
_VALID_PILLARS = {"IDENTITY", "EMPLOYMENT", "TIMELINE", "RESIDENCE", "HOUSING", "SOCIAL_SECURITY", "DEPENDENTS"}


def build_context(country: str, purpose: str, chunks: List[Dict[str, Any]]) -> str:
    """Render the SUBJECT + CONTEXT block (pure)."""
    lines = [f"SUBJECT: country={country}, purpose={purpose}", "", "CONTEXT (retrieved chunks):"]
    for c in chunks:
        url = c.get("source_url") or c.get("source_ref") or ""
        text = (c.get("chunk_text") or "").strip()
        lines.append(f"  [chunk:{c.get('id')}] (source_url: {url})\n    {text}")
    return "\n".join(lines)


def _valid(req: Dict[str, Any]) -> bool:
    """Citation-bound + shape gate: keep only requirements with a non-empty
    citation and the required fields. This is what makes drafts trustworthy."""
    if not isinstance(req, dict):
        return False
    if not (req.get("title") and req.get("description") and req.get("pillar")):
        return False
    cites = req.get("citations") or []
    return bool([c for c in cites if str(c).strip()])


def draft_requirements(
    country: str,
    purpose: str,
    chunks: List[Dict[str, Any]],
    complete_fn: Callable[[str], Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Draft candidate requirements. `complete_fn(context)` returns the parsed
    `emit_requirements` tool input ({"requirements": [...]}). Drops any
    requirement that isn't citation-grounded (rule 1)."""
    if not chunks:
        return []
    context = build_context(country, purpose, chunks)
    result = complete_fn(context) or {}
    raw = result.get("requirements") or []
    out: List[Dict[str, Any]] = []
    for r in raw:
        if not _valid(r):
            continue
        out.append({
            "title": r["title"],
            "pillar": r["pillar"] if r.get("pillar") in _VALID_PILLARS else "IDENTITY",
            "description": r["description"],
            "severity": r.get("severity") or "WARN",
            "owner": r.get("owner") or "EMPLOYEE",
            "applies_to_assignment_types": r.get("applies_to_assignment_types") or None,
            "citations": [c for c in (r.get("citations") or []) if str(c).strip()],
            "confidence": r.get("confidence") or "low",
            "requires_expert_review": bool(r.get("requires_expert_review", True)),
        })
    return out


def to_seed_yaml(country: str, purpose: str, requirements: List[Dict[str, Any]]) -> str:
    """Serialize drafts to the seed_requirements.py YAML shape, marked draft."""
    import yaml
    doc = {
        "verification_status": "draft",
        "purposes_by_country": {country.upper(): [purpose]},
        "requirements": [
            {
                "key": r["title"].lower().replace(" ", "_")[:50],
                "pillar": r["pillar"],
                "severity": r["severity"],
                "owner": r["owner"],
                "applies_to_assignment_types": r["applies_to_assignment_types"],
                "requires_expert_review": r["requires_expert_review"],
                "confidence": r["confidence"],
                "citations": r["citations"],
                "countries": {country.upper(): {"title": r["title"], "description": r["description"]}},
            }
            for r in requirements
        ],
    }
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


_FENCE_RE = re.compile(r"```json\s*(\{.*\})\s*```", re.DOTALL)


def _load_tool_schema() -> Dict[str, Any]:
    """Parse the emit_requirements tool definition from the prompt's fenced block."""
    with open(_PROMPT_PATH, "r", encoding="utf-8") as fh:
        text = fh.read()
    for block in _FENCE_RE.findall(text):
        if '"emit_requirements"' in block and '"input_schema"' in block:
            return json.loads(block)
    raise RuntimeError("draft_requirements: emit_requirements tool schema not found in prompt")


def _real_complete_fn(model: Optional[str]) -> Callable[[str], Dict[str, Any]]:
    """Wire the real Anthropic tool-use call (mirrors roadmap_generator.generate).
    `complete()` returns a dict whose `tool_use` key holds the parsed tool input."""
    from backend.app.services import policy_assistant_llm_client as llm

    with open(_PROMPT_PATH, "r", encoding="utf-8") as fh:
        system = fh.read()
    tool_schema = _load_tool_schema()

    def _complete(context: str) -> Dict[str, Any]:
        client = llm.get_default_client()
        req = llm.LlmRequest(
            system=system,
            user_message=context,
            model=model or llm.DEFAULT_MODEL,
            temperature=0.0,
            max_tokens=4096,
            tools=[tool_schema],
            tool_choice={"type": "tool", "name": "emit_requirements"},
        )
        resp = client.complete(req)
        tu = resp.get("tool_use")
        if isinstance(tu, dict):
            return tu
        # Fallback: parse the first JSON object out of the text seam.
        m = re.search(r"\{.*\}", resp.get("text") or "", re.DOTALL)
        return json.loads(m.group(0)) if m else {}

    return _complete


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Draft requirement candidates from the immigration corpus.")
    parser.add_argument("--country", required=True)
    parser.add_argument("--purpose", default="employment")
    parser.add_argument("--out", required=True, help="Path to write the DRAFT YAML.")
    parser.add_argument("--model", default=None)
    parser.add_argument("--top-k", type=int, default=12)
    args = parser.parse_args(argv)

    try:
        from backend.app.services.immigration_retriever import retrieve_for_profile, UserProfile, PathClassification
        from backend.app.services.country_resources import _country_code_from_name
        iso = _country_code_from_name(args.country) or args.country[:2].upper()
        profile = UserProfile(nationality="", origin_country="", destination_country=iso, is_eea=None)
        classification = PathClassification(pathway_type="unknown", corridor=None)
        chunks = retrieve_for_profile(profile=profile, classification=classification, top_k=args.top_k)
        drafts = draft_requirements(args.country, args.purpose, chunks, _real_complete_fn(args.model))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR drafting: {exc}", file=sys.stderr)
        return 1

    if not drafts:
        print("No citation-grounded requirements drafted (empty/sparse corpus for this country?).")
        return 0
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(to_seed_yaml(args.country, args.purpose, drafts))
    print(f"Wrote {len(drafts)} DRAFT requirement(s) → {args.out} (verification_status: draft). Review before loading.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
