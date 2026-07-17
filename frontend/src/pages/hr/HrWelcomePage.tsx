import { useNavigate } from 'react-router-dom';
import { Button } from '../../components/antigravity/Button';
import { WelcomeShell } from '../../components/WelcomeShell';
import { WelcomeStepCard } from '../../components/WelcomeStepCard';
import { getAuthItem } from '../../utils/demo';
import { markWelcomeSeen } from '../../utils/welcomeSeen';

/**
 * HR first-login orientation. Shown once (see useWelcomeRedirect + welcomeSeen),
 * skippable, rendered inside AppShell. The welcome is NOT marked seen on mount, and
 * the per-step "Get started" links do NOT mark it either — only Skip and the bottom
 * CTA do, so an HR user can open a setup step and still return here until they
 * explicitly move on.
 */
export function HrWelcomePage() {
  const navigate = useNavigate();
  const userId = getAuthItem('relopass_user_id') ?? '';

  const handleSkip = () => {
    markWelcomeSeen(userId);
    navigate('/hr/dashboard');
  };

  const handleGoToDashboard = () => {
    markWelcomeSeen(userId);
    navigate('/hr/command-center');
  };

  return (
    <WelcomeShell onSkip={handleSkip}>
      <p className="text-sm font-medium text-accent-500 uppercase tracking-wide mb-2">Welcome to ReloPass</p>
      <h1 className="text-2xl font-semibold text-navy-800 mb-3">Set up your company workspace</h1>
      <p className="text-sm text-slate-600 mb-10 max-w-lg">
        Before creating your first relocation case, a few things will make everything work better. You can do
        these in any order — or come back to them later.
      </p>

      <div className="flex flex-col gap-4">
        <WelcomeStepCard
          step={1}
          title="Configure your company"
          description="Add your company name, size, default destination, and key contacts. This pre-fills every case you open."
          href="/hr/company-profile"
          badge="Start here"
        />
        <WelcomeStepCard
          step={2}
          title="Build your relocation policy"
          description="Define tiers, budgets, and eligibility rules. The policy engine applies them automatically to each case."
          href="/hr/policy?tab=builder"
        />
        <WelcomeStepCard
          step={3}
          title="Curate your provider list"
          description="Choose which moving companies, housing services, and immigration specialists appear in your cases."
          href="/hr/provider-grid"
        />
      </div>

      <div className="my-10 border-t border-slate-100" />

      <h2 className="text-base font-semibold text-navy-800 mb-1">Ready to open your first case?</h2>
      <p className="text-sm text-slate-600 mb-4">
        You can skip setup for now and start a case directly. The setup steps will remain accessible in the
        sidebar at any time.
      </p>
      <Button variant="primary" onClick={handleGoToDashboard}>
        Go to the Command Center →
      </Button>
    </WelcomeShell>
  );
}
