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

  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900">
      <PlatformSidebar />
      <main className="flex-1 overflow-y-auto">
        <CompanyProfileForm
          company={company}
          loading={loading}
          loadError={error}
          onSave={handleSave}
          onUploadLogo={handleUploadLogo}
          onRemoveLogo={handleRemoveLogo}
          breadcrumbSection="HR Operations"
          title="Company profile"
          subtitle="How your company appears to employees, providers, and relocation partners on ReloPass. Changes are saved to your company account."
        />
      </main>
    </div>
  );
}

export default CompanyProfileV2Page;
