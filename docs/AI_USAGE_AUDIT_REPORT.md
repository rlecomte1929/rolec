# AI Usage Audit Report

**ReloPass — AI, prompts, and intelligent automation**

**Conclusion: The system has no LLM/AI integration. All "intelligent" behavior is deterministic rule-based logic.**

---

## 1. Where AI Is Used

**No AI or LLM is used anywhere in the codebase.**

| Search Term | Result |
|-------------|--------|
| `openai` / `OpenAI` | Only in `supabase/config.toml` (Supabase Studio AI key placeholder); not used by app code |
| `llm` / `LLM` | `extraction_method` placeholder `llm_structured_extraction` in crawler staging schema; `backend/crawler/README.md` mentions "Optional LLM extraction layer" as future work |
| `prompt` | Only UI copy ("suggested prompts", "Find suggested questions"); no LLM prompts |
| `rag` / `RAG` | None |
| `embedding` | Only in `supabase/config.toml` (commented vector bucket config); no app code |
| `vector` | PostgreSQL TSVECTOR (full-text search), Supabase storage vector config; no semantic/vector search |
| `weaviate` | None |
| `document extraction` | Used; implementation is **rule-based** (keywords, regex, schema.org), not AI |

---

## 2. What Prompts Exist

**No LLM prompts exist.**

| Location | What It Is | AI? |
|----------|------------|-----|
| `frontend/.../Step5ReviewCreate.tsx` | Text: "These are suggested prompts based on official destination requirements" | No — user-facing copy only |
| `backend/services/dossier.py` | `build_suggested_questions()` — template strings like "Is your employer sponsoring an Employment Pass (EP)?" | No — hardcoded templates |
| `backend/question_bank.py` | Fixed questions for intake flow | No — static question set |

---

## 3. Which Workflows Trigger AI

**None. No workflow invokes an LLM or AI service.**

Workflows that might sound AI-like but are deterministic:

| Workflow | Trigger | What Runs | AI? |
|----------|---------|-----------|-----|
| **Intake next question** | Employee answers question | `IntakeOrchestrator.get_next_question()` — dependency check, pick next from bank | No |
| **Readiness / recommendations** | Profile completion check | `ReadinessRater.compute_readiness()`, `RecommendationEngine.get_*_recommendations()` — heuristics + seed data | No |
| **Dossier suggested questions** | User clicks "Find suggested questions" | `fetch_search_results()` → SERPAPI → `build_suggested_questions()` — search + template match | No |
| **Guidance pack generation** | User generates guidance | `generate_guidance_pack()` — rule evaluation (`applies_if`) over curated rules | No |
| **Policy extraction** | HR uploads policy PDF/DOCX | `extract_policy_from_bytes()` — regex/keyword matching | No |
| **Crawler extraction** | Crawl run completes | `resource_extractor`, `event_extractor` — rule-based + schema.org | No |

---

## 4. Whether AI Is Authoritative or Advisory

**N/A — no AI in use.**

All logic that might otherwise be AI is **advisory**:

| Component | Role | Binding? |
|-----------|------|----------|
| Recommendations (housing, schools, movers) | Suggestions based on profile | Advisory — user chooses |
| Readiness score | Immigration readiness (GREEN/AMBER/RED) | Advisory — "informational guidance only, not legal advice" |
| Guidance pack | Checklist/steps from rule matching | Advisory — "informational only; confirm with official sources" |
| Suggested dossier questions | Optional questions to fill gaps | Advisory — user confirms |
| Policy extraction | Parsed benefits from uploaded policy | Advisory — HR reviews and can edit |
| Staged candidates | Crawler-extracted resources/events | Advisory — admin approves before publish |

---

## 5. AI Classification by Category

### Document AI

| Component | Location | Method | AI? |
|-----------|----------|--------|-----|
| **HR policy extraction** | `backend/services/policy_extractor.py` | python-docx, pdfplumber; keyword/regex for categories, limits, eligibility | No |
| **Crawler resource extraction** | `backend/crawler/extractors/resource_extractor.py` | Rule-based heuristics, confidence scoring | No |
| **Crawler event extraction** | `backend/crawler/extractors/event_extractor.py` | schema.org parsing, rule-based fallback | No |
| **Company policy extraction** | `company_policies.extraction_status` | Uses policy_extractor | No |

**Placeholder**: `staged_*_candidates.extraction_method` includes `llm_structured_extraction` — not implemented.

---

### Assistant

**None.** No chat, no conversational AI, no virtual assistant.

---

### Knowledge Retrieval

| Component | Location | Method | AI? |
|-----------|----------|--------|-----|
| **Dossier search suggestions** | `backend/services/dossier.py` | SERPAPI (Google search) + template matching on results | No |
| **Personalization hints** | `backend/services/country_resources.py` | Hardcoded rules (has_children, country_code, etc.) — labeled "AI-style" in docstring | No |
| **Requirements builder** | `backend/app/services/requirements_builder.py` | Rule-based `apply_rules`, DB lookup | No |
| **Guidance rules** | `backend/services/guidance_pack_service.py` | `applies_if` rule evaluation (and/or/not, var resolution) | No |

---

### Decision Support

| Component | Location | Method | AI? |
|-----------|----------|--------|-----|
| **IntakeOrchestrator** | `backend/agents/orchestrator.py` | Question flow, dependency check, completion logic | No |
| **ProfileValidator** | `backend/agents/validator.py` | Required-field validation | No |
| **ReadinessRater** | `backend/agents/readiness_rater.py` | 0–100 score, GREEN/AMBER/RED from profile fields | No |
| **RecommendationEngine** | `backend/agents/recommendation_engine.py` | Filter/rank housing, schools, movers from seed data | No |
| **ComplianceEngine** | `backend/agents/compliance_engine.py` | Deterministic rule checks | No |
| **Recommendation plugins** | `backend/app/recommendations/plugins/*` | Tier scoring, availability rules | No |

---

## 6. How AI Interacts With the Relocation Case Workflow

**There is no AI in the relocation case workflow.** The following describes what *would* be AI-triggered flows if they used AI; in reality they use rules and data.

### Case Lifecycle (All Deterministic)

```
Case created → Assignment created → Employee invited
       ↓
Employee wizard (IntakeOrchestrator)
   - get_next_question(profile, answered) → next question or "complete"
   - apply_answer(profile, question_id, answer) → updated profile
   - compute_completion_state(profile) → completeness, readiness, recommendations
       ↓
Employee sees recommendations (housing, schools, movers) — from seed data + filters
       ↓
Employee optionally: "Find suggested questions" (dossier)
   - SERPAPI search → build_suggested_questions (templates)
   - User confirms answers
       ↓
Employee generates guidance pack
   - generate_guidance_pack(draft, dossier_answers, rules, docs)
   - Rule matching on profile snapshot → plan, checklist
       ↓
Employee submits case
       ↓
HR reviews (assignments, policy, eligibility)
   - Policy extraction (if HR uploads policy): extract_policy_from_bytes
   - HR approves or rejects — human decision
```

### Data Flow Summary

| Stage | Input | Output | AI Involved? |
|-------|-------|--------|--------------|
| Intake | Profile, answered IDs | Next question / complete | No |
| Recommendations | Profile | Housing, schools, movers list | No |
| Readiness | Profile | Score, band, disclaimer | No |
| Dossier suggestions | Dest, profile | Search results + template questions | No |
| Guidance pack | Draft, dossier answers, rules | Plan, checklist, markdown | No |
| Policy extraction | PDF/DOCX bytes | Benefits, meta | No |
| HR decision | Assignment, profile, policy | Approve / reject | Human only |

---

## 7. Dependencies

| Package | Purpose | AI? |
|---------|---------|-----|
| python-docx | DOCX text extraction | No |
| pdfplumber | PDF text extraction | No |
| beautifulsoup4 | HTML parsing (crawler) | No |

**No OpenAI, Anthropic, LangChain, or similar in requirements.txt.**

---

## 8. Potential AI Extension Points (From ARCHITECTURE_AUDIT_REPORT)

| Area | Current | Possible AI Use |
|------|---------|-----------------|
| Policy extraction | Keyword/regex | LLM for unstructured policy text |
| Dossier Q&A | SERPAPI + templates | RAG over `source_records` / `knowledge_docs` |
| Requirements builder | Static rules | LLM extraction from official sources |
| Crawler extraction | Rule-based, schema.org | LLM for complex pages (`llm_structured_extraction` placeholder) |
| Supabase | `openai_api_key` in config | Supabase Studio AI features (not app code) |

---

## 9. Summary Table

| Category | AI Used? | Implementation |
|----------|----------|----------------|
| Document AI | No | Regex, keywords, schema.org, python-docx, pdfplumber |
| Assistant | No | — |
| Knowledge retrieval | No | SERPAPI, hardcoded rules, DB lookups |
| Decision support | No | Rule-based agents, seed data filtering |
| **Overall** | **No** | **Fully deterministic** |
