/**
 * Copy for HR starter-template onboarding (platform baselines).
 */

export const STARTER_POLICY_CARD_TITLE = 'Start with a standard baseline';

export const STARTER_POLICY_CARD_EXPLANATION =
  'Use this when you do not have a signed-off file ready yet. ReloPass fills in sensible starting limits you can edit, publish, and refine. When your formal policy is ready, upload it—ReloPass saves it as a new draft until you publish.';

export const STARTER_POLICY_DISCLOSURE_BULLETS = [
  'Every number and label is yours to change before or after you go live.',
  'Employees only see a policy after you publish a version; drafts stay visible to HR only.',
  'You can upload an approved company document anytime to replace or extend this baseline—the upload does not go live until you publish that version.',
];

export type StarterTemplateKey = 'conservative' | 'standard' | 'premium';

export const STARTER_TEMPLATE_OPTIONS: Array<{
  key: StarterTemplateKey;
  label: string;
  description: string;
}> = [
  {
    key: 'conservative',
    label: 'Conservative',
    description: 'Lower illustrative caps — a cautious default you can raise as needed.',
  },
  {
    key: 'standard',
    label: 'Standard',
    description: 'Balanced baseline for most teams; easiest place to start.',
  },
  {
    key: 'premium',
    label: 'Premium',
    description: 'Higher illustrative caps — adjust down if that fits your program better.',
  },
];
