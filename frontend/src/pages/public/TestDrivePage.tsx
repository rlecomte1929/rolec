import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Copy, Check, PlayCircle } from 'lucide-react';
import { PublicLayout } from '../../components/public';
import { Section, HeroSurface, SectionHeader, CTAButton, FadeIn } from '../../components/marketing';
import { Card, Alert, Button, Input } from '../../components/antigravity';
import { usePageMeta } from '../../hooks/usePageMeta';
import {
  provisionTestDrive,
  recordTestDriveEvent,
  type ProvisionSuccess,
  type TestDriveCredential,
} from '../../api/testDrive';

/** localStorage key the FeedbackWidget reads to stamp in-session feedback (TD-9). */
const TEST_DRIVE_LS_KEY = 'relopass_test_drive';
import {
  testDriveContent as c,
  TEST_DRIVE_CORRIDORS,
  DEFAULT_CORRIDOR_ID,
  DEFAULT_CORRIDOR,
} from './testDriveContent';

type SubmitState = 'idle' | 'submitting';

export const TestDrivePage: React.FC = () => {
  usePageMeta({
    title: 'Test drive · ReloPass',
    description:
      'Run one relocation end to end — as both the HR manager and the employee — on sample data. About 20 minutes.',
    ogUrl: 'https://www.relopass.com/test-drive',
  });

  const [searchParams] = useSearchParams();
  const rawCorridor = (searchParams.get('corridor') || '').toUpperCase();
  const matched = TEST_DRIVE_CORRIDORS[rawCorridor];
  const corridorId = matched ? rawCorridor : DEFAULT_CORRIDOR_ID;
  const corridor = matched ?? DEFAULT_CORRIDOR;
  const isTierB = corridor.tier === 'B';
  const corridorLabel = `${corridor.origin} → ${corridor.destination}`;
  const inviteToken = searchParams.get('token') || '';
  const segment: 'internal' | 'prospect' =
    searchParams.get('segment') === 'internal' ? 'internal' : 'prospect';

  const [firstName, setFirstName] = useState('');
  const [state, setState] = useState<SubmitState>('idle');
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ProvisionSuccess | null>(null);

  // TD-8: record a funnel "click" once on landing (per-invite token / corridor).
  useEffect(() => {
    void recordTestDriveEvent({
      event_type: 'click',
      corridor_id: corridorId,
      tester_segment: segment,
      invite_token: inviteToken || undefined,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (state !== 'idle') return;
    if (firstName.trim().length < 1) {
      setError(c.errors.firstNameRequired);
      return;
    }
    setState('submitting');
    setError(null);
    const res = await provisionTestDrive({
      first_name: firstName.trim(),
      corridor_id: corridorId,
      tester_segment: segment,
      invite_token: inviteToken,
    });
    if (res.ok) {
      // TD-9: stash the campaign slice for the FeedbackWidget to stamp in-session feedback.
      try {
        localStorage.setItem(
          TEST_DRIVE_LS_KEY,
          JSON.stringify({
            campaign: res.campaign,
            corridor_id: res.corridorId,
            tester_segment: segment,
            session_id: res.sessionId,
          }),
        );
      } catch {
        /* private-mode / storage disabled — non-fatal */
      }
      setResult(res);
    } else {
      setError(res.error);
    }
    setState('idle');
  };

  return (
    <PublicLayout>
      {/* Hero */}
      <Section spacing="lg" background="transparent">
        <HeroSurface
          eyebrow={`${c.hero.eyebrowPrefix} · ${corridorLabel}`}
          title={c.hero.headline}
          subtitle={c.hero.subhead}
        />
      </Section>

      {/* Corridor label + Tier-B early-coverage note */}
      <Section spacing="sm" background="transparent">
        <div className="mx-auto max-w-2xl text-center">
          <p className="text-sm text-marketing-text">
            <span className="font-semibold text-marketing-primary">{c.corridorLabel.prefix}</span>{' '}
            {corridorLabel}
          </p>
          {isTierB && (
            <Alert variant="info" className="mt-4 text-left">
              {c.corridorLabel.tierBNote}
            </Alert>
          )}
        </div>
      </Section>

      {/* What we're testing */}
      <Section spacing="lg" background="muted">
        <FadeIn>
          <div className="mx-auto max-w-2xl">
            <SectionHeader title={c.whatWeTest.header} align="center" narrow />
            <p className="mt-6 text-marketing-body text-marketing-text leading-relaxed text-center">
              {c.whatWeTest.body}
            </p>
          </div>
        </FadeIn>
      </Section>

      {/* How it works */}
      <Section spacing="lg" background="transparent">
        <FadeIn>
          <SectionHeader title={c.howItWorks.header} align="center" narrow />
          <ol className="mt-10 mx-auto max-w-2xl space-y-5">
            {c.howItWorks.steps.map((step, idx) => (
              <li key={step.title} className="flex gap-4">
                <span
                  aria-hidden="true"
                  className="mt-0.5 inline-flex h-7 w-7 flex-none items-center justify-center rounded-full bg-marketing-accent/10 text-sm font-semibold text-marketing-accent"
                >
                  {idx + 1}
                </span>
                <span className="text-marketing-body text-marketing-text leading-relaxed">
                  <span className="font-semibold text-marketing-primary">{step.title}</span>{' '}
                  {step.body}
                </span>
              </li>
            ))}
          </ol>
        </FadeIn>
      </Section>

      {/* Before you start — video placeholders (real embeds land in TD-11) */}
      <Section spacing="lg" background="muted">
        <FadeIn>
          <SectionHeader title={c.videos.header} align="center" narrow />
          <p className="mt-6 text-marketing-body text-marketing-text-muted text-center">
            {c.videos.intro}
          </p>
          <div className="mt-10 grid gap-6 md:grid-cols-3">
            {c.videos.clips.map((clip) => (
              <div key={clip.label}>
                <div className="aspect-video flex items-center justify-center rounded-xl border border-marketing-border bg-marketing-surface-muted">
                  <PlayCircle aria-hidden="true" size={40} className="text-marketing-text-muted" />
                </div>
                <p className="mt-3 text-sm font-semibold text-marketing-primary">{clip.label}</p>
                <p className="mt-1 text-sm text-marketing-text-muted leading-relaxed">
                  {clip.description}
                </p>
              </div>
            ))}
          </div>
        </FadeIn>
      </Section>

      {/* About the data */}
      <Section spacing="lg" background="transparent">
        <FadeIn>
          <div className="mx-auto max-w-2xl">
            <SectionHeader title={c.aboutData.header} align="center" narrow />
            <p className="mt-6 text-marketing-body text-marketing-text leading-relaxed text-center">
              {c.aboutData.body}
            </p>
          </div>
        </FadeIn>
      </Section>

      {/* Start block — form OR the dual-credential result */}
      <Section spacing="lg" background="muted">
        <FadeIn>
          <div className="mx-auto max-w-xl">
            {result ? (
              <CredentialResult result={result} />
            ) : (
              <>
                <SectionHeader title={c.startBlock.header} align="center" narrow />
                <form
                  onSubmit={handleSubmit}
                  noValidate
                  className="mt-8 rounded-xl border border-marketing-border bg-marketing-surface p-6 sm:p-8"
                >
                  <label
                    htmlFor="td-first-name"
                    className="block text-sm font-medium text-marketing-primary"
                  >
                    {c.startBlock.fieldLabel}
                    <span aria-hidden="true" className="ml-0.5 text-[#dc2626]">*</span>
                  </label>
                  <Input
                    unstyled
                    id="td-first-name"
                    value={firstName}
                    onChange={setFirstName}
                    placeholder={c.startBlock.placeholder}
                    autoComplete="given-name"
                    disabled={state === 'submitting'}
                    aria-describedby="td-first-name-helper"
                    className="mt-1 w-full rounded-lg border border-marketing-border bg-white px-3 py-2 text-sm text-marketing-text transition-colors focus:border-marketing-accent focus:outline-none focus:ring-2 focus:ring-marketing-accent/40 disabled:cursor-not-allowed disabled:bg-marketing-surface-muted"
                  />
                  <p id="td-first-name-helper" className="mt-2 text-xs text-marketing-text-muted">
                    {c.startBlock.helper}
                  </p>

                  {error && (
                    <Alert variant="error" className="mt-4">
                      {error}
                    </Alert>
                  )}

                  <div className="mt-6">
                    <Button
                      unstyled
                      type="submit"
                      disabled={state === 'submitting'}
                      className="inline-flex w-full items-center justify-center rounded-lg bg-marketing-primary px-5 py-3 text-sm font-semibold text-white transition-colors hover:bg-marketing-primary-muted focus:outline-none focus:ring-2 focus:ring-marketing-accent focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {state === 'submitting' ? 'Starting…' : c.startBlock.button}
                    </Button>
                    <p className="mt-3 text-center text-[11px] text-marketing-text-muted">
                      {c.startBlock.legal}
                    </p>
                  </div>
                </form>
              </>
            )}
          </div>
        </FadeIn>
      </Section>

      {/* Feedback reminder */}
      <Section spacing="lg" background="transparent">
        <FadeIn>
          <div className="mx-auto max-w-2xl text-center">
            <SectionHeader title={c.feedback.header} align="center" narrow />
            <p className="mt-6 text-marketing-body text-marketing-text-muted leading-relaxed">
              {c.feedback.body}
            </p>
          </div>
        </FadeIn>
      </Section>
    </PublicLayout>
  );
};

/** Dual-credential display shown after a successful provision. */
const CredentialResult: React.FC<{ result: ProvisionSuccess }> = ({ result }) => (
  <div>
    <SectionHeader title={c.credentials.header} align="center" narrow />
    <Alert variant="info" className="mt-6">
      {c.credentials.note}
    </Alert>
    <div className="mt-6 grid gap-6 md:grid-cols-2">
      <CredentialCard
        title={c.credentials.hr.title}
        caption={c.credentials.hr.caption}
        credential={result.hr}
      />
      <CredentialCard
        title={c.credentials.employee.title}
        caption={c.credentials.employee.caption}
        credential={result.employee}
      />
    </div>
    <div className="mt-8 text-center">
      <CTAButton
        to={`/test-drive/survey?corridor=${result.corridorId}&session=${result.sessionId}`}
        variant="primary"
        size="lg"
      >
        {c.credentials.completeCta}
      </CTAButton>
    </div>
  </div>
);

const CredentialCard: React.FC<{
  title: string;
  caption: string;
  credential: TestDriveCredential;
}> = ({ title, caption, credential }) => (
  <Card padding="lg">
    <h3 className="text-[17px] font-semibold text-marketing-primary">{title}</h3>
    <p className="mt-1 text-sm text-marketing-text-muted leading-relaxed">{caption}</p>
    <div className="mt-4 space-y-2">
      <CopyRow label={c.credentials.usernameLabel} value={credential.username} />
      <CopyRow label={c.credentials.passwordLabel} value={credential.password} />
    </div>
  </Card>
);

const CopyRow: React.FC<{ label: string; value: string }> = ({ label, value }) => {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable — no-op */
    }
  };
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-marketing-border bg-white px-3 py-2">
      <div className="min-w-0">
        <p className="text-[11px] uppercase tracking-wide text-marketing-text-muted">{label}</p>
        <p className="truncate font-mono text-sm text-marketing-text">{value}</p>
      </div>
      <button
        type="button"
        onClick={copy}
        aria-label={`Copy ${label.toLowerCase()}`}
        className="inline-flex flex-none items-center gap-1 rounded-md border border-marketing-border px-2.5 py-1.5 text-xs font-medium text-marketing-primary transition-colors hover:bg-marketing-surface-muted focus:outline-none focus:ring-2 focus:ring-marketing-accent/40"
      >
        {copied ? <Check size={14} aria-hidden="true" /> : <Copy size={14} aria-hidden="true" />}
        <span>{copied ? 'Copied' : 'Copy'}</span>
      </button>
    </div>
  );
};
