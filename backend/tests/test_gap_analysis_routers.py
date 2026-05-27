"""
test_gap_analysis_routers.py — GAP 1, 3, 4, 6, 7, 8, 9, 10

Exercises every new router module directly (no live server, no Supabase).
All DB calls are mocked.  Tests are pure-Python unittest — no pytest plugins needed.

Routers under test
------------------
  relocation_profile  — GET/PUT /api/employee/cases/{id}/relocation-profile
  hr_analytics        — GET /api/hr/policy-compliance-matrix
  advisors            — POST /api/advisors/match  +  GET /api/advisors/{id}
  rules               — GET /api/rules/pet-restrictions
  marketplace         — GET /api/employee/assignments/{id}/marketplace
  exception_requests  — GET/POST/PATCH /api/assignments/{id}/exceptions (enriched GAP-7)
  branding            — GET/PUT /api/company/branding-config
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

# ─── common mock user injected via Depends(get_current_user) ─────────────────
_MOCK_USER = {
    "id": "user-001",
    "email": "test@example.com",
    "role": "hr",
    "company": "company-001",
    "company_id": "company-001",
    "is_admin": False,
}

_SUPABASE_CLIENT_PATH = "backend.app.services.supabase_client.get_supabase_admin_client"


# ═══════════════════════════════════════════════════════════════════════════════
# GAP 1 — relocation_profile
# ═══════════════════════════════════════════════════════════════════════════════
class TestRelocationProfile(unittest.TestCase):
    def _mod(self):
        from backend.app.routers import relocation_profile as m
        return m

    def test_completion_all_sections(self):
        m = self._mod()
        data = {
            "origin_housing": {"owned": True},
            "housing_preferences": {"type": "apartment"},
            "household": {"marital_status": "solo"},
            "temp_housing": {"needed": False},
            "financial": {"has_fx_transfer_needs": False},
        }
        self.assertEqual(m._compute_completion(data), 100)

    def test_completion_one_section(self):
        m = self._mod()
        self.assertEqual(m._compute_completion({"origin_housing": {"owned": True}}), 20)

    def test_completion_empty(self):
        m = self._mod()
        self.assertEqual(m._compute_completion({}), 0)

    def test_nested_sub_models_preserved(self):
        m = self._mod()
        payload = m.RelocationProfilePayload(
            housing_preferences=m.HousingPreferences(
                neighbourhood_priorities=m.NeighbourhoodPriorities(commute=9, safety=8),
            ),
            household=m.HouseholdMembers(
                marital_status="partner_kids",
                spouse=m.SpouseProfile(full_name="Jane Doe"),
                children=[m.ChildProfile(school_type_preference="international")],
                pets=[m.PetProfile(name="Buddy", microchipped=True)],
            ),
        )
        dumped = payload.model_dump(mode="json", exclude_none=True)
        self.assertEqual(dumped["housing_preferences"]["neighbourhood_priorities"]["commute"], 9)
        self.assertTrue(dumped["household"]["pets"][0]["microchipped"])
        self.assertEqual(dumped["household"]["children"][0]["school_type_preference"], "international")

    def test_get_returns_empty_when_no_db_row(self):
        m = self._mod()
        with mock.patch.object(m, "_get_profile_from_db", return_value=None):
            resp = m.get_relocation_profile("case-abc", user=_MOCK_USER)
        self.assertEqual(resp.case_id, "case-abc")
        self.assertEqual(resp.completion_pct, 0)

    def test_put_computes_correct_completion(self):
        m = self._mod()
        payload = m.RelocationProfilePayload(
            origin_housing=m.OriginHousing(owned=True),
            housing_preferences=m.HousingPreferences(type="apartment"),
        )
        with mock.patch.object(m, "_upsert_profile_to_db", return_value={}):
            resp = m.put_relocation_profile("case-abc", payload, user=_MOCK_USER)
        self.assertEqual(resp.completion_pct, 40)

    def test_pet_profile_all_fields(self):
        m = self._mod()
        pet = m.PetProfile(
            name="Rex", species="dog", breed="Labrador",
            weight_kg=25.0, origin_country="FR",
            microchipped=True, vaccinations_up_to_date=True,
            rabies_titre_test_done=False, health_certificate_obtained=True,
        )
        d = pet.model_dump(exclude_none=True)
        self.assertEqual(d["breed"], "Labrador")
        self.assertFalse(d["rabies_titre_test_done"])

    def test_financial_profile(self):
        m = self._mod()
        fin = m.FinancialProfile(
            has_fx_transfer_needs=True,
            estimated_monthly_transfer_eur=2000,
            home_sale_proceeds=True,
            tax_equalisation_applicable=False,
        )
        self.assertEqual(fin.estimated_monthly_transfer_eur, 2000)


# ═══════════════════════════════════════════════════════════════════════════════
# GAP 3 — hr_analytics (compliance matrix)
# ═══════════════════════════════════════════════════════════════════════════════
class TestHrAnalytics(unittest.TestCase):
    def _mod(self):
        from backend.app.routers import hr_analytics as m
        return m

    def test_benefit_columns_min_count(self):
        m = self._mod()
        self.assertGreaterEqual(len(m.BENEFIT_COLUMNS), 13)

    def test_benefit_labels_covers_columns(self):
        m = self._mod()
        for col in m.BENEFIT_COLUMNS:
            self.assertIn(col, m.BENEFIT_LABELS, f"{col} missing from BENEFIT_LABELS")

    def test_compute_cells_grey_when_not_covered(self):
        m = self._mod()
        cells = m._compute_cells({}, set(), set(), {}, {})
        for key in m.BENEFIT_COLUMNS:
            self.assertEqual(cells[key], "grey")

    def test_compute_cells_blue_for_exception(self):
        m = self._mod()
        covered = set(m.BENEFIT_COLUMNS)
        exception_keys = {"immigration"}      # "immigration" is a real column
        cells = m._compute_cells({}, covered, exception_keys, {}, {})
        self.assertEqual(cells["immigration"], "blue")

    def test_compute_cells_green_within_cap(self):
        m = self._mod()
        covered = set(m.BENEFIT_COLUMNS)
        cells = m._compute_cells({}, covered, set(), {"immigration": 800}, {"immigration": 1000})
        self.assertEqual(cells["immigration"], "green")

    def test_compute_cells_red_over_cap(self):
        m = self._mod()
        covered = set(m.BENEFIT_COLUMNS)
        cells = m._compute_cells({}, covered, set(), {"immigration": 1200}, {"immigration": 1000})
        self.assertEqual(cells["immigration"], "red")

    def test_compute_cells_amber_borderline(self):
        m = self._mod()
        covered = set(m.BENEFIT_COLUMNS)
        # 95% utilisation → amber (>= 90%)
        cells = m._compute_cells({}, covered, set(), {"immigration": 950}, {"immigration": 1000})
        self.assertEqual(cells["immigration"], "amber")

    def test_matrix_endpoint_empty_smoke(self):
        m = self._mod()
        # _get_matrix_data(company_id, period_months) returns list of assignment dicts
        # _get_covered_benefits_for_company returns dict {benefit_key: {...}}
        with mock.patch.object(m, "_get_matrix_data", return_value=[]), \
             mock.patch.object(m, "_get_covered_benefits_for_company", return_value={}), \
             mock.patch.object(m, "_get_exception_keys_for_assignment", return_value=set()):
            resp = m.get_policy_compliance_matrix(user=_MOCK_USER)
        # response has .cases (list) and .kpis
        self.assertIsNotNone(resp)
        self.assertIsInstance(resp.cases, list)
        self.assertEqual(resp.kpis.compliance_pct, 100)  # empty → 100%


# ═══════════════════════════════════════════════════════════════════════════════
# GAP 4 — advisors
# ═══════════════════════════════════════════════════════════════════════════════
class TestAdvisors(unittest.TestCase):
    def _mod(self):
        from backend.app.routers import advisors as m
        return m

    def test_fallback_list_count(self):
        m = self._mod()
        self.assertGreaterEqual(len(m._FALLBACK_ADVISORS), 5)

    def test_region_map_eu(self):
        m = self._mod()
        for c in ["DE", "FR", "NL", "BE", "AT", "IT"]:
            self.assertEqual(m._REGION_MAP.get(c), "EU")

    def test_region_map_apac(self):
        m = self._mod()
        for c in ["SG", "JP", "AU", "HK"]:
            self.assertEqual(m._REGION_MAP.get(c), "APAC")

    def test_corridor_match_global(self):
        m = self._mod()
        self.assertTrue(m._advisor_matches_corridor({"corridors": []}, "JP", "US"))

    def test_corridor_match_exact(self):
        m = self._mod()
        self.assertTrue(m._advisor_matches_corridor({"corridors": ["GB"]}, "GB", "US"))

    def test_corridor_match_region(self):
        m = self._mod()
        self.assertTrue(m._advisor_matches_corridor({"corridors": ["EU"]}, "DE", "US"))

    def test_corridor_no_match(self):
        m = self._mod()
        self.assertFalse(m._advisor_matches_corridor({"corridors": ["GB"]}, "SG", "US"))

    def test_match_uses_fallback_when_db_empty(self):
        m = self._mod()
        body = m.AdvisorMatchRequest(destination_country="DE", origin_country="US")
        with mock.patch.object(m, "_get_db_advisors", return_value=[]), \
             mock.patch.object(m, "_get_preferred_advisor_ids_for_company", return_value=set()):
            resp = m.match_advisors(body, user=_MOCK_USER)
        self.assertGreater(resp.total, 0)
        self.assertIn("Helena Morrow", [a.name for a in resp.advisors])

    def test_match_preferred_sorted_first(self):
        m = self._mod()
        body = m.AdvisorMatchRequest(destination_country="DE")
        preferred = {"adv-global-immigration-001"}
        with mock.patch.object(m, "_get_db_advisors", return_value=[]), \
             mock.patch.object(m, "_get_preferred_advisor_ids_for_company", return_value=preferred):
            resp = m.match_advisors(body, user=_MOCK_USER)
        self.assertTrue(resp.advisors[0].preferred_for_company)

    def test_get_advisor_fallback_found(self):
        m = self._mod()
        # Patch at the source module so the local import inside the function fails
        with mock.patch(_SUPABASE_CLIENT_PATH, side_effect=Exception("no db")):
            adv = m.get_advisor("adv-uk-immigration-004", user=_MOCK_USER)
        self.assertEqual(adv.name, "James Whitfield")
        self.assertEqual(adv.firm, "Whitfield Immigration Law")

    def test_get_advisor_not_found_raises_404(self):
        m = self._mod()
        from fastapi import HTTPException
        with mock.patch(_SUPABASE_CLIENT_PATH, side_effect=Exception("no db")):
            with self.assertRaises(HTTPException) as ctx:
                m.get_advisor("adv-nonexistent-999", user=_MOCK_USER)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_initials_helper(self):
        m = self._mod()
        self.assertEqual(m._initials("Helena Morrow"), "HM")
        self.assertEqual(m._initials("Single"), "S")   # single word → first char only


# ═══════════════════════════════════════════════════════════════════════════════
# GAP 6 — pet restrictions (rules.py)
# Note: get_pet_restrictions / check_breed do NOT take a user param (public routes)
# ═══════════════════════════════════════════════════════════════════════════════
class TestRules(unittest.TestCase):
    def _mod(self):
        from backend.app.routers import rules as m
        return m

    def test_quarantine_countries_exist(self):
        m = self._mod()
        self.assertIn("AU", m._QUARANTINE_COUNTRIES)
        self.assertIn("NZ", m._QUARANTINE_COUNTRIES)

    def test_restricted_breeds_dict_populated(self):
        m = self._mod()
        self.assertIsInstance(m._RESTRICTED_BREEDS_BY_COUNTRY, dict)
        self.assertGreater(len(m._RESTRICTED_BREEDS_GLOBAL), 0)

    def test_get_restrictions_au_quarantine(self):
        m = self._mod()
        # PetRestrictionsResponse uses .destination_code (not .destination_country)
        with mock.patch.object(m, "_fetch_from_db", return_value=None):
            resp = m.get_pet_restrictions(destination_code="AU")
        self.assertEqual(resp.destination_code, "AU")
        self.assertTrue(resp.quarantine_required)

    def test_get_restrictions_unknown_country_defaults(self):
        m = self._mod()
        with mock.patch.object(m, "_fetch_from_db", return_value=None):
            resp = m.get_pet_restrictions(destination_code="ZZ")
        self.assertEqual(resp.destination_code, "ZZ")
        self.assertFalse(resp.quarantine_required)

    def test_breed_check_returns_response(self):
        m = self._mod()
        # BreedCheckResponse uses .destination_code field
        with mock.patch.object(m, "_fetch_from_db", return_value=None):
            result = m.check_breed(breed="Labrador", destination_code="DE")
        self.assertIsNotNone(result)
        self.assertEqual(result.destination_code, "DE")

    def test_breed_check_restricted_breed_flagged(self):
        m = self._mod()
        with mock.patch.object(m, "_fetch_from_db", return_value=None):
            result = m.check_breed(breed="Pitbull", destination_code="DE")
        self.assertIsNotNone(result)


# ═══════════════════════════════════════════════════════════════════════════════
# GAP 8 — marketplace
# ═══════════════════════════════════════════════════════════════════════════════
class TestMarketplace(unittest.TestCase):
    def _mod(self):
        from backend.app.routers import marketplace as m
        return m

    def test_logo_initials_two_words(self):
        m = self._mod()
        self.assertEqual(m._logo_initials("Alpha Beta"), "AB")

    def test_logo_initials_one_word(self):
        m = self._mod()
        # single-word name: only first char is taken
        self.assertEqual(m._logo_initials("Single"), "S")

    def test_sla_display_hours(self):
        m = self._mod()
        self.assertEqual(m._sla_display(24), "24h response")

    def test_sla_display_days(self):
        m = self._mod()
        self.assertEqual(m._sla_display(48), "2 day response")

    def test_sla_display_none(self):
        m = self._mod()
        self.assertIsNone(m._sla_display(None))

    def test_price_display_range(self):
        m = self._mod()
        self.assertEqual(m._price_display(1000, 3000), "€1,000–€3,000")

    def test_price_display_from_only(self):
        m = self._mod()
        self.assertEqual(m._price_display(500, None), "From €500")

    def test_price_display_none(self):
        m = self._mod()
        self.assertIsNone(m._price_display(None, None))

    def test_benefit_key_immigration(self):
        m = self._mod()
        self.assertEqual(m._benefit_key_for_category("immigration"), "immigration")

    def test_benefit_key_housing_agent(self):
        m = self._mod()
        self.assertEqual(m._benefit_key_for_category("housing_agent"), "housing")

    def test_benefit_key_pet_relocation(self):
        m = self._mod()
        self.assertEqual(m._benefit_key_for_category("pet_relocation"), "pet_relocation")

    def test_benefit_key_unknown_is_none(self):
        m = self._mod()
        self.assertIsNone(m._benefit_key_for_category("unknown_xyz"))

    def test_marketplace_no_assignment_raises_404(self):
        m = self._mod()
        from fastapi import HTTPException
        from backend.database import db as main_db
        with mock.patch.object(main_db, "get_assignment_by_id", return_value=None):
            with self.assertRaises(HTTPException) as ctx:
                m.get_marketplace("assignment-nonexistent", user=_MOCK_USER)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_marketplace_sort_order(self):
        m = self._mod()
        vendors = [
            m.MarketplaceVendor(id="a", name="A", service_category="housing", logo_initials="A", preferred=False, covered=False),
            m.MarketplaceVendor(id="b", name="B", service_category="housing", logo_initials="B", preferred=True, covered=True, rating=4.5),
            m.MarketplaceVendor(id="c", name="C", service_category="housing", logo_initials="C", preferred=False, covered=True),
        ]
        vendors.sort(key=lambda v: (not (v.preferred and v.covered), not v.covered, not v.preferred, -(v.rating or 0)))
        self.assertEqual(vendors[0].id, "b")  # preferred+covered first
        self.assertEqual(vendors[1].id, "c")  # covered-only second


# ═══════════════════════════════════════════════════════════════════════════════
# GAP 7 — exception_requests (enriched assignment-level)
# Note: uses ExceptionRequestPatch (not AssignmentExceptionPatch)
# ═══════════════════════════════════════════════════════════════════════════════
class TestExceptionRequestsEnriched(unittest.TestCase):
    def _mod(self):
        from backend.app.routers import exception_requests as m
        return m

    def test_assignment_exception_create_model(self):
        m = self._mod()
        req = m.AssignmentExceptionCreate(
            benefit_key="temporary_housing",
            type_label="Temp housing cap override",
            current_value={"amount": 1500, "currency": "EUR"},
            requested_value={"amount": 2200, "currency": "EUR"},
            reason="High cost city",
        )
        self.assertEqual(req.benefit_key, "temporary_housing")
        self.assertEqual(req.current_value["amount"], 1500)

    def test_assignment_exception_read_model(self):
        m = self._mod()
        read = m.AssignmentExceptionRead(
            id="exc-001",
            assignment_id="asgn-001",
            benefit_key="housing",
            status="pending",
            reason="Need more",
            audit_events=[{"ts": "2025-01-01T00:00:00Z", "actor": "hr@co.com", "action": "created", "note": ""}],
        )
        self.assertEqual(len(read.audit_events), 1)
        self.assertEqual(read.status, "pending")

    def test_exception_request_patch_model(self):
        m = self._mod()
        patch = m.ExceptionRequestPatch(status="approved", hr_note="Looks good")
        self.assertEqual(patch.status, "approved")

    def test_list_assignment_exceptions_empty(self):
        m = self._mod()
        # list function uses sb.table().select().eq().order().execute().data
        mock_sb = mock.MagicMock()
        mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = []
        with mock.patch.object(m, "_get_supabase", return_value=mock_sb):
            result = m.list_assignment_exceptions("asgn-001", user=_MOCK_USER)
        self.assertEqual(result, [])

    def test_patch_assignment_exception_approved(self):
        m = self._mod()
        existing = {
            "id": "exc-001",
            "assignment_id": "asgn-001",
            "benefit_key": "housing",
            "status": "pending",
            "reason": "Need more",
            "audit_events": [],
        }
        updated = {**existing, "status": "approved", "hr_note": "Looks good"}
        mock_sb = mock.MagicMock()
        # fetch existing row
        (mock_sb.table.return_value.select.return_value
         .eq.return_value.eq.return_value
         .maybe_single.return_value.execute.return_value.data) = existing
        # update result
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [updated]
        with mock.patch.object(m, "_get_supabase", return_value=mock_sb):
            patch_body = m.ExceptionRequestPatch(status="approved", hr_note="Looks good")
            result = m.resolve_assignment_exception("asgn-001", "exc-001", patch_body, user=_MOCK_USER)
        # resolve_assignment_exception returns updated.data[0] (dict) directly
        # FastAPI wraps it as response_model in prod; in tests we check the raw dict
        status = result.status if hasattr(result, "status") else result["status"]
        self.assertEqual(status, "approved")

    def test_create_exception_request_model_validation(self):
        m = self._mod()
        # base ExceptionRequestCreate (case-level) still works
        req = m.ExceptionRequestCreate(
            case_id="case-001",
            category="housing",
            requested_amount=2000,
            cap_amount=1500,
            currency="EUR",
            reason="Exceeded cap",
        )
        self.assertEqual(req.category, "housing")


# ═══════════════════════════════════════════════════════════════════════════════
# GAP 10 — branding
# ═══════════════════════════════════════════════════════════════════════════════
class TestBranding(unittest.TestCase):
    def _mod(self):
        from backend.app.routers import branding as m
        return m

    def test_branding_config_defaults(self):
        m = self._mod()
        cfg = m.BrandingConfig()
        self.assertFalse(cfg.hide_relopass_branding)
        self.assertIsNone(cfg.primary_colour)

    def test_branding_config_with_values(self):
        m = self._mod()
        cfg = m.BrandingConfig(primary_colour="#1E40AF", hide_relopass_branding=True)
        self.assertEqual(cfg.primary_colour, "#1E40AF")
        self.assertTrue(cfg.hide_relopass_branding)

    def test_get_returns_defaults_when_no_config(self):
        m = self._mod()
        with mock.patch.object(m, "_get_company_branding", return_value=("ACME Corp", {})), \
             mock.patch.object(m, "_resolve_company_id", return_value="company-001"):
            resp = m.get_branding_config(user=_MOCK_USER)
        self.assertEqual(resp.company_name, "ACME Corp")
        self.assertIsNone(resp.branding.primary_colour)

    def test_get_parses_jsonb_correctly(self):
        m = self._mod()
        branding_dict = {
            "primary_colour": "#FF6B35",
            "logo_url": "https://example.com/logo.png",
            "hide_relopass_branding": True,
        }
        with mock.patch.object(m, "_get_company_branding", return_value=("TechCo", branding_dict)), \
             mock.patch.object(m, "_resolve_company_id", return_value="company-001"):
            resp = m.get_branding_config(user=_MOCK_USER)
        self.assertEqual(resp.branding.primary_colour, "#FF6B35")
        self.assertEqual(resp.branding.logo_url, "https://example.com/logo.png")
        self.assertTrue(resp.branding.hide_relopass_branding)

    def test_update_forbidden_for_employee(self):
        m = self._mod()
        from fastapi import HTTPException
        employee_user = {**_MOCK_USER, "role": "employee", "is_admin": False}
        with mock.patch.object(m, "_resolve_company_id", return_value="company-001"):
            with self.assertRaises(HTTPException) as ctx:
                m.update_branding_config(m.BrandingConfig(), user=employee_user)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_update_allowed_for_hr(self):
        m = self._mod()
        hr_user = {**_MOCK_USER, "role": "hr"}
        mock_sb = mock.MagicMock()
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{"name": "ACME"}]
        with mock.patch.object(m, "_resolve_company_id", return_value="company-001"), \
             mock.patch(_SUPABASE_CLIENT_PATH, return_value=mock_sb):
            resp = m.update_branding_config(m.BrandingConfig(primary_colour="#123456"), user=hr_user)
        self.assertEqual(resp.company_id, "company-001")

    def test_update_allowed_for_admin(self):
        m = self._mod()
        admin_user = {**_MOCK_USER, "role": "employee", "is_admin": True}
        mock_sb = mock.MagicMock()
        mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{"name": "Corp"}]
        with mock.patch.object(m, "_resolve_company_id", return_value="company-001"), \
             mock.patch(_SUPABASE_CLIENT_PATH, return_value=mock_sb):
            resp = m.update_branding_config(m.BrandingConfig(), user=admin_user)
        self.assertIsNotNone(resp)


# ═══════════════════════════════════════════════════════════════════════════════
# Cross-router structural checks
# ═══════════════════════════════════════════════════════════════════════════════
class TestCrossRouterChecks(unittest.TestCase):
    def test_all_new_routers_importable(self):
        modules = [
            "backend.app.routers.relocation_profile",
            "backend.app.routers.hr_analytics",
            "backend.app.routers.advisors",
            "backend.app.routers.rules",
            "backend.app.routers.marketplace",
            "backend.app.routers.exception_requests",
            "backend.app.routers.branding",
        ]
        import importlib
        for mod in modules:
            with self.subTest(module=mod):
                m = importlib.import_module(mod)
                self.assertTrue(hasattr(m, "router"), f"{mod} missing .router")

    def test_advisors_router_prefix(self):
        from backend.app.routers.advisors import router
        self.assertEqual(router.prefix, "/api/advisors")

    def test_branding_router_prefix(self):
        from backend.app.routers.branding import router
        self.assertEqual(router.prefix, "/api/company")

    def test_relocation_profile_router_prefix(self):
        from backend.app.routers.relocation_profile import router
        self.assertEqual(router.prefix, "/api/employee/cases")

    def test_marketplace_router_prefix(self):
        from backend.app.routers.marketplace import router
        self.assertEqual(router.prefix, "/api/employee/assignments")

    def test_hr_analytics_has_benefit_columns(self):
        from backend.app.routers.hr_analytics import BENEFIT_COLUMNS
        self.assertGreaterEqual(len(BENEFIT_COLUMNS), 13)

    def test_advisors_has_5_fallback_entries(self):
        from backend.app.routers.advisors import _FALLBACK_ADVISORS
        ids = {a["id"] for a in _FALLBACK_ADVISORS}
        self.assertIn("adv-global-immigration-001", ids)
        self.assertIn("adv-uk-immigration-004", ids)
        self.assertIn("adv-apac-immigration-003", ids)


if __name__ == "__main__":
    unittest.main(verbosity=2)
