import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import { Copy, Check, PlayCircle } from 'lucide-react';
import { PublicLayout } from '../../components/public';
import { Section, HeroSurface, SectionHeader, CTAButton, FadeIn } from '../../components/marketing';
import { Card, Alert, Button, Input } from '../../components/antigravity';
import { usePageMeta } from '../../hooks/usePageMeta';
import { authAPI } from '../../api/client';
import { getAuthItem } from '../../utils/demo';
import {
  provisionTestDrive,
  recordTestDriveEvent,
  completeTestDrive,
  type ProvisionSuccess,
  type TestDriveCredential,
} from '../../api/testDrive';

/** localStorage key the FeedbackWidget reads to stamp in-session feedback (TD-9). */
const TEST_DRIVE_LS_KEY = 'relopass_test_drive';
import {
  testDriveContent as c,
  TEST_DRIVE_CORRIDORS,
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
  const navigate = useNavigate();
  const rawCorridor = (searchParams.get('corridor') || '').toUpperCase();
  const matched = TEST_DRIVE_CORRIDORS[rawCorridor];
  const hasExplicitCorridor = !!matched;
  // null until server assigns one (auto-assign) or immediately set for explicit ?corridor=
  const [assignedCorridorId, setAssignedCorridorId] = useState<string | null>(
    matched ? rawCorridor : null,
  );
  const assignedCorridorMeta = assignedCorridorId ? TEST_DRIVE_CORRIDORS[assignedCorridorId] : null;
  const isTierB = assignedCorridorMeta?.tier === 'B';
  const corridorLabel = assignedCorridorMeta
    ? `${assignedCorridorMeta.origin} → ${assignedCorridorMeta.destination}`
    : '';
  const inviteToken = searchParams.get('token') || '';
  // TD-FIX-2 (AIQ-1503): single link for everyone — the segment is NOT assumed at
  // provision. Honour an explicit ?segment= (internal deploy checks), else leave it
  // undefined so the row is NULL until the survey's one-tap self-ID resolves it.
  const rawSegment = searchParams.get('segment');
  const segment: 'internal' | 'prospect' | undefined =
    rawSegment === 'internal' ? 'internal' : rawSegment === 'prospect' ? 'prospect' : undefined;
  // AIQ-1633: capture the segment at the START via a one-tap landing question, so
  // dropouts (who never reach the survey) are classified too. An explicit ?segment=
  // (internal deploy checks) still wins; unanswered stays honest — NULL, never a
  // silent 'prospect'. The survey pre-fills from and may still override this.
  const [selfSegment, setSelfSegment] = useState<'internal' | 'prospect' | null>(null);
  const effectiveSegment: 'internal' | 'prospect' | undefined = segment ?? selfSegment ?? undefined;
  // AIQ-1563: forward ?campaign= so a QA link (e.g. ?campaign=qa-posthog) provisions AND
  // records its funnel under a separate campaign, never contaminating the real cohort.
  // Absent → undefined, so the backend default (RELOPASS_TEST_DRIVE_CAMPAIGN → insead-2026)
  // applies and the plain cohort link is unchanged. Respect the backend's 64-char cap.
  const campaign = (searchParams.get('campaign') || '').trim().slice(0, 64) || undefined;

  const [firstName, setFirstName] = useState('');
  const [email, setEmail] = useState('');
  const [state, setState] = useState<SubmitState>('idle');
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ProvisionSuccess | null>(null);
  // A session started in a previous visit (stashed at provision, TD-9) — lets the
  // "Finish with the survey" button work even after a reload, once a run exists.
  const [priorSession, setPriorSession] = useState<{ session: string; corridor: string; campaign?: string } | null>(null);

  // TD-8: record a funnel "click" once on landing (per-invite token / corridor).
  useEffect(() => {
    void recordTestDriveEvent({
      event_type: 'click',
      campaign,
      corridor_id: assignedCorridorId ?? undefined,
      tester_segment: segment,
      invite_token: inviteToken || undefined,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // AIQ-1640: recover a prior run from localStorage so it survives navigating away and
  // coming back — the test-drive is a deliberate round trip (leave, use the product,
  // return to complete + survey). localStorage (not session-scoped) so it also survives
  // a FULL browser reload, not just SPA navigation. When the full credential set was
  // stashed we rehydrate the whole `result` (credentials + completion CTA + survey link);
  // otherwise we fall back to the lighter priorSession so at least the survey stays
  // reachable (e.g. an older stash from before credential persistence).
  useEffect(() => {
    try {
      const raw = localStorage.getItem(TEST_DRIVE_LS_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as {
        session_id?: string;
        corridor_id?: string;
        campaign?: string;
        hr?: TestDriveCredential;
        employee?: TestDriveCredential;
      };
      if (!parsed?.session_id) return;
      setPriorSession({
        session: parsed.session_id,
        corridor: parsed.corridor_id || assignedCorridorId || '',
        campaign: parsed.campaign,
      });
      if (parsed.hr && parsed.employee && parsed.corridor_id && parsed.campaign) {
        setAssignedCorridorId(parsed.corridor_id);
        setResult({
          ok: true,
          sessionId: parsed.session_id,
          corridorId: parsed.corridor_id,
          campaign: parsed.campaign,
          hr: parsed.hr,
          employee: parsed.employee,
        });
      }
    } catch {
      /* storage unavailable / private mode — no prior session */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (state !== 'idle') return;
    if (firstName.trim().length < 1) {
      setError(c.errors.firstNameRequired);
      return;
    }
    // AIQ-1556 correction: the email is OPTIONAL — a blank one is a valid choice, not an
    // error. The relocation data is synthetic, so nothing here should force real PII; the
    // only reason to leave an address is consenting to a follow-up. Validate the format
    // only when the tester actually typed something.
    const trimmedEmail = email.trim();
    if (trimmedEmail.length > 0 && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(trimmedEmail)) {
      setError(c.errors.emailInvalid);
      return;
    }
    setState('submitting');
    setError(null);
    const res = await provisionTestDrive({
      first_name: firstName.trim(),
      // AIQ-1556: omitted entirely when blank — declining contact is a valid choice.
      ...(trimmedEmail ? { tester_email: trimmedEmail } : {}),
      // AIQ-1563: forward ?campaign= so QA runs stay out of the real cohort.
      ...(campaign ? { campaign } : {}),
      ...(hasExplicitCorridor ? { corridor_id: rawCorridor } : {}),
      // AIQ-1633: prefer the landing-page one-tap answer (or ?segment= override); still
      // undefined → NULL when the tester skips the question.
      tester_segment: effectiveSegment,
      invite_token: inviteToken || undefined,
    });
    if (res.ok) {
      setAssignedCorridorId(res.corridorId);
      // TD-9: stash the campaign slice for the FeedbackWidget to stamp in-session feedback.
      // TD-M0: also stash the contact so the survey pre-fills it instead of re-asking.
      try {
        localStorage.setItem(
          TEST_DRIVE_LS_KEY,
          JSON.stringify({
            campaign: res.campaign,
            corridor_id: res.corridorId,
            // AIQ-1633: stash the resolved segment so the survey pre-fills it.
            tester_segment: effectiveSegment,
            session_id: res.sessionId,
            tester_name: firstName.trim(),
            // May be '' — the survey lead-in then simply has nothing to pre-fill.
            tester_email: trimmedEmail,
            // AIQ-1640: stash the credential pairs too, so returning to /test-drive
            // after using the product (the test-drive is a deliberate round trip)
            // restores the whole result block — credentials, completion CTA, survey
            // link — not just the survey link. These are disposable @probe.test
            // accounts already shown on screen; persisting them is what the design needs.
            hr: res.hr,
            employee: res.employee,
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

  // Link to the survey, carrying the run's session for attribution. Available once a
  // run exists (this visit's result, or a prior visit recovered from localStorage).
  // AIQ-1640: the survey link carries session_id, corridor_id AND campaign so the
  // returning tester's survey is attributed correctly (the survey endpoint still derives
  // campaign from the session server-side, but the link is self-describing either way).
  const surveyLink = result
    ? `/test-drive/survey?corridor=${result.corridorId}&session=${result.sessionId}&campaign=${encodeURIComponent(result.campaign)}`
    : priorSession
      ? `/test-drive/survey?corridor=${priorSession.corridor}&session=${priorSession.session}${priorSession.campaign ? `&campaign=${encodeURIComponent(priorSession.campaign)}` : ''}`
      : null;
  const surveySessionId = result?.sessionId ?? priorSession?.session ?? null;

  // TD-FIX-1 (AIQ-1502): the "I've completed my test" CTA must RECORD completion
  // before it routes to the survey — otherwise `test_sessions.completed_at` stays NULL
  // and "Testers completed" reads zero forever. completeTestDrive is best-effort, so
  // on failure we still navigate — never trap the tester behind a telemetry call.
  const completeThenSurvey = async (sessionId: string, link: string) => {
    await completeTestDrive(sessionId);
    navigate(link);
  };

  return (
    <PublicLayout>
      {/* Hero */}
      <Section spacing="lg" background="transparent">
        <HeroSurface
          eyebrow={assignedCorridorMeta ? `${c.hero.eyebrowPrefix} · ${corridorLabel}` : c.hero.eyebrowPrefix}
          title={c.hero.headline}
          subtitle={c.hero.subhead}
        />
      </Section>

      {/* Corridor label + Tier-B early-coverage note — hidden until corridor is known */}
      {assignedCorridorMeta && (
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
      )}

      {/* Start block — form OR the dual-credential result. AIQ-1541: kept high on the
          page so the name field + Start button (and, after provisioning, the credentials
          + sign-in link) are reachable without scrolling past the explanatory sections. */}
      <Section spacing="lg" background="muted">
        <FadeIn>
          <div className={result ? 'mx-auto max-w-3xl' : 'mx-auto max-w-xl'}>
            {result ? (
              <CredentialResult
                result={result}
                onComplete={(sessionId, link) => {
                  void completeThenSurvey(sessionId, link);
                }}
              />
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

                  {/* TD-M0 (AIQ-1556, corrected): OPTIONAL contact — captured at the start so a
                      tester who consents is reachable even if they drop out. No required marker:
                      leaving it blank is a valid choice and the full test still runs. */}
                  <label
                    htmlFor="td-email"
                    className="mt-4 block text-sm font-medium text-marketing-primary"
                  >
                    {c.startBlock.emailLabel}
                  </label>
                  <Input
                    unstyled
                    id="td-email"
                    type="email"
                    value={email}
                    onChange={setEmail}
                    placeholder={c.startBlock.emailPlaceholder}
                    autoComplete="email"
                    disabled={state === 'submitting'}
                    aria-describedby="td-email-helper"
                    className="mt-1 w-full rounded-lg border border-marketing-border bg-white px-3 py-2 text-sm text-marketing-text transition-colors focus:border-marketing-accent focus:outline-none focus:ring-2 focus:ring-marketing-accent/40 disabled:cursor-not-allowed disabled:bg-marketing-surface-muted"
                  />
                  <p id="td-email-helper" className="mt-2 text-xs text-marketing-text-muted">
                    {c.startBlock.emailHelper}
                  </p>

                  {/* AIQ-1633: one-tap segment self-ID at the START. Optional (tap again to
                      clear) so an unanswered session stays honest — NULL, never 'prospect'.
                      An explicit ?segment= URL override still wins in the provision payload. */}
                  <fieldset className="mt-4" disabled={state === 'submitting'}>
                    <legend className="block text-sm font-medium text-marketing-primary">
                      {c.startBlock.segment.label}
                    </legend>
                    <div
                      role="radiogroup"
                      aria-label={c.startBlock.segment.label}
                      className="mt-2 grid grid-cols-2 gap-2"
                    >
                      {([['prospect', c.startBlock.segment.yes], ['internal', c.startBlock.segment.no]] as const).map(
                        ([val, label]) => {
                          const active = selfSegment === val;
                          return (
                            <Button
                              key={val}
                              unstyled
                              type="button"
                              role="radio"
                              aria-checked={active}
                              onClick={() => setSelfSegment((prev) => (prev === val ? null : val))}
                              className={`inline-flex items-center justify-center rounded-lg border px-4 py-2 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-marketing-accent/40 ${
                                active
                                  ? 'border-marketing-accent bg-marketing-accent/10 text-marketing-primary'
                                  : 'border-marketing-border bg-white text-marketing-text hover:border-marketing-accent'
                              }`}
                            >
                              {label}
                            </Button>
                          );
                        },
                      )}
                    </div>
                    <p className="mt-2 text-xs text-marketing-text-muted">{c.startBlock.segment.helper}</p>
                  </fieldset>

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

      {/* What ReloPass is (TD-FIX-6 / AIQ-1509) — newcomer intro, above "What
          we're testing". Plain-text paragraphs only — no emphasis on any word. */}
      <Section spacing="lg" background="transparent">
        <FadeIn>
          <div className="mx-auto max-w-2xl">
            <SectionHeader title={c.whatReloPassIs.header} align="center" narrow />
            <div className="mt-6 space-y-4">
              {c.whatReloPassIs.paragraphs.map((p) => (
                <p key={p} className="text-marketing-body text-marketing-text leading-relaxed text-center">
                  {p}
                </p>
              ))}
            </div>
          </div>
        </FadeIn>
      </Section>

      {/* What we're testing */}
      <Section spacing="lg" background="muted">
        <FadeIn>
          <div className="mx-auto max-w-2xl">
            <SectionHeader title={c.whatWeTest.header} align="center" narrow />
            <div className="mt-6 space-y-4">
              {c.whatWeTest.paragraphs.map((p) => (
                <p key={p} className="text-marketing-body text-marketing-text leading-relaxed text-center">
                  {p}
                </p>
              ))}
            </div>
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
                  {/* TD-FIX-5 (AIQ-1506): name the assigned route inside the HR step so the
                      tester keeps the case on-corridor. Shown once a corridor is known. */}
                  {idx === 1 && assignedCorridorMeta && (
                    <span className="mt-2 block font-medium text-marketing-primary">
                      {c.howItWorks.corridorInstruction
                        .replace('{origin}', assignedCorridorMeta.origin)
                        .replace('{destination}', assignedCorridorMeta.destination)}
                    </span>
                  )}
                </span>
              </li>
            ))}
          </ol>
        </FadeIn>
      </Section>

      {/* Unlocking the roadmap — test payment with EXACT card details (no surprises) */}
      <Section spacing="lg" background="muted">
        <FadeIn>
          <div className="mx-auto max-w-2xl">
            <SectionHeader title={c.paymentTest.header} align="center" narrow />
            <p className="mt-6 text-marketing-body text-marketing-text leading-relaxed text-center">
              {c.paymentTest.intro}
            </p>
            <div className="mt-6 mx-auto max-w-md space-y-2 rounded-xl border border-marketing-border bg-white p-4">
              {c.paymentTest.card.map((row) => (
                <CopyRow key={row.label} label={row.label} value={row.value} />
              ))}
            </div>
            <p className="mt-4 text-center text-sm text-marketing-text-muted">{c.paymentTest.note}</p>
          </div>
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
                {clip.file ? (
                  // eslint-disable-next-line jsx-a11y/media-has-caption -- TD-11 v1: silent clip, captions are burned into the frames
                  <video
                    controls
                    preload="metadata"
                    poster={clip.poster}
                    className="aspect-video w-full rounded-xl border border-marketing-border bg-black object-cover"
                  >
                    <source src={clip.file} type="video/mp4" />
                  </video>
                ) : (
                  <div className="aspect-video flex items-center justify-center rounded-xl border border-marketing-border bg-marketing-surface-muted">
                    <PlayCircle aria-hidden="true" size={40} className="text-marketing-text-muted" />
                  </div>
                )}
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

      {/* Finish with the survey — dedicated, always-available exit once a run exists */}
      {surveyLink && (
        <Section spacing="lg" background="muted">
          <FadeIn>
            <div className="mx-auto max-w-2xl text-center">
              <SectionHeader title={c.wrapUp.header} align="center" narrow />
              <p className="mt-6 text-marketing-body text-marketing-text leading-relaxed">
                {c.wrapUp.body}
              </p>
              <div className="mt-8">
                <CTAButton
                  onClick={() => {
                    void completeThenSurvey(surveySessionId ?? '', surveyLink);
                  }}
                  variant="primary"
                  size="lg"
                >
                  {c.wrapUp.button}
                </CTAButton>
              </div>
              <p className="mt-3 text-[11px] text-marketing-text-muted">{c.wrapUp.note}</p>
            </div>
          </FadeIn>
        </Section>
      )}
    </PublicLayout>
  );
};

/**
 * AIQ-1569 (TD-BUG-2): the "Sign in" affordance beside the test credentials.
 *
 * The page assumed a logged-out visitor. It never was for the people who matter most —
 * Romain demoing this to an investor, or any tester who already has a ReloPass account.
 * They clicked "Sign in →", the browser carried their existing session to /auth, and they
 * landed in their OWN account (an admin dashboard, in the reported walkthrough) rather
 * than the test HR login. The only way through was to know to sign out first.
 *
 * So: read the session at render. Logged out — nothing changes, same link as before.
 * Logged in — name the account they're in and offer one click to leave it. This is a UX
 * guard only; it grants nothing and blocks nothing a user couldn't already do.
 */
const SignInAction: React.FC = () => {
  // Read once at mount: this block renders after provisioning, and a session cannot
  // change underneath it without a navigation.
  //
  // Guarded because this is a PUBLIC page: storage access throws outright in some
  // private-browsing modes, and getAuthItem does a bare localStorage.getItem. An
  // unguarded read here would crash the whole credentials block — taking the tester's
  // logins down with it — over an optional convenience. Same reason the prior-session
  // read above is wrapped. Fail closed to "logged out": that renders the plain link,
  // which is exactly the pre-AIQ-1569 behaviour.
  const [signedInAs] = useState<string | null>(() => {
    try {
      if (!getAuthItem('relopass_token')) return null;
      return getAuthItem('relopass_email') || getAuthItem('relopass_username') || 'another account';
    } catch {
      return null;
    }
  });
  const [signingOut, setSigningOut] = useState(false);

  const signInClasses =
    'inline-flex items-center justify-center rounded-lg bg-marketing-primary px-5 py-2.5 ' +
    'text-sm font-semibold text-white transition-colors hover:bg-marketing-primary-muted ' +
    'focus:outline-none focus:ring-2 focus:ring-marketing-accent focus:ring-offset-2 ' +
    'disabled:cursor-not-allowed disabled:opacity-60';

  if (!signedInAs) {
    return (
      <Link to={c.credentials.signInHref} className={signInClasses}>
        {c.credentials.signInCta}
      </Link>
    );
  }

  const handleSignOut = async () => {
    if (signingOut) return;
    setSigningOut(true);
    try {
      // Canonical sign-out: server logout + supabase + clearAuthItems. Never raises.
      await authAPI.logout();
    } catch {
      /* logout swallows its own errors; fall through to the login page regardless */
    }
    // Hard navigation, not react-router: every context in the tree still holds the old
    // session, and the login page must mount clean. Mirrors AppShell's sign-out.
    window.location.assign(c.credentials.signInHref);
  };

  return (
    <div data-testid="td-signed-in-guard" className="mx-auto max-w-md">
      <Alert variant="warning">
        {c.credentials.signedInNotice.replace('{email}', signedInAs)}
      </Alert>
      <Button
        onClick={handleSignOut}
        disabled={signingOut}
        className={`mt-3 ${signInClasses}`}
        data-testid="td-sign-out"
      >
        {signingOut ? c.credentials.signedOutBusy : c.credentials.signedInCta}
      </Button>
    </div>
  );
};

/** Dual-credential display shown after a successful provision. */
const CredentialResult: React.FC<{
  result: ProvisionSuccess;
  onComplete: (sessionId: string, link: string) => void;
}> = ({ result, onComplete }) => {
  // TD-FIX-7 (AIQ-1510): name the assigned route again right where the tester picks up
  // their logins. The route is already pinned on the case, so this is a statement of
  // fact, not an instruction. Plain text — no emphasis on any word.
  const corridor = TEST_DRIVE_CORRIDORS[result.corridorId];
  return (
  <div>
    <SectionHeader title={c.credentials.header} align="center" narrow />
    <Alert variant="info" className="mt-6">
      {c.credentials.note}
    </Alert>
    {corridor && (
      <p className="mt-4 text-center text-marketing-body text-marketing-text">
        {c.credentials.corridorNote
          .replace('{origin}', corridor.origin)
          .replace('{destination}', corridor.destination)}
      </p>
    )}
    {/* AIQ-1539: a direct route to the login page, right beside the credentials.
        AIQ-1569 (TD-BUG-2): but only when the visitor is actually logged out. */}
    <div className="mt-5 text-center">
      <SignInAction />
    </div>
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
    {/* AIQ-1539: plain line — where the test ends, and that the survey is required. */}
    <p className="mt-8 text-center text-marketing-body text-marketing-text leading-relaxed">
      {c.credentials.doneNote}
    </p>
    <div className="mt-4 text-center">
      <CTAButton
        onClick={() =>
          onComplete(
            result.sessionId,
            `/test-drive/survey?corridor=${result.corridorId}&session=${result.sessionId}&campaign=${encodeURIComponent(result.campaign)}`,
          )
        }
        variant="primary"
        size="lg"
      >
        {c.credentials.completeCta}
      </CTAButton>
    </div>
  </div>
  );
};

const CredentialCard: React.FC<{
  title: string;
  caption: string;
  credential: TestDriveCredential;
}> = ({ title, caption, credential }) => (
  <Card padding="lg">
    <h3 className="text-[17px] font-semibold text-marketing-primary">{title}</h3>
    <p className="mt-1 text-sm text-marketing-text-muted leading-relaxed">{caption}</p>
    <div className="mt-4 space-y-2">
      <CopyRow label={c.credentials.emailLabel} value={credential.email} />
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
        {/* AIQ-1622 (F1): break-all + title so the full credential email/password is
            readable, not truncated behind a Copy-only affordance. */}
        <p className="break-all font-mono text-sm text-marketing-text" title={value}>{value}</p>
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
