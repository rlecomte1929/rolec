import React, { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Card, Button } from '../../components/antigravity';
import { AdminLayout } from './AdminLayout';
import { StatusBadge } from '../../components/admin/resources/StatusBadge';
import { ResourceRowActions } from '../../components/admin/resources/ResourceRowActions';
import { adminResourcesAPI, adminStagingAPI } from '../../api/client';
import { buildRoute } from '../../navigation/routes';
import { getAuthItem } from '../../utils/demo';

type ResourceItem = {
  id: string;
  title: string;
  country_code?: string;
  city_name?: string;
  category_id?: string;
  audience_type?: string;
  status?: string;
  is_featured?: boolean;
  is_visible_to_end_users?: boolean;
  updated_at?: string;
};

export const AdminResources: React.FC = () => {
  const [searchParams] = useSearchParams();
  const view = searchParams.get('view') || 'overview';
  const role = getAuthItem('relopass_role');
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [stagingCounts, setStagingCounts] = useState<{ resource_candidates_new?: number; event_candidates_new?: number } | null>(null);
  const [resources, setResources] = useState<ResourceItem[]>([]);
  const [categories, setCategories] = useState<{ id: string; key: string; label: string }[]>([]);
  const [listTotal, setListTotal] = useState(0);
  const [listLoading, setListLoading] = useState(false);
  const [filters, setFilters] = useState({
    country_code: '',
    category_id: '',
    status: '',
    search: '',
  });

  const load = useCallback(async () => {
    if (role !== 'ADMIN') return;
    try {
      const [c, s, cat] = await Promise.all([
        adminResourcesAPI.getCounts(),
        adminStagingAPI.getDashboard().catch(() => null),
        adminResourcesAPI.listCategories().catch(() => ({ categories: [] })),
      ]);
      setCounts(c || {});
      setStagingCounts(s || null);
      setCategories(cat?.categories || []);
    } catch {
      setCounts({});
      setStagingCounts(null);
      setCategories([]);
    }
  }, [role]);

  const loadResources = useCallback(async () => {
    setListLoading(true);
    try {
      const res = await adminResourcesAPI.listResources({
        country_code: filters.country_code || undefined,
        category_id: filters.category_id || undefined,
        status: filters.status || undefined,
        search: filters.search || undefined,
        limit: 50,
      });
      setResources(res.items || []);
      setListTotal(res.total ?? 0);
    } catch {
      setResources([]);
      setListTotal(0);
    } finally {
      setListLoading(false);
    }
  }, [filters]);

  const handleResourceAction = useCallback(async (id: string, action: string, notes?: string) => {
    try {
      switch (action) {
        case 'submit': await adminResourcesAPI.submitForReview(id); break;
        case 'approve': await adminResourcesAPI.approveResource(id, notes); break;
        case 'publish': await adminResourcesAPI.publishResource(id); break;
        case 'unpublish': await adminResourcesAPI.unpublishResource(id); break;
        case 'archive': await adminResourcesAPI.archiveResource(id); break;
        case 'restore': await adminResourcesAPI.restoreResource(id); break;
        default: return;
      }
      load();
      loadResources();
    } catch (e) {
      alert((e as Error)?.message || 'Action failed');
      throw e;
    }
  }, [load, loadResources]);

  useEffect(() => {
    if (view === 'list') loadResources();
  }, [view, loadResources]);

  useEffect(() => {
    load();
  }, [load]);

  if (role !== 'ADMIN') {
    return (
      <AdminLayout title="Resources" subtitle="Restricted">
        <Card padding="lg">You do not have access to the Resources CMS. Admin only.</Card>
      </AdminLayout>
    );
  }

  const published = counts.resources_published ?? 0;
  const eventsPublished = counts.events_published ?? 0;
  const draft = counts.resources_draft ?? 0;
  const inReview = counts.resources_in_review ?? 0;
  const archived = counts.resources_archived ?? 0;

  const categoryLabel = (cid?: string) => categories.find((c) => c.id === cid)?.label || cid || '-';

  if (view === 'list') {
    return (
      <AdminLayout title="Resources" subtitle="Country content: housing, schools, movers, events">
        <div className="mb-4">
          <Link to={buildRoute('adminResources')} className="text-sm text-[#0b2b43] hover:underline">← Back to Resources</Link>
        </div>
        <Card padding="lg">
          <div className="flex flex-wrap gap-2 mb-4">
            <input
              value={filters.search}
              onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value }))}
              placeholder="Search title"
              className="rounded border border-slate-200 px-3 py-2 text-sm w-48"
            />
            <input
              value={filters.country_code}
              onChange={(e) => setFilters((f) => ({ ...f, country_code: e.target.value }))}
              placeholder="Country"
              className="rounded border border-slate-200 px-3 py-2 text-sm w-24"
            />
            <select
              value={filters.category_id}
              onChange={(e) => setFilters((f) => ({ ...f, category_id: e.target.value }))}
              className="rounded border border-slate-200 px-3 py-2 text-sm"
            >
              <option value="">Category</option>
              {categories.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
            </select>
            <select
              value={filters.status}
              onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}
              className="rounded border border-slate-200 px-3 py-2 text-sm"
            >
              <option value="">All statuses</option>
              <option value="draft">Draft</option>
              <option value="in_review">In Review</option>
              <option value="approved">Approved</option>
              <option value="published">Published</option>
              <option value="archived">Archived</option>
            </select>
            <Button onClick={loadResources} disabled={listLoading}>{listLoading ? 'Loading…' : 'Apply'}</Button>
            <Link to={buildRoute('adminResourcesNew')}><Button>New Resource</Button></Link>
          </div>
          <div className="text-sm text-slate-500 mb-2">{listTotal} resource{listTotal !== 1 ? 's' : ''}</div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200">
                  <th className="text-left py-2">Title</th>
                  <th className="text-left py-2">Country</th>
                  <th className="text-left py-2">City</th>
                  <th className="text-left py-2">Category</th>
                  <th className="text-left py-2">Status</th>
                  <th className="text-left py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {resources.map((r) => (
                  <tr key={r.id} className="border-b border-slate-100">
                    <td className="py-2">
                      <Link to={buildRoute('adminResourcesEdit', { id: r.id })} className="text-[#0b2b43] hover:underline font-medium">
                        {r.title || 'Untitled'}
                      </Link>
                    </td>
                    <td className="py-2">{r.country_code || '-'}</td>
                    <td className="py-2">{(r as { city_name?: string }).city_name || '-'}</td>
                    <td className="py-2">{categoryLabel(r.category_id)}</td>
                    <td className="py-2"><StatusBadge status={r.status} /></td>
                    <td className="py-2">
                      <ResourceRowActions resourceId={r.id} status={r.status} onAction={(a, n) => handleResourceAction(r.id, a, n)} disabled={listLoading} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {resources.length === 0 && !listLoading && <div className="py-8 text-center text-slate-500">No resources found.</div>}
        </Card>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout title="Resources" subtitle="Country content: housing, schools, movers, events">
      <div className="space-y-6">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <Card padding="md" className="bg-green-50">
            <div className="text-xs text-green-700">Resources – Published</div>
            <div className="text-xl font-semibold text-green-900">{published}</div>
          </Card>
          <Card padding="md" className="bg-blue-50">
            <div className="text-xs text-blue-700">Events – Published</div>
            <div className="text-xl font-semibold text-blue-900">{eventsPublished}</div>
          </Card>
          <Card padding="md" className="bg-slate-50">
            <div className="text-xs text-slate-600">Resources – Draft</div>
            <div className="text-xl font-semibold text-slate-800">{draft}</div>
          </Card>
          <Card padding="md" className="bg-amber-50">
            <div className="text-xs text-amber-700">Resources – In Review</div>
            <div className="text-xl font-semibold text-amber-900">{inReview}</div>
          </Card>
          <Card padding="md" className="bg-slate-100">
            <div className="text-xs text-slate-600">Resources – Archived</div>
            <div className="text-xl font-semibold text-slate-800">{archived}</div>
          </Card>
        </div>

        <Card padding="lg">
          <h2 className="text-lg font-semibold text-[#0b2b43] mb-4">Manage content</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Link
              to={buildRoute('adminResources') + '?view=list'}
              className="flex flex-col gap-1 p-4 rounded-lg border border-slate-200 hover:border-[#0b2b43]/40 transition"
            >
              <span className="font-medium text-[#0b2b43]">Resources</span>
              <span className="text-sm text-[#6b7280]">Manage country resources (housing, schools, movers, etc.)</span>
            </Link>
            <Link
              to={buildRoute('adminEvents')}
              className="flex flex-col gap-1 p-4 rounded-lg border border-slate-200 hover:border-[#0b2b43]/40 transition"
            >
              <span className="font-medium text-[#0b2b43]">Events</span>
              <span className="text-sm text-[#6b7280]">Manage events by country and city</span>
            </Link>
            <Link
              to={buildRoute('adminCategories')}
              className="flex flex-col gap-1 p-4 rounded-lg border border-slate-200 hover:border-[#0b2b43]/40 transition"
            >
              <span className="font-medium text-[#0b2b43]">Categories</span>
              <span className="text-sm text-[#6b7280]">Resource categories and taxonomy</span>
            </Link>
            <Link
              to={buildRoute('adminTags')}
              className="flex flex-col gap-1 p-4 rounded-lg border border-slate-200 hover:border-[#0b2b43]/40 transition"
            >
              <span className="font-medium text-[#0b2b43]">Tags</span>
              <span className="text-sm text-[#6b7280]">Resource tags and tag groups</span>
            </Link>
            <Link
              to={buildRoute('adminSources')}
              className="flex flex-col gap-1 p-4 rounded-lg border border-slate-200 hover:border-[#0b2b43]/40 transition"
            >
              <span className="font-medium text-[#0b2b43]">Sources</span>
              <span className="text-sm text-[#6b7280]">Source records and attribution</span>
            </Link>
          </div>
        </Card>

        <Card padding="lg" className="border-slate-200 bg-slate-50/50">
          <h2 className="text-lg font-semibold text-[#0b2b43] mb-4">Operations</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Link
              to={buildRoute('adminStagingDashboard')}
              className="flex flex-col gap-1 p-4 rounded-lg border border-slate-200 bg-white hover:border-[#0b2b43]/40 transition"
            >
              <span className="font-medium text-[#0b2b43]">Staging review</span>
              <span className="text-sm text-[#6b7280]">
                Review crawl candidates before promotion. {stagingCounts ? (
                  <>{(stagingCounts.resource_candidates_new ?? 0) + (stagingCounts.event_candidates_new ?? 0)} pending</>
                ) : (
                  'Crawl pipeline → staged candidates → live resources'
                )}
              </span>
            </Link>
            <Link
              to={buildRoute('adminFreshness')}
              className="flex flex-col gap-1 p-4 rounded-lg border border-slate-200 bg-white hover:border-[#0b2b43]/40 transition"
            >
              <span className="font-medium text-[#0b2b43]">Freshness</span>
              <span className="text-sm text-[#6b7280]">
                Monitor content freshness, crawl schedules, and stale alerts
              </span>
            </Link>
            <Link
              to={buildRoute('adminReviewQueue')}
              className="flex flex-col gap-1 p-4 rounded-lg border border-slate-200 bg-white hover:border-[#0b2b43]/40 transition"
            >
              <span className="font-medium text-[#0b2b43]">Review queue</span>
              <span className="text-sm text-[#6b7280]">
                Operational queue for staged candidates and change events
              </span>
            </Link>
          </div>
        </Card>
      </div>
    </AdminLayout>
  );
};
