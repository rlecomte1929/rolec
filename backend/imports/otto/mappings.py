"""Turn a group of Otto facts into one `requirement_items` payload — or refuse.

Otto's facts and the requirement catalog are at different grains. Otto emits one row per
*fact* (`cardFee`, `cardDuration`, `cardOptional` are three rows about one residence card);
`requirement_items` is one row per *requirement* — a thing you must do, carrying a
description, a severity, an owner and citations. So the unit of promotion is the
`entity_topic_key`, never a single fact.

**Why there is no per-topic mapping table.** The obvious design — a dict from
`entity_topic_key` to pillar/purpose/severity — cannot work, because topic keys are invented
per country and unbounded: production already holds `eu_free_movement_worker`, `189-visa-fee`,
`crs-score-draw-process`, `csep_salary_threshold`. Every new country would block on a code
change, and an unmapped key would silently stall. Instead every target column is derived from
a field whose vocabulary IS bounded (`applies_to.nationality`, `applies_to.status`,
`domain_area`), and an unrecognised value in one of *those* is a refusal.

**Refusing is the feature.** `resolve()` returns `Unmapped` far more readily than it returns a
draft, because the failure mode this guards against is not a missing requirement — it is a
wrong one, served confidently. A held-back entity appears on the CLI worklist and becomes the
next research card.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Union

from backend.app.services.nationality_class import EU_EEA, OWN_NATIONAL, THIRD_COUNTRY
from backend.app.services.requirements_country_key import iso_to_catalog_name

from backend.imports.otto.parsers import TIER_AUTO

#: `applies_to.nationality` -> `requirement_items.applies_to_nationality_classes_json`.
#:
#: Note what is NOT here: `"any"`. NULL in that column means *applies to everyone*, and
#: `nationality_class.py` exists precisely because serving the non-EEA visa track to a free
#: mover is the bug this codebase keeps re-committing. Otto writes `"any"` on entities like
#: `schengen_court_sejour` — a short-stay visa an EU citizen does not need at all — so `"any"`
#: is not a categorisation, it is an absence of one. Categorise or refuse; never default to
#: "applies to all".
NATIONALITY_CLASSES: Dict[str, List[str]] = {
    "EU": [OWN_NATIONAL, EU_EEA],
    "EEA": [OWN_NATIONAL, EU_EEA],
    "non-EEA": [THIRD_COUNTRY],
    "non-EU": [THIRD_COUNTRY],
}

#: `applies_to.status` -> `requirement_items.purpose`. The target enum is exactly
#: employment | study | family | other (confirmed against production).
PURPOSES: Dict[str, str] = {
    "professional": "employment",
    "student": "study",
    "family": "family",
    "any": "other",
}

#: Every `otto_staging` entity carries `domain_area='immigration'`, and a residence/entry
#: permit is a RESIDENCE requirement. This is read off the schema, not guessed — which is why
#: a row with any other `domain_area` is refused rather than filed under a default pillar.
IMMIGRATION_PILLAR = "RESIDENCE"

#: Otto's schema carries no notion of blocking-ness, and it cannot be inferred from the text:
#: the France set includes `cardOptional` ("EU citizens have the right, the card is optional"),
#: which is the opposite of a blocker. `WARN` is the catalog's neutral level (85 of 116 rows in
#: production) and the only honest default for content no human has graded. Raising something
#: to BLOCKER is a human act.
DEFAULT_SEVERITY = "WARN"

#: These are documents and registrations the relocating person obtains in person. The
#: employer-side counterpart (sponsorship, work authorisation) is a different requirement that
#: Otto does not currently produce.
DEFAULT_OWNER = "EMPLOYEE"


@dataclass
class Unmapped:
    """An entity that will not be promoted, and the reason, ready for the worklist."""

    topic_key: str
    reason: str


@dataclass
class RequirementDraft:
    """A resolved `requirement_items` payload plus the provenance it is entitled to."""

    topic_key: str
    country_code: str
    purpose: str
    title: str
    payload: Dict[str, Any]
    verification_status: str
    fact_ids: List[str] = field(default_factory=list)
    derivations: List[str] = field(default_factory=list)


def _distinct(values: Sequence[Optional[str]]) -> List[str]:
    seen: List[str] = []
    for v in values:
        v = (v or "").strip()
        if v and v not in seen:
            seen.append(v)
    return seen


def _one_value(facts: Sequence[Any], key: str) -> Optional[str]:
    """The single value of `applies_to[key]` across the group, or None if they disagree.

    Disagreement is a refusal rather than a majority vote: an entity whose facts claim
    different audiences is not one requirement, and picking the commonest would bury that.
    """
    values = _distinct([(f.applies_to or {}).get(key) for f in facts])
    return values[0] if len(values) == 1 else None


#: Marker introducing the non-obvious explanation inside `description`. Matches the wording
#: `gen_ie_es_corridor_load.py` already writes, so both loaders produce one shape.
#:
#: It lives in the description because `requirement_items` has **no note column** — the reader
#: would otherwise get `RequirementList.tsx`'s wordless "Easy to miss" pill and no way to act
#: on it. Keeping it behind a fixed marker is what makes it mechanically strippable when the
#: real column lands: `description.split(NON_OBVIOUS_MARKER)[0].rstrip()`.
NON_OBVIOUS_MARKER = "\n\nWhy this is easy to miss: "


def compose_description(facts: Sequence[Any]) -> str:
    """One requirement's description, built from its facts in a stable order.

    Ordered by `fact_type` rather than by insertion so re-running produces byte-identical text
    and the upsert is a genuine no-op instead of a silent rewrite.

    Any `applies_to.non_obvious_note` on a contributing fact is appended after the facts,
    behind `NON_OBVIOUS_MARKER`. Notes are deduplicated (twinned EEA/non-EEA facts carry the
    same note) and follow the same stable order, so the text stays byte-identical on re-run.

    The note is editorial commentary over cited facts, not a sourced claim — which is exactly
    why it is labelled and kept out of `fact_text`. `fact_text` must stay answerable to its
    `evidence_quote`; this paragraph is answerable to the reviewer who approved it.
    """
    order = {"eligibility": 0, "step": 1, "document": 2, "deadline": 3, "fee": 4,
             "where_to_apply": 5, "other": 6}
    ordered = sorted(facts, key=lambda f: (order.get(f.fact_type, 99), f.fact_key or ""))
    body = "\n".join(f.fact_text.strip() for f in ordered if (f.fact_text or "").strip())

    notes = _distinct([(f.applies_to or {}).get("non_obvious_note") for f in ordered])
    if notes:
        body += NON_OBVIOUS_MARKER + "\n\n".join(notes)
    return body


def _citations_for(facts: Sequence[Any], topic: str) -> List[Dict[str, Any]]:
    """One citation object per distinct source URL.

    This used to be `_distinct([f.source_url for f in facts])` — a flat list of bare URL
    strings. Two things were wrong with that. The reader resolves citations against
    `source_records` and a bare URL matches nothing there, so a promoted requirement served
    with an EMPTY citation list while the provenance guard still passed (it only asserts
    `citations_json IS NOT NULL`). And `needs_lawyer_review` had nowhere to go, so the four
    counsel-flagged VE→IE claims arrived in `requirement_items` indistinguishable from the
    checked ones — at exactly the point a reviewer decides whether to approve.

    The object shape follows `scripts/gen_ie_es_corridor_load.py`, which already reached this
    conclusion for the IE→ES batch. `requirements_builder._citation_dtos` understands all
    three formats prod holds; see its docstring.

    A URL cited by several facts yields ONE citation, flagged if ANY of those facts is
    flagged — dropping the flag because a second, unflagged fact shares the source would
    lose it silently.
    """
    ordered: List[Dict[str, Any]] = []
    by_url: Dict[str, Dict[str, Any]] = {}
    for fact in facts:
        url = (fact.source_url or "").strip()
        if not url:
            continue
        meta = fact.applies_to or {}
        citation = by_url.get(url)
        if citation is None:
            citation = {"url": url, "topic_key": topic}
            name = str(meta.get("source_name") or "").strip()
            if name:
                citation["name"] = name
            corridor = str(meta.get("corridor") or "").strip()
            if corridor:
                citation["corridor"] = corridor
            by_url[url] = citation
            ordered.append(citation)
        if meta.get("needs_lawyer_review"):
            citation["needs_lawyer_review"] = True
    return ordered


def resolve(entity: Any, facts: Sequence[Any]) -> Union[RequirementDraft, Unmapped]:
    """Build one requirement payload from an entity and its facts, or explain the refusal.

    `entity` needs `.destination_country`, `.topic_key`, `.title`, `.domain_area`.
    `facts` need `.fact_text`, `.fact_type`, `.fact_key`, `.applies_to`, `.source_url`,
    `.evidence_quote`, `.accuracy_tier`, `.id`.
    """
    topic = entity.topic_key

    if not facts:
        return Unmapped(topic, "entity has no facts yet — Otto enumerated the topic but never "
                               "delivered its content")

    if (entity.domain_area or "") != "immigration":
        return Unmapped(topic, f"domain_area {entity.domain_area!r} is not 'immigration', so "
                               f"the {IMMIGRATION_PILLAR} pillar cannot be read off the schema")

    country_code = iso_to_catalog_name(entity.destination_country)
    if not country_code:
        # Deliberately the narrow map: it answers "do we hold requirement catalog data for
        # this country?" Promoting into a country the catalog does not cover would create
        # rows no destination resolves to.
        return Unmapped(topic, f"no requirement catalog coverage for "
                               f"{entity.destination_country!r} — see requirements_country_key")

    # Absent and conflicting are different problems with different fixes, and both used to
    # report "facts disagree" — which sends the reader hunting for a disagreement that is not
    # there. The B3 batch staged 20 facts with no nationality at all and every one of them
    # blamed a conflict.
    nationality_values = _distinct([(f.applies_to or {}).get("nationality") for f in facts])
    if not nationality_values:
        return Unmapped(topic, "no fact carries applies_to.nationality — the audience is "
                               "unscoped, and NULL here would serve a visa track to free "
                               "movers. Derive it from the corridor before staging")
    if len(nationality_values) > 1:
        return Unmapped(topic, f"facts disagree on applies_to.nationality "
                               f"({', '.join(sorted(nationality_values))}), so this is not one "
                               "requirement")
    nationality = nationality_values[0]
    classes = NATIONALITY_CLASSES.get(nationality)
    if classes is None:
        return Unmapped(
            topic,
            f"applies_to.nationality={nationality!r} is not a categorisation — NULL here means "
            "'applies to everyone', which serves a visa track to free movers",
        )

    # `applies_to.status` refuses on the same three conditions its sibling `nationality`
    # does — absent, conflicting, unrecognised — instead of silently defaulting to
    # `purpose='other'`.
    #
    # The silent default is worse than it looks. `crud.list_requirements` matches purpose
    # with strict `==` and no catch-all, and `public_corridor` defaults to
    # `purpose='employment'`, so a row promoted at 'other' by accident is counted as loaded
    # by every reconciliation, is approvable in the review queue, and can never be returned
    # to a reader. It is invisible in exactly the way that looks like success.
    #
    # An explicit `"any"` still promotes at 'other': FRANCE already serves an approved row
    # there, so choosing it is a decision. Only the three ways a topic arrives at 'other'
    # without anyone choosing it refuse here — the same set `executor._unscoped_topics()`
    # already pre-flights and reports. That report is what this turns into a refusal.
    status_values = _distinct([(f.applies_to or {}).get("status") for f in facts])
    if not status_values:
        return Unmapped(topic, "no fact carries applies_to.status — the requirement would "
                               "promote as purpose='other', which crud.list_requirements "
                               "can never return to a reader. Set it before staging")
    if len(status_values) > 1:
        return Unmapped(topic, f"facts disagree on applies_to.status "
                               f"({', '.join(sorted(status_values))}), so this is not one "
                               "requirement")
    status = status_values[0]
    if status not in PURPOSES:
        return Unmapped(
            topic,
            f"applies_to.status={status!r} is not a recognised purpose "
            f"({', '.join(sorted(PURPOSES))}) — it would promote as purpose='other' and be "
            "invisible to every reader",
        )
    purpose = PURPOSES[status]

    derivations = [
        f"pillar={IMMIGRATION_PILLAR} from domain_area='immigration'",
        f"severity={DEFAULT_SEVERITY} (not derivable from Otto's schema; a human raises it)",
        f"owner={DEFAULT_OWNER} (employee-obtained document)",
        f"purpose={purpose} from applies_to.status={status!r}",
        f"nationality classes {classes} from applies_to.nationality={nationality!r}",
    ]

    # `corpus_grounded` requires EVERY contributing fact to have cleared the sourcing gate.
    # One weak fact makes the whole requirement weak, because they are merged into one
    # description a reader cannot unpick.
    #
    # **`accuracy_tier` alone is not enough, and trusting it was a real bug.** The tier is a
    # column in `otto_staging`, and the research routine writes rows straight into that schema
    # with `accuracy_tier='auto_accepted'` set by itself — the parser's sourcing gate never
    # ran. On 2026-08-12 that promoted two France requirements as "Source-grounded" when all
    # 15 contributing facts had `evidence_quote IS NULL`, i.e. nothing a reviewer could
    # re-check without re-reading the source. A tier the producer assigned to its own output
    # is a claim, not evidence. So the quote is now checked here, independently.
    weak = [
        f for f in facts
        if f.accuracy_tier != TIER_AUTO or not (f.evidence_quote or "").strip()
    ]
    verification_status = "representative" if weak else "corpus_grounded"
    if weak:
        unquoted = sum(1 for f in weak if not (f.evidence_quote or "").strip())
        reason = f"{len(weak)} of {len(facts)} facts were not source-grounded"
        if unquoted:
            reason += f" ({unquoted} with no evidence_quote)"
        derivations.append(f"verification_status=representative: {reason}")

    citations = _citations_for(facts, topic)

    # `non_obvious` is the batch's whole point — the divergence between what the official
    # page says and what actually happens — and it drives the client's badge. It rides in
    # `applies_to` because `immigration_fact_candidates` has no column for it. Any
    # contributing fact being non-obvious makes the merged requirement non-obvious: the
    # facts are composed into one description a reader cannot unpick.
    non_obvious = any(bool((f.applies_to or {}).get("non_obvious")) for f in facts)
    if non_obvious:
        derivations.append("non_obvious=True from a contributing fact's applies_to")

    # `timing` rides in `applies_to` for the same reason `non_obvious` does — the staging
    # table has no column for it — but it merges differently. It is free text, not a flag,
    # so `any()` has no meaning: take the FIRST contributing fact that carries one, in fact
    # order, which is stable for a given batch. Everything downstream already supports this
    # column (`requirement_items.timing` from 20261103000000, the update branch in
    # `crud.create_requirement_item`, `requirements_builder`'s "timing" DTO field and the
    # client's practical-realities line) — only this payload never populated it, so a batch
    # that stated a deadline silently lost it at promote time.
    timing = next(
        (str(t).strip() for f in facts
         if (t := (f.applies_to or {}).get("timing")) and str(t).strip()),
        None,
    )
    if timing:
        derivations.append("timing from a contributing fact's applies_to")

    payload = {
        "country_code": country_code,
        "purpose": purpose,
        "pillar": IMMIGRATION_PILLAR,
        "title": entity.title,
        "description": compose_description(facts),
        "severity": DEFAULT_SEVERITY,
        "owner": DEFAULT_OWNER,
        "required_fields_json": "[]",
        "citations_json": json.dumps(citations, ensure_ascii=False),
        "applies_to_nationality_classes_json": json.dumps(classes),
        "verification_status": verification_status,
        "non_obvious": non_obvious,
    }
    # Only send `timing` when this batch actually carries one. `crud.create_requirement_item`
    # updates the column on the mere presence of the key, so passing an unconditional None
    # would blank a deadline a reviewer had curated — the same downgrade-to-empty that the
    # citations_json guard there exists to prevent.
    if timing:
        payload["timing"] = timing

    return RequirementDraft(
        topic_key=topic,
        country_code=country_code,
        purpose=purpose,
        title=entity.title,
        verification_status=verification_status,
        fact_ids=[str(f.id) for f in facts],
        derivations=derivations,
        payload=payload,
    )
