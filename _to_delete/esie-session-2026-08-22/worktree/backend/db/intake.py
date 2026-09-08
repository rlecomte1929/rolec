"""[AUDIT-C1.5] Intake/wizard-domain DB methods, extracted from backend/database.py.

Wizard answers, dossier questions/answers, and policy-assistant answer audits.
These were methods on the monolithic ``Database`` class; they live here as a
mixin (:class:`IntakeMixin`) that ``Database`` inherits, so every caller
(``db.save_answer(...)`` etc.) keeps working unchanged via normal MRO.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from ..db_config import DATABASE_URL as _raw_url

log = logging.getLogger(__name__)


class IntakeMixin:
    """Intake/wizard-domain methods mixed into :class:`backend.database.Database`."""

    def save_answer(self, user_id: str, question_id: str, answer: Any, is_unknown: bool = False) -> bool:
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO answers (user_id, question_id, answer_json, is_unknown, created_at) "
                "VALUES (:uid, :qid, :aj, :iu, :ca)"
            ), {
                "uid": user_id, "qid": question_id,
                "aj": json.dumps(answer), "iu": 1 if is_unknown else 0,
                "ca": datetime.utcnow().isoformat(),
            })
        return True

    def get_answers(self, user_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT question_id, answer_json, is_unknown FROM answers "
                "WHERE user_id = :uid ORDER BY created_at"
            ), {"uid": user_id}).fetchall()
        return self._rows_to_list(rows)

    def apply_wizard_patch_side_effects(self, case_id: str, draft: Dict[str, Any], derived: Dict[str, Any]) -> None:
        """
        After PATCH /api/cases/{id}: sync relocation_cases columns used by HR dashboard,
        and move assignment into awaiting_intake once the employee enters basics.
        """
        cid = (case_id or "").strip()
        if not cid:
            return
        home = (derived.get("origin_country") or "").strip() or None
        host = (derived.get("dest_country") or "").strip() or None
        if home or host:
            self.touch_relocation_case_route_from_wizard(cid, home_country=home, host_country=host)
        assignment = self.get_assignment_by_case_id(cid)
        if not assignment:
            return
        # Bridge the wizard intake into the canonical public.cases row that the
        # Case Engine (trigger_engine) reads. The wizard writes wizard_cases; the
        # trigger reads public.cases — without this row no CaseForms (hence no
        # roadmap/dossier) are ever generated. Fail-safe (skips on any gap).
        self._ensure_canonical_case_from_wizard(cid, derived, assignment)
        # Sync the wizard family (spouse + children) into case_dependents — the
        # table the trigger reads for has_spouse/has_children, which gate the
        # family-reunion forms. The household intake writes only the draft;
        # without this no family form is ever generated. Runs after the canonical
        # case exists (FK case_dependents.case_id -> public.cases).
        canonical = str(assignment.get("canonical_case_id") or cid).strip()
        self._sync_case_dependents_from_draft(canonical, draft)
        st = (assignment.get("status") or "").strip().lower()
        if st not in ("created", "assigned"):
            return
        basics = draft.get("relocationBasics") or {}
        if not any((str(basics.get(k) or "").strip()) for k in ("destCountry", "destCity", "originCountry", "originCity")):
            return
        self.update_assignment_status(assignment["id"], "awaiting_intake")

    def seed_dossier_questions_if_missing(self) -> None:
        """
        Idempotent: insert destination dossier_questions that are not yet in the
        local DB.  Mirrors the Supabase migration seed so local dev works without
        running migrations manually.  Safe to call every startup.
        """
        _SEED: list = [
            # ── DE — Germany (EU Blue Card / Skilled Worker) ──────────────────
            ("DE", "immigration", "de.visa_type_confirmed",
             "Has the work visa type been confirmed by your employer? (EU Blue Card or Skilled Worker Visa)",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Germany","DE"]}', 10),
            ("DE", "immigration", "de.qualifications_recognized",
             "Have your foreign professional qualifications been formally recognised by the relevant German authority?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Germany","DE"]}', 20),
            ("DE", "immigration", "de.consulate_appointment",
             "Has your appointment at the German consulate been booked for the visa application?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Germany","DE"]}', 30),
            ("DE", "immigration", "de.visa_submitted",
             "Has your visa application been submitted to the German consulate?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Germany","DE"]}', 40),
            ("DE", "registration", "de.anmeldung_completed",
             "Have you registered your address (Anmeldung) at the local Einwohnermeldeamt within 14 days of arrival?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Germany","DE"]}', 50),
            ("DE", "immigration", "de.aufenthaltstitel_submitted",
             "Has your residence permit (Aufenthaltstitel) application been submitted to the Ausländerbehörde?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Germany","DE"]}', 60),
            ("DE", "insurance", "de.health_insurance",
             "Do you have statutory or private health insurance in place? (Required for the residence permit application)",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Germany","DE"]}', 70),
            ("DE", "immigration", "de.dependents",
             "Will any dependents (spouse, children) accompany you and require German visas or residence permits?",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Germany","DE"]}', 80),
            ("DE", "immigration", "de.dependent_details",
             "If yes, how many dependents will apply for German residence permits?",
             "text", None, False,
             '{"field":"relocationBasics.hasDependents","op":"==","value":true}', 90),
            # ── FR — France (Salarié / Passeport Talent) ─────────────────────
            ("FR", "immigration", "fr.work_permit_route",
             "Has your employer confirmed the work permit route (Salarié or Passeport Talent)?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["France","FR"]}', 10),
            ("FR", "immigration", "fr.consulate_appointment",
             "Has your consulate appointment been booked for the long-stay visa application?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["France","FR"]}', 20),
            ("FR", "immigration", "fr.vls_ts_submitted",
             "Has your long-stay visa (VLS-TS) application been submitted to the consulate?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["France","FR"]}', 30),
            ("FR", "immigration", "fr.ofii_completed",
             "Have you completed the OFII arrival declaration and medical visit after entering France?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["France","FR"]}', 40),
            ("FR", "immigration", "fr.titre_sejour_scheduled",
             "Has your titre de séjour (residence permit) prefecture appointment been scheduled?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["France","FR"]}', 50),
            ("FR", "housing", "fr.housing_proof",
             "Do you have proof of housing available (signed lease or employer-provided accommodation)?",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["France","FR"]}', 60),
            ("FR", "immigration", "fr.dependents",
             "Will any dependents (spouse, children) accompany you and require French visas or residency?",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["France","FR"]}', 70),
            ("FR", "immigration", "fr.dependent_details",
             "If yes, how many dependents will apply for French residency documents?",
             "text", None, False,
             '{"field":"relocationBasics.hasDependents","op":"==","value":true}', 80),
            # ── GB — UK Skilled Worker ────────────────────────────────────────
            ("GB", "immigration", "gb.sponsor_licence",
             "Does your employer hold an active UK Sponsor Licence issued by the Home Office?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["United Kingdom","GB","UK"]}', 10),
            ("GB", "immigration", "gb.cos_confirmed",
             "Has a Certificate of Sponsorship (CoS) been assigned to you by your employer?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["United Kingdom","GB","UK"]}', 20),
            ("GB", "immigration", "gb.salary_threshold",
             "Does your salary meet the Skilled Worker visa general threshold (£38,700 or SOC going rate, whichever is higher)?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["United Kingdom","GB","UK"]}', 30),
            ("GB", "immigration", "gb.points_eligibility",
             "Have the mandatory 70 points under the UK points-based system been confirmed? (Job offer 20 pts + sponsor 20 pts + salary 20 pts + English 10 pts)",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["United Kingdom","GB","UK"]}', 40),
            ("GB", "immigration", "gb.english_evidence",
             "Is English language evidence available? (degree taught in English, or approved test such as IELTS/LanguageCert)",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["United Kingdom","GB","UK"]}', 50),
            ("GB", "registration", "gb.move_date_confirm",
             "Do you have a confirmed arrival date in the UK?",
             "boolean", None, True,
             '{"field":"relocationBasics.targetMoveDate","op":"exists","value":false}', 60),
            ("GB", "immigration", "gb.dependents",
             "Will any dependents (spouse, children) accompany you and require a UK Dependant visa?",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["United Kingdom","GB","UK"]}', 70),
            ("GB", "immigration", "gb.dependent_details",
             "If yes, how many dependents will apply for UK Dependant visas?",
             "text", None, False,
             '{"field":"relocationBasics.hasDependents","op":"==","value":true}', 80),
            # ── NO — Norway (Skilled Worker Permit / EEA Registration) ───────
            ("NO", "immigration", "no.permit_type_confirmed",
             "Has the work authorisation type been confirmed? (Skilled Worker Permit for non-EU/EEA, or Registration Certificate for EU/EEA nationals)",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Norway","NO","Oslo"]}', 10),
            ("NO", "immigration", "no.udi_application_submitted",
             "Has the Skilled Worker Permit application been submitted to UDI (Utlendingsdirektoratet)?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Norway","NO","Oslo"]}', 20),
            ("NO", "immigration", "no.permit_granted",
             "Has the Norwegian work permit or EEA registration certificate been granted?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Norway","NO","Oslo"]}', 30),
            ("NO", "registration", "no.d_number",
             "Have you obtained a Norwegian D-number or national identity number (fødselsnummer) from Skatteetaten?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Norway","NO","Oslo"]}', 40),
            ("NO", "registration", "no.skattekort",
             "Have you obtained your tax card (Skattekort) from Skatteetaten? (Required before first payroll)",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Norway","NO","Oslo"]}', 50),
            ("NO", "registration", "no.folkeregisteret",
             "Have you registered your Norwegian address with the National Population Register (Folkeregisteret)?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Norway","NO","Oslo"]}', 60),
            ("NO", "insurance", "no.health_coverage",
             "Are you enrolled in the Norwegian National Insurance Scheme (Folketrygden) or do you have private coverage?",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Norway","NO","Oslo"]}', 70),
            ("NO", "immigration", "no.dependents",
             "Will any dependents (spouse, children) accompany you and require Norwegian family immigration permits?",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Norway","NO","Oslo"]}', 80),
            ("NO", "immigration", "no.dependent_details",
             "If yes, how many dependents will apply for Norwegian family immigration permits?",
             "text", None, False,
             '{"field":"relocationBasics.hasDependents","op":"==","value":true}', 90),
            # ── BR — Brazil (VITEM V / CRNM) ──────────────────────────────────
            ("BR", "immigration", "br.mte_authorization",
             "Has the employer obtained work authorisation approval from the Ministry of Labour (SINFRE/MTE)?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Brazil","BR","Rio de Janeiro"]}', 10),
            ("BR", "immigration", "br.consulate_appointment",
             "Has a consulate appointment been booked for the VITEM V (temporary worker) visa application?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Brazil","BR","Rio de Janeiro"]}', 20),
            ("BR", "immigration", "br.vitem_v_submitted",
             "Has the VITEM V work visa application been submitted at the Brazilian consulate?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Brazil","BR","Rio de Janeiro"]}', 30),
            ("BR", "immigration", "br.vitem_v_granted",
             "Has the VITEM V work visa been granted?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Brazil","BR","Rio de Janeiro"]}', 40),
            ("BR", "immigration", "br.crnm_registered",
             "Has the CRNM (Carteira de Registro Nacional Migratório) been registered at the Federal Police within 90 days of arrival?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Brazil","BR","Rio de Janeiro"]}', 50),
            ("BR", "registration", "br.cpf_registered",
             "Has your CPF (Cadastro de Pessoas Físicas) tax ID number been registered with Receita Federal?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Brazil","BR","Rio de Janeiro"]}', 60),
            ("BR", "insurance", "br.health_insurance",
             "Do you have Brazilian private health insurance (plano de saúde) in place?",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Brazil","BR","Rio de Janeiro"]}', 70),
            ("BR", "immigration", "br.dependents",
             "Will any dependents accompany you and require Brazilian visas or residency documents?",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Brazil","BR","Rio de Janeiro"]}', 80),
            # ── IT — Italy (Nulla Osta / Permesso di Soggiorno) ───────────────
            ("IT", "immigration", "it.nulla_osta",
             "Has the Nulla Osta (work authorisation) been obtained from the Sportello Unico per l'Immigrazione?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Italy","IT","Rome","Roma"]}', 10),
            ("IT", "immigration", "it.type_d_visa_submitted",
             "Has the National (Type D) visa application been submitted at the Italian consulate?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Italy","IT","Rome","Roma"]}', 20),
            ("IT", "immigration", "it.type_d_visa_granted",
             "Has the Italian National (Type D) visa been granted?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Italy","IT","Rome","Roma"]}', 30),
            ("IT", "immigration", "it.permesso_soggiorno",
             "Has the Permesso di Soggiorno (residence permit) application been submitted to the Questura within 8 working days of arrival?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Italy","IT","Rome","Roma"]}', 40),
            ("IT", "registration", "it.codice_fiscale",
             "Have you obtained your Italian tax code (Codice Fiscale) from the Agenzia delle Entrate?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Italy","IT","Rome","Roma"]}', 50),
            ("IT", "insurance", "it.asl_enrollment",
             "Have you enrolled in the Italian national healthcare system (SSN/ASL)?",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Italy","IT","Rome","Roma"]}', 60),
            ("IT", "registration", "it.residenza",
             "Have you registered your Italian address at the local municipality (Residenza anagrafica)?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Italy","IT","Rome","Roma"]}', 70),
            ("IT", "immigration", "it.dependents",
             "Will any dependents accompany you and require Italian family visas or residence permits?",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Italy","IT","Rome","Roma"]}', 80),
            # ── ES — Spain (Work & Residence Authorization / NIE) ─────────────
            ("ES", "immigration", "es.work_auth_submitted",
             "Has the combined work and residence authorisation (autorización de residencia y trabajo) been applied for?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Spain","ES","Madrid"]}', 10),
            ("ES", "immigration", "es.visa_granted",
             "Has the Spanish work/residence visa been granted at the consulate?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Spain","ES","Madrid"]}', 20),
            ("ES", "registration", "es.nie_obtained",
             "Have you obtained your NIE (Número de Identidad de Extranjero) — the Spanish foreigner identification number?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Spain","ES","Madrid"]}', 30),
            ("ES", "registration", "es.empadronamiento",
             "Have you completed the Empadronamiento (municipal address registration) at your local town hall (Ayuntamiento)?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Spain","ES","Madrid"]}', 40),
            ("ES", "immigration", "es.tie_submitted",
             "Has the TIE (Tarjeta de Identidad de Extranjero) residence card application been submitted to the Policía Nacional?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Spain","ES","Madrid"]}', 50),
            ("ES", "registration", "es.social_security",
             "Have you obtained your Spanish Social Security number (Número de Afiliación a la Seguridad Social)?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Spain","ES","Madrid"]}', 60),
            ("ES", "insurance", "es.health_coverage",
             "Do you have access to Spanish public healthcare (via Social Security) or private health insurance?",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Spain","ES","Madrid"]}', 70),
            ("ES", "immigration", "es.dependents",
             "Will any dependents accompany you and require Spanish family residence visas?",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Spain","ES","Madrid"]}', 80),
            # ── AU — Australia (TSS 482 / ENS 186) ───────────────────────────────
            ("AU", "immigration", "au.visa_type_confirmed",
             "Has the visa type been confirmed by your employer? (Temporary Skill Shortage subclass 482, or Employer Nomination subclass 186)",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Australia","AU","Sydney","Melbourne","Brisbane","Perth","Adelaide"]}', 10),
            ("AU", "immigration", "au.labour_market_testing",
             "Has Labour Market Testing (LMT) been completed and documented by the employer?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Australia","AU","Sydney","Melbourne","Brisbane","Perth","Adelaide"]}', 20),
            ("AU", "immigration", "au.skills_assessment",
             "Has the skills assessment been submitted to the relevant Australian assessing authority (if required for your occupation)?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Australia","AU","Sydney","Melbourne","Brisbane","Perth","Adelaide"]}', 30),
            ("AU", "immigration", "au.visa_lodged",
             "Has the visa application been lodged with the Australian Department of Home Affairs?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Australia","AU","Sydney","Melbourne","Brisbane","Perth","Adelaide"]}', 40),
            ("AU", "registration", "au.tfn_applied",
             "Have you applied for a Tax File Number (TFN) with the Australian Taxation Office (ATO)?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Australia","AU","Sydney","Melbourne","Brisbane","Perth","Adelaide"]}', 50),
            ("AU", "insurance", "au.medicare_health",
             "Have you enrolled in Medicare (if eligible) or arranged private overseas health insurance?",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Australia","AU","Sydney","Melbourne","Brisbane","Perth","Adelaide"]}', 60),
            ("AU", "registration", "au.superannuation",
             "Has your employer nominated or confirmed a superannuation fund for compulsory contributions?",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Australia","AU","Sydney","Melbourne","Brisbane","Perth","Adelaide"]}', 70),
            ("AU", "immigration", "au.dependents",
             "Will any dependents accompany you and require Australian secondary applicant visas?",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Australia","AU","Sydney","Melbourne","Brisbane","Perth","Adelaide"]}', 80),
            # ── CA — Canada (Work Permit / LMIA) ─────────────────────────────────
            ("CA", "immigration", "ca.permit_route_confirmed",
             "Has the work permit route been confirmed? (LMIA-required, LMIA-exempt via CUSMA/USMCA, Intracompany Transfer, or Express Entry)",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Canada","CA","Toronto","Vancouver","Montreal"]}', 10),
            ("CA", "immigration", "ca.lmia_obtained",
             "Has the employer obtained a positive Labour Market Impact Assessment (LMIA) from ESDC (if required for your work permit route)?",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Canada","CA","Toronto","Vancouver","Montreal"]}', 20),
            ("CA", "immigration", "ca.work_permit_submitted",
             "Has the Canadian work permit application been submitted online or at a port of entry?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Canada","CA","Toronto","Vancouver","Montreal"]}', 30),
            ("CA", "immigration", "ca.work_permit_granted",
             "Has the Canadian work permit been granted?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Canada","CA","Toronto","Vancouver","Montreal"]}', 40),
            ("CA", "registration", "ca.sin_obtained",
             "Have you obtained a Social Insurance Number (SIN) from Service Canada?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Canada","CA","Toronto","Vancouver","Montreal"]}', 50),
            ("CA", "insurance", "ca.provincial_health",
             "Have you enrolled in the provincial health insurance plan? (Note: most provinces have a 3-month waiting period — interim private insurance is recommended)",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Canada","CA","Toronto","Vancouver","Montreal"]}', 60),
            ("CA", "immigration", "ca.dependents",
             "Will any dependents accompany you and require open or restricted Canadian work/study permits?",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Canada","CA","Toronto","Vancouver","Montreal"]}', 70),
            # ── CH — Switzerland (Permit B/L) ─────────────────────────────────────
            ("CH", "immigration", "ch.permit_type_confirmed",
             "Has the Swiss residence/work permit type been confirmed with the cantonal migration office? (Permit L for short stay, B for annual stay)",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Switzerland","CH","Zurich","Geneva","Bern","Basel","Lausanne"]}', 10),
            ("CH", "immigration", "ch.cantonal_permit_submitted",
             "Has the cantonal migration office permit application been submitted by the employer?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Switzerland","CH","Zurich","Geneva","Bern","Basel","Lausanne"]}', 20),
            ("CH", "immigration", "ch.permit_granted",
             "Has the Swiss residence and work permit been granted?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Switzerland","CH","Zurich","Geneva","Bern","Basel","Lausanne"]}', 30),
            ("CH", "registration", "ch.commune_registration",
             "Have you registered your address at the local commune (Einwohnerkontrolle / contrôle des habitants) within 14 days of arrival?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Switzerland","CH","Zurich","Geneva","Bern","Basel","Lausanne"]}', 40),
            ("CH", "insurance", "ch.health_insurance",
             "Is mandatory Swiss health insurance (Krankenkasse / assurance maladie) in place? (Required within 3 months of arrival)",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Switzerland","CH","Zurich","Geneva","Bern","Basel","Lausanne"]}', 50),
            ("CH", "registration", "ch.ahv_number",
             "Have you received your AHV/AVS social security number from the cantonal compensation office?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Switzerland","CH","Zurich","Geneva","Bern","Basel","Lausanne"]}', 60),
            ("CH", "immigration", "ch.dependents",
             "Will any dependents accompany you and require Swiss family reunion permits?",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Switzerland","CH","Zurich","Geneva","Bern","Basel","Lausanne"]}', 70),
            # ── HK — Hong Kong (Employment Visa) ─────────────────────────────────
            ("HK", "immigration", "hk.employment_visa_submitted",
             "Has the employment visa application been submitted to the Hong Kong Immigration Department?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Hong Kong","HK","Kowloon"]}', 10),
            ("HK", "immigration", "hk.employment_visa_granted",
             "Has the Hong Kong employment visa been granted?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Hong Kong","HK","Kowloon"]}', 20),
            ("HK", "registration", "hk.hkid_obtained",
             "Have you obtained your Hong Kong Identity Card (HKID) at an Immigration Services Centre within 30 days of arrival?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Hong Kong","HK","Kowloon"]}', 30),
            ("HK", "registration", "hk.mpf_enrolled",
             "Has your employer enrolled you in the Mandatory Provident Fund (MPF) scheme?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Hong Kong","HK","Kowloon"]}', 40),
            ("HK", "registration", "hk.ird_tax",
             "Have you noted your obligations with the Inland Revenue Department (IRD) for salaries tax?",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Hong Kong","HK","Kowloon"]}', 50),
            ("HK", "immigration", "hk.dependents",
             "Will any dependents accompany you and require Hong Kong Dependant Visas?",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Hong Kong","HK","Kowloon"]}', 60),
            # ── JP — Japan (COE / Work Visa) ──────────────────────────────────────
            ("JP", "immigration", "jp.coe_obtained",
             "Has the Certificate of Eligibility (COE) been obtained from the Regional Immigration Services Bureau by the employer?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Japan","JP","Tokyo","Osaka","Fukuoka"]}', 10),
            ("JP", "immigration", "jp.work_visa_submitted",
             "Has the Japanese work visa application (Engineer/Specialist in Humanities or equivalent) been submitted at the consulate?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Japan","JP","Tokyo","Osaka","Fukuoka"]}', 20),
            ("JP", "immigration", "jp.work_visa_granted",
             "Has the Japanese work visa been granted?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Japan","JP","Tokyo","Osaka","Fukuoka"]}', 30),
            ("JP", "registration", "jp.juminhyo_registered",
             "Have you completed resident registration (Juminhyo) at the municipal office within 14 days of establishing residence?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Japan","JP","Tokyo","Osaka","Fukuoka"]}', 40),
            ("JP", "registration", "jp.my_number",
             "Have you received your My Number (Individual Number) notification card from the municipality?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Japan","JP","Tokyo","Osaka","Fukuoka"]}', 50),
            ("JP", "insurance", "jp.health_insurance",
             "Are you enrolled in Japanese health insurance via your employer (Shakai Hoken) or the National Health Insurance (Kokumin Kenko Hoken)?",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Japan","JP","Tokyo","Osaka","Fukuoka"]}', 60),
            ("JP", "immigration", "jp.dependents",
             "Will any dependents accompany you and require Japanese Dependent (Kazoku Taizai) visas?",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Japan","JP","Tokyo","Osaka","Fukuoka"]}', 70),
            # ── NL — Netherlands (Highly Skilled Migrant / IND) ──────────────────
            ("NL", "immigration", "nl.kennismigrant_confirmed",
             "Has the Highly Skilled Migrant (Kennismigrant) permit route been confirmed with the IND by the recognised employer?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Netherlands","NL","Amsterdam","Rotterdam","Utrecht","The Hague"]}', 10),
            ("NL", "immigration", "nl.ind_application_submitted",
             "Has the IND (Immigratie en Naturalisatiedienst) permit application been submitted by the employer?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Netherlands","NL","Amsterdam","Rotterdam","Utrecht","The Hague"]}', 20),
            ("NL", "immigration", "nl.residence_permit_granted",
             "Has the Dutch residence permit (verblijfsvergunning) been granted?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Netherlands","NL","Amsterdam","Rotterdam","Utrecht","The Hague"]}', 30),
            ("NL", "registration", "nl.bsn_obtained",
             "Have you obtained a BSN (Burgerservicenummer — Dutch citizen service number) at the municipality?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Netherlands","NL","Amsterdam","Rotterdam","Utrecht","The Hague"]}', 40),
            ("NL", "insurance", "nl.health_insurance",
             "Is mandatory Dutch health insurance (basisverzekering) in place? (Required within 4 months of registering as resident)",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Netherlands","NL","Amsterdam","Rotterdam","Utrecht","The Hague"]}', 50),
            ("NL", "registration", "nl.digid_applied",
             "Have you applied for a DigiD (Dutch digital identity) for access to online government services?",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Netherlands","NL","Amsterdam","Rotterdam","Utrecht","The Hague"]}', 60),
            ("NL", "immigration", "nl.dependents",
             "Will any dependents accompany you and require Dutch family reunification permits?",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["Netherlands","NL","Amsterdam","Rotterdam","Utrecht","The Hague"]}', 70),
            # ── AE — UAE (Employment Entry Permit / Residence Visa) ───────────────
            ("AE", "immigration", "ae.entry_permit_obtained",
             "Has the Employment Entry Permit been obtained from MOHRE (Ministry of Human Resources and Emiratisation)?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["UAE","AE","Dubai","Abu Dhabi","Sharjah"]}', 10),
            ("AE", "immigration", "ae.medical_fitness",
             "Has the mandatory medical fitness test (including blood test and chest X-ray) been completed in the UAE?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["UAE","AE","Dubai","Abu Dhabi","Sharjah"]}', 20),
            ("AE", "immigration", "ae.residence_visa_stamped",
             "Has the UAE residence visa been stamped in the passport by the General Directorate of Residency and Foreigners Affairs (GDRFA)?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["UAE","AE","Dubai","Abu Dhabi","Sharjah"]}', 30),
            ("AE", "registration", "ae.emirates_id",
             "Has the Emirates ID application been submitted to the ICP (Federal Authority for Identity, Citizenship, Customs and Port Security)?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["UAE","AE","Dubai","Abu Dhabi","Sharjah"]}', 40),
            ("AE", "registration", "ae.work_permit_issued",
             "Has the MOHRE work permit / labour card been issued?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["UAE","AE","Dubai","Abu Dhabi","Sharjah"]}', 50),
            ("AE", "insurance", "ae.health_insurance",
             "Is UAE mandatory health insurance in place? (Required by law; employer must provide for employees in Dubai and Abu Dhabi)",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["UAE","AE","Dubai","Abu Dhabi","Sharjah"]}', 60),
            ("AE", "immigration", "ae.dependents",
             "Will any dependents accompany you and require UAE residence visas as your dependants?",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["UAE","AE","Dubai","Abu Dhabi","Sharjah"]}', 70),
            # ── ZA — South Africa (Critical Skills / Work Visa) ───────────────────
            ("ZA", "immigration", "za.visa_type_confirmed",
             "Has the visa type been confirmed? (Critical Skills Work Visa, General Work Visa, or Intra-Company Transfer Work Visa)",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["South Africa","ZA","Johannesburg","Cape Town","Durban","Pretoria"]}', 10),
            ("ZA", "immigration", "za.saqa_evaluation",
             "Has the SAQA (South African Qualifications Authority) foreign qualification evaluation been submitted (if required for your visa category)?",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["South Africa","ZA","Johannesburg","Cape Town","Durban","Pretoria"]}', 20),
            ("ZA", "immigration", "za.work_visa_submitted",
             "Has the South African work visa application been submitted at the nearest VFS Global / SA mission?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["South Africa","ZA","Johannesburg","Cape Town","Durban","Pretoria"]}', 30),
            ("ZA", "immigration", "za.work_visa_granted",
             "Has the South African work visa been granted?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["South Africa","ZA","Johannesburg","Cape Town","Durban","Pretoria"]}', 40),
            ("ZA", "registration", "za.sars_tax_number",
             "Have you registered with SARS (South African Revenue Service) for a South African tax number?",
             "boolean", None, True,
             '{"field":"relocationBasics.destCountry","op":"in","value":["South Africa","ZA","Johannesburg","Cape Town","Durban","Pretoria"]}', 50),
            ("ZA", "insurance", "za.health_insurance",
             "Do you have private health insurance (medical aid scheme) in South Africa? (Public healthcare has long wait times — private cover is strongly recommended)",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["South Africa","ZA","Johannesburg","Cape Town","Durban","Pretoria"]}', 60),
            ("ZA", "immigration", "za.dependents",
             "Will any dependents accompany you and require South African relative's visas?",
             "boolean", None, False,
             '{"field":"relocationBasics.destCountry","op":"in","value":["South Africa","ZA","Johannesburg","Cape Town","Durban","Pretoria"]}', 70),
        ]
        now = datetime.utcnow().isoformat()
        for row in _SEED:
            dest, domain, qkey, qtext, atype, opts, mandatory, applies, sort = row
            try:
                with self.engine.connect() as conn:
                    existing = conn.execute(
                        text("SELECT id FROM dossier_questions WHERE destination_country=:d AND question_key=:k"),
                        {"d": dest, "k": qkey},
                    ).fetchone()
                if existing:
                    continue
                with self.engine.begin() as conn:
                    conn.execute(
                        text(
                            "INSERT INTO dossier_questions "
                            "(id, destination_country, domain, question_key, question_text, answer_type, "
                            "options, is_mandatory, applies_if, sort_order, version, created_at) "
                            "VALUES (:id,:dest,:domain,:key,:text,:atype,:opts,:mand,:app,:sort,1,:now)"
                        ),
                        {
                            "id": str(uuid.uuid4()), "dest": dest, "domain": domain,
                            "key": qkey, "text": qtext, "atype": atype,
                            "opts": json.dumps(opts) if opts is not None else None,
                            "mand": 1 if mandatory else 0,
                            "app": applies, "sort": sort, "now": now,
                        },
                    )
                log.info("dossier_question seeded: %s / %s", dest, qkey)
            except Exception as e:
                log.warning("dossier_question seed skipped (%s/%s): %s", dest, qkey, e)

    def list_dossier_questions(self, destination_country: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM dossier_questions WHERE destination_country = :dest "
                "ORDER BY sort_order ASC, created_at ASC"
            ), {"dest": destination_country}).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            item["options"] = self._json_load(item.get("options"))
            item["applies_if"] = self._json_load(item.get("applies_if"))
        return items

    def list_dossier_answers(self, case_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Prefers canonical_case_id, falls back to case_id."""
        cid = self.coalesce_case_lookup_id(case_id)
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT * FROM dossier_answers WHERE (canonical_case_id = :cid OR case_id = :cid) AND user_id = :uid"
            ), {"cid": cid, "uid": user_id}).fetchall()
        items = self._rows_to_list(rows)
        for item in items:
            item["answer"] = self._json_load(item.get("answer_json"))
        return items

    def upsert_dossier_answers(self, case_id: str, user_id: str, answers: List[Dict[str, Any]]) -> None:
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            for ans in answers:
                payload = {
                    "id": ans.get("id") or str(uuid.uuid4()),
                    "cid": case_id,
                    "uid": user_id,
                    "qid": ans["question_id"],
                    "answer": json.dumps(ans["answer"]),
                    "answered_at": now,
                }
                conn.execute(text(
                    "INSERT INTO dossier_answers (id, case_id, user_id, question_id, answer_json, answered_at) "
                    "VALUES (:id, :cid, :uid, :qid, :answer, :answered_at) "
                    "ON CONFLICT(case_id, user_id, question_id) DO UPDATE SET "
                    "answer_json = excluded.answer_json, answered_at = excluded.answered_at"
                ), payload)

    def save_employee_answer(self, assignment_id: str, question_id: str, answer: Any) -> None:
        with self.engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO employee_answers (assignment_id, question_id, answer_json, created_at) "
                "VALUES (:aid, :qid, :aj, :ca)"
            ), {
                "aid": assignment_id, "qid": question_id,
                "aj": json.dumps(answer), "ca": datetime.utcnow().isoformat(),
            })

    def get_employee_answers(self, assignment_id: str) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT question_id, answer_json FROM employee_answers "
                "WHERE assignment_id = :aid ORDER BY created_at"
            ), {"aid": assignment_id}).fetchall()
        return self._rows_to_list(rows)

    def insert_policy_assistant_answer_audit(
        self,
        *,
        company_id: str,
        asked_by_user_id: str,
        question_text: str,
        answer_text: str,
        evidence_status: str,
        case_id: Optional[str] = None,
        question_session_id: Optional[str] = None,
        policy_document_id: Optional[str] = None,
        snapshot_id: Optional[str] = None,
        extraction_run_id: Optional[str] = None,
        normalized_question_topic: Optional[str] = None,
        fact_ids: Optional[List[str]] = None,
        chunk_ids: Optional[List[str]] = None,
        applicability_decision_json: Optional[Dict[str, Any]] = None,
        ambiguity_flags_json: Optional[List[Any]] = None,
    ) -> str:
        if not self.policy_hardening_tables_available():
            return ""
        aid = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO policy_assistant_answer_audits
                    (id, company_id, case_id, asked_by_user_id, question_session_id, policy_document_id,
                     snapshot_id, extraction_run_id, question_text, normalized_question_topic, answer_text,
                     evidence_status, fact_ids_json, chunk_ids_json, applicability_decision_json,
                     ambiguity_flags_json, created_at)
                    VALUES (:id, :cid, :case_id, :uid, :qs, :pd, :snap, :run, :qt, :nt, :at, :ev,
                     :fj, :cj, :adj, :afj, :now)
                    """
                ),
                {
                    "id": aid,
                    "cid": company_id,
                    "case_id": case_id,
                    "uid": asked_by_user_id,
                    "qs": question_session_id,
                    "pd": policy_document_id,
                    "snap": snapshot_id,
                    "run": extraction_run_id,
                    "qt": question_text,
                    "nt": normalized_question_topic,
                    "at": answer_text,
                    "ev": evidence_status,
                    "fj": json.dumps(fact_ids or []),
                    "cj": json.dumps(chunk_ids or []),
                    "adj": json.dumps(applicability_decision_json or {}),
                    "afj": json.dumps(ambiguity_flags_json or []),
                    "now": now,
                },
            )
        return aid

    def list_policy_assistant_answer_audits(
        self,
        *,
        company_id: Optional[str] = None,
        case_id: Optional[str] = None,
        snapshot_id: Optional[str] = None,
        evidence_status: Optional[str] = None,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        from ..database import _coerce_json_dict  # lazy: avoid import cycle
        if not self.policy_hardening_tables_available():
            return []
        where = ["1=1"]
        params: Dict[str, Any] = {"lim": limit}
        if company_id:
            where.append("company_id = :cid")
            params["cid"] = company_id
        if case_id:
            where.append("case_id = :case_id")
            params["case_id"] = case_id
        if snapshot_id:
            where.append("snapshot_id = :sid")
            params["sid"] = snapshot_id
        if evidence_status:
            where.append("evidence_status = :ev")
            params["ev"] = evidence_status
        if created_after:
            where.append("created_at >= :ca")
            params["ca"] = created_after
        if created_before:
            where.append("created_at <= :cb")
            params["cb"] = created_before
        sql = (
            "SELECT * FROM policy_assistant_answer_audits WHERE "
            + " AND ".join(where)
            + " ORDER BY created_at DESC LIMIT :lim"
        )
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()
        items = self._rows_to_list(rows)
        for d in items:
            d["fact_ids_json"] = _coerce_json_dict(d.get("fact_ids_json"))
            d["chunk_ids_json"] = _coerce_json_dict(d.get("chunk_ids_json"))
            d["applicability_decision_json"] = _coerce_json_dict(d.get("applicability_decision_json"))
            d["ambiguity_flags_json"] = _coerce_json_dict(d.get("ambiguity_flags_json"))
        return items
