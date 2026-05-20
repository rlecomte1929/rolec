import { hrAPI } from '../../../api/client';
import type { CompanyProfilePayload } from '../../../types';
import { useHrCompanyContext } from '../../../contexts/HrCompanyContext';
import { CompanyProfileForm } from './CompanyProfileForm';
import { PlatformSidebar } from '../sidebar';

/**
 * HR's own-company profile page. Data comes from useHrCompanyContext
 * (session-scoped), persistence goes through hrAPI.saveCompanyProfile +
 * hrAPI.{upload,remove}CompanyLogo. The shared CompanyProfileForm handles
 * everything else (sections, dirty tracking, sticky save bar).
 *
 * Layout uses the V2 collapsible PlatformSidebar (state persists via
 * localStorage), not the legacy AppShell, so the page matches the new
 * platform chrome direction.
 */
export function CompanyProfileV2Page() {
  const { company, loading, error, refresh } = useHrCompanyContext();

  async function handleSave(payload: CompanyProfilePayload) {
    await hrAPI.saveCompanyProfile(payload);
    await refresh();
  }

  async function handleUploadLogo(file: File) {
    await hrAPI.uploadCompanyLogo(file);
    await refresh();
  }

  async function handleRemoveLogo() {
    await hrAPI.removeCompanyLogo();
    await refresh();
  }

  const companyName = (company?.['name'] as string | undefined) || 'Company profile';

  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900">
      <PlatformSidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="border-b border-slate-200 bg-white px-8 py-4">
          <div className="flex items-center gap-2 text-[12.5px] text-slate-500">
            <span>{companyName}</span>
            <span className="text-slate-300">/</span>
            <span>HR Operations</span>
            <span className="text-slate-300">/</span>
            <span className="font-medium text-slate-800">Company profile</span>
          </div>
        </div>
        <CompanyProfileForm
          company={company}
          loading={loading}
          loadError={error}
          onSave={handleSave}
          onUploadLogo={handleUploadLogo}
          onRemoveLogo={handleRemoveLogo}
          eyebrow="ReloPass · /hr/company-profile"
          title="Company profile"
          subtitle="How your company appears across ReloPass — to your employees, your providers, and the platform's recommendation engine. Changes save against your tenant."
        />
      </main>
    </div>
  );
}

export default CompanyProfileV2Page;
