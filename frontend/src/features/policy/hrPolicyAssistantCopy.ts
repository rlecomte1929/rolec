export const HR_POLICY_ASSISTANT_TITLE = 'Ask about this policy';

export const HR_POLICY_ASSISTANT_SUBTITLE =
  'Ask to find the right clause, then open the source. The workspace text is the fact; the assistant is orientation, not a substitute for the published policy.';

export const HR_POLICY_ASSISTANT_PLACEHOLDER = 'Example: What do employees see for shipment?';

export const HR_POLICY_ASSISTANT_SCOPE_NOTE =
  'Answers use normalized policy data in this workspace (draft, published, rules). Not legal or immigration advice.';

/**
 * Trust-signal pill replacing the SCOPE_NOTE paragraph in the panel.
 * Visible above the response section. SCOPE_NOTE export kept for
 * back-compat; the panel no longer renders it.
 */
export const HR_POLICY_ASSISTANT_TRUST_PILL =
  "Verified from this workspace's policy data — not legal or immigration advice";

export const HR_POLICY_ASSISTANT_NO_POLICY =
  'Publish a policy for this workspace to enable Q&A. Once a policy is live, you can ask questions about it here.';

export const HR_POLICY_ASSISTANT_SUBMIT = 'Ask';

export const HR_POLICY_ASSISTANT_SUGGESTIONS: string[] = [
  'What do employees see for shipment?',
  'Is temporary housing comparison-ready?',
  'What changes if I publish this draft?',
  'Why is school search informational only?',
];
