#!/usr/bin/env python3
"""[AIQ-1513] Fail CI if shipped copy makes an EU AI Act status claim.

WHY
---
docs/compliance/AIQ-1487_eu_ai_act_assessment.md is explicit:

    "Do not ship an 'EU AI Act Ready' / 'Compliant' badge. For a limited-risk system
     there is no certification to be 'ready' for, and the phrasing implies a formal
     status we don't hold."
    "A false or premature compliance claim is itself a legal liability."

It also determined ReloPass's AI is **limited-risk, NOT high-risk** — so copy must not
imply we are a high-risk HR system either.

Despite that, relopass.com shipped an "EU AI Act Ready" badge and a downloadable PDF
saying the same, aimed at compliance and procurement teams. This guard exists so that
cannot silently come back.

WHAT IS AND ISN'T BANNED
------------------------
BANNED in shipped, customer-facing copy: any claim of EU AI Act *status* — ready,
compliant, certified, conformant — and any wording that classifies ReloPass itself as a
high-risk AI system.

ALLOWED, and encouraged: describing what the controls actually do — human review on
every AI recommendation, the decision/AI-output audit log, source-grounded answers, PII
masked before any LLM call. Those are verifiable product facts, not a legal status.
Describe the controls; claim no status.

If you genuinely need a new compliance claim, it needs legal sign-off first — then add
it here with the sign-off recorded, not by deleting the rule.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Copy that reaches a customer: the SPA, static assets, marketing, published content.
SCAN_DIRS = [
    REPO / "frontend" / "src",
    REPO / "frontend" / "public",
    REPO / "docs" / "marketing",
    REPO / "content",
    # docs/gtm holds the paid-ad copy — the 8 card titles and bodies handed verbatim to
    # the ad platform. That copy is customer-facing the moment a campaign launches, and
    # it reaches an audience that never visits the site, but it lived outside this guard
    # until 2026-08-10. Ad copy was in fact the ONLY customer-facing surface with no
    # automated check, which is the opposite of what its blast radius deserves: a badge
    # on a web page can be edited in a minute, a claim inside an approved ad creative is
    # already impressed on people and may be cached by the platform.
    REPO / "docs" / "gtm",
]
SCAN_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".html", ".md", ".mdx", ".json", ".txt"}

# Internal analysis, legal assessment, and this guard itself must be free to USE these
# phrases in order to discuss and forbid them. Exempt by path.
EXEMPT_PARTS = (
    "/docs/compliance/",     # the assessment itself
    "/node_modules/",
    "/dist/",
    "/__tests__/",
    "/tests/",
)
EXEMPT_NAMES = {"check_compliance_claims.py"}

# Each: (compiled pattern, human explanation)
BANNED = [
    (
        re.compile(r"EU\s+AI\s+Act\s+Ready", re.I),
        '"EU AI Act Ready" — implies a formal status; there is no readiness scheme to hold.',
    ),
    (
        re.compile(r"AI\s+Act[^.\n]{0,40}\b(compliant|compliance guarantee|certified|certification)\b", re.I),
        'claims EU AI Act compliance/certification — no such certification scheme exists.',
    ),
    (
        re.compile(r"\b(compliant|certified|conformant)\s+with\s+the\s+EU\s+AI\s+Act", re.I),
        'claims EU AI Act compliance — we hold no such status.',
    ),
    (
        re.compile(r"(ReloPass|we|our\s+\w+)\s+(is|are)\s+a?\s*[\"“']?high[- ]risk", re.I),
        'classifies ReloPass as high-risk — the AIQ-1487 assessment found limited-risk, NOT high-risk.',
    ),
    (
        re.compile(r"the\s+Art\.?\s*14\s+evidence\s+high[- ]risk", re.I),
        'implies ReloPass is a high-risk HR system (Art. 14 framing) — it is not.',
    ),
    # Caught nothing until a real miss proved it necessary: the /compliance meta
    # description shipped "the EU AI Act controls for high-risk HR AI", which reads as
    # our own classification without ever saying "ReloPass is". Match the possessive
    # framing too — this string is syndicated to search results and link previews.
    (
        re.compile(r"(our|ReloPass[’'s]*|the)\s+[^.\n]{0,40}high[- ]risk\s+(HR\s+)?AI", re.I),
        'describes ReloPass\'s AI as high-risk — the assessment found limited-risk, NOT high-risk.',
    ),
]

# A banned phrase inside a code comment is not shipped to a user — and the files that
# FORBID these phrases must be able to quote them. Skip comment lines so the guard does
# not flag the very rule that enforces it (and so a doc-block can cite the assessment).
_COMMENT_PREFIXES = ("*", "//", "/*", "<!--", "#")


def iter_files():
    for base in SCAN_DIRS:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SCAN_SUFFIXES:
                continue
            posix = path.as_posix()
            if any(part in posix for part in EXEMPT_PARTS) or path.name in EXEMPT_NAMES:
                continue
            yield path


def main() -> int:
    violations = []
    for path in iter_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.lstrip()
            # Markdown/MDX prose IS shipped copy, so `#` there is a heading, not a comment.
            prefixes = _COMMENT_PREFIXES
            if path.suffix.lower() in {".md", ".mdx"}:
                prefixes = tuple(p for p in _COMMENT_PREFIXES if p != "#")
            if stripped.startswith(prefixes):
                continue
            for pattern, why in BANNED:
                if pattern.search(line):
                    violations.append((path.relative_to(REPO), lineno, line.strip()[:110], why))

    if not violations:
        print("[compliance-claims] OK — no EU AI Act status claims in shipped copy.")
        return 0

    print(f"[compliance-claims] FAIL — {len(violations)} prohibited compliance claim(s):\n")
    for rel, lineno, snippet, why in violations:
        print(f"  {rel}:{lineno}")
        print(f"    {snippet}")
        print(f"    ↳ {why}\n")
    print("Per docs/compliance/AIQ-1487_eu_ai_act_assessment.md:")
    print('  "A false or premature compliance claim is itself a legal liability."\n')
    print("Describe what the controls DO (human review, audit log, PII masking).")
    print("Do not claim a regulatory STATUS. A new claim needs legal sign-off first.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
