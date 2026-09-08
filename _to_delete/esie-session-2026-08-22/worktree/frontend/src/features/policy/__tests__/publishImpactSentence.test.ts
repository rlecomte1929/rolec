/**
 * Slice 3c — publishImpactSentence covers the phase-aware "If you
 * publish right now: …" copy. Locks the contract so accidentally
 * dropping a phase reveals itself in CI.
 */
import { describe, expect, it } from 'vitest';
import { publishImpactSentence } from '../policyWorkflowCopy';

describe('publishImpactSentence', () => {
  it('no_policy: tells HR there is nothing to publish yet', () => {
    const s = publishImpactSentence({ phase: 'no_policy' }, {});
    expect(s).toMatch(/no policy to publish/i);
  });

  it('draft_not_publishable + N issues: surfaces the blocker count', () => {
    const s = publishImpactSentence(
      { phase: 'draft_not_publishable', highlightIssues: [{}, {}, {}] },
      {}
    );
    expect(s).toMatch(/3 blockers/);
    expect(s).toMatch(/What to fix before going live/i);
  });

  it('draft_not_publishable + 1 issue: pluralizes correctly', () => {
    const s = publishImpactSentence(
      { phase: 'draft_not_publishable', highlightIssues: [{}] },
      {}
    );
    expect(s).toMatch(/1 blocker\b/);
  });

  it('draft_not_publishable + 0 issues: still nudges to the checklist', () => {
    const s = publishImpactSentence({ phase: 'draft_not_publishable' }, {});
    expect(s).toMatch(/needs review/i);
  });

  it('ready_to_publish: promises immediate effect after Publish', () => {
    const s = publishImpactSentence({ phase: 'ready_to_publish' }, {});
    expect(s).toMatch(/immediately after you click Publish/i);
  });

  it('published (no replacement): says nothing changes right now', () => {
    const s = publishImpactSentence(
      { phase: 'published', hasUnpublishedDraftAhead: false },
      {}
    );
    expect(s).toMatch(/no immediate change/i);
    expect(s).not.toMatch(/replacement draft/i);
  });

  it('published + replacement draft: explains employees keep live view', () => {
    const s = publishImpactSentence(
      { phase: 'published', hasUnpublishedDraftAhead: true },
      { draftReplacement: { title: 'Replacement draft' } }
    );
    expect(s).toMatch(/HR-only/i);
  });

  it('unknown phase: falls back to a safe sentence', () => {
    const s = publishImpactSentence({ phase: 'something-new' }, {});
    expect(s).toMatch(/Publish when ready/i);
  });
});
