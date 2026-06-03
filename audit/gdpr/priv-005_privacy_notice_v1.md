# PRIV-005 · Privacy Notice at Point of Collection (Art. 13) v1 · ReloPass

**Task**: AIQ-473 · PRIV-005 (partial — copy + schema spec + component spec shipped here; React wiring ships in Claude Code)
**Author**: Claude Cowork via notion-task-executor
**Date**: 2026-06-03
**Owner**: Romain (CTO + acting DPO) → counsel sign-off → Claude Code for React wiring
**Regulation reference**: GDPR Article 13 (information to be provided where data are collected from the data subject)
**Cross-references**: PRIV-003 retention policy; PRIV-001 erasure runbook; P1-07e GDPR checklist; AI-003 Annex IV §1.9
**Document status**: v1 — copy + schema + component spec complete. React implementation queued for Claude Code.

---

## 1. Where the notice appears

The Pathway employee flow is the **single point of collection** for personal data from data subjects (employees + family members). The privacy notice must appear:

1. **Before the first ask** — on the welcome screen of every new Pathway session (consent screen IMM-07).
2. **At each material expansion of scope** — first time family-member data is requested; first time medical or financial data is requested.
3. **Always linkable** — a `/privacy` footer link on every Pathway page + on relopass.com.
4. **Re-presented on lawful basis change** — if a customer (HR) changes the deployment configuration in ways that change processing scope, the consent screen re-appears.

HR users (the deployer-side data subjects) receive a separate privacy notice at HR-account creation — out of scope of this PRIV-005, ships as PRIV-005b.

---

## 2. Privacy notice copy (Art. 13 verbatim)

This is the **ship-ready copy**. Voice tuned to ReloPass brand-voice rules (no hype, plain language, two-sentence cadence). Article references in §3 below map each paragraph to the GDPR sub-clause it satisfies.

### 2.1 Full notice (consent screen + standalone /privacy page)

> **Your data, in plain English.**
>
> Before we ask you anything, here's what we'll do with your answers.
>
> **Who we are.** ReloPass SAS (registered in France) is the company processing your data. We're acting on behalf of your employer to help with your international move. Your employer asked us to do this work, and we both follow EU data protection law (GDPR).
>
> **What we collect.** Documents you upload (passports, employment contracts, certificates), the answers you give in this workspace, and your contact details. If you tell us about your family, we also collect their data — with your confirmation that you're authorised to share it.
>
> **Why we collect it.** To file the immigration applications, register your address, set up your payroll, and coordinate the services your move requires. We do not use your data for anything else.
>
> **The legal basis.** Most of what we do is to perform the contract between you, your employer, and ReloPass (GDPR Article 6(1)(b)). Some processing of sensitive data (family records, health insurance proof) is necessary under employment and social-security law (Article 9(2)(b)).
>
> **Who else sees it.** Your HR team at your employer sees what we extract. The immigration authorities receive the formal applications. Specialised vendors (translators, notaries) see only the documents they need to do their work — and only after you approve their involvement. We do **not** sell or share your data with anyone else.
>
> **Where your data lives.** Inside the European Union. We use European cloud providers (Supabase, Render, Cloudflare) for storage and compute. Our AI tools — for reading your documents and pre-filling your forms — run on European infrastructure provided by Mistral AI, Microsoft Azure, Anthropic, and OpenAI. Each of these providers is bound by a data processing agreement that forbids using your data to train their models.
>
> **How long we keep it.** Your active case data is kept while your move is in progress and for 12 months after the case closes. Audit records — proof that we followed the rules — are kept for 6 years to meet our legal obligations under the EU AI Act and accounting law.
>
> **Your rights.** You can:
> - **See your data** — ask for a copy in machine-readable format.
> - **Correct it** — edit fields directly in this workspace, or write to us.
> - **Delete it** — at any time, except where law requires us to keep audit records.
> - **Restrict processing** — if you disagree with how we handle something.
> - **Object** — to any processing not strictly necessary for the contract.
> - **Withdraw consent** — for processing based on consent (you'll see a clear marker when this applies).
> - **Complain to a regulator** — in France, the CNIL ([cnil.fr](https://www.cnil.fr/)).
>
> **AI-assisted decisions.** Our AI extracts values from your documents and surfaces possible contradictions. Every value is shown to you for confirmation before we file anything. No AI makes terminal decisions about your move — your HR team does, with you. You can review the audit trail of any AI decision on request.
>
> **Contact us.** dpo@relopass.com for any privacy question. We answer within 72 hours; complete handling within 1 month per GDPR Article 12(3).
>
> By tapping "I understand and agree," you confirm you've read this. By tapping "Not now," you can read it later before sharing any data.
>
> [ I understand and agree ]    [ Not now ]

### 2.2 Short notice (for footer + inline contexts)

Used as the link-text + tooltip on every Pathway page:

> *Privacy notice — what we collect, why, and your rights. [Read full notice →](/privacy)*

### 2.3 Just-in-time notices (Article 13(3) re-disclosure)

When the AI escalates to HR per the "we don't pretend" pattern:

> *Your question has been shared with your HR team. The case context (your name, case ID, recent uploads) is included so they can respond fully. Read more in our privacy notice.*

When a family-member is added:

> *Adding family members means we'll process their data too. Confirm you've informed them and have their authorisation to share. [Family privacy summary →](/privacy/family)*

---

## 3. Article 13 element-by-element mapping

GDPR Article 13(1) + (2) requires nine information categories. Every category is covered above. Counsel review checklist:

| Art. 13 element | Where it's covered | Counsel verify |
|---|---|---|
| (1)(a) Identity + contact details of controller | "Who we are" paragraph + contact section | ✅ |
| (1)(b) Contact of DPO | "Contact us" paragraph: dpo@relopass.com | ✅ |
| (1)(c) Purposes of processing + legal basis | "Why we collect it" + "The legal basis" | ✅ |
| (1)(d) Where 6(1)(f) basis: legitimate interests pursued | N/A — primary basis is 6(1)(b) + 9(2)(b); LIA on file for §3.4 P1-07e cases | ⚠ confirm |
| (1)(e) Recipients or categories of recipients | "Who else sees it" | ✅ |
| (1)(f) Intent to transfer outside EU + safeguards | "Where your data lives" | ✅ |
| (2)(a) Retention period or criteria | "How long we keep it" | ✅ |
| (2)(b) Rights enumeration (Art. 15-22) | "Your rights" | ✅ |
| (2)(c) Right to withdraw consent (where applicable) | "Your rights" item 6 | ✅ |
| (2)(d) Right to lodge a complaint with supervisory authority | "Your rights" final item — CNIL named | ✅ |
| (2)(e) Whether provision is statutory or contractual + consequences | "The legal basis" — needs explicit consequence clause | ⚠ add: "Failure to provide required data may delay or prevent the relocation." |
| (2)(f) Existence of automated decision-making + meaningful info about logic | "AI-assisted decisions" paragraph | ✅ — also covered by AI-003 Annex IV transparency |

### Gaps to address in v1.1

- ⚠ Add explicit consequence clause to "The legal basis" paragraph (Art. 13(2)(e)).
- ⚠ Confirm legitimate-interest paragraph is included if any 6(1)(f) processing remains after counsel review.

---

## 4. Database schema spec — `privacy_consents`

The act of agreement (or declining) must be logged for audit. Schema:

```sql
CREATE TABLE public.privacy_consents (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  subject_id          uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  subject_role        text NOT NULL CHECK (subject_role IN ('EMPLOYEE','HR_USER','FAMILY_PROXY')),
  notice_version      text NOT NULL,                  -- e.g., '2026-06-03-v1.0' — references the Git-versioned notice text
  consent_status      text NOT NULL CHECK (consent_status IN ('agreed','declined','withdrawn')),
  agreed_at           timestamptz,
  declined_at         timestamptz,
  withdrawn_at        timestamptz,
  context             jsonb NOT NULL DEFAULT '{}',    -- e.g., { surface: 'pathway_welcome', case_id: '<uuid>' }
  ip_address          inet,                            -- optional, for fraud / impersonation diagnostics
  user_agent          text,                            -- same
  created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ix_privacy_consents_subject ON public.privacy_consents(subject_id, created_at DESC);
CREATE INDEX ix_privacy_consents_version ON public.privacy_consents(notice_version);

-- RLS — subjects see their own; HR/Admin see their tenant; Service role full
ALTER TABLE public.privacy_consents ENABLE ROW LEVEL SECURITY;

CREATE POLICY privacy_consents_subject_self
  ON public.privacy_consents
  FOR SELECT
  TO authenticated
  USING (subject_id = auth.uid());

CREATE POLICY privacy_consents_hr_tenant
  ON public.privacy_consents
  FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid()
        AND p.role IN ('HR_AGENT','HR_LEAD','ADMIN')
        AND p.company_id = (SELECT company_id FROM public.profiles WHERE id = privacy_consents.subject_id)
    )
  );

-- Retention: 6 years (audit chain — per PRIV-003 §3.2 row 8 sibling)
-- Erasure handling: NOT erased on Art. 17 — pseudonymised (subject_id replaced with anon_employee_hash)
```

### 4.1 Engineer notes

- Insert one row at every "I understand and agree" or "Not now" tap.
- Notice version tracks the Git-pinned text — if the copy changes materially, a new version means a new consent prompt.
- `context` captures the surface so the audit can answer "which screen elicited consent?"
- IP + UA are optional; collect them for adult employee accounts only, never for minors (none expected here, but defensive).

---

## 5. React component spec — `<PrivacyNoticeGate />`

### 5.1 Props

```typescript
type PrivacyNoticeGateProps = {
  subjectId: string;                            // current authed user
  caseId?: string;                              // optional — surface context
  noticeVersion: string;                        // e.g., '2026-06-03-v1.0'
  noticeMarkdownContent: string;                // §2.1 full notice
  onAgree: () => void;                          // proceed to Pathway
  onDecline: () => void;                        // halt — show "Read later" view
  onWithdrawal?: () => void;                    // optional — for re-presentation case
};
```

### 5.2 Behavior

1. Renders the §2.1 full notice in scrollable markdown (use existing markdown component).
2. Two buttons: **I understand and agree** (primary) + **Not now** (tertiary).
3. On click:
   - POST `/api/privacy/consents` with `{ subject_id, notice_version, status, context }`.
   - On 2xx success → call `onAgree` (or `onDecline`).
   - On non-2xx → show inline error: "We couldn't save your choice. Try again — your data hasn't been shared yet."
4. If `consent_status = 'agreed'` already exists for `(subject_id, notice_version)`, skip the gate entirely and call `onAgree` immediately (idempotent).
5. Accessibility:
   - `role="dialog"` + `aria-modal="true"` when surfaced in a modal context.
   - Focus trap inside the modal.
   - Esc dismisses to "Not now" (treated as decline).
   - Headline gets `aria-labelledby`.
   - Body content has heading levels h2/h3 for screen reader navigation.

### 5.3 Visual spec (refs C1-11D)

| Element | Token / spec |
|---|---|
| Modal background | `--surface-elevated`, `--radius-lg`, `--shadow-lg` |
| Title | `--font-display-md`, weight 700 |
| Body markdown | `--font-body-md`, line-height 1.6 |
| Section headings (h2 in markdown) | `--font-body-lg`, weight 600, `--space-4` top margin |
| Primary button "I understand and agree" | `--button-primary-bg`, 44 px height, full width on mobile |
| Secondary "Not now" | `--button-secondary-bg`, same height |
| Scroll indicator (if body overflows) | subtle gradient fade at bottom, `--surface-elevated` to transparent |
| Spacing between paragraphs | `--space-3` |

### 5.4 Behavior on "Not now" (decline path)

- Subject is signed out of the Pathway flow (or kept on the welcome screen).
- A static informational page renders: "Take your time. When you're ready, sign in again and we'll start fresh." with a link back to the full privacy notice.
- The `privacy_consents` row is written with `status = 'declined'`.

### 5.5 Behavior on withdrawal (Art. 7(3))

- For processing based on consent (limited — most ReloPass processing is contract-based), a "Withdraw consent" button appears in profile settings.
- Withdrawal triggers an erasure flow per PRIV-001 if the processing was solely consent-based, OR a restriction flow per Art. 18 if other lawful bases apply.
- A new `privacy_consents` row with `status = 'withdrawn'` is logged.

---

## 6. API endpoint spec

```yaml
POST /api/privacy/consents
Auth: Authenticated session required.
Body:
  notice_version: string  # required
  status: 'agreed' | 'declined' | 'withdrawn'
  context: object         # optional
Response:
  200 OK
  { consent_id: uuid, created_at: iso }
Errors:
  401 Unauthorized
  400 Bad Request: missing/invalid notice_version
  409 Conflict: agreed already exists for (subject_id, notice_version) — return existing
  500: internal — log with sentry
```

### 6.1 Idempotency

For `status = 'agreed'`, treat as idempotent — second call with same `(subject_id, notice_version, status='agreed')` returns the original `consent_id`. This handles the network-flaky case where the React component retries.

---

## 7. Validation against AIQ-473 criteria

- ✅ **Criterion: Privacy notice covers all 8/9 Art. 13 elements in plain language** — §3 element-by-element table. Two minor gaps flagged for v1.1.
- ✅ **Criterion: privacy_consents schema specified** — §4 with RLS policies.
- ✅ **Criterion: React component spec** — §5 with behaviour, accessibility, visual tokens.
- ⚠ **Criterion: React component implementation** — out of scope; ships in Claude Code follow-up.
- ⚠ **Criterion: API endpoint implementation** — out of scope; ships in Claude Code follow-up.
- ⚠ **Criterion: Wired into IMM-07 consent screen** — Claude Code task.

**Recommendation**: mark PRIV-005 in Notion as **Validation** rather than Done — the doc + spec half is complete, the code wiring waits for Claude Code.

---

## 8. Known gaps

- ⚠ Counsel review of §2 copy (legal-language vs plain-language balance).
- ⚠ Add explicit consequence clause to "The legal basis" paragraph (Art. 13(2)(e) — flagged in §3 table).
- ⚠ Family-proxy authorisation language — current copy says "you confirm you're authorised to share"; counsel should verify this is sufficient.
- ⚠ Minors handling — current copy assumes adult employees only; if family members include minors, add explicit parental-authority language.
- ⚠ Notice versioning policy — codify how/when a new `notice_version` is cut. Recommend: any material change to scope, retention, or recipients triggers a new version + re-prompt.
- ⚠ Multi-locale — FR and NO translations needed for Cohort 4 corridors (per Pathway strings deferral note in `outputs/pathway_strings_v1.json`).

---

## 9. Document metadata

- **Version**: v1.0 (Cowork half — copy + schema + component spec).
- **Generated**: 2026-06-03.
- **Generator**: Claude Cowork via notion-task-executor.
- **Source materials**: GDPR Art. 7, 12, 13; PRIV-003 retention policy; PRIV-001 erasure runbook; AI-003 Annex IV §1; Pathway strings v1.
- **Next planned revision**: v1.1 after counsel review + consequence-clause addition + multi-locale work.

---

*Generated 2026-06-03 by Claude Cowork via notion-task-executor. Copy ready for counsel review; schema + component spec ready for Claude Code implementation.*
