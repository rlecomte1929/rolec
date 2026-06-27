import { hrAPI } from '../../../api/client';
import type { CompanyProfilePayload } from '../../../types';
import { useHrCompanyContext } from '../../../contexts/HrCompanyContext';
import { PlatformShellSidebar } from '../../../components/PlatformShellSidebar';
import { CompanyBrand } from '../../../components/CompanyBrand';
import { CompanyProfileForm } from './CompanyProfileForm';

/**
 * HR's own-company profile page. Data comes from useHrCompanyContext
 * (session-scoped), persistence goes through hrAPI.saveCompanyProfile +
 * hrAPI.{upload,remove}CompanyLogo. The shared CompanyProfileForm handles
 * everything else (sections, dirty tracking, sticky save bar).
 *
 * Layout uses PlatformShellSidebar (the canonical sidebar) with role='HR'
 * so the nav items, badges, and labels are always in sync with the rest of
 * the HR shell. The old PlatformSidebar (v2-preview) has been retired here.
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
      <PlatformShellSidebar persona="HR" companySlot={<CompanyBrand />} />
      <main className="flex-1 overflow-y-auto">
        <CompanyProfileForm
          company={company}
          loading={loading}
          loadError={error}
          onSave={handleSave}
          onUploadLogo={handleUploadLogo}
          onRemoveLogo={handleRemoveLogo}
          showBreadcrumb
          title="Company profile"
          subtitle="How your company appears to employees, providers, and relocation partners on ReloPass. Changes are saved to your company account."
        />
      </main>
    </div>
  );
}

export default CompanyProfileV2Page;
