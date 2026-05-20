import { AppShell } from '../../../components/AppShell';
import { hrAPI } from '../../../api/client';
import type { CompanyProfilePayload } from '../../../types';
import { useHrCompanyContext } from '../../../contexts/HrCompanyContext';
import { CompanyProfileForm } from './CompanyProfileForm';

/**
 * HR's own-company profile page. Data comes from useHrCompanyContext
 * (session-scoped), persistence goes through hrAPI.saveCompanyProfile +
 * hrAPI.{upload,remove}CompanyLogo. The shared CompanyProfileForm handles
 * everything else (sections, dirty tracking, sticky save bar).
 *
 * Sibling admin route /admin/companies/:companyId/profile mounts the same
 * form with admin-API handlers — see AdminCompanyProfilePage.
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
    <AppShell>
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
        badge="v2 preview"
      />
    </AppShell>
  );
}

export default CompanyProfileV2Page;
