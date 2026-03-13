# ReloPass User Testing Kit

Practical setup for real user testing of the relocation and services flow.

---

## 1. Test Scenarios

### Scenario A: Single Employee Relocation (Baseline)
**Profile**: One person, no dependents, mid-budget assignment.

| Step | Action | Expected |
|------|--------|----------|
| 1 | Sign in as employee | Dashboard loads |
| 2 | Select services: Housing, Movers | Services saved |
| 3 | Answer questions (destination city, budget, timeline) | Answers saved, recommendations load |
| 4 | View recommendations | 2+ per category |
| 5 | Shortlist 1 mover, 1 housing option | Shortlist persists |
| 6 | Create RFQ from shortlist | RFQ created, redirect to quotes inbox |
| 7 | View RFQ detail | Items and recipients visible |

**Friction points**: Destination missing, save failures, empty recommendations, RFQ creation errors.

---

### Scenario B: Family Relocation with School Needs
**Profile**: Couple with 2 kids, school-age, destination Singapore.

| Step | Action | Expected |
|------|--------|----------|
| 1 | Select Housing, Schools, Movers | All three services |
| 2 | Provide school preferences (curriculum, start date) | Answers saved |
| 3 | Provide housing preferences (bedrooms, areas) | Answers saved |
| 4 | Get recommendations for all three | Recommendations per category |
| 5 | Shortlist schools and housing | Shortlist persists |
| 6 | Create RFQ for movers only (schools may not support RFQ) | RFQ created or clear messaging if not supported |

**Friction points**: School questions confusing, housing vs school ordering, destination context lost.

---

### Scenario C: Housing + Movers + Banking
**Profile**: Employee moving Oslo → Singapore, needs housing, movers, and local banking.

| Step | Action | Expected |
|------|--------|----------|
| 1 | Select Housing, Movers, Banks | Services saved |
| 2 | Complete housing and movers questions | Recommendations load |
| 3 | Note banking recommendations (may be fewer/different format) | Recommendations or guidance |
| 4 | Shortlist 2 movers, 1 housing | Shortlist persists |
| 5 | Create RFQ | RFQ created |
| 6 | Return later, reload | Answers and shortlist still there |

**Friction points**: Banking flow differs, save/reload reliability, cross-service consistency.

---

### Scenario D: High-Budget Corporate Assignment
**Profile**: Senior role, premium budget, short timeline.

| Step | Action | Expected |
|------|--------|----------|
| 1 | Select Housing, Schools, Movers, Insurances | Services saved |
| 2 | Enter high budget and premium preferences | Answers saved |
| 3 | Get recommendations | Higher-tier options surfaced |
| 4 | Assess explanation for why suppliers were recommended | Rationale visible and understandable |
| 5 | Shortlist and create RFQ | RFQ created |
| 6 | Compare quotes (if vendor flow available) | Quote comparison usable |

**Friction points**: Budget/premium not reflected, explanation unclear, RFQ intent unclear.

---

### Scenario E: Relocation with Missing Destination Context
**Profile**: Employee with incomplete case (e.g. no destination city).

| Step | Action | Expected |
|------|--------|----------|
| 1 | Navigate to services before case has destination | Clear blocking or fallback |
| 2 | Try to get recommendations without destination | Clear error or guidance |
| 3 | Add destination in intake / case, return to services | Flow unblocked |
| 4 | Complete questions and recommendations | Recommendations load |

**Friction points**: Silent failure, unclear "complete intake first" path, lost progress.

---

## 2. Moderator Script

### Pre-Test Setup (15 min)

1. **Environment**
   - [ ] Backend running (local or staging)
   - [ ] Frontend running
   - [ ] Test user(s) created (employee, optionally HR)
   - [ ] Optional: demo assignment pre-created for faster start
   - [ ] Screen recording + audio enabled
   - [ ] DevTools Console open (preserve log checked) for `[services-workflow]` logs

2. **Briefing**
   - "You’ll go through a relocation services flow as an employee. There are no wrong answers."
   - "Think aloud—say what you’re trying to do and what you notice."
   - "We’re testing the tool, not you."

3. **Scenario assignment**
   - Assign one scenario (A–E) per session
   - Note scenario ID and start time

---

### During Test

#### Task 1: Select Services (2–3 min)
- "Choose which services you’d need for this relocation."
- **Observe**: Time to select, confusion about categories, navigation
- **Ask**: "What would you expect next?"

#### Task 2: Answer Questions (5–8 min)
- "Complete the questions for your selected services."
- **Observe**: Wording clarity, required vs optional, autosave behavior, errors
- **Ask (mid-task)**: "Is it clear why we’re asking this?"
- **Ask (if stuck)**: "What would you need to continue?"

#### Task 3: Get Recommendations (2–3 min)
- "Request recommendations."
- **Observe**: Load time, empty states, destination errors
- **Ask**: "What do you notice about these results?"

#### Task 4: Understand Why Recommended
- "Pick one recommendation. Can you see why it was suggested?"
- **Observe**: Use of explanation/rationale
- **Ask**: "Does that make sense for your situation?"

#### Task 5: Shortlist & Create RFQ (3–5 min)
- "Select one or more options to shortlist, then create a quotation request."
- **Observe**: Shortlist interaction, RFQ creation, errors, redirect
- **Ask**: "Would you expect to do anything else here?"

#### Optional: Quote Comparison (if vendor flow available)
- "Imagine vendors have responded. Compare their quotes."
- **Observe**: Comparison layout, decision-making, acceptance flow

---

### Friction Recording

For each friction event, capture:

| Field | Note |
|-------|------|
| **When** | Task and step |
| **What** | Action taken |
| **Expected** | What user expected |
| **Actual** | What happened |
| **Recovery** | How user recovered (or didn’t) |
| **Severity** | 1–5 (1=minor, 5=blocking) |

---

### Post-Task Questions

1. "On a scale of 1–5, how easy was it to complete the flow?"
2. "What was most confusing?"
3. "What would make this more useful for you?"
4. "Would you trust these recommendations for a real move?"

---

## 3. Success Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| **Task completion rate** | % of users completing the full flow (through RFQ creation) | ≥ 80% |
| **Time to recommendations** | Time from "Get recommendations" to first results | < 5 s |
| **Save/reload reliability** | % of sessions where answers persist after page reload | ≥ 95% |
| **Explanation understanding** | % of users who correctly explain why a supplier was recommended | ≥ 70% |
| **RFQ intent** | % of users who create an RFQ after shortlisting | ≥ 60% |
| **Error recovery rate** | % of users who recover from errors without moderator help | ≥ 50% |
| **SUS score** | System Usability Scale (10 questions) | ≥ 68 |

---

### Data Sources

| Metric | Source |
|--------|--------|
| Task completion | Moderator checklist |
| Time to recommendations | Backend `recommendations_generated` event (`duration_ms`), or manual timing |
| Save/reload | Backend `services_answers_saved`, reload check |
| RFQ intent | Backend `rfq_created` event |
| Errors | Console logs, moderator notes, `services_save_failed` etc. |

---

## 4. Instrumentation to Inspect

### Backend (analytics_events)

Query via `GET /api/admin/workflow/events` or direct DB:

| Event | Use |
|-------|-----|
| `case_created` | Test start, case setup |
| `services_selected` | Task 1 completion, service mix |
| `services_answers_saved` | Task 2 completion, save reliability |
| `recommendations_generated` | Task 3, `duration_ms`, `counts.items` |
| `supplier_selected` | Shortlist behavior |
| `rfq_created` | Task 5, RFQ intent |
| `quote_received`, `quote_compared`, `quote_accepted` | Quote flow (if tested) |

**Filter by**: `user_id` (test user), `case_id` or `assignment_id`, `created_at` in test window.

---

### Frontend (Console)

With DevTools "Preserve log" on, look for:

- `[services-workflow] save_answers_succeeded` / `save_answers_failed`
- `[services-workflow] recommendations_succeeded` / `recommendations_failed`
- `[services-workflow] save_preferences_succeeded` / `save_preferences_failed`
- `[services-workflow] services_autosave_*` for autosave behavior

---

### Optional: Test Session Tagging

To correlate events per session, use a dedicated test user per session and note:

- `user_id`
- `assignment_id` (if applicable)
- `case_id`
- Start/end timestamps

Query `analytics_events` with these filters for a per-session event sequence.

---

## 5. Post-Test Debrief Format

### 1. Quick Summary (5 min)

- Scenario tested: _____
- Completed full flow? Y / N
- Blockers? Y / N (describe)
- Top 3 friction points: _____

---

### 2. Quantitative (5 min)

| Metric | Value |
|--------|-------|
| Time to complete (min) | _____ |
| Tasks completed / total | _____ |
| Errors encountered | _____ |
| Self-rated ease (1–5) | _____ |

---

### 3. Qualitative Themes (10 min)

**Clarity**
- What was confusing?
- What was clear?

**Trust**
- Did recommendations feel relevant?
- Would they use this in a real relocation?

**Workflow**
- Save/reload behavior?
- Navigation and flow?

**RFQ / Quotes**
- RFQ creation experience?
- Quote comparison (if tested)?

---

### 4. Action Items (5 min)

| Priority | Finding | Suggested change |
|----------|---------|------------------|
| P0 | | |
| P1 | | |
| P2 | | |

---

### 5. Next Steps

- [ ] Export analytics for test window
- [ ] Clip notable moments from recording
- [ ] Update friction log
- [ ] Share summary with product/engineering
