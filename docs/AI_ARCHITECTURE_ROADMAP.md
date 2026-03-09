# ReloPass AI-Ready Mobility Infrastructure Roadmap

**Platform architect — AI architecture for deterministic mobility platform**

Strict, phased approach: AI augments existing primitives. No chat-first AI unless justified by platform primitives.

---

## 1. WHAT SHOULD STAY DETERMINISTIC

These components must remain rule-based and auditable. Introducing AI here would create unacceptable legal, financial, or operational risk.

| Component | Reason |
|-----------|--------|
| **Assignment workflow transitions** | Status changes (submit, approve, reject) are binding. Must be deterministic and traceable. |
| **Eligibility and compliance checks** | Policy-based eligibility affects budget and legal obligations. No model inference in approval path. |
| **Intake question flow** | `get_next_question` / `apply_answer` control data collection. Dependency logic is explicit. |
| **Readiness score** | Labeled "informational only" but used for HR visibility. Heuristic is explainable; LLM is not. |
| **Requirement `statusForCase`** | MISSING/PROVIDED/NEEDS_REVIEW drives checklist. Must derive from rules + evidence, not model. |
| **Guidance rule matching** | `applies_if` evaluation selects which rules apply. Logic must be reproducible for audit. |
| **HR approval/rejection** | Human decision only. No AI recommendation that could be construed as binding. |
| **RFQ/Quote status** | Procurement workflow is contractual. Status transitions remain deterministic. |
| **Review queue transitions** | Admin actions (assign, resolve, defer) must be explicit. |
| **Resource/Event CMS workflow** | Publish lifecycle is content governance. No AI in approval path. |

**Principle**: If it affects case outcome, budget, or legal record, it stays deterministic.

---

## 2. FIRST AI USE CASES

Prioritized by: (1) clear scope, (2) human review already in place, (3) bounded output schema, (4) no chat required.

| # | Use Case | Domain | AI Role | Human Review | Justification |
|---|----------|--------|---------|--------------|---------------|
| 1 | **Policy benefit extraction** | Evidence & Document | LLM extracts benefits from unstructured policy text; outputs structured JSON | HR reviews and edits before save | Regex fails on narrative policies. Output schema exists (`policy_benefits`). HR already reviews. |
| 2 | **Crawler extraction for complex pages** | Knowledge & Operations | LLM structured extraction when rule-based/schema.org fails | Admin approves staged candidates | `extraction_method` placeholder exists. Staging workflow is human-in-the-loop. |
| 3 | **Dossier suggested questions** | Evidence & Document | RAG over `knowledge_docs` + `source_records` to propose questions | User confirms each answer | Replaces SERPAPI + templates. Bounded: suggest questions, not answers. User confirms. |
| 4 | **Requirement fact extraction** | Compliance Intelligence | LLM extracts eligibility/document/step facts from official sources | Admin reviews `requirement_entities`/`requirement_facts` | Structured output; admin approval workflow exists. |
| 5 | **Document classification** | Evidence & Document | Classify uploaded evidence (passport, employment letter, etc.) | Optional; employee/HR can correct | Low risk; improves UX. Correctable. |

**Explicitly NOT first use cases**:

| Use Case | Why Not First |
|----------|---------------|
| Chat assistant | No conversational primitive. Relocation flows are form/wizard-driven. Chat adds scope without clear integration point. |
| Recommendation engine replacement | Seed data + rules work. Replacing with model would reduce explainability. |
| Readiness score | Heuristic is sufficient. LLM would reduce auditability. |
| Guidance pack generation | Rule matching is deterministic. LLM could hallucinate steps. |
| Assignment risk prediction | Would imply AI influence on HR decisions. Defer until governance is mature. |

---

## 3. REQUIRED DATA PRIMITIVES BEFORE AI

AI use cases depend on these being in place. Do not add AI before primitives are ready.

| Primitive | Status | Requirement |
|-----------|--------|-------------|
| **Structured extraction output schema** | Exists | `policy_benefits`, `staged_*_candidates` with `extraction_method`, `provenance` |
| **Knowledge corpus for RAG** | Partial | `knowledge_docs.text_content`, `source_records` — need chunking, metadata, country/domain indexing |
| **CaseActions for AI-assisted steps** | Phase 1 migration | Log when AI suggested X; human confirmed/overrode. Audit trail. |
| **Confidence / provenance on AI output** | Missing | Add `confidence_score`, `extraction_method`, `model_id` to extracted records |
| **Embeddings store** | Missing | Vector index over knowledge chunks. Supabase pgvector or external. |
| **PII handling** | Partial | Policy docs may contain employee data. Define redaction before extraction. |
| **Requirement entity/fact schema** | Exists | `requirement_entities`, `requirement_facts` with `status` (pending, approved, rejected) |

**Pre-AI checklist**:

- [ ] `case_actions` table exists; backend writes on assignment transitions
- [ ] `policy_benefits` supports `extraction_method`, `confidence`, `source_quote`
- [ ] `knowledge_docs` + `source_records` have consistent `country_code`, `domain` for filtering
- [ ] Chunking strategy for RAG (size, overlap, metadata)
- [ ] PII redaction policy for document extraction (or scope to non-PII docs only)
- [ ] Feature flag for AI extraction (off by default)

---

## 4. HUMAN-IN-THE-LOOP CONTROL POINTS

Every AI output flows through a human control point before affecting case state.

| AI Output | Control Point | Action |
|-----------|---------------|--------|
| Policy benefits | HR Policy page | HR reviews extracted benefits; can edit, add, remove before save |
| Staged resource/event candidates | Admin staging UI | Admin approves, rejects, or merges. No auto-publish. |
| Dossier suggested questions | Step5ReviewCreate | User sees questions; confirms or skips. No auto-population of answers. |
| Requirement facts | Admin requirement review | Admin approves or rejects entities/facts before they affect cases |
| Evidence classification | Evidence upload | Optional override; employee/HR can correct document type |
| Future: Guidance suggestions | Guidance pack | If AI suggests rules, human selects which to apply. Rule matching stays deterministic. |

**Rules**:

1. AI never writes directly to case-affecting tables (assignments, compliance, policy_benefits live) without human confirmation.
2. AI output is always draft/suggestion. Human action promotes to canonical.
3. Audit: `case_actions` or equivalent records "AI suggested X" and "Human confirmed/overrode X".

---

## 5. MODEL RISK AND COMPLIANCE GUARDRAILS

### Risk Categories

| Risk | Mitigation |
|------|------------|
| **Hallucination** | Structured output (JSON schema); cite source spans; confidence scores. Reject low-confidence. |
| **PII leakage** | Redact policy docs before extraction, or restrict to company policy templates. Log model requests without full content. |
| **Immigration/legal sensitivity** | All guidance remains "informational only." AI never states eligibility. Dossier questions are suggestions; user confirms. |
| **Bias** | Monitor extraction by policy type, country. Audit sample outputs. |
| **Cost/latency** | Use smaller models for classification; reserve larger models for extraction. Caching for repeated queries. |

### Compliance Guardrails

| Guardrail | Implementation |
|-----------|----------------|
| **No AI in approval path** | Assignment approve/reject, policy publish, staged approve—human only. |
| **Provenance** | Every AI-derived record stores `extraction_method`, `model_id`, `source_doc_id`, `source_quote`. |
| **Overridability** | Human can always override AI. Override is logged. |
| **Scope limiting** | RAG scoped by `country_code`, `domain`. No cross-country bleed. |
| **Rate limiting** | Cap extraction requests per tenant/hour. |
| **Opt-out** | Feature flag to disable AI extraction per company or globally. |

### Logging

- Log: `case_id`, `assignment_id`, `action_type` (e.g. `policy_extraction_ai`), `model_id`, `input_hash` (no PII), `output_schema_version`, `confidence_summary`, `duration_ms`.
- Do not log: Full policy text, employee names, raw model prompts with PII.

---

## 6. TARGET AI SERVICES

| Service | Use Case | Provider Options | Notes |
|---------|----------|------------------|-------|
| **Structured extraction** | Policy benefits, requirement facts, crawler candidates | OpenAI Structured Outputs, Anthropic structured output, Google Gemini JSON mode | Bounded schema. No chat. |
| **Embeddings** | RAG retrieval over knowledge corpus | OpenAI text-embedding-3-small, Supabase pgvector | Store in Supabase. |
| **Classification** | Document type (passport, employment letter, etc.) | Small classifier or LLM with fixed labels | Low latency. |
| **RAG** | Dossier question suggestion | Embed query → retrieve chunks → LLM with context → structured "suggested questions" | Not open-ended Q&A. Output: list of `{question_text, sources[]}`. |

**Explicitly out of scope for Phase 1–3**:

- General chat API for conversational assistant
- Image/document OCR (keep pdfplumber/python-docx for text; add OCR only if justified)
- Audio/voice
- Generative content for marketing or copy

---

## 7. PHASED IMPLEMENTATION ROADMAP

### Phase 0: Data & Primitives (4–6 weeks)

| Task | Deliverable |
|------|-------------|
| Complete Phase 1 migration | `case_actions`, `case_participants`, canonical case |
| Add extraction metadata | `policy_benefits.extraction_method`, `confidence`, `source_quote` |
| Prepare knowledge corpus | Chunk `knowledge_docs`, `source_records`; add `country_code`, `domain` indexes |
| PII policy | Define redaction rules for policy extraction; document scope |
| Feature flag | `AI_POLICY_EXTRACTION_ENABLED` (default false) |

**Gate**: No AI models called until Phase 0 complete.

---

### Phase 1: Policy Benefit Extraction (6–8 weeks)

| Task | Deliverable |
|------|-------------|
| Integrate LLM extraction | Call structured extraction API when regex confidence < threshold |
| Hybrid flow | Run regex first; if insufficient, call LLM; merge results with provenance |
| HR review UI | Show AI-extracted vs regex-extracted; allow edit before save |
| Logging | `case_actions` or audit log for extraction runs |
| Guardrails | Confidence threshold; reject low-confidence extractions |

**Success metric**: HR adoption; reduction in manual benefit entry; no increase in support tickets.

**Rollback**: Feature flag off; fall back to regex-only.

---

### Phase 2: Crawler LLM Extraction (6–8 weeks)

| Task | Deliverable |
|------|-------------|
| Implement `llm_structured_extraction` | When rule-based + schema.org fail, call LLM for candidate |
| Set `extraction_method` | `rule_based` \| `schema_parser` \| `llm_structured_extraction` |
| Staging workflow | No change; admin still approves. AI only improves recall. |
| Cost control | Limit LLM calls per crawl run; use for ambiguous pages only |

**Gate**: Phase 1 stable; staging queue healthy.

---

### Phase 3: RAG for Dossier Suggestions (8–10 weeks)

| Task | Deliverable |
|------|-------------|
| Embeddings pipeline | Chunk knowledge docs; embed; store in pgvector |
| Retrieval service | Query → embed → retrieve top-k by country/domain |
| Suggestion endpoint | Replace SERPAPI path with RAG: retrieve → LLM "suggest questions" → structured output |
| User confirmation | No change; user still confirms each suggested question |
| Scope | Restrict to `knowledge_docs`, `source_records`; no external search |

**Gate**: Knowledge corpus quality; embedding index built.

---

### Phase 4: Requirement Fact Extraction (8–10 weeks)

| Task | Deliverable |
|------|-------------|
| LLM extraction from official sources | Given URL or doc, extract facts (eligibility, document, step) |
| Output schema | Map to `requirement_facts`; `status = pending` |
| Admin review | Existing `requirement_reviews` workflow |
| Citation | Link facts to `source_doc_id` |

**Gate**: Phase 2 and 3 stable; compliance sign-off on fact extraction.

---

### Phase 5: Optional Extensions (Future)

| Candidate | Condition | Notes |
|-----------|-----------|-------|
| Evidence classification | Phase 3 done; evidence upload volume justifies | Classify document type from upload. Overridable. |
| Constrained Q&A | RAG mature; clear "ask about relocation" surface | Not chat. Single-turn: question → answer with citations. Requires product decision. |
| Risk/triage assist | Governance mature; HR requests it | AI suggests risk flags; HR decides. High bar. |

**Chat-first assistant**: Do not build until (1) there is a defined conversational workflow, (2) RAG and extraction are proven, (3) guardrails and compliance are in place. Current platform is form-driven; chat is not a primitive.

---

## Summary

| Phase | Focus | AI Type | Human Review |
|-------|-------|---------|--------------|
| 0 | Data primitives | None | — |
| 1 | Policy extraction | Structured extraction | HR |
| 2 | Crawler extraction | Structured extraction | Admin staging |
| 3 | Dossier suggestions | RAG + structured output | User |
| 4 | Requirement facts | Structured extraction | Admin |
| 5 | Optional | Classification, constrained Q&A | Varies |

**Principle**: AI augments existing primitives. Deterministic workflows stay deterministic. Human-in-the-loop for all AI output that affects case state.
