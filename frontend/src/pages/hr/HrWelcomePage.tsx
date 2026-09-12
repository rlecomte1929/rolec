import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LoadingButton } from '../../components/antigravity/LoadingButton';
import { WelcomeShell } from '../../components/WelcomeShell';
import { WelcomeStepCard } from '../../components/WelcomeStepCard';
import { buildRoute, homeRouteKeyForRole } from '../../navigation/routes';
import { trackHrWelcomeExit, type HrWelcomeExit } from '../../analyticsEvents';
import { getAuthItem } from '../../utils/demo';
import { looksLikeTestEmail } from '../../utils/testAccount';
import { markWelcomeSeen } from '../../utils/welcomeSeen';
import { persistWelcomeSeen } from '../../api/welcome';

/**
 * HR first-login orientation. Shown once (see useWelcomeRedirect + welcomeSeen),
 * skippable, rendered inside AppShell. The welcome is NOT marked seen on mount, and
 * the per-step "Get started" links do NOT mark it either — only Skip and the bottom
 * CTA do, so an HR user can open a setup step and still return here until they
 * explicitly move on.
 *
 * AIQ-1571 (TD-BUG-4): a real HR genuinely should configure their company first — it
 * pre-fills every case they ever open. A test-drive HR should not: the campaign asks
 * them to "run the HR side, configure the case and hand it to the employee", and this
 * page answered with a 12-field company-profile form badged "Start here", with the case
 * CTA below a divider at the bottom. Testers did sysadmin work before reaching the point
 * of the test. So for a test-drive session the emphasis inverts — case first, setup
 * demoted to optional. Same page, same steps, different order of insistence; nothing is
 * removed, so a tester who wants the full HR experience still has every step.
 */
export function HrWelcomePage() {
  const navigate = useNavigate();
  const userId = getAuthItem('relopass_user_id') ?? '';
  const isTestDrive = looksLikeTestEmail(getAuthItem('relopass_email'));
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    void import('../HrDashboard');
    void import('../../features/platform-v2/mobility-control/MobilityControlCenterV2Page');
  }, []);

  const variant: 'real' | 'test_drive' = isTestDrive ? 'test_drive' : 'real';

  const leave = (exit: HrWelcomeExit, to: string) => {
    if (leaving) return;
    setLeaving(true);
    markWelcomeSeen(userId);
    void persistWelcomeSeen().catch(() => {});
    trackHrWelcomeExit({ exit, variant });
    navigate(to);
  };

  // 'HR' literal on purpose: an ADMIN previewing the HR welcome must land on the HR
  // home, not /admin. homeRouteKeyForRole is the resolver behind the login redirect
  // and the AppShell identity link, so this exit moves with them (AIQ-2177).
  const handleSkip = () => leave('skip', buildRoute(homeRouteKeyForRole('HR')));
  const handleOpenCommandCenter = () => leave('command_center', buildRoute('hrCommandCenter'));
  // The one real case form (HrDashboard.openNewCaseForm) via the ?new=1 deep link
  // AIQ-1568 added. Both variants use it now (AIQ-2321).
  const handleOpenFirstCase = () => leave('open_case', `${buildRoute('hrDashboard')}?new=1`);

  if (isTestDrive) {
    return (
      <WelcomeShell onSkip={handleSkip} hideSkip>
        <p className="text-sm font-medium text-accent-600 uppercase tracking-wide mb-2">Welcome to ReloPass</p>
        <h1 className="text-2xl font-semibold text-navy-800 mb-3">Open your first relocation case</h1>
        <p className="text-sm text-slate-600 mb-6 max-w-lg">
          Your company and route are already set up for this test — you can go straight to the case, add the
          employee, and hand it off. That is the part worth your time.
        </p>
        {leaving ? (
          <div className="fixed top-0 inset-x-0 z-[70] h-0.5 bg-accent-500" role="progressbar" aria-label="Opening page" />
        ) : null}
        <LoadingButton
          variant="primary"
          onClick={handleOpenFirstCase}
          loading={leaving}
          loadingLabel="Opening…"
        >
          Create your first case →
        </LoadingButton>

        <div className="my-10 border-t border-slate-100" />

        <h2 className="text-base font-semibold text-navy-800 mb-1">Optional — the full HR setup</h2>
        <p className="text-sm text-slate-600 mb-4 max-w-lg">
          None of this is needed to run the test, and it stays in the sidebar if you want to explore it.
        </p>
        <div className="flex flex-col gap-4">
          <WelcomeStepCard
            step={1}
            title="Configure your company"
            description="Add your company name, size, default destination, and key contacts. This pre-fills every case you open."
            href="/hr/company-profile"
            ctaLabel="Open company profile →"
          />
          <WelcomeStepCard
            step={2}
            title="Build your relocation policy"
            description="Define tiers, budgets, and eligibility rules. The policy engine applies them automatically to each case."
            // AIQ-1599: land on the policy OVERVIEW (default 'policy' tab), not straight
            // into the builder — the builder stays reachable via its own tab there.
            href="/hr/policy"
            ctaLabel="Open policy →"
          />
          <WelcomeStepCard
            step={3}
            title="Curate your service providers"
            description="Choose which moving companies, housing services, and immigration specialists appear in your cases."
            href={`${buildRoute('hrServiceProviders')}?tab=vendor`}
            ctaLabel="Open service providers →"
          />
        </div>

        <div className="my-10 border-t border-slate-100" />

        <button
          type="button"
          onClick={handleOpenCommandCenter}
          disabled={leaving}
          className="inline-flex min-h-6 items-center text-sm text-slate-500 hover:text-slate-700 hover:underline disabled:opacity-60"
        >
          {leaving ? 'Opening…' : 'Open the mobility command center'}
        </button>
      </WelcomeShell>
    );
  }

  return (
    <WelcomeShell onSkip={handleSkip} hideSkip wide>
      <p className="text-sm font-medium text-accent-600 uppercase tracking-wide mb-2">Welcome to ReloPass</p>
      <h1 className="text-2xl font-semibold text-navy-800 mb-3">Set up your company workspace</h1>
      <p className="text-sm text-slate-600 mb-10 max-w-lg">
        Before creating a relocation case, a few things will make everything work better. You can do
        these in any order — or come back to them later.
      </p>

      <div
        data-testid="hr-welcome-layout"
        className="grid grid-cols-1 gap-10 min-[960px]:grid-cols-[minmax(0,1fr)_minmax(16rem,20rem)] min-[960px]:items-start"
      >
        <div>
          <h2 className="text-base font-semibold text-navy-800 mb-4">How it works</h2>
          <div className="flex flex-col gap-4">
            <WelcomeStepCard
              step={1}
              title="Configure your company"
              description="Add your company name, size, default destination, and key contacts. This pre-fills every case you open."
              href="/hr/company-profile"
              badge="Start here"
              ctaLabel="Open company profile →"
              emphasized
            />
            <WelcomeStepCard
              step={2}
              title="Build your relocation policy"
              description="Define tiers, budgets, and eligibility rules. The policy engine applies them automatically to each case."
              // AIQ-1599: land on the policy OVERVIEW (default 'policy' tab), not straight
              // into the builder — the builder stays reachable via its own tab there.
              href="/hr/policy"
              ctaLabel="Open policy →"
            />
            <WelcomeStepCard
              step={3}
              title="Curate your service providers"
              description="Choose which moving companies, housing services, and immigration specialists appear in your cases."
              href={`${buildRoute('hrServiceProviders')}?tab=vendor`}
              ctaLabel="Open service providers →"
            />
          </div>
        </div>

        <aside>
          {leaving ? (
            <div className="fixed top-0 inset-x-0 z-[70] h-0.5 bg-accent-500" role="progressbar" aria-label="Opening page" />
          ) : null}
          <h2 className="text-base font-semibold text-navy-800 mb-1">Ready to open your first case?</h2>
          <p className="text-sm text-slate-600 mb-4">
            You can skip setup for now and start a case directly. The setup steps stay in the sidebar.
          </p>
          <LoadingButton
            variant="primary"
            onClick={handleOpenFirstCase}
            loading={leaving}
            loadingLabel="Opening…"
            data-testid="hr-welcome-open-first-case"
          >
            Open your first case →
          </LoadingButton>
          <button
            type="button"
            onClick={handleOpenCommandCenter}
            disabled={leaving}
            className="mt-3 inline-flex min-h-6 items-center text-sm text-slate-500 hover:text-slate-700 hover:underline disabled:opacity-60"
          >
            {leaving ? 'Opening…' : 'Open the mobility command center'}
          </button>
        </aside>
      </div>
    </WelcomeShell>
  );
}
