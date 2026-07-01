import { useEffect, useMemo, useState } from 'react';
import { useSpaceRuntime } from '../SpaceRuntimeContext';
import { ArrowLeft, ArrowRight, Check, Heart, Shield, Sparkles } from 'lucide-react';

export const EMAIL_GATE_VERSION = 101;

const INTAKE_VERSION = '2026-03-26';

interface EmailGateProps {
  spaceId: string;
}

type QuestionId = 'urgent' | 'support' | 'situation';
type GateStep = 'question' | 'summary';

interface QuestionOption {
  id: string;
  label: string;
  note: string;
}

interface IntakeQuestion {
  id: QuestionId;
  eyebrow: string;
  title: string;
  helper: string;
  options: QuestionOption[];
}

type IntakeAnswers = Partial<Record<QuestionId, string>>;

interface IntakeResult {
  headline: string;
  reflection: string;
  anchor: string;
  nextSteps: string[];
  starterPrompts: string[];
}

interface StoredBeaconSession {
  id?: string;
  workspaceSessionId?: string;
  email?: string;
  contactId?: string | null;
  timestamp?: number;
  verified?: boolean;
  metadata?: Record<string, unknown>;
  intake?: {
    answers: IntakeAnswers;
    result: IntakeResult;
    completedAt: number;
    version: string;
  };
}

const QUESTIONS: IntakeQuestion[] = [
  {
    id: 'urgent',
    eyebrow: 'Question 1 of 3',
    title: 'What feels most urgent right now?',
    helper: 'Pick the first thing you want Beacon to help you steady.',
    options: [
      {
        id: 'prepare_conversation',
        label: 'I need to prepare for a hard conversation.',
        note: 'You want help choosing words, boundaries, and tone before you talk.',
      },
      {
        id: 'process_after',
        label: 'A conversation already happened and I need to process it.',
        note: 'You want help sorting what happened before reacting again.',
      },
      {
        id: 'hold_boundaries',
        label: 'I keep getting pulled into chaos and need steadier boundaries.',
        note: 'You want something calmer and more repeatable than the current cycle.',
      },
      {
        id: 'money_or_safety',
        label: 'Money, safety, or another immediate ask keeps throwing me off.',
        note: 'You need enough structure to make the next decision more clearly.',
      },
    ],
  },
  {
    id: 'support',
    eyebrow: 'Question 2 of 3',
    title: 'What would help most first?',
    helper: 'Beacon will use this to shape your first reflection.',
    options: [
      {
        id: 'words_to_use',
        label: 'Words I can actually use.',
        note: 'Scripts and phrasing you can say out loud without sounding robotic.',
      },
      {
        id: 'calmer_frame',
        label: 'A calmer way to think about this.',
        note: 'Less spiraling, more perspective.',
      },
      {
        id: 'small_plan',
        label: 'A small plan for the next 24 hours.',
        note: 'One grounded next move, not a giant overhaul.',
      },
      {
        id: 'what_helps',
        label: 'Clarity on what helps and what backfires.',
        note: 'Beacon can orient you around CRAFT-aligned patterns.',
      },
    ],
  },
  {
    id: 'situation',
    eyebrow: 'Question 3 of 3',
    title: 'How would you describe the situation right now?',
    helper: 'This helps Beacon tune the first step to the amount of instability you are carrying.',
    options: [
      {
        id: 'active_unstable',
        label: 'Things feel active, unstable, or unpredictable.',
        note: 'The first move should lower pressure, not add more intensity.',
      },
      {
        id: 'early_recovery',
        label: 'They are trying to get better, but it still feels fragile.',
        note: 'You need support that stays warm without taking over.',
      },
      {
        id: 'same_cycle',
        label: 'We keep ending up in the same painful cycle.',
        note: 'You want to interrupt the pattern, not relive it again.',
      },
      {
        id: 'hard_to_describe',
        label: 'I am not even sure how to describe it yet.',
        note: 'The first value Beacon should give you is clarity.',
      },
    ],
  },
];

function getSessionKey(spaceId: string) {
  return `space_session_${spaceId}`;
}

function getHandoffKey(spaceId: string) {
  return `beacon_intake_handoff_${spaceId}`;
}

function createTeaserSessionId() {
  return `beacon_intake_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function readStoredSession(spaceId: string): StoredBeaconSession | null {
  try {
    const stored =
      localStorage.getItem(getSessionKey(spaceId)) ||
      sessionStorage.getItem(getSessionKey(spaceId));

    if (!stored) {
      return null;
    }

    return JSON.parse(stored) as StoredBeaconSession;
  } catch (error) {
    console.error('[BeaconEmailGate] Failed to read stored session:', error);
    return null;
  }
}

function writeStoredSession(spaceId: string, session: StoredBeaconSession) {
  const serialized = JSON.stringify(session);
  localStorage.setItem(getSessionKey(spaceId), serialized);
  sessionStorage.setItem(getSessionKey(spaceId), serialized);
}

function getOption(questionId: QuestionId, optionId?: string | null) {
  if (!optionId) {
    return null;
  }

  const question = QUESTIONS.find((item) => item.id === questionId);
  return question?.options.find((option) => option.id === optionId) || null;
}

function buildStarterPrompts(answers: IntakeAnswers): string[] {
  const urgentPromptMap: Record<string, string> = {
    prepare_conversation: 'Help me prepare for the next conversation without making it worse.',
    process_after: 'Help me make sense of the conversation that just happened.',
    hold_boundaries: 'Help me hold a boundary without sounding cold or explosive.',
    money_or_safety: 'Help me think through the next money or safety decision clearly.',
  };

  const supportPromptMap: Record<string, string> = {
    words_to_use: 'Give me a few grounded phrases I can actually use.',
    calmer_frame: 'Help me get calmer before I decide what to do next.',
    small_plan: 'Help me make a small plan for the next 24 hours.',
    what_helps: 'Help me understand what is likely to help and what could backfire.',
  };

  const situationPromptMap: Record<string, string> = {
    active_unstable: 'Help me stay grounded when things feel unpredictable.',
    early_recovery: 'Help me support progress without over-managing it.',
    same_cycle: 'Help me break one part of the pattern we keep repeating.',
    hard_to_describe: 'Help me describe what is happening so I can think more clearly.',
  };

  return [
    urgentPromptMap[answers.urgent || 'prepare_conversation'],
    supportPromptMap[answers.support || 'small_plan'],
    situationPromptMap[answers.situation || 'hard_to_describe'],
  ];
}

function buildIntakeResult(answers: IntakeAnswers): IntakeResult {
  const urgentMap: Record<string, { headline: string; reflection: string; nextStep: string }> = {
    prepare_conversation: {
      headline: 'Start with one steadier conversation, not the whole future.',
      reflection:
        'When a hard conversation is coming, the goal is not to say everything perfectly. It is to stay grounded enough to be clear, calm, and boundaried.',
      nextStep: 'Choose the one point you most need to land and the one place you will stop, even if the conversation stays messy.',
    },
    process_after: {
      headline: 'Before you decide what comes next, help your nervous system catch up.',
      reflection:
        'After a painful conversation, it is easy to replay everything or jump straight into fixing. Beacon can help you separate what happened from the stress story around it.',
      nextStep: 'Name the part that hurt most, then decide whether the next move is repair, distance, or simply a pause.',
    },
    hold_boundaries: {
      headline: 'A steadier boundary starts by making the next line smaller and clearer.',
      reflection:
        'You do not need a perfect long-term system before you can stop one familiar pattern. Small consistency often lands better than a dramatic reset.',
      nextStep: 'Pick one limit you can actually keep this week, then let Beacon help you phrase it without overexplaining.',
    },
    money_or_safety: {
      headline: 'When things feel urgent, the first move is to slow the decision down enough to think.',
      reflection:
        'Money and safety asks can create instant panic, guilt, or confusion. Beacon can help you sort what is urgent, what is yours to carry, and what needs outside support.',
      nextStep: 'Get clear on the immediate facts first, then decide what you will do, what you will not do, and who else should be involved.',
    },
  };

  const supportMap: Record<string, { anchor: string; nextStep: string }> = {
    words_to_use: {
      anchor: 'Let Beacon turn your instinct into a few grounded sentences you can actually say out loud.',
      nextStep: 'Draft the sentence you most need, then pressure-test it for warmth, clarity, and boundaries.',
    },
    calmer_frame: {
      anchor: 'Start by shrinking the problem down to the next honest, useful step instead of carrying the whole story at once.',
      nextStep: 'Notice the thought that is spiking the most fear, then replace it with something truer and more workable.',
    },
    small_plan: {
      anchor: 'The goal is one manageable plan for the next 24 hours, not a full blueprint for the relationship.',
      nextStep: 'Leave with one conversation goal, one boundary, and one support action you can take today.',
    },
    what_helps: {
      anchor: 'Beacon can help you separate actions that reinforce health from actions that accidentally reinforce chaos.',
      nextStep: 'Name one pattern you want to reinforce less and one healthier behavior you want to notice more.',
    },
  };

  const situationMap: Record<string, { reflectionTail: string; nextStep: string }> = {
    active_unstable: {
      reflectionTail: 'Because things feel unstable right now, the first step should lower pressure rather than add more intensity.',
      nextStep: 'Keep the first move simple enough to do even on a hard day.',
    },
    early_recovery: {
      reflectionTail: 'Because things still feel fragile, support matters most when it stays steady without trying to control the outcome.',
      nextStep: 'Focus on what is yours to communicate and what belongs to their recovery work.',
    },
    same_cycle: {
      reflectionTail: 'Because the pattern feels repetitive, changing one small part of the exchange can matter more than searching for a perfect breakthrough.',
      nextStep: 'Interrupt the most predictable moment in the cycle with a calmer, shorter response.',
    },
    hard_to_describe: {
      reflectionTail: 'Because the situation still feels hard to name, clarity is the first value Beacon should give you.',
      nextStep: 'Use the first conversation with Beacon to turn a blur of stress into a few concrete facts and needs.',
    },
  };

  const urgentProfile = urgentMap[answers.urgent || 'prepare_conversation'];
  const supportProfile = supportMap[answers.support || 'small_plan'];
  const situationProfile = situationMap[answers.situation || 'hard_to_describe'];

  return {
    headline: urgentProfile.headline,
    reflection: `${urgentProfile.reflection} ${situationProfile.reflectionTail}`,
    anchor: supportProfile.anchor,
    nextSteps: [
      urgentProfile.nextStep,
      supportProfile.nextStep,
      situationProfile.nextStep,
    ],
    starterPrompts: buildStarterPrompts(answers),
  };
}

function buildFlatMetadata(answers: IntakeAnswers, result: IntakeResult): Record<string, string> {
  return {
    beacon_intake_version: INTAKE_VERSION,
    beacon_intake_urgent: answers.urgent || '',
    beacon_intake_urgent_label: getOption('urgent', answers.urgent)?.label || '',
    beacon_intake_support: answers.support || '',
    beacon_intake_support_label: getOption('support', answers.support)?.label || '',
    beacon_intake_situation: answers.situation || '',
    beacon_intake_situation_label: getOption('situation', answers.situation)?.label || '',
    beacon_intake_headline: result.headline,
    beacon_intake_anchor: result.anchor,
    beacon_intake_prompt_1: result.starterPrompts[0] || '',
    beacon_intake_prompt_2: result.starterPrompts[1] || '',
    beacon_intake_prompt_3: result.starterPrompts[2] || '',
  };
}

function getVisitorId(): string {
  const key = 'audos_visitor_id';
  let id = localStorage.getItem(key);

  if (!id) {
    id = `v_${Math.random().toString(36).slice(2)}_${Date.now()}`;
    localStorage.setItem(key, id);
  }

  return id;
}

function getAttribution() {
  const params = new URLSearchParams(window.location.search);
  const attribution: Record<string, string> = {};

  if (params.get('utm_source')) attribution.utmSource = params.get('utm_source') as string;
  if (params.get('utm_medium')) attribution.utmMedium = params.get('utm_medium') as string;
  if (params.get('utm_campaign')) attribution.utmCampaign = params.get('utm_campaign') as string;
  if (params.get('utm_content')) attribution.utmContent = params.get('utm_content') as string;
  if (params.get('utm_term')) attribution.utmTerm = params.get('utm_term') as string;
  if (params.get('fbclid')) attribution.fbclid = params.get('fbclid') as string;
  if (params.get('gclid')) attribution.gclid = params.get('gclid') as string;
  if (params.get('ref')) attribution.referrer = params.get('ref') as string;
  if (document.referrer) attribution.httpReferrer = document.referrer;

  return Object.keys(attribution).length > 0 ? attribution : null;
}

function trackMetaPixelLead(email: string) {
  if (typeof window !== 'undefined' && (window as any).fbq) {
    (window as any).fbq('track', 'Lead', {
      content_name: 'Beacon Guided Intake',
      content_category: 'Space Registration',
      em: email.toLowerCase().trim(),
    });
  }
}

// Task #1480: parallel Reddit Pixel Lead fire (SwingCaddy + future per-workspace
// allowlist entries). conversionId is opaque to BeaconEmailGateDraft because it
// has no server-track POST of its own; caller passes it in if dedupe is needed.
// Calls window.rdt directly — the queue stub installed by the live PageVisit
// snippet (Task #1456) handles late pixel.js loads.
function trackRedditPixelLead(email: string, conversionId: string) {
  if (typeof window === 'undefined') return;
  try {
    const rdt = (window as any).rdt;
    const pixelId = (window as any).__REDDIT_PIXEL_ID__;
    if (typeof rdt !== 'function') return;
    if (pixelId) {
      rdt('init', pixelId, { email: email.toLowerCase().trim() });
    }
    rdt('track', 'Lead', { conversionId });
  } catch (e) {
    try { console.warn('[BeaconEmailGate] Reddit Pixel Lead failed', e); } catch (_) {}
  }
}

export default function EmailGate({ spaceId }: EmailGateProps) {
  const { setSessionId } = useSpaceRuntime();
  const [step, setStep] = useState<GateStep>('question');
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [answers, setAnswers] = useState<IntakeAnswers>({});
  const [intakeResult, setIntakeResult] = useState<IntakeResult | null>(null);
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [mounted, setMounted] = useState(false);

  const currentQuestionConfig = QUESTIONS[currentQuestion];
  const progress = step === 'summary' ? 100 : Math.round(((currentQuestion + 1) / QUESTIONS.length) * 100);
  const answerSummary = useMemo(
    () =>
      QUESTIONS.map((question) => {
        const selected = getOption(question.id, answers[question.id]);
        if (!selected) {
          return null;
        }

        return { question: question.title, answer: selected.label };
      }).filter(Boolean) as Array<{ question: string; answer: string }>,
    [answers]
  );

  useEffect(() => {
    setMounted(true);

    const existingSession = readStoredSession(spaceId);
    if (!existingSession) {
      return;
    }

    if (existingSession.email) {
      setEmail(existingSession.email);
    }

    const effectiveSessionId =
      existingSession.workspaceSessionId ||
      (typeof existingSession.id === 'string' && existingSession.id.startsWith('wses_')
        ? existingSession.id
        : null);

    if (effectiveSessionId) {
      setSessionId(effectiveSessionId);
      return;
    }

    if (existingSession.intake?.answers) {
      setAnswers(existingSession.intake.answers);
    }

    if (existingSession.intake?.result) {
      setIntakeResult(existingSession.intake.result);
      setStep('summary');
      setCurrentQuestion(QUESTIONS.length - 1);
    }
  }, [spaceId, setSessionId]);

  const persistTeaser = (nextAnswers: IntakeAnswers, result: IntakeResult) => {
    const existingSession = readStoredSession(spaceId) || {};
    const nextSession: StoredBeaconSession = {
      ...existingSession,
      id: existingSession.id || createTeaserSessionId(),
      email: email.trim() || existingSession.email,
      timestamp: existingSession.timestamp || Date.now(),
      metadata: {
        ...(existingSession.metadata || {}),
        ...buildFlatMetadata(nextAnswers, result),
      },
      intake: {
        answers: nextAnswers,
        result,
        completedAt: Date.now(),
        version: INTAKE_VERSION,
      },
    };

    writeStoredSession(spaceId, nextSession);
    return nextSession;
  };

  const handleSelectAnswer = (optionId: string) => {
    const nextAnswers = {
      ...answers,
      [currentQuestionConfig.id]: optionId,
    };

    setAnswers(nextAnswers);
    setError('');

    if (currentQuestion === QUESTIONS.length - 1) {
      const result = buildIntakeResult(nextAnswers);
      persistTeaser(nextAnswers, result);
      setIntakeResult(result);
      setStep('summary');
      return;
    }

    setCurrentQuestion((value) => value + 1);
  };

  const handleBack = () => {
    setError('');

    if (step === 'summary') {
      setStep('question');
      setCurrentQuestion(QUESTIONS.length - 1);
      return;
    }

    if (currentQuestion > 0) {
      setCurrentQuestion((value) => value - 1);
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    if (!email || !email.includes('@')) {
      setError('Please enter a valid email address');
      return;
    }

    if (!intakeResult) {
      setError('Finish the quick intake first so Beacon can carry your context forward.');
      return;
    }

    setLoading(true);
    setError('');

    const normalizedEmail = email.toLowerCase().trim();

    try {
      const existingSession = readStoredSession(spaceId) || persistTeaser(answers, intakeResult);
      const workspaceId = (window as any).__WORKSPACE_ID__ || null;
      const visitorId = getVisitorId();
      const metadata = {
        ...buildFlatMetadata(answers, intakeResult),
        beacon_intake_stage: 'completed',
      };

      const response = await fetch(`/api/space/${spaceId}/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: normalizedEmail,
          sessionId: existingSession.id || createTeaserSessionId(),
          visitorId,
          attribution: getAttribution(),
          metadata,
          workspaceId,
        }),
      });

      const result = await response.json();

      if (!response.ok) {
        setError(result.error || 'Registration failed. Please try again.');
        setLoading(false);
        return;
      }

      trackMetaPixelLead(normalizedEmail);
      // Task #1480: parallel Reddit Pixel Lead. conversionId is deterministic
      // off the canonical session so a later server-side CAPI call (if BeaconEmailGate
      // ever gets its own track POST) can dedupe with the rdt('track','Lead',…) here.
      const beaconLeadConversionId = `lead_${spaceId}_${(result?.workspaceSessionId || existingSession.id || Date.now())}`;
      trackRedditPixelLead(normalizedEmail, beaconLeadConversionId);

      const canonicalSessionId =
        result.workspaceSessionId || result.sessionId || existingSession.id || createTeaserSessionId();

      const mergedSession: StoredBeaconSession = {
        ...existingSession,
        id: canonicalSessionId,
        workspaceSessionId: result.workspaceSessionId || canonicalSessionId,
        email: normalizedEmail,
        contactId: result.contactId || existingSession.contactId || null,
        verified: true,
        timestamp: Date.now(),
        metadata: {
          ...(existingSession.metadata || {}),
          ...(result.metadata || {}),
          ...metadata,
        },
        intake: existingSession.intake || {
          answers,
          result: intakeResult,
          completedAt: Date.now(),
          version: INTAKE_VERSION,
        },
      };

      writeStoredSession(spaceId, mergedSession);
      sessionStorage.setItem(getHandoffKey(spaceId), 'ready');

      try {
        window.dispatchEvent(
          new CustomEvent('audos:session-established', {
            detail: {
              contactId: result.contactId || null,
              workspaceSessionId: result.workspaceSessionId || canonicalSessionId,
              email: normalizedEmail,
            },
          })
        );
      } catch (dispatchError) {
        console.warn('[BeaconEmailGate] Failed to dispatch session-established event:', dispatchError);
      }

      setSessionId(result.workspaceSessionId || canonicalSessionId);
    } catch (submitError) {
      console.error('[BeaconEmailGate] Failed to register Beacon session:', submitError);
      setError('Connection error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      <link
        href="https://fonts.googleapis.com/css2?family=Fraunces:wght@500;600;700&family=Source+Sans+3:wght@400;500;600;700&display=swap"
        rel="stylesheet"
      />

      <div
        className="min-h-screen px-4 py-8 md:px-6 md:py-10"
        style={{
          background: 'linear-gradient(180deg, #FDF8F3 0%, #F6F1EA 48%, #EEF5F3 100%)',
          fontFamily: "'Source Sans 3', system-ui, sans-serif",
          opacity: mounted ? 1 : 0,
          transition: 'opacity 240ms ease',
        }}
      >
        <div className="mx-auto max-w-3xl">
          <div className="mb-6 text-center">
            <p
              className="text-sm font-semibold uppercase tracking-[0.22em]"
              style={{ color: '#2D7A6D' }}
            >
              Beacon
            </p>
            <h1
              className="mt-3 text-3xl font-semibold leading-tight md:text-4xl"
              style={{ color: '#1E3A34', fontFamily: "'Fraunces', Georgia, serif" }}
            >
              Start with a calmer next step.
            </h1>
            <p className="mx-auto mt-3 max-w-2xl text-base leading-7 text-stone-600 md:text-lg">
              Answer three quick questions. Beacon will give you a personalized starting point before asking for your email.
            </p>
          </div>

          <div className="mx-auto max-w-2xl rounded-[28px] border border-white/70 bg-white/90 p-6 shadow-[0_24px_80px_rgba(30,58,52,0.10)] backdrop-blur md:p-8">
            <div className="mb-6">
              <div className="mb-3 flex items-center justify-between text-sm text-stone-500">
                <span>{step === 'summary' ? 'Your starting point' : currentQuestionConfig.eyebrow}</span>
                <span>{progress}%</span>
              </div>
              <div className="h-2 rounded-full bg-stone-100">
                <div
                  className="h-2 rounded-full transition-all duration-300"
                  style={{ width: `${progress}%`, background: 'linear-gradient(90deg, #2D7A6D 0%, #7C9A92 100%)' }}
                />
              </div>
            </div>

            {step === 'question' && (
              <>
                <div className="mb-6">
                  <h2
                    className="text-2xl font-semibold leading-tight"
                    style={{ color: '#1E3A34', fontFamily: "'Fraunces', Georgia, serif" }}
                  >
                    {currentQuestionConfig.title}
                  </h2>
                  <p className="mt-3 text-base leading-7 text-stone-600">
                    {currentQuestionConfig.helper}
                  </p>
                </div>

                <div className="space-y-3">
                  {currentQuestionConfig.options.map((option) => (
                    <button
                      key={option.id}
                      type="button"
                      onClick={() => handleSelectAnswer(option.id)}
                      className="w-full rounded-2xl border px-5 py-4 text-left transition hover:-translate-y-0.5"
                      style={{
                        borderColor: '#E7E2DA',
                        background: '#FFFCF9',
                        boxShadow: '0 8px 24px rgba(30, 58, 52, 0.04)',
                      }}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="text-base font-semibold text-stone-800">{option.label}</p>
                          <p className="mt-1 text-sm leading-6 text-stone-500">{option.note}</p>
                        </div>
                        <ArrowRight className="mt-1 h-4 w-4 flex-shrink-0 text-stone-400" />
                      </div>
                    </button>
                  ))}
                </div>

                <div className="mt-6 flex items-center justify-between">
                  <button
                    type="button"
                    onClick={handleBack}
                    disabled={currentQuestion === 0}
                    className="inline-flex items-center gap-2 text-sm font-medium disabled:opacity-40"
                    style={{ color: '#5C7670' }}
                  >
                    <ArrowLeft className="h-4 w-4" />
                    Back
                  </button>
                  <p className="text-sm text-stone-400">Takes about 30 seconds</p>
                </div>
              </>
            )}

            {step === 'summary' && intakeResult && (
              <div className="space-y-6">
                <div className="rounded-[24px] border border-emerald-100 bg-gradient-to-br from-emerald-50 via-white to-stone-50 px-5 py-5">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-700 text-white">
                      <Sparkles className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-700">
                        Your Beacon starting point
                      </p>
                      <h2
                        className="mt-1 text-2xl font-semibold"
                        style={{ color: '#1E3A34', fontFamily: "'Fraunces', Georgia, serif" }}
                      >
                        {intakeResult.headline}
                      </h2>
                    </div>
                  </div>
                  <p className="mt-4 text-base leading-7 text-stone-700">{intakeResult.reflection}</p>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="rounded-2xl border border-stone-200 bg-stone-50 px-4 py-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">Today's anchor</p>
                    <p className="mt-3 text-sm leading-6 text-stone-700">{intakeResult.anchor}</p>
                  </div>
                  <div className="rounded-2xl border border-stone-200 bg-stone-50 px-4 py-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-stone-500">What Beacon will remember</p>
                    <div className="mt-3 space-y-2 text-sm text-stone-700">
                      {answerSummary.map((item) => (
                        <div key={item.question}>
                          <p className="font-medium text-stone-800">{item.question}</p>
                          <p>{item.answer}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div>
                  <p className="text-sm font-semibold text-stone-800">A good next move might be:</p>
                  <div className="mt-3 space-y-2">
                    {intakeResult.nextSteps.map((stepItem) => (
                      <div
                        key={stepItem}
                        className="flex items-start gap-3 rounded-2xl border border-stone-200 bg-white px-4 py-3 text-sm leading-6 text-stone-700"
                      >
                        <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-emerald-700" />
                        <span>{stepItem}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-[24px] border border-stone-200 bg-[#FFFDFC] px-5 py-5">
                  <p className="text-sm font-semibold text-stone-800">Unlock the full Beacon space.</p>
                  <p className="mt-2 text-sm leading-6 text-stone-600">
                    Enter your email to save this prep sheet and continue into Beacon chat, quick reference, and practice tools without repeating yourself.
                  </p>
                  <div className="mt-4 space-y-2 text-sm text-stone-700">
                    <div className="flex items-start gap-3 rounded-2xl bg-stone-50 px-4 py-3">
                      <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-emerald-700" />
                      <span>Keep this starting point attached to your session.</span>
                    </div>
                    <div className="flex items-start gap-3 rounded-2xl bg-stone-50 px-4 py-3">
                      <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-emerald-700" />
                      <span>Move between prep, quick reference, and role-play practice.</span>
                    </div>
                    <div className="flex items-start gap-3 rounded-2xl bg-stone-50 px-4 py-3">
                      <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-emerald-700" />
                      <span>Start free. No credit card required.</span>
                    </div>
                  </div>

                  <form onSubmit={handleSubmit} className="mt-4 space-y-4">
                    <div>
                      <input
                        type="email"
                        value={email}
                        onChange={(event) => {
                          setEmail(event.target.value);
                          setError('');
                        }}
                        placeholder="Enter your email"
                        className="w-full rounded-2xl border px-4 py-4 text-base outline-none transition"
                        style={{
                          borderColor: error ? '#E07A5F' : '#E7E2DA',
                          background: '#FFFFFF',
                          color: '#1E3A34',
                        }}
                        data-testid="input-email"
                        required
                      />
                      {error && (
                        <p className="mt-2 text-sm" style={{ color: '#E07A5F' }}>
                          {error}
                        </p>
                      )}
                    </div>

                    <button
                      type="submit"
                      disabled={loading}
                      className="inline-flex w-full items-center justify-center gap-2 rounded-2xl px-5 py-4 text-base font-semibold text-white transition"
                      style={{
                        background: loading ? '#9AB8B0' : '#2D7A6D',
                        boxShadow: loading ? 'none' : '0 16px 32px rgba(45, 122, 109, 0.24)',
                      }}
                      data-testid="button-continue"
                    >
                      <span>{loading ? 'Saving your starting point...' : 'Continue with Beacon'}</span>
                      {!loading && <ArrowRight className="h-4 w-4" />}
                    </button>
                  </form>
                </div>

                <div className="grid gap-3 text-sm text-stone-600 md:grid-cols-2">
                  <div className="flex items-start gap-3 rounded-2xl bg-stone-50 px-4 py-4">
                    <Shield className="mt-0.5 h-4 w-4 flex-shrink-0 text-emerald-700" />
                    <span>Your answers stay with your session so Beacon can pick up where this leaves off.</span>
                  </div>
                  <div className="flex items-start gap-3 rounded-2xl bg-stone-50 px-4 py-4">
                    <Heart className="mt-0.5 h-4 w-4 flex-shrink-0 text-rose-500" />
                    <span>Beacon is educational support, not a substitute for treatment or crisis care.</span>
                  </div>
                </div>

                <div className="flex items-center justify-between">
                  <button
                    type="button"
                    onClick={handleBack}
                    disabled={loading}
                    className="inline-flex items-center gap-2 text-sm font-medium disabled:opacity-40"
                    style={{ color: '#5C7670' }}
                  >
                    <ArrowLeft className="h-4 w-4" />
                    Edit answers
                  </button>
                  <p className="text-xs text-stone-400">No credit card required</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
