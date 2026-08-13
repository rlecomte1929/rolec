#!/usr/bin/env python3
"""
ReloPass data-integration & RFQ eval harness.

Read-only. Executes SELECT statements only — it never writes to the database,
never creates an RFQ, never applies a migration.

Asserts the invariants defined in ReloPass_Data_Integration_Audit_2026-08-13.md §4.
Every eval maps to a spec id (S1..S15) and a finding id (F-1..F-10).

Usage
-----
    export DATABASE_URL='postgresql://user:pass@host:5432/postgres'
        # NOTE: session mode (port 5432). The transaction pooler (6543) breaks
        # on repeated prepared statements — see CLAUDE.md.
    export RELOPASS_REPO=/path/to/rolec      # optional; defaults to cwd

    python relopass_integration_evals.py                    # everything
    python relopass_integration_evals.py --corridor FR-NO   # one corridor
    python relopass_integration_evals.py --suite A,B        # subset
    python relopass_integration_evals.py --json out.json    # machine-readable
    python relopass_integration_evals.py --baseline evals_baseline.json
                                                            # diff vs baseline;
                                                            # fail only on NEW breakage

    pytest relopass_integration_evals.py -v                 # CI mode

Exit codes
----------
    0  all selected evals passed (or matched the baseline, with --baseline)
    1  at least one eval failed
    2  harness could not run (no DATABASE_URL, repo not found, etc.)

Dependencies: psycopg2-binary (or psycopg[binary]). Nothing else.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

#: Corridors to evaluate. Extend as coverage grows.
CORRIDORS: Dict[str, Dict[str, str]] = {
    "FR-NO": {"origin": "FR", "dest": "NO", "dest_city": "Oslo"},
    "NO-FR": {"origin": "NO", "dest": "FR", "dest_city": "Paris"},
}

#: Thresholds. Tighten these as the platform improves — that is the point.
THRESHOLDS = {
    "slate_geo_precision_min": 1.00,      # S1  — no wrong-geography vendor, ever
    "curation_geo_validity_min": 1.00,    # S4
    "profiles_null_company_max": 0.05,    # S6  — 5% tolerance for genuine admin rows
    "catalog_rfq_reachability_min": 1.00,  # S11
    "stalled_rfq_ratio_max": 0.90,        # S8-adjacent — not everything may sit at 'sent'
    "stalled_rfq_age_days": 14,
}

#: Names that appear in the Singapore demo datasets. Used by B3 as a canary:
#: if any of these is served to a non-SG destination, the geo gate is not working.
SG_DEMO_CANARIES = {
    "movers": {
        "Asian Tigers", "Crown Relocations", "Shalom Movers", "Santa Fe Relocation",
        "Leo's Moving", "Allied Pickfords", "Movers.sg", "Pacific Relocations",
        "Transworld Relocation", "JK Movers",
    },
    "banks": {"DBS", "OCBC", "UOB"},
    "telecom": {"Singtel", "StarHub", "M1"},
    "electricity": {"SP Group", "Tuas Power", "Geneco", "Senoko Energy"},
    "medical": {"Raffles Medical", "Parkway Health", "Mount Elizabeth", "Gleneagles"},
    "insurance": {"AIA Singapore"},
    "tax_finance": {"KPMG Singapore"},
    "legal_admin": {"Quahe Woo & Palmer", "Dentons Rodyk"},
    "storage": {"Lock+Store", "Extra Space Asia"},
    "transport": {"ComfortDelGro Driving Centre", "SSDC"},
    "language_integration": {"British Council Singapore"},
    "childcare": {"EtonHouse", "Cherrybrook", "MindChamps"},
}

#: Continents the product sells into. S3 checks the scorer covers all of them.
REQUIRED_REGION_KEYWORDS = {"europe", "asia", "america", "africa", "oceania"}


# --------------------------------------------------------------------------
# Result plumbing
# --------------------------------------------------------------------------

@dataclass
class EvalResult:
    eval_id: str
    suite: str
    spec: str
    finding: str
    title: str
    passed: bool
    observed: Any = None
    expected: Any = None
    detail: str = ""
    rows: List[Dict[str, Any]] = field(default_factory=list)
    skipped: bool = False

    def line(self) -> str:
        if self.skipped:
            mark, colour = "SKIP", "\033[90m"
        elif self.passed:
            mark, colour = "PASS", "\033[32m"
        else:
            mark, colour = "FAIL", "\033[31m"
        reset = "\033[0m" if sys.stdout.isatty() else ""
        colour = colour if sys.stdout.isatty() else ""
        head = f"{colour}[{mark}]{reset} {self.eval_id} ({self.spec}/{self.finding}) {self.title}"
        if self.skipped:
            return f"{head}\n         {self.detail}"
        if not self.passed:
            body = f"\n         observed: {self.observed}\n         expected: {self.expected}"
            if self.detail:
                body += f"\n         {self.detail}"
            for r in self.rows[:5]:
                body += f"\n           · {r}"
            if len(self.rows) > 5:
                body += f"\n           · … {len(self.rows) - 5} more"
            return head + body
        return head


class Harness:
    def __init__(self, conn, repo: Path, corridors: Dict[str, Dict[str, str]]):
        self.conn = conn
        self.repo = repo
        self.corridors = corridors
        self.results: List[EvalResult] = []

    # -- helpers ---------------------------------------------------------

    def q(self, sql: str, params: Optional[dict] = None) -> List[Dict[str, Any]]:
        """Run a read-only query. Refuses anything that is not a SELECT/WITH."""
        head = sql.lstrip().lstrip("-").lstrip().lower()
        if not (head.startswith("select") or head.startswith("with")):
            raise RuntimeError(f"Harness is read-only; refused: {sql[:60]!r}")
        with self.conn.cursor() as cur:
            cur.execute(sql, params or {})
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def record(self, r: EvalResult) -> EvalResult:
        self.results.append(r)
        return r

    def skip(self, eval_id, suite, spec, finding, title, why) -> EvalResult:
        return self.record(EvalResult(eval_id, suite, spec, finding, title,
                                      passed=True, skipped=True, detail=why))

    def datasets_dir(self) -> Optional[Path]:
        d = self.repo / "backend" / "app" / "recommendations" / "datasets"
        return d if d.is_dir() else None

    # ==================================================================
    # SUITE A — static dataset hygiene (no DB)
    # ==================================================================

    def a1_datasets_have_geo(self) -> EvalResult:
        """S2 / F-1: every dataset row declares a country or explicit global coverage."""
        d = self.datasets_dir()
        if d is None:
            return self.skip("A1", "A", "S2", "F-1", "Dataset rows declare geography",
                             f"datasets dir not found under {self.repo}")
        offenders = []
        total = bad = 0
        for path in sorted(d.glob("*.json")):
            try:
                rows = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:                       # noqa: BLE001
                offenders.append({"file": path.name, "error": str(exc)})
                continue
            if isinstance(rows, dict):
                rows = rows.get("items", [])
            file_bad = 0
            for row in rows:
                if not isinstance(row, dict):
                    continue
                total += 1
                has_geo = bool(row.get("country") or row.get("city"))
                explicit_global = row.get("global_coverage") is True
                if not has_geo and not explicit_global:
                    file_bad += 1
                    bad += 1
            if file_bad:
                offenders.append({"file": path.name, "rows_without_geo": file_bad,
                                  "rows_total": len(rows)})
        return self.record(EvalResult(
            "A1", "A", "S2", "F-1", "Dataset rows declare geography",
            passed=(bad == 0), observed=f"{bad}/{total} rows lack country/city and global_coverage",
            expected="0 rows without geography",
            detail="Rows with no geo metadata are admitted to every corridor by "
                   "_load_dataset_with_registry. Add `country` (ISO2) or `global_coverage: true`.",
            rows=offenders))

    def a2_no_single_country_datasets(self) -> EvalResult:
        """S2 / F-1: a dataset whose every located row is one country is demo residue."""
        d = self.datasets_dir()
        if d is None:
            return self.skip("A2", "A", "S2", "F-1", "No single-country demo datasets",
                             "datasets dir not found")
        offenders = []
        for path in sorted(d.glob("*.json")):
            try:
                rows = json.loads(path.read_text(encoding="utf-8"))
            except Exception:                              # noqa: BLE001
                continue
            if isinstance(rows, dict):
                rows = rows.get("items", [])
            countries = {r.get("country") for r in rows
                         if isinstance(r, dict) and r.get("country")}
            named = SG_DEMO_CANARIES.get(path.stem, set())
            hits = {r.get("name") for r in rows
                    if isinstance(r, dict) and r.get("name") in named}
            if len(countries) == 1 and len(rows) > 1:
                offenders.append({"file": path.name, "only_country": countries.pop(),
                                  "rows": len(rows)})
            elif hits and not countries:
                offenders.append({"file": path.name, "rows": len(rows),
                                  "known_SG_demo_rows": sorted(hits)[:5],
                                  "declared_countries": 0})
        return self.record(EvalResult(
            "A2", "A", "S2", "F-1", "No single-country demo datasets",
            passed=(not offenders),
            observed=f"{len(offenders)} dataset(s) are effectively single-country",
            expected="0", rows=offenders,
            detail="Single-country seed data leaks into every other corridor."))

    def a3_service_area_regions(self) -> EvalResult:
        """S3 / F-1: the mover service-area scorer must not favour one continent."""
        p = self.repo / "backend" / "app" / "recommendations" / "plugins" / "movers.py"
        if not p.is_file():
            return self.skip("A3", "A", "S3", "F-1", "Service-area scorer covers all regions",
                             f"{p} not found")
        src = p.read_text(encoding="utf-8")
        found = {kw for kw in REQUIRED_REGION_KEYWORDS
                 if re.search(rf'["\'][^"\']*{kw}[^"\']*["\']', src, re.I)}
        missing = sorted(REQUIRED_REGION_KEYWORDS - found)
        return self.record(EvalResult(
            "A3", "A", "S3", "F-1", "Service-area scorer covers all regions",
            passed=(not missing), observed=f"missing region keywords: {missing}",
            expected="all of " + ", ".join(sorted(REQUIRED_REGION_KEYWORDS)),
            detail="_service_area_score currently tiers only Asia keywords at 75; "
                   "a Europe-covering mover falls through to 20 for an Oslo move."))

    # ==================================================================
    # SUITE B — slate geo-precision  (the F-1 regression test)
    # ==================================================================

    def b1_slate_geo_precision(self, corridor: str) -> EvalResult:
        """S1 / F-1: every served slate item is geo-valid for the case destination."""
        cfg = self.corridors[corridor]
        rows = self.q("""
            with served as (
              select rs.category,
                     rs.case_id,
                     jsonb_array_elements(rs.items_json) as it
              from recommendation_slates rs
              join relocation_cases rc on rc.id::text = rs.case_id
              where rc.corridor = %(corridor)s
            ),
            resolved as (
              select s.category,
                     s.case_id,
                     s.it->>'name' as vendor_name,
                     sci.country   as item_country,
                     sci.city      as item_city
              from served s
              left join service_catalog_items sci
                     on sci.name = s.it->>'name'
                    and sci.category = s.category
            )
            select category, vendor_name, item_country, item_city, count(*) as impressions,
                   count(distinct case_id) as cases
            from resolved
            group by 1,2,3,4
        """, {"corridor": corridor})
        if not rows:
            return self.skip(f"B1[{corridor}]", "B", "S1", "F-1",
                             f"Slate geo-precision — {corridor}",
                             "no recommendation_slates for this corridor")
        total = sum(r["impressions"] for r in rows)
        bad = [r for r in rows
               if r["item_country"] is not None
               and r["item_country"] != cfg["dest"]
               and (r["item_city"] or "") != cfg["dest_city"]]
        bad_n = sum(r["impressions"] for r in bad)
        precision = (total - bad_n) / total if total else 1.0
        return self.record(EvalResult(
            f"B1[{corridor}]", "B", "S1", "F-1", f"Slate geo-precision — {corridor}",
            passed=(precision >= THRESHOLDS["slate_geo_precision_min"]),
            observed=f"{precision:.1%} ({total - bad_n}/{total} impressions geo-valid)",
            expected=f">= {THRESHOLDS['slate_geo_precision_min']:.0%}",
            rows=[{"category": r["category"], "vendor": r["vendor_name"],
                   "located_in": f"{r['item_city'] or '-'}/{r['item_country']}",
                   "impressions": r["impressions"], "cases": r["cases"]}
                  for r in sorted(bad, key=lambda x: -x["impressions"])],
            detail=f"Destination is {cfg['dest_city']}/{cfg['dest']}. Items resolving to "
                   "another country were still served."))

    def b3_sg_canaries(self, corridor: str) -> EvalResult:
        """S1 / F-1: no Singapore demo vendor is ever served to a non-SG destination."""
        cfg = self.corridors[corridor]
        if cfg["dest"] == "SG":
            return self.skip(f"B3[{corridor}]", "B", "S1", "F-1",
                             f"No SG demo vendors — {corridor}", "destination is SG")
        names = sorted({n for s in SG_DEMO_CANARIES.values() for n in s})
        rows = self.q("""
            select rs.category,
                   jsonb_array_elements(rs.items_json)->>'name' as vendor_name,
                   count(*) over () as _ignore
            from recommendation_slates rs
            join relocation_cases rc on rc.id::text = rs.case_id
            where rc.corridor = %(corridor)s
        """, {"corridor": corridor})
        hits: Dict[tuple, int] = {}
        for r in rows:
            if r["vendor_name"] in names:
                hits[(r["category"], r["vendor_name"])] = \
                    hits.get((r["category"], r["vendor_name"]), 0) + 1
        return self.record(EvalResult(
            f"B3[{corridor}]", "B", "S1", "F-1", f"No SG demo vendors — {corridor}",
            passed=(not hits), observed=f"{sum(hits.values())} impressions of SG demo vendors",
            expected="0",
            rows=[{"category": k[0], "vendor": k[1], "impressions": v}
                  for k, v in sorted(hits.items(), key=lambda kv: -kv[1])],
            detail="These names come from backend/app/recommendations/datasets/*.json "
                   "(Singapore demo seed). Their presence proves the geo gate is missing."))

    # ==================================================================
    # SUITE C — curation integrity
    # ==================================================================

    def c1_curation_geo_validity(self) -> EvalResult:
        """S4 / F-2: a selection's country matches the catalog item it points at."""
        rows = self.q("""
            select v.country as selection_country,
                   s.country as item_country,
                   s.city    as item_city,
                   s.name    as item_name,
                   count(*)  as rows_,
                   count(distinct v.company_id) as companies
            from company_vendor_selections v
            join service_catalog_items s on s.id = v.master_item_id
            where v.selected
              and v.country is not null
              and s.country is not null
              and v.country <> s.country
            group by 1,2,3,4
            order by 5 desc
        """)
        total = self.q("select count(*) as n from company_vendor_selections where selected")[0]["n"]
        bad = sum(r["rows_"] for r in rows)
        validity = (total - bad) / total if total else 1.0
        return self.record(EvalResult(
            "C1", "C", "S4", "F-2", "HR approvals are geographically valid",
            passed=(validity >= THRESHOLDS["curation_geo_validity_min"]),
            observed=f"{validity:.1%} valid ({bad}/{total} rows point at another country)",
            expected=f">= {THRESHOLDS['curation_geo_validity_min']:.0%}",
            rows=[{"approved_as": r["selection_country"], "vendor": r["item_name"],
                   "actually_in": f"{r['item_city'] or '-'}/{r['item_country']}",
                   "rows": r["rows_"], "companies": r["companies"]} for r in rows]))

    def c2_curation_company_fk(self) -> EvalResult:
        """S7 / F-8: every curation row belongs to a real company."""
        rows = self.q("""
            select count(*) as orphans
            from company_vendor_selections v
            left join companies c on c.id = v.company_id
            where c.id is null
        """)
        n = rows[0]["orphans"]
        return self.record(EvalResult(
            "C2", "C", "S7", "F-8", "Curation rows resolve to a company",
            passed=(n == 0), observed=f"{n} orphan rows", expected="0",
            detail="company_vendor_selections.company_id with no matching companies row."))

    def c3_multi_country_curation(self) -> EvalResult:
        """S5 / F-3: guards the latent cross-country bleed in list_curation()."""
        rows = self.q("""
            select company_id::text as company_id,
                   count(distinct country) as countries,
                   string_agg(distinct country, ',') as which
            from company_vendor_selections
            where selected and country is not null
            group by 1
            having count(distinct country) > 1
        """)
        return self.record(EvalResult(
            "C3", "C", "S5", "F-3", "No company curates across countries while country is unfiltered",
            passed=(not rows), observed=f"{len(rows)} companies span >1 country", expected="0",
            rows=rows,
            detail="list_curation() filters on company_id + category only; country is never a "
                   "predicate and destination_city IS NULL matches every city. Any company here "
                   "will show its other-country vendors on this corridor."))

    def c4_profiles_without_company(self) -> EvalResult:
        """S6 / F-5: a null company_id skips apply_hr_curation entirely."""
        r = self.q("""
            select count(*) filter (where company_id is null) as nulls,
                   count(*) as total
            from profiles
        """)[0]
        ratio = r["nulls"] / r["total"] if r["total"] else 0.0
        return self.record(EvalResult(
            "C4", "C", "S6", "F-5", "Profiles resolve to a company (curation cannot be bypassed)",
            passed=(ratio <= THRESHOLDS["profiles_null_company_max"]),
            observed=f"{ratio:.1%} ({r['nulls']}/{r['total']}) profiles have company_id NULL",
            expected=f"<= {THRESHOLDS['profiles_null_company_max']:.0%}",
            detail="engine.py:302 `will_curate = bool(company_id) and ...` — a null company_id "
                   "returns the FULL un-curated master catalog. Fail closed instead."))

    # ==================================================================
    # SUITE D — RFQ integrity
    # ==================================================================

    def d1_rfq_has_items(self) -> EvalResult:
        """S8 / F-6: an RFQ with recipients but no service line is meaningless."""
        rows = self.q("""
            select r.id::text, r.rfq_ref, r.status,
                   (select count(*) from rfq_recipients rc where rc.rfq_id = r.id) as recipients
            from rfqs r
            where not exists (select 1 from rfq_items i where i.rfq_id = r.id)
        """)
        return self.record(EvalResult(
            "D1", "D", "S8", "F-6", "Every RFQ has at least one item",
            passed=(not rows), observed=f"{len(rows)} RFQs with 0 items", expected="0",
            rows=rows,
            detail="Suppliers were emailed a quote request with no service on it."))

    def d2_recipient_vendor_fk(self) -> EvalResult:
        """S9 / F-8: rfq_recipients.vendor_id resolves to suppliers.id."""
        n = self.q("""
            select count(*) as n
            from rfq_recipients r
            left join suppliers s on s.id = r.vendor_id
            where s.id is null
        """)[0]["n"]
        return self.record(EvalResult(
            "D2", "D", "S9", "F-8", "RFQ recipients resolve to a supplier",
            passed=(n == 0), observed=f"{n} unresolvable", expected="0"))

    def d3_quote_vendor_fk(self) -> EvalResult:
        """S9 / F-8: quotes.vendor_id resolves to suppliers.id."""
        n = self.q("""
            select count(*) as n
            from quotes q
            left join suppliers s on s.id = q.vendor_id
            where s.id is null
        """)[0]["n"]
        return self.record(EvalResult(
            "D3", "D", "S9", "F-8", "Quotes resolve to a supplier",
            passed=(n == 0), observed=f"{n} unresolvable", expected="0"))

    def d4_catalog_rfq_reachable(self) -> EvalResult:
        """S11 / F-9: an employee cannot pick a vendor we cannot email."""
        r = self.q("""
            select count(*) filter (where supplier_id is null) as unreachable,
                   count(*) as total
            from service_catalog_items
            where active
        """)[0]
        ratio = (r["total"] - r["unreachable"]) / r["total"] if r["total"] else 1.0
        return self.record(EvalResult(
            "D4", "D", "S11", "F-9", "Active catalog items are RFQ-reachable",
            passed=(ratio >= THRESHOLDS["catalog_rfq_reachability_min"]),
            observed=f"{ratio:.1%} reachable ({r['unreachable']}/{r['total']} have supplier_id NULL)",
            expected=f">= {THRESHOLDS['catalog_rfq_reachability_min']:.0%}",
            detail="resolve_recipient_ids() walks external_id → supplier_id → suppliers.id. "
                   "A NULL supplier_id yields 'it is not a supplier we can reach.'"))

    def d5_rfq_funnel_moves(self) -> EvalResult:
        """S10-adjacent / F-6: RFQs must not all be frozen at 'sent'."""
        r = self.q("""
            select count(*) as aged,
                   count(*) filter (where status = 'sent') as still_sent,
                   count(*) filter (where validated_quote_id is not null) as awarded,
                   count(*) filter (where was_recommended is not null) as attributed
            from rfqs
            where created_at < now() - interval '%s days'
        """ % int(THRESHOLDS["stalled_rfq_age_days"]))[0]
        if not r["aged"]:
            return self.skip("D5", "D", "S10", "F-6", "RFQ funnel progresses past 'sent'",
                             "no RFQs older than the stall window")
        ratio = r["still_sent"] / r["aged"]
        return self.record(EvalResult(
            "D5", "D", "S10", "F-6", "RFQ funnel progresses past 'sent'",
            passed=(ratio <= THRESHOLDS["stalled_rfq_ratio_max"]),
            observed=(f"{ratio:.0%} of {r['aged']} aged RFQs still 'sent'; "
                      f"{r['awarded']} awarded; {r['attributed']} carry was_recommended"),
            expected=f"<= {THRESHOLDS['stalled_rfq_ratio_max']:.0%} still 'sent'",
            detail="was_recommended/recommendation_snapshot are never written, so "
                   "recommendation adherence is unmeasurable."))

    # ==================================================================
    # SUITE E — corridor knowledge wiring
    # ==================================================================

    def e1_corridor_reaches_employee(self) -> EvalResult:
        """S12 / F-4: authored corridor content must reach an employee-read table."""
        cdir = self.repo / "corridors"
        if not cdir.is_dir():
            return self.skip("E1", "E", "S12", "F-4", "Corridors reach an employee surface",
                             f"{cdir} not found")
        authored = sorted(p.name for p in cdir.iterdir()
                          if p.is_dir() and (p / "corridor.yaml").is_file())
        offenders = []
        for name in authored:
            try:
                origin, dest = name.split("_", 1)
            except ValueError:
                offenders.append({"corridor": name, "reason": "unparseable dir name"})
                continue
            req = self.q("""
                select count(*) as n from requirement_items
                where upper(coalesce(country_code, country, '')) in (%(d2)s, %(d3)s)
            """, {"d2": dest.upper(), "d3": dest.upper()[:3]}) if self._has_cols(
                "requirement_items", {"country_code", "country"}) else [{"n": 0}]
            imm = self.q("""
                select count(*) as n from immigration_requirements
                where upper(coalesce(corridor_from,'')) = %(o)s
                  and upper(coalesce(corridor_to,''))   = %(d)s
            """, {"o": origin.upper(), "d": dest.upper()})
            if (req[0]["n"] + imm[0]["n"]) == 0:
                offenders.append({"corridor": name,
                                  "requirement_items": req[0]["n"],
                                  "immigration_requirements": imm[0]["n"]})
        return self.record(EvalResult(
            "E1", "E", "S12", "F-4", "Corridors reach an employee surface",
            passed=(not offenders),
            observed=f"{len(offenders)}/{len(authored)} corridors have no employee-visible rows",
            expected="0", rows=offenders,
            detail="corridors/** is written to rce.* by populate_rce_from_cases.py, which is "
                   "not wired to render.yaml, CI, or any cron. Employees read requirement_items "
                   "and immigration_requirements instead."))

    def e2_corridor_yaml_parses(self) -> EvalResult:
        """S13 / F-4: every corridor declares at least one pathway file that exists."""
        cdir = self.repo / "corridors"
        if not cdir.is_dir():
            return self.skip("E2", "E", "S13", "F-4", "Corridor manifests are well-formed",
                             f"{cdir} not found")
        offenders = []
        for p in sorted(cdir.iterdir()):
            y = p / "corridor.yaml"
            if not (p.is_dir() and y.is_file()):
                continue
            text = y.read_text(encoding="utf-8")
            files = re.findall(r'file:\s*["\']?([^"\'\n]+)', text)
            if not files:
                offenders.append({"corridor": p.name, "reason": "no pathway file declared"})
            for f in files:
                if not (p / f.strip()).is_file():
                    offenders.append({"corridor": p.name, "missing_pathway": f.strip()})
        return self.record(EvalResult(
            "E2", "E", "S13", "F-4", "Corridor manifests are well-formed",
            passed=(not offenders), observed=f"{len(offenders)} problems", expected="0",
            rows=offenders))

    # ==================================================================
    # SUITE F — referential integrity (regression guard on what works)
    # ==================================================================

    def f_referential(self) -> List[EvalResult]:
        checks = [
            ("F1", "service_catalog_items.supplier_id → suppliers.id", """
                select count(*) as n from service_catalog_items s
                left join suppliers p on p.id = s.supplier_id
                where s.supplier_id is not null and p.id is null"""),
            ("F2", "supplier_service_capabilities.supplier_id → suppliers.id", """
                select count(*) as n from supplier_service_capabilities c
                left join suppliers p on p.id = c.supplier_id where p.id is null"""),
            ("F3", "company_vendor_selections.master_item_id → service_catalog_items.id", """
                select count(*) as n from company_vendor_selections v
                left join service_catalog_items s on s.id = v.master_item_id
                where v.master_item_id is not null and s.id is null"""),
            ("F4", "suppliers have at least one capability", """
                select count(*) as n from suppliers p
                where not exists (select 1 from supplier_service_capabilities c
                                  where c.supplier_id = p.id)"""),
            ("F5", "supplier_service_capabilities scope is self-consistent", """
                select count(*) as n from supplier_service_capabilities
                where coverage_scope_type = 'country' and city_name is not null"""),
        ]
        out = []
        for eid, title, sql in checks:
            n = self.q(sql)[0]["n"]
            out.append(self.record(EvalResult(
                eid, "F", "S14", "F-8", title,
                passed=(n == 0), observed=f"{n} violations", expected="0")))
        return out

    # -- introspection ---------------------------------------------------

    def _has_cols(self, table: str, cols: set) -> bool:
        rows = self.q("""
            select column_name from information_schema.columns
            where table_schema = 'public' and table_name = %(t)s
        """, {"t": table})
        have = {r["column_name"] for r in rows}
        return bool(have & cols)

    # -- driver ----------------------------------------------------------

    def run(self, suites: Optional[set] = None) -> List[EvalResult]:
        want = (lambda s: suites is None or s in suites)
        if want("A"):
            self.a1_datasets_have_geo()
            self.a2_no_single_country_datasets()
            self.a3_service_area_regions()
        if want("B"):
            for c in self.corridors:
                self.b1_slate_geo_precision(c)
                self.b3_sg_canaries(c)
        if want("C"):
            self.c1_curation_geo_validity()
            self.c2_curation_company_fk()
            self.c3_multi_country_curation()
            self.c4_profiles_without_company()
        if want("D"):
            self.d1_rfq_has_items()
            self.d2_recipient_vendor_fk()
            self.d3_quote_vendor_fk()
            self.d4_catalog_rfq_reachable()
            self.d5_rfq_funnel_moves()
        if want("E"):
            self.e1_corridor_reaches_employee()
            self.e2_corridor_yaml_parses()
        if want("F"):
            self.f_referential()
        return self.results


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def connect(dsn: str):
    try:
        import psycopg2                                    # type: ignore
        conn = psycopg2.connect(dsn)
        conn.set_session(readonly=True, autocommit=True)
        return conn
    except ImportError:
        pass
    try:
        import psycopg                                     # type: ignore
        return psycopg.connect(dsn, autocommit=True)
    except ImportError:
        print("Need psycopg2-binary or psycopg[binary]:  pip install psycopg2-binary",
              file=sys.stderr)
        raise SystemExit(2)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corridor", action="append",
                    help="restrict to a corridor (repeatable), e.g. --corridor FR-NO")
    ap.add_argument("--suite", help="comma-separated suites to run, e.g. A,B,D")
    ap.add_argument("--json", dest="json_out", help="write machine-readable results here")
    ap.add_argument("--baseline", help="baseline JSON; fail only on regressions vs it")
    ap.add_argument("--write-baseline", help="write current results as a new baseline")
    ap.add_argument("--repo", default=os.environ.get("RELOPASS_REPO", "."),
                    help="path to the rolec checkout (default: $RELOPASS_REPO or cwd)")
    args = ap.parse_args(argv)

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        print("DATABASE_URL is not set.\n"
              "  export DATABASE_URL='postgresql://…@…:5432/postgres'   # session mode, port 5432",
              file=sys.stderr)
        return 2
    if ":6543/" in dsn:
        print("warning: port 6543 is the transaction pooler; repeated prepared statements "
              "fail there. Use 5432.", file=sys.stderr)

    repo = Path(args.repo).expanduser().resolve()
    corridors = ({k: v for k, v in CORRIDORS.items() if k in set(args.corridor)}
                 if args.corridor else CORRIDORS)
    if not corridors:
        print(f"No known corridor matched {args.corridor}. Known: {list(CORRIDORS)}",
              file=sys.stderr)
        return 2
    suites = set(s.strip().upper() for s in args.suite.split(",")) if args.suite else None

    conn = connect(dsn)
    try:
        h = Harness(conn, repo, corridors)
        results = h.run(suites)
    finally:
        conn.close()

    print(f"\nReloPass integration evals — repo {repo}\n" + "=" * 72)
    for r in results:
        print(r.line())

    ran = [r for r in results if not r.skipped]
    failed = [r for r in ran if not r.passed]
    skipped = [r for r in results if r.skipped]
    print("=" * 72)
    print(f"{len(ran) - len(failed)}/{len(ran)} passed"
          + (f", {len(skipped)} skipped" if skipped else ""))

    payload = {"results": [asdict(r) for r in results],
               "summary": {"total": len(ran), "passed": len(ran) - len(failed),
                           "failed": len(failed), "skipped": len(skipped)}}

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2, default=str))
        print(f"wrote {args.json_out}")
    if args.write_baseline:
        Path(args.write_baseline).write_text(json.dumps(
            {r.eval_id: r.passed for r in results}, indent=2, sort_keys=True))
        print(f"wrote baseline {args.write_baseline}")

    if args.baseline:
        base = json.loads(Path(args.baseline).read_text())
        regressions = [r.eval_id for r in ran
                       if not r.passed and base.get(r.eval_id, False)]
        fixes = [r.eval_id for r in ran if r.passed and base.get(r.eval_id) is False]
        if fixes:
            print(f"newly passing: {', '.join(fixes)}")
        if regressions:
            print(f"REGRESSIONS vs baseline: {', '.join(regressions)}")
            return 1
        print("no regressions vs baseline")
        return 0

    return 1 if failed else 0


# --------------------------------------------------------------------------
# pytest mode:  pytest relopass_integration_evals.py -v
# --------------------------------------------------------------------------

def _pytest_results():
    import pytest                                          # type: ignore
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        pytest.skip("DATABASE_URL not set", allow_module_level=True)
    conn = connect(dsn)
    h = Harness(conn, Path(os.environ.get("RELOPASS_REPO", ".")).resolve(), CORRIDORS)
    try:
        return h.run()
    finally:
        conn.close()


try:                                                       # pragma: no cover
    import pytest                                          # type: ignore

    @pytest.fixture(scope="module")
    def eval_results():
        return _pytest_results()

    def test_all_evals(eval_results):
        failed = [r for r in eval_results if not r.passed and not r.skipped]
        assert not failed, "\n" + "\n".join(r.line() for r in failed)
except ImportError:                                        # pragma: no cover
    pass


if __name__ == "__main__":
    raise SystemExit(main())
