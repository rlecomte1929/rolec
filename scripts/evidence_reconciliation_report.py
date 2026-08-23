#!/usr/bin/env python3
"""Evidence scoreboard — how many served facts carry a quote that is really in their source.

Reads through `fact_evidence.normalise`, the ONE quote normaliser, rather than re-expressing it
in SQL. The SQL version of this census (`scripts/sql/evidence_reconciliation_report.sql`) drifted
from that definition twice in a single day and under-verified 12 facts between them; it is kept
only as a readable sketch and is marked superseded.

Which source column: `knowledge_docs` carries two and neither is reliably fuller — across the
corpus the excerpt wins, but the enterprise.gov.ie permit pages hold the real page in
`text_content` and 308 characters of cookie banner in the excerpt. `best_source_text` takes the
longer, and this report goes through it for the same reason the review queue does.

Usage:  ./.venv311/bin/python scripts/evidence_reconciliation_report.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text  # noqa: E402

from backend.app.services.fact_evidence import (  # noqa: E402
    best_source_text,
    check_evidence,
    NO_SOURCE,
    VERIFIED,
)
from backend.db_config import (  # noqa: E402
    DATABASE_URL,
    get_masked_db_log_line,
    sqlalchemy_engine_kwargs,
)

SERVED = """
    SELECT e.destination_country, f.fact_key, f.evidence_quote,
           k.content_excerpt, k.text_content
      FROM requirement_facts f
      JOIN requirement_entities e ON e.id = f.entity_id
      LEFT JOIN knowledge_docs k ON k.id = f.source_doc_id
     WHERE f.status = 'approved' AND COALESCE(f.evidence_verified, TRUE) = TRUE
"""


def main() -> int:
    print("target:", get_masked_db_log_line())
    eng = create_engine(DATABASE_URL, **sqlalchemy_engine_kwargs(DATABASE_URL))
    tally: Counter = Counter()
    by_country: dict = {}
    with eng.connect() as c:
        for dest, key, quote, excerpt, body in c.execute(text(SERVED)):
            source = best_source_text(excerpt, body)
            check = check_evidence(quote, source)
            if check.status == VERIFIED:
                verdict = "EVIDENCED"
            elif check.status == NO_SOURCE:
                verdict = "no usable source archived"
            elif not (quote or "").strip():
                verdict = "no quote to check"
            else:
                verdict = "quote not in source"
            tally[verdict] += 1
            by_country.setdefault(verdict, set()).add(dest)

    total = sum(tally.values())
    print(f"\n{total} served fact(s)\n")
    for verdict, n in tally.most_common():
        dests = " ".join(sorted(by_country[verdict]))
        print(f"  {n:>4}  {100.0 * n / total:5.1f}%  {verdict:<26} {dests}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
