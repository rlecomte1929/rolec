"""
End-to-end audit: company-scoped policy retrieval, RBAC, citations, and structured rendering.

Run from repo root (after venv + migrations):

  python backend/scripts/audit_policy_assistant.py

PDF paths default to RELOPASS_AUDIT_POLICY_GOPS / RELOPASS_AUDIT_POLICY_LTA, or
--gops-pdf / --lta-pdf. Optional repo-relative fallbacks are tried when env vars are unset.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Match bootstrap_backend_database.py: default SQLite file is backend/relopass.db (not cwd-relative ./relopass.db).
if "DATABASE_URL" not in os.environ:
    _default_db = os.path.abspath(os.path.join(REPO_ROOT, "backend", "relopass.db"))
    os.environ["DATABASE_URL"] = f"sqlite:///{_default_db}"

from sqlalchemy import text

from backend.database import Database, db
from backend.dev_seed_auth import ensure_dev_seed_auth_user
from backend.services.policy_canonical_access import ensure_company_scope_for_write
from backend.services.policy_canonical_chunking import chunk_canonical_policy_document
from backend.services.policy_canonical_extraction import extract_canonical_policy_facts
from backend.services.policy_canonical_ingestion import ingest_canonical_policy_document
from backend.services.policy_query_answering import answer_company_scoped_policy_query
from backend.services.policy_rendering import render_canonical_policy_markdown

from passlib.context import CryptContext

_pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
_AUDIT_PASSWORD_HASH = _pwd.hash("AuditPassw0rd!")

DEFAULT_COMPANY_ACME = "company_acme"
DEFAULT_COMPANY_BETA = "company_beta"


def _default_queries(
    company_acme: str,
    company_beta: str,
) -> List[Tuple[str, str, str]]:
    """(role, company_id, question)."""
    return [
        (
            "EMPLOYEE",
            company_acme,
            "What is the relocation allowance for an assignee with two dependants?",
        ),
        (
            "HR",
            company_acme,
            "What mobility premium applies for a long-term assignment?",
        ),
        (
            "EMPLOYEE",
            company_beta,
            "Is there a COLA and when does it apply?",
        ),
        (
            "HR",
            company_beta,
            "What is the policy on home leave?",
        ),
    ]


def _resolve_pdf_paths(
    gops: Optional[str],
    lta: Optional[str],
) -> Tuple[str, str]:
    env_gops = gops or os.getenv("RELOPASS_AUDIT_POLICY_GOPS")
    env_lta = lta or os.getenv("RELOPASS_AUDIT_POLICY_LTA")
    candidates_gops = [
        env_gops,
        os.path.join(REPO_ROOT, "docs", "samples", "GOPS 12102.pdf"),
        os.path.join(REPO_ROOT, "samples", "GOPS 12102.pdf"),
    ]
    candidates_lta = [
        env_lta,
        os.path.join(REPO_ROOT, "docs", "samples", "Long Term Assignment Policy Summary.pdf"),
        os.path.join(REPO_ROOT, "samples", "Long Term Assignment Policy Summary.pdf"),
    ]
    path_gops = next((p for p in candidates_gops if p and os.path.isfile(p)), None)
    path_lta = next((p for p in candidates_lta if p and os.path.isfile(p)), None)
    if not path_gops or not path_lta:
        raise SystemExit(
            "Could not find audit PDFs. Set RELOPASS_AUDIT_POLICY_GOPS and "
            "RELOPASS_AUDIT_POLICY_LTA to absolute paths, or pass --gops-pdf / --lta-pdf."
        )
    return os.path.abspath(path_gops), os.path.abspath(path_lta)


def _ensure_company_row(database: Database, company_id: str, name: str) -> None:
    if database.get_company(company_id):
        return
    now = __import__("datetime").datetime.utcnow().isoformat()
    if database.engine.dialect.name == "sqlite":
        with database.engine.begin() as conn:
            col_rows = conn.execute(text("PRAGMA table_info(companies)")).fetchall()
            col_names = {r[1] for r in col_rows}
            row: Dict[str, Any] = {"id": company_id, "name": name, "created_at": now}
            if "country" in col_names:
                row["country"] = "SG"
            if "size_band" in col_names:
                row["size_band"] = "1-50"
            if "updated_at" in col_names:
                row["updated_at"] = now
            if "status" in col_names:
                row["status"] = "active"
            if "plan_tier" in col_names:
                row["plan_tier"] = "low"
            keys = [k for k in row if k in col_names]
            vals = {k: row[k] for k in keys}
            qcols = ", ".join(keys)
            qplace = ", ".join(f":{k}" for k in keys)
            conn.execute(text(f"INSERT OR IGNORE INTO companies ({qcols}) VALUES ({qplace})"), vals)
    else:
        database.create_company(company_id, name, "SG", "1-50", "", "", "")


def _seed_users_for_company(
    database: Database,
    *,
    company_id: str,
    label: str,
) -> Dict[str, str]:
    """Returns stable keys hr_id, emp_id for RBAC and query audit."""
    suffix = uuid.uuid4().hex[:8]
    hr_email = f"audit-{label}-hr-{suffix}@policy-audit.local"
    emp_email = f"audit-{label}-emp-{suffix}@policy-audit.local"
    hr_id = str(uuid.uuid4())
    emp_id = str(uuid.uuid4())
    hr_id = ensure_dev_seed_auth_user(
        database,
        user_id=hr_id,
        email=hr_email,
        password_hash=_AUDIT_PASSWORD_HASH,
        role="HR",
        name=f"Audit HR {label}",
    )
    emp_id = ensure_dev_seed_auth_user(
        database,
        user_id=emp_id,
        email=emp_email,
        password_hash=_AUDIT_PASSWORD_HASH,
        role="EMPLOYEE",
        name=f"Audit Employee {label}",
    )
    database.ensure_profile_record(hr_id, hr_email, "HR", f"Audit HR {label}", company_id)
    database.ensure_profile_record(emp_id, emp_email, "EMPLOYEE", f"Audit Employee {label}", company_id)
    try:
        database.create_hr_user(str(uuid.uuid4()), company_id, hr_id, {"can_manage_policy": True})
    except Exception:
        pass
    return {"hr_id": hr_id, "emp_id": emp_id}


def _seed_company_policy(
    database: Database,
    company_id: str,
    file_path: str,
    *,
    use_fallback: bool,
) -> Dict[str, Any]:
    document = ingest_canonical_policy_document(
        database,
        company_id=company_id,
        file_path=file_path,
        mime_type="application/pdf",
    )
    chunk_canonical_policy_document(database, str(document["id"]))
    extract_canonical_policy_facts(database, str(document["id"]), use_fallback=use_fallback)
    return database.get_canonical_policy_document(str(document["id"])) or document


def chunk_company_ids(
    database: Database,
    chunk_ids: Sequence[str],
) -> Dict[str, Optional[str]]:
    """Map chunk id -> company_id from canonical_policy_document_chunks."""
    out: Dict[str, Optional[str]] = {}
    with database.engine.connect() as conn:
        for cid in chunk_ids:
            row = conn.execute(
                text("SELECT company_id FROM canonical_policy_document_chunks WHERE id = :id"),
                {"id": cid},
            ).fetchone()
            out[cid] = str(row._mapping["company_id"]) if row else None
    return out


def cross_tenant_leaks_for_user_company(
    expected_company_id: str,
    chunk_ids: Sequence[str],
    id_to_company: Dict[str, Optional[str]],
) -> List[Dict[str, Any]]:
    leaks: List[Dict[str, Any]] = []
    for cid in chunk_ids:
        got = id_to_company.get(cid)
        if got is None or str(got) != str(expected_company_id):
            leaks.append(
                {
                    "chunk_id": cid,
                    "expected_company_id": expected_company_id,
                    "actual_company_id": got,
                }
            )
    return leaks


def run_rbac_checks(
    database: Database,
    *,
    company_acme: str,
    company_beta: str,
    users_acme: Dict[str, str],
    users_beta: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Employees must not pass ensure_company_scope_for_write; HR same-company must."""
    results: List[Dict[str, Any]] = []

    def _expect_403(user: Dict[str, Any], target_cid: str, label: str) -> None:
        from fastapi import HTTPException

        try:
            ensure_company_scope_for_write(user, target_cid, database)
            results.append({"check": label, "ok": False, "detail": "expected HTTPException, got success"})
        except HTTPException as exc:
            ok = exc.status_code == 403
            results.append({"check": label, "ok": ok, "status_code": exc.status_code, "detail": exc.detail})

    def _expect_ok(user: Dict[str, Any], target_cid: str, label: str) -> None:
        from fastapi import HTTPException

        try:
            ensure_company_scope_for_write(user, target_cid, database)
            results.append({"check": label, "ok": True})
        except HTTPException as exc:
            results.append({"check": label, "ok": False, "status_code": exc.status_code, "detail": exc.detail})

    _expect_403(
        {"id": users_acme["emp_id"], "role": "EMPLOYEE"},
        company_acme,
        "employee_cannot_write_same_company",
    )
    _expect_403(
        {"id": users_acme["hr_id"], "role": "HR"},
        company_beta,
        "hr_cannot_write_other_company",
    )
    _expect_ok(
        {"id": users_acme["hr_id"], "role": "HR"},
        company_acme,
        "hr_acme_can_write_own_company",
    )
    _expect_ok(
        {"id": users_beta["hr_id"], "role": "HR"},
        company_beta,
        "hr_beta_can_write_own_company",
    )
    _expect_403(
        {"id": users_beta["emp_id"], "role": "EMPLOYEE"},
        company_beta,
        "employee_beta_cannot_write_same_company",
    )
    return results


def run_policy_assistant_audit(
    database: Database,
    *,
    company_acme: str = DEFAULT_COMPANY_ACME,
    company_beta: str = DEFAULT_COMPANY_BETA,
    pdf_acme: Optional[str] = None,
    pdf_beta: Optional[str] = None,
    queries: Optional[List[Tuple[str, str, str]]] = None,
    use_fallback: bool = True,
    seed_tenants: bool = True,
) -> Dict[str, Any]:
    """
    Ingest policies per company, run representative queries, validate chunk company_id,
    RBAC, and render previews.
    """
    if not database.canonical_policy_tables_available():
        raise RuntimeError(
            "Canonical policy tables are missing. Run: PYTHONPATH=. python "
            "backend/scripts/bootstrap_backend_database.py"
        )
    queries = queries or _default_queries(company_acme, company_beta)
    report: Dict[str, Any] = {
        "companies": {},
        "queries": [],
        "rbac": [],
        "summary": {
            "queries_run": 0,
            "answers_returned": 0,
            "query_errors": 0,
            "validation_failures": 0,
            "cross_company_retrievals": 0,
            "rbac_failures": 0,
        },
    }

    users_acme: Dict[str, str] = {}
    users_beta: Dict[str, str] = {}

    if seed_tenants:
        if not pdf_acme or not pdf_beta:
            raise ValueError("pdf_acme and pdf_beta are required when seed_tenants=True")
        _ensure_company_row(database, company_acme, "Audit Acme")
        _ensure_company_row(database, company_beta, "Audit Beta")
        users_acme = _seed_users_for_company(database, company_id=company_acme, label="acme")
        users_beta = _seed_users_for_company(database, company_id=company_beta, label="beta")

        doc_acme = _seed_company_policy(database, company_acme, pdf_acme, use_fallback=use_fallback)
        doc_beta = _seed_company_policy(database, company_beta, pdf_beta, use_fallback=use_fallback)
    else:
        doc_acme = database.get_active_canonical_policy_document_for_company(company_acme)
        doc_beta = database.get_active_canonical_policy_document_for_company(company_beta)
        if not doc_acme or not doc_beta:
            raise RuntimeError("seed_tenants=False requires existing canonical documents for both companies.")

    for company_id, document in (
        (company_acme, doc_acme),
        (company_beta, doc_beta),
    ):
        facts = database.list_canonical_policy_facts(str(document["id"]), company_id=company_id)
        report["companies"][company_id] = {
            "document_id": document["id"],
            "title": document.get("title"),
            "filename": document.get("filename"),
            "render_preview_chars": 500,
            "render_preview": render_canonical_policy_markdown(document, facts)[:500],
        }

    if seed_tenants and users_acme and users_beta:
        report["rbac"] = run_rbac_checks(
            database,
            company_acme=company_acme,
            company_beta=company_beta,
            users_acme=users_acme,
            users_beta=users_beta,
        )
        report["summary"]["rbac_failures"] = sum(1 for row in report["rbac"] if not row.get("ok"))

    user_by_company_role: Dict[Tuple[str, str], str] = {}
    if users_acme:
        user_by_company_role[(company_acme, "HR")] = users_acme["hr_id"]
        user_by_company_role[(company_acme, "EMPLOYEE")] = users_acme["emp_id"]
    if users_beta:
        user_by_company_role[(company_beta, "HR")] = users_beta["hr_id"]
        user_by_company_role[(company_beta, "EMPLOYEE")] = users_beta["emp_id"]

    for role, company_id, question in queries:
        report["summary"]["queries_run"] += 1
        uid = user_by_company_role.get((company_id, role))
        if not uid:
            uid = f"audit-fallback-{company_id}-{role.lower()}"
        err: Optional[str] = None
        answer = ""
        citations: List[str] = []
        retrieved_ids: List[str] = []
        try:
            result = answer_company_scoped_policy_query(
                database,
                company_id=company_id,
                user_id=uid,
                user_role=role,
                query=question,
            )
            answer = str(result.get("answer") or "")
            citations = list(result.get("citations") or [])
            retrieved_ids = list(result.get("retrieved_chunk_ids") or [])
            report["summary"]["answers_returned"] += 1
        except Exception as exc:  # noqa: BLE001 — audit harness surfaces all failures
            err = str(exc)
            report["summary"]["query_errors"] += 1

        id_map = chunk_company_ids(database, retrieved_ids)
        leaks = cross_tenant_leaks_for_user_company(company_id, retrieved_ids, id_map)
        if leaks:
            report["summary"]["cross_company_retrievals"] += len(leaks)
            report["summary"]["validation_failures"] += 1

        report["queries"].append(
            {
                "role": role,
                "company_id": company_id,
                "user_id": uid,
                "question": question,
                "error": err,
                "answer_preview": answer[:320] if answer else "",
                "citations": citations,
                "retrieved_chunk_ids": retrieved_ids,
                "chunk_company_ids": id_map,
                "cross_tenant_leakage": leaks,
            }
        )

    return report


def _print_summary(report: Dict[str, Any]) -> None:
    s = report["summary"]
    print("")
    print("=== Policy assistant audit summary ===")
    print(f"  Queries run:              {s['queries_run']}")
    print(f"  Answers returned:         {s['answers_returned']}")
    print(f"  Query errors:             {s['query_errors']}")
    print(f"  Validation failures:      {s['validation_failures']}")
    print(f"  Cross-company chunk hits: {s['cross_company_retrievals']}")
    print(f"  RBAC check failures:      {s['rbac_failures']}")
    if report.get("rbac"):
        print("  RBAC checks:")
        for row in report["rbac"]:
            status = "ok" if row.get("ok") else "FAIL"
            print(f"    - [{status}] {row.get('check')}")
    print("")


def _parse_queries_json(path: str) -> List[Tuple[str, str, str]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    out: List[Tuple[str, str, str]] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) == 3:
                out.append((str(item[0]), str(item[1]), str(item[2])))
            elif isinstance(item, dict):
                out.append(
                    (
                        str(item["role"]),
                        str(item["company_id"]),
                        str(item["question"]),
                    )
                )
    return out


def main() -> int:
    if not db.canonical_policy_tables_available():
        raise SystemExit(
            "Canonical policy tables are missing. From the repo root run: "
            "PYTHONPATH=. python backend/scripts/bootstrap_backend_database.py "
            "(or ensure DATABASE_URL matches a DB where you ran init_db + alembic upgrade head)"
        )
    parser = argparse.ArgumentParser(description="Audit company-scoped policy assistant (retrieval, RBAC, citations).")
    parser.add_argument("--company-acme", default=DEFAULT_COMPANY_ACME, help="Company id for GOPS PDF")
    parser.add_argument("--company-beta", default=DEFAULT_COMPANY_BETA, help="Company id for LTA PDF")
    parser.add_argument("--gops-pdf", default=None, help="Path to GOPS 12102.pdf (or set RELOPASS_AUDIT_POLICY_GOPS)")
    parser.add_argument("--lta-pdf", default=None, help="Path to Long Term Assignment Policy Summary.pdf")
    parser.add_argument("--queries-json", default=None, help="JSON list of {role, company_id, question} or [role, cid, q] tuples")
    parser.add_argument("--output-json", default="audit_report.json", help="Write full JSON report (default: audit_report.json)")
    parser.add_argument(
        "--use-openai-extraction",
        action="store_true",
        help="Use OpenAI for fact extraction (default: deterministic fallback).",
    )
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Do not create companies/users or ingest; use existing active canonical docs for the two company ids.",
    )
    args = parser.parse_args()

    use_fallback = not args.use_openai_extraction
    if args.no_seed:
        pdf_acme = None
        pdf_beta = None
    else:
        pdf_acme, pdf_beta = _resolve_pdf_paths(args.gops_pdf, args.lta_pdf)
    queries: Optional[List[Tuple[str, str, str]]] = None
    if args.queries_json:
        queries = _parse_queries_json(args.queries_json)

    try:
        report = run_policy_assistant_audit(
            db,
            company_acme=args.company_acme,
            company_beta=args.company_beta,
            pdf_acme=pdf_acme,
            pdf_beta=pdf_beta,
            queries=queries,
            use_fallback=use_fallback,
            seed_tenants=not args.no_seed,
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    out_path = Path(args.output_json)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _print_summary(report)
    print(f"Wrote {out_path.resolve()}")
    if report["summary"]["validation_failures"] or report["summary"]["cross_company_retrievals"]:
        return 2
    if report["summary"]["query_errors"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
