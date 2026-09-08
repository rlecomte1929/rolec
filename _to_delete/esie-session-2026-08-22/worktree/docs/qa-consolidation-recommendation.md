# Policy Q&A entry points on `/hr/policy` — gap analysis & recommendation

**Ticket:** AIQ-1508 · **Feedback:** BUG-260713-D3F4 — *"I see that there is no area available to type text when I click on 'Ask about this policy'. Is this function still needed if there is the question-mark widget in the page to ask questions?"*

## RECOMMENDATION (read this first)

**Keep both mechanisms — they are distinct features, not duplicate Q&A — and fix the real confusion, which is a mis-timed affordance, not a bug.**

The HR user hit two things the ticket mis-diagnosed:

1. **"Ask about this policy" is not broken.** Its ask box is intentionally gated: policy Q&A is company-scoped Retrieval-Augmented Generation over the **published** policy, so there is nothing to answer about until a policy is live. With no published policy the panel correctly shows *"Publish a policy for this workspace to enable Q&A."* — but with **no text input**. Because the trigger button stayed **enabled**, clicking it opened a dead-end panel, which reads as "broken."
2. **The two entry points are not the same feature.** One asks about *policy content*; the other is *product/setup help*. Removing either would delete a working, distinct capability.

**Implemented fix (minimal, low-risk):** disable the "Ask about this policy" trigger until a policy is live, with an inline explanation ("Publish your policy to ask questions about it."). This removes the dead-end that caused the confusion, keeps the feature discoverable, and preserves both tools. No feature deleted, no backend/schema change.

## The two entry points

| | **"Ask about this policy"** | **Floating "?" widget** |
|---|---|---|
| Component | `HrPolicyAssistantPanel` (in `HrPolicyPageV2`, opened via `PolicyAssistantDockedShell`) | `SetupAssistantFab` → `SetupAssistantDrawer` → `SetupAssistantPanel` (rendered globally by `AppShell`, HR-only) |
| Question it answers | *"What does my policy say?"* — benefit rules, employee-visible values, publish impact, draft-vs-published | *"How do I use ReloPass?"* — e.g. "How do I publish a policy?", "What's my next setup step?" |
| Backend | `hrAPI.postPolicyAssistantQuery` (company-scoped policy RAG, grounded in the published policy) | `askSetupAssistant` / `getSetupStatus` (`api/setupAssistant`) — onboarding/setup guidance |
| Availability | Gated on a **published** policy (`canQuery` / `hasQueryablePolicy`) | Always available for HR, every page |

## Gap analysis (6 dimensions)

1. **Feature completeness.** Both support free-text input, submit-to-backend, and grounded answers. The policy assistant adds citations/evidence deep-links, follow-up chips, and draft-vs-published context; the setup assistant adds a setup-status checklist. Neither is a subset of the other.
2. **Code maintainability.** No shared broken code and no dead code: `SetupAssistantPanel`/`Fab`/`Drawer` are explicit re-skins of the policy assistant's structure but target a different endpoint. Deleting one would not simplify the other. The `PolicyAssistantFab` the ticket imagined was already retired and replaced by the in-page "Ask about this policy" trigger.
3. **UX clarity.** The genuine issue: two "ask a question" affordances on one page invite "which one?", and the policy trigger opened a dead-end before a policy existed. The fix disables the trigger (with an inline reason) until it's useful; the setup "?" remains the product-help path. Their labels/subtitles already differ ("Ask about this policy version…" vs "Get guided help setting up your ReloPass workspace"), so relabeling is optional.
4. **Backend coupling.** Different endpoints, no shared logic. The policy assistant is RAG over `policy_assistant_chunks`; the setup assistant answers product how-to. Consolidating them would require merging two unrelated backends — not warranted.
5. **Context awareness.** The policy assistant is already scoped to the workspace's published policy (company-scoped RAG; `policy_id` is no longer sent). The setup assistant is intentionally global. No context-injection change is needed.
6. **Accessibility / mobile.** The surviving fix uses an always-visible inline hint next to a disabled button rather than a hover-only tooltip, so it works on touch and with keyboards. The ask box, when it renders, already has an associated `<label>` (sr-only) and is keyboard-navigable.

## Why not "consolidate to one"

Validation criterion 1 ("only ONE Q&A entry point") assumes the two are the same feature. They are not: policy-content Q&A and product/setup help serve different questions and different backends. Deleting either would regress a working capability and confuse users who relied on it. The confusion the feedback describes is fully resolved by not offering the policy Q&A trigger before it can work — which this change does.

## What changed

- `frontend/src/features/policy/HrPolicyPageV2.tsx` — the "Ask about this policy" trigger is now `disabled` until `hasLivePolicy`, with an inline "Publish your policy to ask questions about it." hint. Both features are retained.
- `docs/qa-consolidation-recommendation.md` — this document.
