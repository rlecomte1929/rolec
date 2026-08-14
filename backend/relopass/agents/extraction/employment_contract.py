"""EMPLOYMENT_CONTRACT Extraction Agent (C1-05c · AIQ-1766).

Multi-jurisdiction (FR CDI/CDD, DE Arbeitsvertrag, NO arbeidskontrakt). The three
locale prompts shipped in PR #163; only this agent was missing, which is why
``document_type_vocabulary`` parked EMPLOYMENT_CONTRACT in CLASSIFIER_PENDING_RUNTIME.

The emitted fields feed two consumers that already exist:
  * ``contradiction.py`` — ``employer_legal_name`` and ``gross_salary_annual`` are
    in COHORT_1_FIELD_KEYS (salary compared across documents at ±5 %).
  * the prefill / data-sheet paths, which want employer + position + salary + start date.

Three things here differ from the other extraction agents, each deliberate:

1. **One document-type code, locale chosen from the document's own text.** AIQ-1774
   split TAX_CERT into three codes because a runtime ``issuing_country`` selector was
   supplied by nothing and left three agents inert. The lesson is "never require a
   signal nothing supplies" — not "always split the code". Here the signal comes from
   the document itself, so ``run(document)`` keeps the orchestrator's calling
   convention with nothing extra to thread through. A split would also contradict the
   C1-04a classifier, which emits exactly one EMPLOYMENT_CONTRACT code, and the three
   prompts share an identical output schema (unlike the tax certificates, whose
   locales genuinely differ in the fields they carry).

2. **PII is masked before the LLM call** (GDPR Art. 28/44, root CLAUDE.md). No other
   agent in this package does this yet; this one does it at its own call site.

3. **Registry IDs are recovered from raw text on-platform**, because masking destroys
   them: ``mask_pii("SIREN 552 120 222")`` → ``"SIREN [REDACTED_PHONE]"`` (a 9-digit
   space-grouped run is indistinguishable from a phone number). The raw text never
   leaves the platform, so the data-minimisation rule is satisfied while
   ``employer_registry_id`` — which the NO data sheet needs as employer_org_number —
   still gets extracted. DE "HRB 12345" survives masking and comes back from the LLM.

The prompt annualises the salary itself (``gross_salary_annual`` is a decimal string
already scaled per the locale's ×12 / ×13 / ×12.92 rules), so this agent parses rather
than recomputes it.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal, Mapping, Optional, Tuple
from uuid import UUID, uuid4

from backend.app.services.pii_masker import mask_pii, safe_log_text
from backend.relopass.normalize import normalize_employer, parse_date

from ..models import (
    ExtractedField,
    ExtractionAgent,
    ExtractionAgentVersion,
    ParsedDocument,
)
from ..registry import AgentRegistry, SaveResult
from ..runtime import ExtractionSink
from ._common import call_llm_with_retry, make_field

logger = logging.getLogger(__name__)


EMPLOYMENT_CONTRACT_AGENT_NAME = "employment_contract"
EMPLOYMENT_CONTRACT_DOCUMENT_TYPE = "EMPLOYMENT_CONTRACT"


Jurisdiction = Literal["FR", "DE", "NO"]

JURISDICTION_COUNTRY_ISO3: Mapping[str, str] = {"FR": "FRA", "DE": "DEU", "NO": "NOR"}


_PROMPTS_DIR = Path(__file__).resolve().parents[4] / "prompts" / "extraction"

_PROMPT_PATHS: Mapping[str, Path] = {
    "FR": _PROMPTS_DIR / "employment_contract_fr_v1.txt",
    "DE": _PROMPTS_DIR / "employment_contract_de_v1.txt",
    "NO": _PROMPTS_DIR / "employment_contract_no_v1.txt",
}


def load_employment_contract_prompt(jurisdiction: str) -> str:
    """Load the locale prompt. Raises KeyError for an unknown jurisdiction —
    callers resolve it via ``detect_jurisdiction`` first, which returns None
    rather than guessing."""
    return _PROMPT_PATHS[jurisdiction].read_text(encoding="utf-8")


def _all_prompts_concatenated() -> str:
    """All three prompts, so the agent's version hash changes when any of them
    does. The per-run prompt is still the single locale one."""
    return "\n\n=== PROMPT BREAK ===\n\n".join(
        load_employment_contract_prompt(j) for j in ("FR", "DE", "NO")
    )


# ─────────────────────────────────────────────────────────────────────────────
# Jurisdiction detection
# ─────────────────────────────────────────────────────────────────────────────
#
# Cues are drawn from the contract's own vocabulary: the document title, the
# statutory contract-type words, and the salary/party terms that appear in
# essentially every contract of that jurisdiction. Scored rather than
# first-match so a passing mention of one language ("CDI" inside a German
# contract's history clause) cannot outvote the document's actual language.

_JURISDICTION_CUES: Mapping[str, Tuple[str, ...]] = {
    "FR": (
        "contrat de travail",
        "durée indéterminée",
        "durée déterminée",
        "salarié",
        "rémunération",
        "employeur",
        "convention collective",
        "période d'essai",
    ),
    "DE": (
        "arbeitsvertrag",
        "arbeitnehmer",
        "arbeitgeber",
        "bruttogehalt",
        "vergütung",
        "probezeit",
        "arbeitszeit",
        "kündigungsfrist",
    ),
    "NO": (
        "arbeidsavtale",
        "arbeidskontrakt",
        "arbeidstaker",
        "arbeidsgiver",
        "månedslønn",
        "årslønn",
        "prøvetid",
        "stillingsprosent",
    ),
}

# Standalone contract-type tokens, matched on word boundaries so "CDI" does not
# fire inside "CDISC". Weighted the same as a cue phrase.
_JURISDICTION_TOKENS: Mapping[str, Tuple[str, ...]] = {
    "FR": ("cdi", "cdd"),
    "DE": ("gmbh", "hrb", "hra"),
    # Deliberately not "as" (the Norwegian AS suffix): lowercased, \bas\b matches
    # the English word in any document and would outvote the real language.
    "NO": ("orgnr", "aksjeselskap", "arbeidsmiljøloven"),
}


def detect_jurisdiction(text: str) -> Optional[str]:
    """Return "FR" | "DE" | "NO", or None when the text names no locale.

    None is a real outcome, not an error: guessing a locale would run the wrong
    prompt and emit confidently wrong fields, which is worse than extracting
    nothing. The caller skips the LLM entirely in that case.
    """
    if not text:
        return None
    lower = text.lower()
    scores = {
        j: sum(1 for cue in cues if cue in lower)
        for j, cues in _JURISDICTION_CUES.items()
    }
    for j, tokens in _JURISDICTION_TOKENS.items():
        for token in tokens:
            if re.search(rf"\b{re.escape(token)}\b", lower):
                scores[j] += 1

    best = max(scores, key=lambda j: scores[j])
    if scores[best] == 0:
        return None
    # A tie means the evidence is genuinely ambiguous — treat it as undetected.
    if sum(1 for v in scores.values() if v == scores[best]) > 1:
        return None
    return best


# ─────────────────────────────────────────────────────────────────────────────
# Registry-ID recovery from raw (unmasked) text
# ─────────────────────────────────────────────────────────────────────────────
#
# Runs in-process on text that is never sent anywhere. Anchored on the cue word
# that precedes the number in every real contract, so a bare 9-digit run
# elsewhere in the document cannot be mistaken for a company number.

_REGISTRY_ID_PATTERNS: Mapping[str, "re.Pattern[str]"] = {
    "FR": re.compile(
        r"\b(?:SIRET|SIREN|RCS)\b[^0-9]{0,24}((?:\d[\s.]?){9,14})",
        re.IGNORECASE,
    ),
    "DE": re.compile(
        r"\b(HRB|HRA)\b[^0-9]{0,24}(\d{1,10})",
        re.IGNORECASE,
    ),
    "NO": re.compile(
        r"\b(?:organisasjonsnummer|foretaksnummer|org\.?\s?nr\.?)\b[^0-9]{0,24}"
        r"((?:\d[\s.]?){9})",
        re.IGNORECASE,
    ),
}


def recover_registry_id(raw_text: str, jurisdiction: str) -> Optional[str]:
    """Pull the employer registry ID out of unmasked contract text.

    Returns it in the canonical shape each prompt specifies: digits-only for FR
    (SIREN 9 / SIRET 14) and NO (organisasjonsnummer 9), "HRB <digits>" for DE.
    None when no cue-anchored number is present.
    """
    pattern = _REGISTRY_ID_PATTERNS.get(jurisdiction)
    if not pattern or not raw_text:
        return None
    match = pattern.search(raw_text)
    if match is None:
        return None

    if jurisdiction == "DE":
        return f"{match.group(1).upper()} {match.group(2)}"

    digits = re.sub(r"\D", "", match.group(1))
    if jurisdiction == "FR" and len(digits) in (9, 14):
        return digits
    if jurisdiction == "NO" and len(digits) == 9:
        return digits
    return None


def _registry_id_kind(registry_id: Optional[str], jurisdiction: str) -> Optional[str]:
    """The prompt's `employer_registry_id_kind` enum, derived from the ID shape."""
    if not registry_id:
        return None
    if jurisdiction == "FR":
        return {9: "SIREN", 14: "SIRET"}.get(len(re.sub(r"\D", "", registry_id)))
    if jurisdiction == "DE":
        head = registry_id.strip().upper()[:3]
        return head if head in ("HRB", "HRA") else None
    if jurisdiction == "NO":
        return "ORGNR"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Value coercion
# ─────────────────────────────────────────────────────────────────────────────


def _confidence_band_to_float(band: Any) -> float:
    """The prompts emit per-field confidence as a high/medium/low band. Same
    mapping as ``passport_td3._confidence_band_to_float`` so the numbers mean
    the same thing across agents. Unknown/absent → the 0.9 make_field default."""
    if isinstance(band, bool):
        return 0.9
    if isinstance(band, (int, float)):
        return max(0.0, min(1.0, float(band)))
    if isinstance(band, str):
        return {"high": 0.95, "medium": 0.75, "low": 0.50}.get(band.strip().lower(), 0.9)
    return 0.9


def _parse_decimal(raw: Any) -> Optional[Decimal]:
    """The prompt emits gross_salary_annual as a 2-dp decimal string, already
    annualised. Malformed input yields None rather than raising — fail-soft."""
    if raw is None or raw == "":
        return None
    try:
        # Strip any whitespace, including the NBSP/thin-space thousands
        # separators FR and NO documents use.
        value = Decimal(re.sub(r"\s", "", str(raw)))
    except (InvalidOperation, ValueError):
        logger.warning(
            "employment_contract: unparseable gross_salary_annual %r — field dropped",
            safe_log_text(str(raw)),
        )
        return None
    if value <= 0:
        return None
    return value


def _normalize_date(raw: Any, jurisdiction: str) -> Optional[date]:
    """The prompt already emits ISO-8601. Re-parsing through the C1-06 date
    library with a locale hint is a cheap guard against a model that answered in
    the document's own format anyway."""
    if not raw:
        return None
    parsed = parse_date(str(raw), locale_hint=jurisdiction.lower())
    if parsed.iso is None:
        return None
    try:
        return date.fromisoformat(parsed.iso)
    except ValueError:
        return None


# Salary components that make the pay not guaranteed-fixed-only. Matched against
# the raw contract text as a cross-check on the LLM's boolean, because this
# binary gates the IN→DE Blue Card salary-threshold decision downstream — a false
# "fixed only" would clear a threshold the employee does not actually meet.
# English terms are included: contracts borrow them in all three languages.
NON_FIXED_TRIGGERS: Tuple[str, ...] = (
    "commission",
    "bonus",
    "boni",
    "variable",
    "target",
    "stock option",
    "sign-on",
    "signon",
    "prime variable",
    "prime cible",
    "intéressement",
    "participation",
    "tantieme",
    "tantième",
    "provision",
    "erfolgsbeteiligung",
    "leistungsprämie",
    "resultatlønn",
    "provisjon",
)


def is_guaranteed_fixed_only(contract_text: str) -> bool:
    """True when the text names no variable-pay component."""
    lower = (contract_text or "").lower()
    return not any(trigger in lower for trigger in NON_FIXED_TRIGGERS)


# ─────────────────────────────────────────────────────────────────────────────
# ExtractionAgent definition (lazy singleton)
# ─────────────────────────────────────────────────────────────────────────────


def _build_agent() -> ExtractionAgent:
    return ExtractionAgent(
        name=EMPLOYMENT_CONTRACT_AGENT_NAME,
        description=(
            "Multi-jurisdiction EMPLOYMENT_CONTRACT extraction (FR CDI/CDD, DE "
            "Arbeitsvertrag, NO arbeidskontrakt). Emits employer, position, "
            "annualised gross salary + currency, start date, duration and "
            "working-time percent, each with per-field confidence."
        ),
        extraction_instructions=_all_prompts_concatenated(),
        value_type="enum",
        unit=None,
        dimensions="structured: employer + position + salary + dates",
        resolution_instructions=(
            "Salary arrives already annualised per the locale prompt (×12 default; "
            "×13 for a guaranteed DE Weihnachtsgeld / FR 13e mois; ×12.92 for "
            "explicit NO feriepenger) and is parsed, not recomputed. Ambiguous "
            "salary → null + low confidence; precision over recall. Employer "
            "registry IDs are recovered from the unmasked document text on-platform "
            "because masking redacts the 9-digit SIREN/organisasjonsnummer shapes."
        ),
        inconsistency_instructions=(
            "If the document is not an employment contract (CDI/CDD/Arbeitsvertrag/"
            "arbeidsavtale), set is_employment_contract=false and emit no fields. "
            "If no jurisdiction can be read from the text, emit no fields rather "
            "than running an arbitrary locale prompt."
        ),
        enable_web_search=False,
        enable_complex_calculations_in_resolution=False,
        examples=(),
        # Deliberately the four keys downstream depends on, not all 11 the prompt
        # marks required: a missing nullable key would otherwise force a paid
        # escalation retry to claude-sonnet-4-6 on every otherwise-fine response.
        output_schema_required_keys=(
            "is_employment_contract",
            "employer_legal_name",
            "gross_salary_annual",
            "currency_iso3",
        ),
    )


_AGENT_SINGLETON: Optional[ExtractionAgent] = None


def _get_agent() -> ExtractionAgent:
    global _AGENT_SINGLETON
    if _AGENT_SINGLETON is None:
        _AGENT_SINGLETON = _build_agent()
    return _AGENT_SINGLETON


# ─────────────────────────────────────────────────────────────────────────────
# Result
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class EmploymentContractResult:
    agent_run_id: UUID
    agent_version_id: UUID
    jurisdiction: Optional[str]
    fields: Tuple[ExtractedField, ...]
    llm_payload: Mapping[str, Any]
    gross_salary_annual: Optional[Decimal]
    currency_iso3: Optional[str]
    guaranteed_fixed_only: Optional[bool]
    model_name: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    skipped_reason: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Agent
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class EmploymentContractAgent:
    registry: AgentRegistry
    sink: ExtractionSink
    agent_override: Optional[ExtractionAgent] = None
    _agent_version: Optional[ExtractionAgentVersion] = field(
        default=None, init=False, repr=False
    )

    def register(self) -> SaveResult:
        agent = self.agent_override or _get_agent()
        result = self.registry.save_agent(agent)
        self._agent_version = result.version
        return result

    @property
    def agent_version(self) -> ExtractionAgentVersion:
        if self._agent_version is None:
            raise RuntimeError("EmploymentContractAgent.run() called before register()")
        return self._agent_version

    async def run(self, document: ParsedDocument) -> EmploymentContractResult:
        version = self.agent_version
        agent_run_id = uuid4()
        started_at = datetime.now(tz=timezone.utc)
        raw_text = document.text or ""

        jurisdiction = detect_jurisdiction(raw_text)
        if jurisdiction is None:
            logger.info(
                "employment_contract: no jurisdiction detected for doc=%s — "
                "skipping the LLM call",
                document.document_id,
            )
            return self._empty_result(
                document=document,
                agent_run_id=agent_run_id,
                started_at=started_at,
                reason="jurisdiction_undetected",
            )

        # GDPR Art. 28/44 — nothing unmasked reaches the LLM sub-processor.
        prompt = (
            load_employment_contract_prompt(jurisdiction)
            + "\n\n=== DOCUMENT TEXT ===\n\n"
            + mask_pii(raw_text)
        )
        llm = await call_llm_with_retry(
            prompt,
            required_keys=version.output_schema_required_keys,
            case_id=str(document.case_id) if document.case_id else None,
        )
        payload = llm.payload

        if payload.get("is_employment_contract") is False:
            logger.info(
                "employment_contract: doc=%s is not an employment contract",
                document.document_id,
            )
            return self._empty_result(
                document=document,
                agent_run_id=agent_run_id,
                started_at=started_at,
                reason="not_an_employment_contract",
                llm=llm,
                jurisdiction=jurisdiction,
            )

        country_iso3 = JURISDICTION_COUNTRY_ISO3[jurisdiction]
        source = f"llm_employment_contract_{jurisdiction.lower()}_v1"

        # The LLM sees masked text, so for FR/NO the registry ID comes back null;
        # recover it here from raw text that never left the process.
        registry_id = payload.get("employer_registry_id") or recover_registry_id(
            raw_text, jurisdiction
        )
        registry_id_kind = payload.get("employer_registry_id_kind") or _registry_id_kind(
            registry_id, jurisdiction
        )

        employer = None
        legal_name = payload.get("employer_legal_name")
        if legal_name:
            norm = normalize_employer(
                str(legal_name),
                country_iso3=country_iso3,
                registry_id=str(registry_id) if registry_id else None,
            )
            employer = {
                "legal_name_display": norm.legal_name_display,
                "legal_name_stripped": norm.legal_name_stripped,
                "legal_suffix": norm.legal_suffix,
                "registry_id": norm.registry_id,
                "registry_id_kind": norm.registry_id_kind,
                "country_iso3": norm.country_iso3,
            }

        gross_salary = _parse_decimal(payload.get("gross_salary_annual"))
        currency_iso3 = payload.get("currency_iso3")
        start_date = _normalize_date(payload.get("contract_start_date"), jurisdiction)

        # Trust the model when it commits, but a variable-pay mention in the text
        # overrides a "fixed only" claim — never the other way round.
        llm_fixed_only = payload.get("gross_salary_guaranteed_fixed_only_bool")
        text_fixed_only = is_guaranteed_fixed_only(raw_text)
        guaranteed_fixed_only = (
            bool(llm_fixed_only) and text_fixed_only
            if isinstance(llm_fixed_only, bool)
            else text_fixed_only
        )

        def _conf(key: str) -> float:
            return _confidence_band_to_float(payload.get(f"{key}_confidence"))

        raw_fields = (
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="contract_type",
                value=payload.get("contract_type"),
                source=source,
                confidence=_conf("contract_type"),
                canonical_extras={"jurisdiction": jurisdiction},
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="employer_legal_name",
                value=(employer or {}).get("legal_name_display") or legal_name,
                source=f"{source}+normalize_employers",
                confidence=_conf("employer_legal_name"),
                canonical_extras=employer or {},
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="employer_registry_id",
                value=(employer or {}).get("registry_id") or registry_id,
                source=(
                    source
                    if payload.get("employer_registry_id")
                    else "raw_text_recovery+normalize_employers"
                ),
                confidence=_conf("employer_registry_id"),
                canonical_extras={
                    "kind": (employer or {}).get("registry_id_kind") or registry_id_kind,
                    "recovered_from_raw_text": not payload.get("employer_registry_id"),
                },
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="position_title",
                value=payload.get("position_title"),
                source=source,
                confidence=_conf("position_title"),
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="position_isco_2008",
                value=payload.get("position_isco_2008"),
                source=source,
                confidence=_conf("position_isco_2008"),
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="gross_salary_annual",
                value=str(gross_salary) if gross_salary is not None else None,
                source=source,
                confidence=_conf("gross_salary_annual"),
                canonical_extras={
                    "currency_iso3": currency_iso3,
                    "jurisdiction": jurisdiction,
                    "annualized_by": "prompt",
                },
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="currency_iso3",
                value=currency_iso3,
                source=source,
                confidence=_conf("gross_salary_annual"),
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="gross_salary_guaranteed_fixed_only_bool",
                value=str(guaranteed_fixed_only).lower(),
                source=f"{source}+text_heuristic",
                confidence=_conf("gross_salary_guaranteed_fixed_only_bool"),
                canonical_extras={
                    "llm_value": llm_fixed_only,
                    "text_heuristic_value": text_fixed_only,
                },
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="contract_start_date",
                value=start_date.isoformat() if start_date else None,
                source=f"{source}+normalize_dates",
                confidence=_conf("contract_start_date"),
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="contract_duration_months",
                value=payload.get("contract_duration_months"),
                source=source,
                confidence=_conf("contract_duration_months"),
            ),
            make_field(
                document_id=document.document_id,
                agent_run_id=agent_run_id,
                key="working_time_percent",
                value=payload.get("working_time_percent"),
                source=source,
                confidence=_conf("working_time_percent"),
            ),
        )
        fields = tuple(f for f in raw_fields if f is not None)

        self.sink.write_agent_run(
            agent_run_id=agent_run_id,
            agent_version_id=version.agent_version_id,
            case_id=document.case_id,
            document_id=document.document_id,
            model_name=llm.model_name,
            tokens_in=llm.tokens_in,
            tokens_out=llm.tokens_out,
            cost_usd=llm.cost_usd,
            inputs_digest=llm.inputs_digest,
            output_digest=llm.output_digest,
            started_at=started_at,
            finished_at=datetime.now(tz=timezone.utc),
            status="OK",
        )
        self.sink.write_extracted_fields(fields)

        return EmploymentContractResult(
            agent_run_id=agent_run_id,
            agent_version_id=version.agent_version_id,
            jurisdiction=jurisdiction,
            fields=fields,
            llm_payload=payload,
            gross_salary_annual=gross_salary,
            currency_iso3=currency_iso3,
            guaranteed_fixed_only=guaranteed_fixed_only,
            model_name=llm.model_name,
            tokens_in=llm.tokens_in,
            tokens_out=llm.tokens_out,
            cost_usd=llm.cost_usd,
        )

    def run_sync(self, document: ParsedDocument) -> EmploymentContractResult:
        import asyncio

        return asyncio.run(self.run(document))

    # ---- helpers ----

    def _empty_result(
        self,
        *,
        document: ParsedDocument,
        agent_run_id: UUID,
        started_at: datetime,
        reason: str,
        llm: Any = None,
        jurisdiction: Optional[str] = None,
    ) -> EmploymentContractResult:
        """Record the run, emit no fields. Used for both "no locale readable" and
        "not an employment contract" — in each case extracting nothing is the
        correct answer, and the agent_run row is still written so the attempt is
        auditable."""
        version = self.agent_version
        self.sink.write_agent_run(
            agent_run_id=agent_run_id,
            agent_version_id=version.agent_version_id,
            case_id=document.case_id,
            document_id=document.document_id,
            model_name=llm.model_name if llm else "(none — LLM not called)",
            tokens_in=llm.tokens_in if llm else 0,
            tokens_out=llm.tokens_out if llm else 0,
            cost_usd=llm.cost_usd if llm else 0.0,
            inputs_digest=llm.inputs_digest if llm else "",
            output_digest=llm.output_digest if llm else "",
            started_at=started_at,
            finished_at=datetime.now(tz=timezone.utc),
            status="OK",
        )
        self.sink.write_extracted_fields(())
        return EmploymentContractResult(
            agent_run_id=agent_run_id,
            agent_version_id=version.agent_version_id,
            jurisdiction=jurisdiction,
            fields=(),
            llm_payload=llm.payload if llm else {},
            gross_salary_annual=None,
            currency_iso3=None,
            guaranteed_fixed_only=None,
            model_name=llm.model_name if llm else "(none — LLM not called)",
            tokens_in=llm.tokens_in if llm else 0,
            tokens_out=llm.tokens_out if llm else 0,
            cost_usd=llm.cost_usd if llm else 0.0,
            skipped_reason=reason,
        )
