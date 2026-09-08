import { AdminLayout } from '../../../pages/admin/AdminLayout';
import { CompaniesV2 } from './CompaniesV2';
import { useCompaniesV2 } from './useCompaniesV2';

/**
 * Page wrapper that mounts CompaniesV2 inside the existing AdminLayout
 * shell (sidebar + topbar) and feeds it real data through useCompaniesV2.
 *
 * Routed at /admin/companies-v2 (sibling to legacy /admin/companies) in
 * step 7 of the per-screen recipe. After promotion (step 9) this is the
 * component rendered by V2Gate on /admin/companies when the flag is on.
 */
export function CompaniesV2Page() {
  const { companies, loading, error, refresh } = useCompaniesV2();

  return (
    <AdminLayout>
      <CompaniesV2
        companies={companies}
        loading={loading}
        error={error}
        onRefresh={() => {
          void refresh();
        }}
      />
    </AdminLayout>
  );
}

export default CompaniesV2Page;
