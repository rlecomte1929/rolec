import { useNavigate } from 'react-router-dom';
import { Button } from '../../components/antigravity/Button';
import { WelcomeShell } from '../../components/WelcomeShell';
import { WelcomeStepCard } from '../../components/WelcomeStepCard';
import { buildRoute, ROUTE_DEFS } from '../../navigation/routes';
import { getAuthItem } from '../../utils/demo';
import { markWelcomeSeen } from '../../utils/welcomeSeen';
import { persistWelcomeSeen } from '../../api/welcome';

/**
 * Employee first-login orientation. Same dismiss/navigate rules as the HR page:
 * shown once, skippable, inside AppShell; only Skip and the bottom CTA mark the
 * welcome as seen (step links leave it reachable).
 */
export function EmployeeWelcomePage() {
  const navigate = useNavigate();
  const userId = getAuthItem('relopass_user_id') ?? '';

  const handleSkip = () => {
    markWelcomeSeen(userId);
    void persistWelcomeSeen().catch(() => {});
    navigate(buildRoute('employeeDashboard'));
  };

  const handleStartIntake = () => {
    markWelcomeSeen(userId);
    void persistWelcomeSeen().catch(() => {});
    navigate(buildRoute('employeeIntake'));
  };

  return (
    <WelcomeShell onSkip={handleSkip}>
      <p className="text-sm font-medium text-accent-500 uppercase tracking-wide mb-2">Welcome to ReloPass</p>
      <h1 className="text-2xl font-semibold text-navy-800 mb-3">Your relocation starts here</h1>
      <p className="text-sm text-slate-600 mb-10 max-w-lg">
        Three steps stand between you and a clear, personalised relocation plan. Follow them in order — each one
        unlocks the next.
      </p>

      <div className="flex flex-col gap-4">
        <WelcomeStepCard
          step={1}
          title="Tell us about your move"
          description="The intake form collects your destination, timeline, and personal situation. It takes about 5 minutes."
          href={buildRoute('employeeIntake')}
          badge="Start here"
          note="Your HR team may have pre-filled some information for you."
        />
        <WelcomeStepCard
          step={2}
          title="Get your personalised roadmap"
          description="Once intake is complete, ReloPass generates a step-by-step plan covering admin tasks, housing, immigration, and more."
          href={ROUTE_DEFS.employeeDashboard.path}
          badge="Unlocked after intake"
        />
        <WelcomeStepCard
          step={3}
          title="Find the services you need"
          description="Browse vetted housing, legal, and logistics providers recommended for your destination."
          href="/services"
          badge="Explore anytime"
        />
      </div>

      <div className="my-10 border-t border-slate-100" />

      <h2 className="text-base font-semibold text-navy-800 mb-1">Questions before you start?</h2>
      <p className="text-sm text-slate-600 mb-4">
        Your HR contact is available through the Messages tab if you need anything.
      </p>
      <Button variant="primary" onClick={handleStartIntake}>
        Begin the intake form →
      </Button>
    </WelcomeShell>
  );
}
