"""
[AIQ-1831] The shared corridor resolver must consult relocation_cases.

`_get_case_details` is the de-facto corridor resolver for the immigration surface:
the HR requirements route, the employee snapshot, `immigration_status`, and
`immigration_intake_interview` all reach the corridor through it (directly or via
`resolve_case_corridor`). It COALESCEd `mobility_cases` and `wizard_cases` only.

`relocation_cases` is the HR case of record and the table `submit_assignment`
actually writes the route to (`sync_relocation_case_route_from_wizard_draft`), so a
case that exists ONLY there resolved to corridor=null despite having correct
origin/dest columns. Verified in production 2026-08-13 on case
07a99b8f-bd18-425b-8416-8daa7bf03414 (relocation_cases: ES/IE, corridor 'ES-IE'):

    GET /api/hr/cases/07a99b8f-.../immigration-requirements
    -> 200 {"coverage_reason": "corridor_not_supported", "corridor_from": null}

Same-day measurements against prod, running both COALESCE variants over all 955
case_assignments rows:

    changed_existing_answer =  0   <- the third arm cannot regress a correct answer
    newly_resolved          = 21
    still_null              = 364  <- genuinely no geography in any of the 3 tables

SCOPE OF THIS TEST: the COALESCE is evaluated by Postgres, and the backend test
suite has no live Postgres (conftest mocks `backend.database`), so this asserts the
*shape of the SQL* rather than its result. That is a deliberate, stated limit — it
locks in the third arm and its ordering so the regression cannot be silently
reintroduced. The behavioural proof is the prod measurement recorded above.
"""
import inspect
import re

from backend.app.services import immigration_service


def _resolver_sql() -> str:
    """The SQL literal inside _get_case_details, whitespace-collapsed."""
    src = inspect.getsource(immigration_service._get_case_details)
    return re.sub(r"\s+", " ", src)


def test_resolver_joins_relocation_cases():
    sql = _resolver_sql()
    assert "public.relocation_cases" in sql, (
        "_get_case_details must LEFT JOIN public.relocation_cases — it is the table "
        "submit_assignment writes the route to. Without it a relocation-only case "
        "resolves corridor=null (AIQ-1831)."
    )
    assert re.search(r"LEFT JOIN public\.relocation_cases\s+\w+\s+ON\s+\w+\.id::text = ca\.case_id", sql), (
        "the relocation_cases join must key on ca.case_id (cast to text) like the "
        "mobility_cases / wizard_cases arms beside it"
    )


def test_both_coalesce_arms_include_relocation_columns_last():
    """Ordering is load-bearing: relocation_cases must be the LAST arm.

    Placed last it can only fire where the existing arms are already NULL, which is
    what makes the change incapable of altering a currently-correct answer
    (changed_existing_answer = 0 across all 955 prod rows). Promoting it ahead of
    mobility/wizard would silently change resolved corridors and void that proof.
    """
    sql = _resolver_sql()

    dest = re.search(r"COALESCE\(([^)]*dest[^)]*)\)\s+AS dest_country", sql)
    assert dest, "dest_country COALESCE not found in the resolver SQL"
    dest_arms = [a.strip() for a in dest.group(1).split(",")]
    assert dest_arms == [
        "mc.destination_country",
        "wc.dest_country",
        "rc.dest_country_code",
    ], f"unexpected dest_country COALESCE arms/order: {dest_arms}"

    origin = re.search(r"COALESCE\(([^)]*origin[^)]*)\)\s+AS origin_country", sql)
    assert origin, "origin_country COALESCE not found in the resolver SQL"
    origin_arms = [a.strip() for a in origin.group(1).split(",")]
    assert origin_arms == [
        "mc.origin_country",
        "wc.origin_country",
        "rc.origin_country_code",
    ], f"unexpected origin_country COALESCE arms/order: {origin_arms}"


def test_resolver_still_matches_by_pk_or_fk():
    """The dual PK/FK match is why one helper serves both call shapes — keep it."""
    sql = _resolver_sql()
    assert "WHERE ca.id = :case_id OR ca.case_id = :case_id" in sql
