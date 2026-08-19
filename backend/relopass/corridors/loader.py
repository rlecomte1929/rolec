"""Corridor YAML loader and structural validator (C1-09).

Loads a corridor agent config file (e.g.
``corridors/IN_DE/pathways/BLUECARD_2026/v1.yaml``) into a typed dataclass tree.
Catches malformed corridor files at module-load time instead of inside a
long-running pipeline. The file's location is resolved via the corridor registry
(``corridor_registry.get_pathway_file``); this loader stays path-only + app-free.

The evaluator that runs a Case against a loaded :class:`CorridorAgent` lives
in C1-05 (the Extraction Agent / Corridor runtime). When that lands, the
public API will be::

    from backend.relopass.corridors import load_corridor
    from backend.relopass.agents.corridor_runtime import evaluate

    corridor = load_corridor("corridors/IN_DE/pathways/BLUECARD_2026/v1.yaml")
    result = evaluate(corridor, case)
    # result.verdict ∈ {ELIGIBLE, ALTERNATE_PATHWAY, NOT_ELIGIBLE}
    # result.citations is List[RuleCitation]

The loader has no SDK or framework dependencies (see
``backend/relopass/__init__.py`` constraint).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────────────────────


class CorridorLoadError(Exception):
    """Raised when a corridor YAML is malformed."""


# ─────────────────────────────────────────────────────────────────────────────
# Dataclass tree
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CorridorRule:
    legal_reference: str
    rule_id: str
    summary: Optional[str] = None


@dataclass(frozen=True)
class CorridorDataPoint:
    key: str
    type: str
    source: Optional[str] = None  # USER_INPUT | EXTERNAL_LOOKUP | DERIVED
    lookup: Optional[str] = None
    validations: Tuple[str, ...] = ()


@dataclass(frozen=True)
class CorridorEligibilityBranch:
    id: str
    label: str
    cite: str
    requires_all: Tuple[str, ...]
    verdict_on_pass: str
    annotation: Optional[str] = None


@dataclass(frozen=True)
class CorridorExceptionCase:
    id: str
    condition: str
    cite: str
    action: str
    hint: Optional[str] = None


@dataclass(frozen=True)
class CorridorDeadlineTrigger:
    """A step's opt-in to the deadline-alert sweep.

    Only steps that state a hard legal window carry one. ``lead_days`` opens the
    alert window: the sweep fires when ``due - lead_days <= today <= due``, so
    the message is always "this window is open", never "due today".

    ``tag`` is the copy key AND the destination-correctness boundary. One tag
    maps to exactly ONE destination's rule set — see
    :mod:`backend.relopass.corridors.deadline_alerts`. Norway requires an
    anti-echinococcus treatment before arrival and France requires none; a tag
    shared across both destinations forces copy that is wrong for half its
    readers, so the invariant is enforced rather than documented.

    ``tag`` is NOT the ledger key — ``step_id`` is. Renaming a tag is therefore
    safe (it re-points copy); renaming a step_id re-fires history.
    """

    tag: str
    label: str
    channel: str
    lead_days: int
    # The country whose rule set this alert states, ISO3. Defaults to the
    # corridor's destination, which is right for every entry obligation.
    #
    # It exists for EXIT obligations, which are owed to the origin: NO_FR's
    # "report the move abroad to Folkeregisteret" is a Norwegian rule inside a
    # corridor bound for France. Keyed on the corridor destination it would be
    # labelled French, and a second Norway-exit corridor would then look like a
    # cross-destination tag conflict when the two rule sets are in fact identical.
    jurisdiction: Optional[str] = None


@dataclass(frozen=True)
class CorridorStep:
    step_id: str
    name: str
    responsible_party: str
    expected_duration_days: int
    prerequisite_step_ids: Tuple[str, ...] = ()
    time_window_relative_to: Optional[str] = None
    time_window_min_days: Optional[int] = None
    time_window_max_days: Optional[int] = None
    conditional_on: Optional[str] = None
    cite: Optional[str] = None
    # 'action' (something is required of someone) or 'nothing_to_do' (a stated
    # positive: nothing is required, and here is why). A returning citizen's
    # immigration steps are genuinely nothing-to-do; rendering them as blank rows
    # reads as a broken screen, so they are first-class rather than absent.
    outcome_type: str = "action"
    # Something a non-expert wouldn't know to look for — the flag the product
    # exists to raise: the week-seven ambush, surfaced in week one.
    non_obvious: bool = False
    # 'information_only' or 'route_to_professional'. A personalised legal or tax
    # determination must route to a regulated professional and must never be
    # answered in ReloPass's own voice.
    advice_boundary: str = "information_only"
    # 'HARD' (the engine asserts this) or 'PENDING' (an open counsel question —
    # surface as pending_verification, NEVER as asserted fact).
    assertion: str = "HARD"
    # Marks where the PRE-arrival runway ends: the step at which the mover is in
    # the destination and in-country obligations begin. Everything upstream of it
    # must complete before the start date, which is what makes an employment-permit
    # corridor infeasible at short notice while a free-movement one never is.
    # Declared rather than inferred: step-id spelling is not a safe proxy (NO_FR's
    # is A0_DEPART_NO, IN_DE's graph roots elsewhere entirely).
    arrival_anchor: bool = False
    # Opt-in to the deadline-alert sweep. None (the default) means this step is
    # scheduled and flagged as before but never sends anything — alerting is
    # additive, so every existing corridor keeps its current behaviour.
    deadline_trigger: Optional[CorridorDeadlineTrigger] = None


@dataclass(frozen=True)
class CorridorAgent:
    corridor_id: str
    version: str
    petitioning_party: str
    origin_country_iso3: Optional[str]
    destination_country_iso3: Optional[str]
    description: Optional[str]

    applicable_rules: Tuple[CorridorRule, ...]
    required_documents: Tuple[str, ...]
    required_data_points: Tuple[CorridorDataPoint, ...]
    salary_thresholds_eur: Mapping[str, float]
    eligibility_branches: Tuple[CorridorEligibilityBranch, ...]
    no_branch_verdict: str
    exception_cases: Tuple[CorridorExceptionCase, ...]
    step_graph: Tuple[CorridorStep, ...]

    def rule_ids(self) -> Tuple[str, ...]:
        return tuple(r.rule_id for r in self.applicable_rules)

    def step_ids(self) -> Tuple[str, ...]:
        return tuple(s.step_id for s in self.step_graph)

    def get_step(self, step_id: str) -> Optional[CorridorStep]:
        for s in self.step_graph:
            if s.step_id == step_id:
                return s
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Hand-rolled YAML parser
# ─────────────────────────────────────────────────────────────────────────────
#
# The corridor YAMLs use only a small, predictable subset of YAML:
#   - Nested mappings (key: value)
#   - Lists of strings (- "foo")
#   - Lists of mappings (- key: value …)
#   - Block scalars (>) collapsed to a single line
#   - Inline scalars: string / int / float / bool / null
#
# Avoids a PyYAML dependency for the same reason as C1-13 — keeps the
# relopass primitive package vendor-free. If the YAML files grow more
# expressive (anchors, flow style, multi-doc), swap to ruamel.yaml in a
# higher layer.


_INDENT_RE = re.compile(r"^( *)(.*)$")


def _strip_comment(line: str) -> str:
    # Strip "# comment" but leave "#" inside a quoted string alone.
    out: List[str] = []
    in_single = False
    in_double = False
    for ch in line:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        if ch == "#" and not in_single and not in_double:
            break
        out.append(ch)
    return "".join(out).rstrip()


def _split_flow_items(body: str) -> List[str]:
    """Split a flow-style list body on commas that aren't inside nested
    brackets or quotes. Supports the minimal subset the corridor YAMLs use.
    """
    parts: List[str] = []
    depth = 0
    in_single = False
    in_double = False
    buf: List[str] = []
    for ch in body:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        if not in_single and not in_double:
            if ch in "[{":
                depth += 1
            elif ch in "]}":
                depth -= 1
            if ch == "," and depth == 0:
                parts.append("".join(buf).strip())
                buf = []
                continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def _parse_scalar(raw: str) -> Any:
    s = raw.strip()
    if s == "" or s.lower() == "null" or s == "~":
        return None
    if s.lower() == "true":
        return True
    if s.lower() == "false":
        return False
    # Inline flow-style collections — the corridor schema uses these for
    # short string lists (e.g. ISCO code allowlists, prerequisite step IDs).
    # Full nested flow style isn't supported; only single-level [a, b, c]
    # and the empty-collection cases [] / {}.
    if s == "[]":
        return []
    if s == "{}":
        return {}
    if s.startswith("[") and s.endswith("]"):
        body = s[1:-1].strip()
        if body == "":
            return []
        return [_parse_scalar(item) for item in _split_flow_items(body)]
    # Quoted string — strip the quotes.
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    # Int / float (be conservative about leading zeros / signs).
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        return float(s)
    return s


def _indent(line: str) -> int:
    m = _INDENT_RE.match(line)
    return len(m.group(1)) if m else 0


def _yaml_parse(text: str) -> Any:
    """Tiny YAML loader for the corridor subset described above.

    Returns nested dicts/lists/scalars. Raises :class:`CorridorLoadError`
    on anything it can't handle.
    """
    # Pre-process: drop empty lines and comment-only lines, but keep
    # indentation by replacing with empty strings rather than removing.
    raw_lines = text.splitlines()
    processed: List[Tuple[int, str]] = []
    i = 0
    while i < len(raw_lines):
        line = raw_lines[i]
        clean = _strip_comment(line)
        if clean.strip() == "":
            i += 1
            continue
        # Block scalar handling: "key: >" or "key: |"
        m = re.match(r"^( *)([^:\s][^:]*?):\s*([>|])\s*$", clean)
        if m:
            indent = len(m.group(1))
            key = m.group(2).strip()
            i += 1
            buf: List[str] = []
            scalar_indent: Optional[int] = None
            while i < len(raw_lines):
                next_line = raw_lines[i]
                if next_line.strip() == "":
                    i += 1
                    continue
                ni = _indent(next_line)
                if scalar_indent is None:
                    scalar_indent = ni
                if ni < (scalar_indent or 0):
                    break
                buf.append(next_line.strip())
                i += 1
            joined = " ".join(buf)
            processed.append((indent, f"{key}: {joined!r}"))
            continue
        processed.append((_indent(clean), clean.strip()))
        i += 1
    return _parse_block(processed, 0, 0)[0]


def _parse_block(
    lines: Sequence[Tuple[int, str]],
    start: int,
    base_indent: int,
) -> Tuple[Any, int]:
    """Parse a YAML block starting at ``lines[start]`` whose entries are
    indented at exactly ``base_indent``. Returns (parsed, next_index).
    """
    if start >= len(lines):
        return None, start

    first_indent, first_line = lines[start]
    if first_indent < base_indent:
        return None, start

    # Determine if this block is a list (lines start with "- ") or a map.
    is_list = first_line.startswith("- ") or first_line == "-"

    if is_list:
        return _parse_list(lines, start, base_indent)
    return _parse_map(lines, start, base_indent)


def _parse_list(
    lines: Sequence[Tuple[int, str]],
    start: int,
    base_indent: int,
) -> Tuple[List[Any], int]:
    items: List[Any] = []
    i = start
    while i < len(lines):
        indent, content = lines[i]
        if indent < base_indent:
            break
        if indent > base_indent:
            raise CorridorLoadError(
                f"Unexpected indentation in list: {content!r} (indent={indent}, base={base_indent})"
            )
        if not (content.startswith("- ") or content == "-"):
            break
        after_dash = content[1:].lstrip()
        if after_dash == "":
            # Bare "-" followed by a sub-block.
            inner, next_i = _parse_block(lines, i + 1, base_indent + 2)
            items.append(inner)
            i = next_i
            continue
        # "- key: value" — start of an inline map within the list.
        if ":" in after_dash and not after_dash.startswith('"'):
            # Treat as a single-key map and continue parsing siblings.
            key, sep, value = after_dash.partition(":")
            value = value.strip()
            entry: Dict[str, Any] = {}
            if value == "":
                # value is a sub-block on subsequent lines at deeper indent
                sub, next_i = _parse_block(lines, i + 1, indent + 2)
                entry[key.strip()] = sub
                i = next_i
            else:
                entry[key.strip()] = _parse_scalar(value)
                i += 1
            # Continue absorbing further keys at the same effective indent
            # (which sits at (indent + 2) because of the "- " prefix).
            child_indent = indent + 2
            while i < len(lines):
                ci, cc = lines[i]
                if ci < child_indent:
                    break
                if ci > child_indent:
                    raise CorridorLoadError(
                        f"Unexpected indentation: {cc!r} (indent={ci}, expected={child_indent})"
                    )
                if cc.startswith("- "):
                    break
                if ":" not in cc:
                    raise CorridorLoadError(f"Expected 'key: value' line, got: {cc!r}")
                k, _, v = cc.partition(":")
                v = v.strip()
                if v == "":
                    sub, next_i = _parse_block(lines, i + 1, child_indent + 2)
                    entry[k.strip()] = sub
                    i = next_i
                else:
                    entry[k.strip()] = _parse_scalar(v)
                    i += 1
            items.append(entry)
        else:
            # "- scalar"
            items.append(_parse_scalar(after_dash))
            i += 1
    return items, i


def _parse_map(
    lines: Sequence[Tuple[int, str]],
    start: int,
    base_indent: int,
) -> Tuple[Dict[str, Any], int]:
    out: Dict[str, Any] = {}
    i = start
    while i < len(lines):
        indent, content = lines[i]
        if indent < base_indent:
            break
        if indent > base_indent:
            raise CorridorLoadError(
                f"Unexpected indentation in map: {content!r} (indent={indent}, base={base_indent})"
            )
        if ":" not in content:
            raise CorridorLoadError(f"Expected 'key: value' line, got: {content!r}")
        key, _, value = content.partition(":")
        key = key.strip()
        value = value.strip()
        if value == "":
            sub, next_i = _parse_block(lines, i + 1, base_indent + 2)
            out[key] = sub
            i = next_i
        else:
            out[key] = _parse_scalar(value)
            i += 1
    return out, i


# ─────────────────────────────────────────────────────────────────────────────
# Structural validation + dataclass building
# ─────────────────────────────────────────────────────────────────────────────


def _require(d: Mapping[str, Any], key: str, where: str) -> Any:
    if key not in d:
        raise CorridorLoadError(f"Missing required key {key!r} under {where}")
    return d[key]


# Closed vocabularies. A typo in corridor content must fail the load, not sail
# through as a silently-wrong default — 'assertion: PENIDNG' quietly becoming
# HARD would publish an open counsel question as asserted fact.
_OUTCOME_TYPES = ("action", "nothing_to_do")
_ADVICE_BOUNDARIES = ("information_only", "route_to_professional")
_ASSERTIONS = ("HARD", "PENDING")


def _enum(step: Any, key: str, allowed: Tuple[str, ...], default: str) -> str:
    if not isinstance(step, Mapping) or step.get(key) is None:
        return default
    value = str(step[key])
    if value not in allowed:
        raise CorridorLoadError(
            f"step_graph[*].{key} must be one of {list(allowed)}, got {value!r}"
        )
    return value


# Delivery channels the sweep knows how to emit. A typo must fail the load rather
# than silently produce an alert nothing dispatches.
_ALERT_CHANNELS = ("email", "in_app")

# Tag grammar: relopass-deadline-<slug>[-<dest-iso2-lower>]. Lowercase kebab only,
# so a tag is safe as a copy-registry key and as an external CRM tag alike.
_TAG_RE = re.compile(r"^relopass-deadline-[a-z0-9]+(?:-[a-z0-9]+)*$")


def _deadline_trigger(step: Any, step_id: str) -> Optional[CorridorDeadlineTrigger]:
    """Build a step's deadline trigger, or None when it declares none.

    Every field is required: a half-declared trigger is a content bug, and
    defaulting ``lead_days`` would invent a legal notice period we never authored.
    """
    if not isinstance(step, Mapping):
        return None
    raw = step.get("deadline_trigger")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise CorridorLoadError(
            f"step {step_id}: deadline_trigger must be a mapping, got {type(raw).__name__}"
        )

    unknown = set(raw) - {"tag", "label", "channel", "lead_days", "jurisdiction"}
    if unknown:
        raise CorridorLoadError(
            f"step {step_id}: unknown deadline_trigger key(s) {sorted(unknown)}"
        )

    tag = str(_require(raw, "tag", f"step_graph[{step_id}].deadline_trigger"))
    if not _TAG_RE.match(tag):
        raise CorridorLoadError(
            f"step {step_id}: deadline_trigger.tag {tag!r} must match "
            f"relopass-deadline-<slug>, lowercase kebab-case"
        )

    channel = str(_require(raw, "channel", f"step_graph[{step_id}].deadline_trigger"))
    if channel not in _ALERT_CHANNELS:
        raise CorridorLoadError(
            f"step {step_id}: deadline_trigger.channel must be one of "
            f"{list(_ALERT_CHANNELS)}, got {channel!r}"
        )

    raw_lead = _require(raw, "lead_days", f"step_graph[{step_id}].deadline_trigger")
    if not isinstance(raw_lead, int) or isinstance(raw_lead, bool) or raw_lead < 1:
        raise CorridorLoadError(
            f"step {step_id}: deadline_trigger.lead_days must be a positive int, "
            f"got {raw_lead!r}"
        )

    label = str(_require(raw, "label", f"step_graph[{step_id}].deadline_trigger"))
    if not label.strip():
        raise CorridorLoadError(f"step {step_id}: deadline_trigger.label must not be empty")

    jurisdiction = raw.get("jurisdiction")
    if jurisdiction is not None:
        jurisdiction = str(jurisdiction)
        if not re.fullmatch(r"[A-Z]{3}", jurisdiction):
            raise CorridorLoadError(
                f"step {step_id}: deadline_trigger.jurisdiction must be an ISO 3166-1 "
                f"alpha-3 code in uppercase, got {jurisdiction!r}"
            )

    return CorridorDeadlineTrigger(
        tag=tag,
        label=label,
        channel=channel,
        lead_days=raw_lead,
        jurisdiction=jurisdiction,
    )


def _as_tuple(value: Any) -> Tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, list):
        return tuple(value)
    if isinstance(value, tuple):
        return value
    raise CorridorLoadError(f"Expected list/tuple, got {type(value).__name__}: {value!r}")


def _build_corridor(parsed: Mapping[str, Any]) -> CorridorAgent:
    if "corridor_agent" not in parsed:
        raise CorridorLoadError("Top-level 'corridor_agent' key missing")
    cfg = parsed["corridor_agent"]
    if not isinstance(cfg, Mapping):
        raise CorridorLoadError("'corridor_agent' must be a mapping")

    rules = tuple(
        CorridorRule(
            legal_reference=str(_require(r, "legal_reference", "applicable_rules[*]")),
            rule_id=str(_require(r, "rule_id", "applicable_rules[*]")),
            summary=(r.get("summary") if isinstance(r, Mapping) else None),
        )
        for r in _as_tuple(cfg.get("applicable_rules"))
    )

    data_points = tuple(
        CorridorDataPoint(
            key=str(_require(dp, "key", "required_data_points[*]")),
            type=str(_require(dp, "type", "required_data_points[*]")),
            source=(dp.get("source") if isinstance(dp, Mapping) else None),
            lookup=(dp.get("lookup") if isinstance(dp, Mapping) else None),
            validations=_as_tuple(dp.get("validations") if isinstance(dp, Mapping) else ()),
        )
        for dp in _as_tuple(cfg.get("required_data_points"))
    )

    raw_logic = cfg.get("eligibility_logic", {})
    if not isinstance(raw_logic, Mapping):
        raise CorridorLoadError("'eligibility_logic' must be a mapping")
    branches = tuple(
        CorridorEligibilityBranch(
            id=str(_require(b, "id", "eligibility_logic.branches[*]")),
            label=str(_require(b, "label", "eligibility_logic.branches[*]")),
            cite=str(_require(b, "cite", "eligibility_logic.branches[*]")),
            requires_all=_as_tuple(_require(b, "requires_all", "eligibility_logic.branches[*]")),
            verdict_on_pass=str(_require(b, "verdict_on_pass", "eligibility_logic.branches[*]")),
            annotation=(b.get("annotation") if isinstance(b, Mapping) else None),
        )
        for b in _as_tuple(raw_logic.get("branches"))
    )

    exceptions = tuple(
        CorridorExceptionCase(
            id=str(_require(e, "id", "exception_cases[*]")),
            condition=str(_require(e, "condition", "exception_cases[*]")),
            cite=str(_require(e, "cite", "exception_cases[*]")),
            action=str(_require(e, "action", "exception_cases[*]")),
            hint=(e.get("hint") if isinstance(e, Mapping) else None),
        )
        for e in _as_tuple(cfg.get("exception_cases"))
    )

    steps = tuple(
        CorridorStep(
            step_id=str(_require(s, "step_id", "step_graph[*]")),
            name=str(_require(s, "name", "step_graph[*]")),
            responsible_party=str(_require(s, "responsible_party", "step_graph[*]")),
            expected_duration_days=int(_require(s, "expected_duration_days", "step_graph[*]")),
            prerequisite_step_ids=_as_tuple(s.get("prerequisite_step_ids") if isinstance(s, Mapping) else ()),
            time_window_relative_to=(s.get("time_window_relative_to") if isinstance(s, Mapping) else None),
            time_window_min_days=(s.get("time_window_min_days") if isinstance(s, Mapping) else None),
            time_window_max_days=(s.get("time_window_max_days") if isinstance(s, Mapping) else None),
            conditional_on=(s.get("conditional_on") if isinstance(s, Mapping) else None),
            cite=(s.get("cite") if isinstance(s, Mapping) else None),
            outcome_type=_enum(s, "outcome_type", _OUTCOME_TYPES, "action"),
            non_obvious=bool(s.get("non_obvious", False)) if isinstance(s, Mapping) else False,
            advice_boundary=_enum(s, "advice_boundary", _ADVICE_BOUNDARIES, "information_only"),
            assertion=_enum(s, "assertion", _ASSERTIONS, "HARD"),
            arrival_anchor=bool(s.get("arrival_anchor", False)) if isinstance(s, Mapping) else False,
            deadline_trigger=_deadline_trigger(s, str(s.get("step_id")) if isinstance(s, Mapping) else "?"),
        )
        for s in _as_tuple(cfg.get("step_graph"))
    )

    salary = cfg.get("salary_thresholds_eur") or {}
    if not isinstance(salary, Mapping):
        raise CorridorLoadError("'salary_thresholds_eur' must be a mapping")
    salary_typed: Dict[str, float] = {}
    for k, v in salary.items():
        try:
            salary_typed[str(k)] = float(v)
        except (TypeError, ValueError) as exc:
            raise CorridorLoadError(
                f"salary_thresholds_eur.{k} must be numeric, got {v!r}"
            ) from exc

    # Structural sanity checks — fail loudly at load time.
    rule_id_set = {r.rule_id for r in rules}
    for branch in branches:
        if branch.cite not in rule_id_set:
            raise CorridorLoadError(
                f"eligibility branch {branch.id} cites unknown rule {branch.cite!r}; "
                f"add it to applicable_rules first"
            )
    step_id_set = {s.step_id for s in steps}
    for step in steps:
        for prereq in step.prerequisite_step_ids:
            if prereq not in step_id_set:
                raise CorridorLoadError(
                    f"step {step.step_id} has prerequisite {prereq!r} not in step_graph"
                )
        if step.time_window_relative_to is not None:
            if step.time_window_relative_to not in step_id_set:
                raise CorridorLoadError(
                    f"step {step.step_id} time_window_relative_to "
                    f"{step.time_window_relative_to!r} not in step_graph"
                )
        if step.deadline_trigger is not None:
            # compute_deadlines only dates a step that states a window, so a
            # trigger without one could never fire. Refuse it at load time rather
            # than ship an alert that is silently unreachable.
            has_window = step.time_window_relative_to is not None and (
                step.time_window_max_days is not None
                or step.time_window_min_days is not None
            )
            if not has_window:
                raise CorridorLoadError(
                    f"step {step.step_id} declares a deadline_trigger but states no "
                    f"time window; a step with no due date can never fire an alert"
                )

    return CorridorAgent(
        corridor_id=str(_require(cfg, "corridor_id", "corridor_agent")),
        version=str(_require(cfg, "version", "corridor_agent")),
        petitioning_party=str(cfg.get("petitioning_party", "EMPLOYEE")),
        origin_country_iso3=cfg.get("origin_country_iso3"),
        destination_country_iso3=cfg.get("destination_country_iso3"),
        description=cfg.get("description"),
        applicable_rules=rules,
        required_documents=_as_tuple(cfg.get("required_documents")),
        required_data_points=data_points,
        salary_thresholds_eur=salary_typed,
        eligibility_branches=branches,
        no_branch_verdict=str(raw_logic.get("no_branch_verdict", "NOT_ELIGIBLE")),
        exception_cases=exceptions,
        step_graph=steps,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def load_corridor(path: str | Path) -> CorridorAgent:
    p = Path(path)
    if not p.exists():
        raise CorridorLoadError(f"Corridor file not found: {path}")
    return load_corridor_text(p.read_text(encoding="utf-8"))


def load_corridor_text(text: str) -> CorridorAgent:
    try:
        parsed = _yaml_parse(text)
    except CorridorLoadError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise CorridorLoadError(f"YAML parse failed: {exc}") from exc
    if not isinstance(parsed, Mapping):
        raise CorridorLoadError("Top-level YAML must be a mapping")
    return _build_corridor(parsed)
