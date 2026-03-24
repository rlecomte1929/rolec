"""
Deterministic policy assistant message classifier.

Maps user text to bounded intents and canonical topics. Rules-first; optional LLM hook
is intentionally not wired — any future LLM must still emit only contract enums.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field

from .policy_assistant_contract import (
    POLICY_ASSISTANT_TOPIC_ORDER,
    PolicyAssistantCanonicalTopic,
    PolicyAssistantIntent,
    PolicyAssistantRefusalCode,
    PolicyAssistantRoleScope,
)


class PolicyAssistantClassificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supported: bool = Field(..., description="True if in-domain and role-allowed for assistant handling.")
    intent: PolicyAssistantIntent
    canonical_topic: Optional[PolicyAssistantCanonicalTopic] = None
    ambiguity_reason: Optional[str] = Field(None, max_length=2000)
    refusal_code: Optional[PolicyAssistantRefusalCode] = None
    normalized_question: str = Field("", max_length=8000, description="Whitespace-normalized question text.")
    guardrail_note: Optional[str] = Field(
        None,
        max_length=2000,
        description="When set, non-policy parts of the message were dropped; answer only the policy thread.",
    )


# --- Normalization ---


def _normalize_message(message: str) -> str:
    if not message or not isinstance(message, str):
        return ""
    s = unicodedata.normalize("NFKD", message)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.strip().lower()
    s = re.sub(r"[\s\u00a0]+", " ", s)
    return s


def _parse_role(role: Union[str, PolicyAssistantRoleScope]) -> PolicyAssistantRoleScope:
    if isinstance(role, PolicyAssistantRoleScope):
        return role
    r = str(role or "").strip().lower()
    if r in ("hr", "admin"):
        return PolicyAssistantRoleScope.HR
    return PolicyAssistantRoleScope.EMPLOYEE


def _parse_available_topics(
    available_topics: Optional[Sequence[Union[str, PolicyAssistantCanonicalTopic]]],
) -> List[PolicyAssistantCanonicalTopic]:
    if not available_topics:
        return list(POLICY_ASSISTANT_TOPIC_ORDER)
    out: List[PolicyAssistantCanonicalTopic] = []
    for t in available_topics:
        if isinstance(t, PolicyAssistantCanonicalTopic):
            out.append(t)
            continue
        key = str(t).strip().lower().replace("-", "_")
        try:
            out.append(PolicyAssistantCanonicalTopic(key))
        except ValueError:
            continue
    return out if out else list(POLICY_ASSISTANT_TOPIC_ORDER)


# --- Global unsupported (runs before topic scoring) ---

_UNSUPPORTED_PATTERNS: List[Tuple[re.Pattern[str], PolicyAssistantRefusalCode]] = [
    (
        re.compile(
            r"\bnegotiate\b|\bbetter package\b|\b(counter[- ]?offer|renegotiate)\b",
            re.I,
        ),
        PolicyAssistantRefusalCode.OUT_OF_SCOPE_NEGOTIATION,
    ),
    (
        re.compile(
            r"\bwhich visa\b|\bwhat visa should\b|\bvisa should i\b|\bapply for (?:a |the )?visa\b",
            re.I,
        ),
        PolicyAssistantRefusalCode.OUT_OF_SCOPE_IMMIGRATION_BEYOND_POLICY,
    ),
    (
        re.compile(
            r"\bwhich school do you recommend\b|\brecommend (?:a |the )?school\b|\bbest school for\b|"
            r"\bwhich school (?:is best|should i (?:pick|choose))\b|\bbest schools?\b.*\b(?:for kids|in \w+)\b",
            re.I,
        ),
        PolicyAssistantRefusalCode.OUT_OF_SCOPE_SCHOOL_OR_NEIGHBORHOOD_ADVICE,
    ),
    (
        re.compile(
            r"\bneighborhood safe\b|\bis this (?:area|neighborhood) safe\b|\bsafe to live\b",
            re.I,
        ),
        PolicyAssistantRefusalCode.OUT_OF_SCOPE_SCHOOL_OR_NEIGHBORHOOD_ADVICE,
    ),
    (
        re.compile(
            r"\bwrite (?:an? )?email\b|\bdraft (?:an? )?email\b|\bemail to hr\b",
            re.I,
        ),
        PolicyAssistantRefusalCode.OUT_OF_SCOPE_UNRELATED_CHAT,
    ),
    (
        re.compile(
            r"\blegal advice\b|\b(?:talk to|hire|get) (?:a |an )?lawyer\b|\bnot legal advice\b",
            re.I,
        ),
        PolicyAssistantRefusalCode.OUT_OF_SCOPE_LEGAL_ADVICE,
    ),
    (
        re.compile(
            r"\bimmigration lawyer\b|\bimmigration attorney\b",
            re.I,
        ),
        PolicyAssistantRefusalCode.OUT_OF_SCOPE_IMMIGRATION_BEYOND_POLICY,
    ),
    (
        re.compile(
            r"\btax advice\b|\bhow much tax (?:will|would) i owe\b|\bshould i (?:file|claim)\b.*\bdeduction\b",
            re.I,
        ),
        PolicyAssistantRefusalCode.OUT_OF_SCOPE_TAX_BEYOND_POLICY,
    ),
    (
        re.compile(
            r"\bbest (?:restaurant|hotel)s?\b|\bthings to do in\b|\bweather in\b|\bflight deal\b|"
            r"\btourist\b.*\bvisit\b|\bvacation (?:spot|idea)s?\b",
            re.I,
        ),
        PolicyAssistantRefusalCode.OUT_OF_SCOPE_TRAVEL_OR_LIFESTYLE,
    ),
    (
        re.compile(
            r"\bignore\s+(?:all\s+)?(?:previous\s+)?(?:instructions|rules)\b|"
            r"\bignore\s+your\s+(?:instructions|rules)\b|"
            r"\bdisregard\s+(?:all\s+)?(?:your\s+)?(?:instructions|rules)\b|"
            r"\byou are (?:now )?(?:a |an )?(?:helpful )?assistant with no rules\b|"
            r"\bjailbreak\b|\bDAN mode\b",
            re.I,
        ),
        PolicyAssistantRefusalCode.OUT_OF_SCOPE_UNRELATED_CHAT,
    ),
    (
        re.compile(
            r"^(?:hi|hello|hey|good morning|good afternoon|how are you|what's up|sup)\b[!.?,\s]*$",
            re.I,
        ),
        PolicyAssistantRefusalCode.OUT_OF_SCOPE_UNRELATED_CHAT,
    ),
]

# Draft / publish: HR-only substantive classification
_DRAFT_PUBLISHED_HR = re.compile(
    r"\b(?:what|how)\s+(?:changes?|would change|happens?)\b.*\bdraft\b.*\b(?:publish|published)\b|"
    r"\bdraft\b.*\b(?:publish|published)\b.*\b(?:change|effect|impact|difference)\b|"
    r"\bwhy\s+publish\b.*\bdraft\b|"
    r"\bdraft\s+vs\.?\s*published\b|"
    r"\bpublished\s+vs\.?\s*draft\b",
    re.I,
)
_DRAFT_PUBLISHED_EMPLOYEE_PROBE = re.compile(
    r"\bdraft\b.*\b(?:publish|published)\b|\b(?:publish|published)\b.*\bdraft\b",
    re.I,
)

_HR_STRATEGY_UNSUPPORTED = re.compile(
    r"\bhow should we (?:as a company )?(?:structure|design) (?:our )?(?:compensation|benefits|policy)\b|"
    r"\bwhat should (?:hr|the company) (?:offer|pay|provide)\b.*\b(?:market|competitors?)\b|"
    r"\bwrite (?:the |our |a )?(?:entire |full )?policy (?:document )?(?:from scratch|for me)\b|"
    r"\bghostwrite\b.*\bpolicy\b",
    re.I,
)

_EMPLOYEE_VISIBILITY_HR = re.compile(
    r"\bwhat do employees see (?:now|today)\b|"
    r"\bwhat employees see (?:now|today)\b|"
    r"\bemployee(?:'s|s')? view (?:of |on )?(?:the )?policy\b|"
    r"\bemployees (?:currently )?see\b",
    re.I,
)

_OVERRIDE_EFFECT_HR = re.compile(
    r"\bwhat (?:does|will) (?:the |my )?hr override\b|"
    r"\boverride effect\b|"
    r"\bhow do(?:es)? (?:the )?overrides? affect\b|"
    r"\beffect of (?:the )?(?:hr )?override",
    re.I,
)

# Readiness / comparison phrasing (in-domain, often topic-agnostic)
_COMPARISON_READINESS_Q = re.compile(
    r"\bwhy\s+is\s+(?:this|it)\s+informational only\b|"
    r"\binformational only\b.*\?|"
    r"\bcomparison ready\b|"
    r"\bwhy\s+.*\b(?:not\s+)?compar(?:e|able|ison)\b",
    re.I,
)

_STATUS_Q = re.compile(
    r"\bis (?:the |my )?policy published\b|\bunder review\b|\bvisible to me\b|"
    r"\bwhen (?:will|can) (?:i|we) see\b.*\bpolicy\b",
    re.I,
)

_APPROVAL_Q = re.compile(
    r"\bapproval required\b|\bneed approval\b|\bis approval\b.*\brequired\b|"
    r"\bprior approval\b",
    re.I,
)


# Topic: (positive patterns or literals), negative patterns (if match, skip topic or penalize)
@dataclass(frozen=True)
class _TopicRule:
    topic: PolicyAssistantCanonicalTopic
    # Substrings or regex patterns (positive), weight
    phrases: Tuple[Tuple[Union[str, re.Pattern[str]], int], ...]
    negatives: Tuple[re.Pattern[str], ...] = ()


_TOPIC_RULES: Tuple[_TopicRule, ...] = (
    _TopicRule(
        PolicyAssistantCanonicalTopic.TEMPORARY_HOUSING,
        (
            ("temporary housing", 5),
            ("temp housing", 4),
            ("interim housing", 4),
            ("short-term housing", 4),
            (re.compile(r"\btemporary\b.*\b(accommodation|housing)\b", re.I), 4),
            # Weak signal — may tie with host_housing; disambiguation block handles ties
            (re.compile(r"\bhousing\b.*\bincluded\b|\bincluded\b.*\bhousing\b", re.I), 3),
        ),
        negatives=(
            re.compile(r"\bhost[- ]country housing\b|\bhost housing\b", re.I),
        ),
    ),
    _TopicRule(
        PolicyAssistantCanonicalTopic.HOST_HOUSING,
        (
            ("host housing", 6),
            ("host country housing", 6),
            ("host-country housing", 6),
            ("company-provided housing", 4),
            ("leased accommodation", 3),
            (re.compile(r"\bhousing\b.*\bincluded\b|\bincluded\b.*\bhousing\b", re.I), 3),
        ),
        negatives=(),
    ),
    _TopicRule(
        PolicyAssistantCanonicalTopic.HOME_SEARCH,
        (
            ("home search", 6),
            ("house hunting", 5),
            ("housing search", 4),
            ("look-see", 3),
            ("look see", 3),
        ),
        negatives=(),
    ),
    _TopicRule(
        PolicyAssistantCanonicalTopic.SHIPMENT,
        (
            ("shipment", 5),
            ("household goods", 5),
            ("shipping", 4),
            ("moving my stuff", 3),
            (re.compile(r"\bshipment cap\b", re.I), 6),
        ),
        negatives=(),
    ),
    _TopicRule(
        PolicyAssistantCanonicalTopic.SCHOOL_SEARCH,
        (
            ("school search", 6),
            ("schooling", 3),
            ("dependent children", 3),
            ("international school", 4),
            (re.compile(r"\bschool search\b.*\bfamily\b|\bfamily\b.*\bschool", re.I), 5),
        ),
        negatives=(
            re.compile(r"\brecommend\b|\bbest school\b|\bwhich school\b", re.I),
        ),
    ),
    _TopicRule(
        PolicyAssistantCanonicalTopic.SPOUSE_SUPPORT,
        (
            ("spouse support", 6),
            ("partner support", 5),
            ("dual career", 5),
            ("trailing spouse", 5),
            ("spousal allowance", 4),
        ),
        negatives=(),
    ),
    _TopicRule(
        PolicyAssistantCanonicalTopic.VISA_SUPPORT,
        (
            ("visa support", 5),
            ("visa processing", 5),
            ("immigration support", 4),
        ),
        negatives=(
            re.compile(r"\bwhich visa should\b|\bwhat visa should\b|\bapply for\b", re.I),
        ),
    ),
    _TopicRule(
        PolicyAssistantCanonicalTopic.WORK_PERMIT_SUPPORT,
        (
            ("work permit", 6),
            ("work permits", 6),
            ("work authorization", 5),
            ("residence permit", 4),
        ),
        negatives=(),
    ),
    _TopicRule(
        PolicyAssistantCanonicalTopic.TAX_BRIEFING,
        (
            ("tax briefing", 6),
            ("tax orientation", 5),
            ("hypothetical tax", 4),
        ),
        negatives=(
            re.compile(r"\btax return\b|\bfiling\b|\bfile my taxes\b", re.I),
        ),
    ),
    _TopicRule(
        PolicyAssistantCanonicalTopic.TAX_RETURN_SUPPORT,
        (
            ("tax return", 6),
            ("tax return support", 6),
            ("filing support", 4),
            (re.compile(r"\bfile (?:my |our )?taxes\b", re.I), 5),
        ),
        negatives=(),
    ),
    _TopicRule(
        PolicyAssistantCanonicalTopic.HOME_LEAVE,
        (
            ("home leave", 6),
            (re.compile(r"\br&r\b", re.I), 4),
            ("rest and recuperation", 5),
            ("trip home", 3),
        ),
        negatives=(),
    ),
    _TopicRule(
        PolicyAssistantCanonicalTopic.RELOCATION_ALLOWANCE,
        (
            ("relocation allowance", 6),
            ("lump sum", 4),
            ("mobility allowance", 5),
            ("settling in", 3),
        ),
        negatives=(),
    ),
)


def _score_topics(
    norm: str,
    allowed: List[PolicyAssistantCanonicalTopic],
    *,
    relaxed: bool = False,
) -> Dict[PolicyAssistantCanonicalTopic, int]:
    scores: Dict[PolicyAssistantCanonicalTopic, int] = {t: 0 for t in allowed}
    for rule in _TOPIC_RULES:
        if rule.topic not in scores:
            continue
        skip = any(n.search(norm) for n in rule.negatives)
        if (
            skip
            and relaxed
            and rule.topic == PolicyAssistantCanonicalTopic.SCHOOL_SEARCH
            and "school search" in norm
        ):
            skip = False
        if skip:
            continue
        for p, w in rule.phrases:
            if isinstance(p, str):
                if p in norm:
                    scores[rule.topic] += w
            elif p.search(norm):
                scores[rule.topic] += w
    return scores


def score_policy_assistant_topics(
    message: str,
    available_topics: Optional[Sequence[Union[str, PolicyAssistantCanonicalTopic]]] = None,
    *,
    relaxed: bool = False,
) -> Dict[PolicyAssistantCanonicalTopic, int]:
    """Topic scores for guardrails / mixed-scope recovery (same rules as classify, optional relaxed school_search)."""
    norm = _normalize_message(message)
    allowed = _parse_available_topics(available_topics)
    return _score_topics(norm, allowed, relaxed=relaxed)


def _best_topic_from_scores(
    scores: Dict[PolicyAssistantCanonicalTopic, int],
) -> Tuple[Optional[PolicyAssistantCanonicalTopic], int, int]:
    sorted_vals = sorted((s for s in scores.values() if s > 0), reverse=True)
    best_score = sorted_vals[0] if sorted_vals else 0
    second = sorted_vals[1] if len(sorted_vals) > 1 else 0
    best_topic: Optional[PolicyAssistantCanonicalTopic] = None
    if best_score > 0:
        best_topic = max(
            scores.items(),
            key=lambda x: (x[1], -POLICY_ASSISTANT_TOPIC_ORDER.index(x[0])),
        )[0]
    return best_topic, best_score, second


def _pick_intent(norm: str, has_topic: bool) -> PolicyAssistantIntent:
    if _COMPARISON_READINESS_Q.search(norm):
        return PolicyAssistantIntent.POLICY_COMPARISON_QUESTION
    if _STATUS_Q.search(norm):
        return PolicyAssistantIntent.POLICY_STATUS_QUESTION
    if _APPROVAL_Q.search(norm):
        return PolicyAssistantIntent.POLICY_ENTITLEMENT_QUESTION
    if has_topic:
        return PolicyAssistantIntent.POLICY_ENTITLEMENT_QUESTION
    return PolicyAssistantIntent.POLICY_ENTITLEMENT_QUESTION


def classify_policy_chat_message(
    message: str,
    role: Union[str, PolicyAssistantRoleScope],
    available_topics: Optional[Sequence[Union[str, PolicyAssistantCanonicalTopic]]] = None,
    *,
    use_llm_fallback: bool = False,
) -> PolicyAssistantClassificationResult:
    """
    Classify a single user message for the bounded policy assistant.

    ``use_llm_fallback`` is reserved; rules-first classifier does not call external LLMs.
    When True, behavior is unchanged until an LLM adapter is implemented.
    """
    _ = use_llm_fallback  # hook for future bounded reranker
    norm = _normalize_message(message)
    normalized_question = norm[:8000] if norm else (message or "").strip()[:8000]
    rs = _parse_role(role)
    allowed = _parse_available_topics(available_topics)

    if not norm:
        return PolicyAssistantClassificationResult(
            supported=False,
            intent=PolicyAssistantIntent.AMBIGUOUS_QUESTION,
            canonical_topic=None,
            ambiguity_reason="Empty message.",
            refusal_code=PolicyAssistantRefusalCode.AMBIGUOUS_OR_UNGROUNDED,
            normalized_question=normalized_question,
        )

    for pat, code in _UNSUPPORTED_PATTERNS:
        if pat.search(norm):
            return PolicyAssistantClassificationResult(
                supported=False,
                intent=PolicyAssistantIntent.UNSUPPORTED_QUESTION,
                canonical_topic=None,
                ambiguity_reason=None,
                refusal_code=code,
                normalized_question=normalized_question,
            )

    if rs == PolicyAssistantRoleScope.HR and _HR_STRATEGY_UNSUPPORTED.search(norm):
        return PolicyAssistantClassificationResult(
            supported=False,
            intent=PolicyAssistantIntent.UNSUPPORTED_QUESTION,
            canonical_topic=None,
            ambiguity_reason=None,
            refusal_code=PolicyAssistantRefusalCode.OUT_OF_SCOPE_GENERAL,
            normalized_question=normalized_question,
        )

    scores = _score_topics(norm, allowed)
    best_topic, best_score, second = _best_topic_from_scores(scores)

    if rs == PolicyAssistantRoleScope.HR:
        if _OVERRIDE_EFFECT_HR.search(norm):
            return PolicyAssistantClassificationResult(
                supported=True,
                intent=PolicyAssistantIntent.OVERRIDE_EFFECT_QUESTION,
                canonical_topic=None,
                ambiguity_reason=None,
                refusal_code=None,
                normalized_question=normalized_question,
            )
        # Topic-specific "what employees see if I publish this draft" → grounded entitlement on draft row
        if (
            best_topic is not None
            and best_score >= 4
            and re.search(r"\bemployees see\b|\bemployee view\b|\bworkers see\b", norm)
            and "publish" in norm
            and "draft" in norm
        ):
            return PolicyAssistantClassificationResult(
                supported=True,
                intent=PolicyAssistantIntent.POLICY_ENTITLEMENT_QUESTION,
                canonical_topic=best_topic,
                ambiguity_reason=None,
                refusal_code=None,
                normalized_question=normalized_question,
            )
        if _EMPLOYEE_VISIBILITY_HR.search(norm):
            return PolicyAssistantClassificationResult(
                supported=True,
                intent=PolicyAssistantIntent.EMPLOYEE_VISIBILITY_QUESTION,
                canonical_topic=None,
                ambiguity_reason=None,
                refusal_code=None,
                normalized_question=normalized_question,
            )

    # HR draft vs published
    if _DRAFT_PUBLISHED_EMPLOYEE_PROBE.search(norm):
        if rs != PolicyAssistantRoleScope.HR:
            return PolicyAssistantClassificationResult(
                supported=False,
                intent=PolicyAssistantIntent.DRAFT_VS_PUBLISHED_QUESTION,
                canonical_topic=None,
                ambiguity_reason=None,
                refusal_code=PolicyAssistantRefusalCode.ROLE_FORBIDDEN_DRAFT,
                normalized_question=normalized_question,
            )
        if _DRAFT_PUBLISHED_HR.search(norm) or _DRAFT_PUBLISHED_EMPLOYEE_PROBE.search(norm):
            return PolicyAssistantClassificationResult(
                supported=True,
                intent=PolicyAssistantIntent.DRAFT_VS_PUBLISHED_QUESTION,
                canonical_topic=None,
                ambiguity_reason=None,
                refusal_code=None,
                normalized_question=normalized_question,
            )

    # Generic "housing" without disambiguation: tie temporary vs host
    t1 = PolicyAssistantCanonicalTopic.TEMPORARY_HOUSING
    t2 = PolicyAssistantCanonicalTopic.HOST_HOUSING
    if (
        t1 in scores
        and t2 in scores
        and scores[t1] == scores[t2]
        and scores[t1] >= 3
        and re.search(r"\bhousing\b", norm)
    ):
        return PolicyAssistantClassificationResult(
            supported=True,
            intent=_pick_intent(norm, False),
            canonical_topic=None,
            ambiguity_reason="Multiple housing topics match; specify temporary housing vs host-country housing.",
            refusal_code=None,
            normalized_question=normalized_question,
        )

    if best_score == 0:
        # In-domain phrasing but no topic hit
        if _COMPARISON_READINESS_Q.search(norm) or _STATUS_Q.search(norm):
            return PolicyAssistantClassificationResult(
                supported=True,
                intent=_pick_intent(norm, False),
                canonical_topic=None,
                ambiguity_reason=None,
                refusal_code=None,
                normalized_question=normalized_question,
            )
        return PolicyAssistantClassificationResult(
            supported=False,
            intent=PolicyAssistantIntent.AMBIGUOUS_QUESTION,
            canonical_topic=None,
            ambiguity_reason="Could not map to a known policy topic; try naming a benefit (e.g. shipment, home leave).",
            refusal_code=PolicyAssistantRefusalCode.AMBIGUOUS_OR_UNGROUNDED,
            normalized_question=normalized_question,
        )

    intent = _pick_intent(norm, True)
    # Close race between two topics (e.g. tax briefing vs return) — require explicit follow-up
    if (
        best_topic is not None
        and second >= 4
        and (best_score - second) <= 2
    ):
        return PolicyAssistantClassificationResult(
            supported=True,
            intent=intent,
            canonical_topic=None,
            ambiguity_reason="Multiple policy topics match your question; please name one benefit explicitly.",
            refusal_code=None,
            normalized_question=normalized_question,
        )

    assert best_topic is not None
    return PolicyAssistantClassificationResult(
        supported=True,
        intent=intent,
        canonical_topic=best_topic,
        ambiguity_reason=None,
        refusal_code=None,
        normalized_question=normalized_question,
    )
