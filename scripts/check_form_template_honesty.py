#!/usr/bin/env python3
"""
Guard: a permit/visa template must not be attachable by someone who needs no permit.

WHY THIS EXISTS — three real, shipped defects

`RESID-PERMIT-DE` ("Residence permit appointment (Auslaenderbehoerde)") declared
conditions {"destination_country": "DE"} and no `visa_type`. `_matches_conditions`
only checks the keys a rule DECLARES, so it matched every DE-destination case —
including FR→DE, where `_build_context` resolves `visa_type: 'eea_registration'`
because both countries are EEA. It told EU citizens to attend an Auslaenderbehoerde
appointment, with a biometric photo and their passport original, to collect a
document German law does not issue them:

    FreizuegG/EU § 2(4): "EU citizens shall not require a visa in order to enter the
    federal territory or a residence title in order to stay in the federal territory."

That was fixed (AIQ-1795). Checking whether it was unique found TWO MORE beside it —
`FAM-SPOUSE` and `FAM-CHILD`, both "Family reunion visa (Familiennachzug)", both
ungated on DE, both firing on `roadmap.profile_completed`, i.e. EARLIER in the
journey. Familiennachzug is a third-country-national procedure; an EU citizen's
spouse has derived free-movement rights under FreizuegG/EU § 3 and needs no such visa.

One instance was fixed by hand and two sat next to it. This script is what makes the
CLASS detectable instead of the instances.

WHY THE EXISTING GUARD CANNOT CATCH THIS

`backend/tests/test_trigger_condition_vocabulary.py` scans the same corpus and passed
on all three. It validates the condition keys that are PRESENT against
`_build_context`'s vocabulary. An OMITTED key is not an invalid key — and omission is
the entire defect, because an absent condition is never checked and therefore always
matches.

WHY STATIC, NOT AGAINST THE DATABASE

Migrations here are committed and applied out-of-band, often much later. A DB check
would only notice a bad template after someone applied it. This parses
`supabase/migrations/*.sql` from disk so it fails the PR that ADDS one, needs no
secret, and covers corridors no environment has applied yet.

WHAT IT DELIBERATELY DOES NOT FLAG

  * `ANMELDUNG` — § 17 BMG registration applies to everyone moving into a German
    dwelling. Ungated is CORRECT. Not permit-like.
  * `BLUE-CARD`, `WORK-VISA-DE` — already declare `visa_type: skilled_worker`, which
    `_build_context` cannot produce on an EEA corridor. They look wrong and are right.
  * `BRP-COLLECT`, `DEP-*`, `JP-*`, `US-*` — permit-like and ungated, but their
    destination is GB/JP/US. `eea_registration` requires BOTH countries in the EEA, so
    those rules are unreachable by an EEA free-mover and are not violations.

Precision matters as much as recall here: a checker that flagged everything ungated
would condemn `ANMELDUNG` and eight legitimate templates, and would be switched off
within a day. `backend/tests/test_form_template_honesty.py` scores both against a
hand-labelled corpus.

Exit codes:
  0 — no violations
  1 — at least one violation
  2 — the corpus could not be parsed (a vacuous pass is a failure, not a pass)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_MIGRATIONS = os.path.join(_REPO_ROOT, "supabase", "migrations")

# Imported, never restated. A second copy of this set is how these bugs start — the whole
# of AIQ-1778 was 'FRANCE' failing to match a pure-ISO-2 set. test_form_template_honesty
# asserts there is no private copy here.
#
# Imported from `eea_countries`, NOT from `trigger_engine`, which owns the set semantically
# but pulls in SQLAlchemy at module level. This script runs in the always-on compliance job,
# which installs no backend dependencies, and importing the engine there failed with
# `ModuleNotFoundError: No module named 'sqlalchemy'`. `eea_countries` is stdlib-only and
# `trigger_engine` now imports the same module, so there is still one copy.
from backend.app.services.eea_countries import EEA_COUNTRIES as _EEA_COUNTRIES  # noqa: E402

# A template is permit-like when its subject is a document granting or evidencing a
# right to reside or work. Matched on name as well as category because the seeds are
# inconsistent: RESID-PERMIT-DE is category 'registration', FAM-SPOUSE is 'family'.
_PERMIT_CATEGORIES = {"work_permit"}
_PERMIT_NAME_RE = re.compile(
    r"\b(permit|visa|residence\s+card|aufenthaltstitel|familiennachzug|"
    r"residence\s+permit|zairyu)\b",
    re.IGNORECASE,
)

# The visa_type _build_context produces when origin AND destination are both EEA.
_EEA_VISA_TYPE = "eea_registration"


# ─────────────────────────────────────────────────────────────────────────────
# SQL parsing. Deliberately narrow: enough to read the seeds, not a SQL engine.
# ─────────────────────────────────────────────────────────────────────────────

_DOLLAR_TAG_RE = re.compile(r"\$[A-Za-z_]*\$")


def _skip_literal(text: str, i: int) -> Optional[int]:
    """If a string literal starts at `i`, return the index just past it, else None.

    Handles BOTH quoting styles Postgres allows and this corpus uses:
      * `'...'` with `''` as an escaped quote
      * `$tag$...$tag$` dollar-quoting

    Dollar-quoting is not a nicety. The Singapore seed writes
    `$$Dependant's Pass - child$$` — an apostrophe inside a dollar-quoted literal.
    Treating that `'` as a string delimiter desynchronised the scanner for the rest of
    the file, which silently dropped SG-DP-CHILD, and in the FR->NO seed made the
    statement-terminator search run past the real `;` and find zero tuples, dropping
    RP-NO-DATASHEET. Both were invisible: the tuples simply failed the column-count
    check and were skipped without a word. test_form_template_honesty now asserts
    self-coverage so a parser blind spot fails loudly instead.
    """
    if text[i] == "'":
        j = i + 1
        while j < len(text):
            if text[j] == "'":
                if j + 1 < len(text) and text[j + 1] == "'":
                    j += 2
                    continue
                return j + 1
            j += 1
        return len(text)
    if text[i] == "$":
        m = _DOLLAR_TAG_RE.match(text, i)
        if not m:
            return None
        tag = m.group(0)
        end = text.find(tag, m.end())
        return (end + len(tag)) if end != -1 else len(text)
    # SQL comments are skipped by the same mechanism, for the same reason: the FR->NO
    # seed carries a long `--` explanation BETWEEN its `fields` and `trigger_rules`
    # values, inside the statement, and a `;` in that prose terminated the scan early —
    # so RP-NO-DATASHEET, the one data sheet we actually ship, was invisible to this
    # guard. Literals and comments are the only places SQL punctuation is inert.
    if text.startswith("--", i):
        nl = text.find("\n", i)
        return len(text) if nl == -1 else nl + 1
    if text.startswith("/*", i):
        end = text.find("*/", i + 2)
        return len(text) if end == -1 else end + 2
    return None


def _split_top_level(text: str) -> List[str]:
    """Split on commas outside literals and parens."""
    out, buf, depth = [], [], 0
    i = 0
    while i < len(text):
        nxt = _skip_literal(text, i)
        if nxt is not None:
            buf.append(text[i:nxt])
            i = nxt
            continue
        ch = text[i]
        if ch in "([":
            depth += 1
            buf.append(ch)
        elif ch in ")]":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    if buf:
        out.append("".join(buf))
    return [s.strip() for s in out]


def _unquote(token: str) -> Optional[str]:
    """`'abc'::jsonb` / `'ab''c'` / `$$abc$$` → the literal. None for NULL/expression."""
    t = re.sub(r"::\s*\w+\s*$", "", token.strip()).strip()
    if t.upper() == "NULL":
        return None
    if t.startswith("'") and t.endswith("'") and len(t) >= 2:
        return t[1:-1].replace("''", "'")
    m = _DOLLAR_TAG_RE.match(t)
    if m and t.endswith(m.group(0)) and len(t) >= 2 * len(m.group(0)):
        return t[m.end():-len(m.group(0))]
    return None


def _value_tuples(values_region: str) -> List[str]:
    """The inner text of each `( ... )` tuple in a VALUES region."""
    tuples, depth, start = [], 0, None
    i = 0
    while i < len(values_region):
        nxt = _skip_literal(values_region, i)
        if nxt is not None:
            i = nxt
            continue
        ch = values_region[i]
        if ch == "(":
            if depth == 0:
                start = i + 1
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0 and start is not None:
                tuples.append(values_region[start:i])
                start = None
        i += 1
    return tuples


def _statement_end(body: str, start: int) -> int:
    """Index of the statement-terminating `;`, ignoring semicolons inside string
    literals.

    A naive `(.*?);` regex silently truncated two templates — RP-NO-DATASHEET and
    SG-DP-CHILD — because their seeded `note` text contains a semicolon
    ("...(Art. 12, Reg. 883/2004); an Art. 16 exception..."). The truncated tuple then
    failed the column-count check and was skipped without a word. That is precisely
    the silent blind spot this guard exists to prevent, so the parser must not have
    one: test_form_template_honesty asserts every seeded code is reachable.
    """
    i = start
    while i < len(body):
        nxt = _skip_literal(body, i)
        if nxt is not None:
            i = nxt
            continue
        if body[i] == ";":
            return i
        i += 1
    return len(body)


def parse_templates(migrations_dir: str = _MIGRATIONS) -> List[Dict[str, Any]]:
    """Every form_templates row the repo's migrations INSERT, with its rules."""
    rows: List[Dict[str, Any]] = []
    if not os.path.isdir(migrations_dir):
        return rows
    head_re = re.compile(
        r"INSERT\s+INTO\s+(?:public\.)?form_templates\s*\(([^)]*)\)\s*VALUES\s*",
        re.IGNORECASE | re.DOTALL,
    )
    for fname in sorted(os.listdir(migrations_dir)):
        if not fname.endswith(".sql"):
            continue
        body = open(os.path.join(migrations_dir, fname), encoding="utf-8").read()
        for m in head_re.finditer(body):
            cols = [c.strip().lower() for c in m.group(1).replace("\n", " ").split(",")]
            values_region = body[m.end():_statement_end(body, m.end())]
            for tup in _value_tuples(values_region):
                vals = _split_top_level(tup)
                if len(vals) != len(cols):
                    continue  # a SELECT-driven insert or a shape we don't model
                rec = dict(zip(cols, vals))
                code = _unquote(rec.get("code", ""))
                if not code:
                    continue
                raw_rules = _unquote(rec.get("trigger_rules", "") or "")
                try:
                    rules = json.loads(raw_rules) if raw_rules else []
                except (json.JSONDecodeError, TypeError):
                    rules = []
                if not isinstance(rules, list):
                    rules = []
                rows.append({
                    "code": code,
                    "name": _unquote(rec.get("name", "")) or "",
                    "category": _unquote(rec.get("category", "")) or "",
                    "rules": rules,
                    "file": fname,
                })
    return rows


def superseded_codes(migrations_dir: str = _MIGRATIONS) -> Dict[str, str]:
    """code → the later migration that REWRITES its trigger_rules.

    A forward migration may fix a seeded rule (that is how AIQ-1795 fixed
    RESID-PERMIT-DE). Those writes use jsonb_build_array(...) rather than a JSON
    literal, so this script does not attempt to parse them — it records that the
    seeded shape no longer stands and defers, rather than reporting a violation that
    has already been fixed. `--db` evaluates the live row instead.
    """
    out: Dict[str, str] = {}
    if not os.path.isdir(migrations_dir):
        return out
    pat = re.compile(
        r"UPDATE\s+(?:public\.)?form_templates\s+SET\b[^;]*?\btrigger_rules\s*=[^;]*?"
        r"WHERE[^;]*?code\s*=\s*'([^']+)'",
        re.IGNORECASE | re.DOTALL,
    )
    for fname in sorted(os.listdir(migrations_dir)):
        if not fname.endswith(".sql"):
            continue
        body = open(os.path.join(migrations_dir, fname), encoding="utf-8").read()
        for m in pat.finditer(body):
            out[m.group(1)] = fname
    return out


# ─────────────────────────────────────────────────────────────────────────────
# The invariant
# ─────────────────────────────────────────────────────────────────────────────

def is_permit_like(name: str, category: str) -> bool:
    if (category or "").strip().lower() in _PERMIT_CATEGORIES:
        return True
    return bool(_PERMIT_NAME_RE.search(name or ""))


def rule_is_eea_reachable(conditions: Dict[str, Any]) -> bool:
    """Can this rule match a case whose visa_type is 'eea_registration'?

    Origin is deliberately NOT examined. visa_type is 'eea_registration' only when
    BOTH countries are EEA, so an EEA destination guarantees a qualifying origin
    exists. Requiring an origin condition would make the check miss every rule that
    omits one — which is nearly all of them, and omission is the defect.
    """
    dest = (conditions or {}).get("destination_country")
    if not isinstance(dest, str) or dest.strip().upper() not in _EEA_COUNTRIES:
        return False
    if "visa_type" not in (conditions or {}):
        return True  # never checked ⇒ matches every visa_type, including EEA
    return str(conditions.get("visa_type")).strip().lower() == _EEA_VISA_TYPE


def find_violations(rows: List[Dict[str, Any]],
                    superseded: Dict[str, str]) -> Tuple[List[Dict], List[Dict]]:
    """(violations, deferred)."""
    violations, deferred = [], []
    for row in rows:
        if not is_permit_like(row["name"], row["category"]):
            continue
        hits = [r for r in row["rules"]
                if isinstance(r, dict) and rule_is_eea_reachable(r.get("conditions") or {})]
        if not hits:
            continue
        entry = {
            "code": row["code"], "name": row["name"], "category": row["category"],
            "file": row["file"],
            "conditions": [r.get("conditions") for r in hits],
            "events": [r.get("event") for r in hits],
        }
        if row["code"] in superseded:
            entry["superseded_by"] = superseded[row["code"]]
            deferred.append(entry)
        else:
            violations.append(entry)
    return violations, deferred


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    ap.add_argument("--migrations", default=_MIGRATIONS)
    args = ap.parse_args()

    rows = parse_templates(args.migrations)
    superseded = superseded_codes(args.migrations)
    violations, deferred = find_violations(rows, superseded)

    report = {
        "templates_parsed": len(rows),
        "permit_like": sum(1 for r in rows if is_permit_like(r["name"], r["category"])),
        "violations": violations,
        "deferred": deferred,
    }

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"[template-honesty] parsed {len(rows)} seeded templates, "
              f"{report['permit_like']} permit-like")
        for d in deferred:
            print(f"[template-honesty] deferred: {d['code']} — seeded shape would violate, "
                  f"rewritten by {d['superseded_by']}")
        if violations:
            print(f"\n[template-honesty] FAIL — {len(violations)} permit/visa template(s) "
                  f"attach to EEA free-movement cases:\n")
            for v in violations:
                print(f"  • {v['code']}  ({v['file']})")
                print(f"      {v['name']}")
                for cond, ev in zip(v["conditions"], v["events"]):
                    print(f"      on {ev}: {json.dumps(cond, sort_keys=True)}")
            print("\n  An EEA free-mover needs no residence title (FreizuegG/EU § 2(4)) and no")
            print("  family-reunion visa (§ 3). A rule that omits visa_type is never checked")
            print("  against one, so it matches eea_registration too.")
            print("\n  Fix: add one rule per non-EEA visa_type — skilled_worker,")
            print("  intra_company_transfer, family_join, remote_work — as")
            print("  20261023000000_resid_permit_de_gate_non_eea.sql does. _matches_conditions")
            print("  has no list support, but trigger_rules is iterated as an array.")

    if not rows:
        print("[template-honesty] ERROR — parsed 0 templates. A vacuous pass is not a pass.",
              file=sys.stderr)
        return 2
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
