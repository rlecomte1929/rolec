import React, { useCallback, useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Card, Button } from '../../components/antigravity';
import { AdminLayout } from './AdminLayout';
import { StatusBadge } from '../../components/admin/resources/StatusBadge';
import { ResourceRowActions } from '../../components/admin/resources/ResourceRowActions';
import { adminResourcesAPI } from '../../api/client';
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
  is_family_friendly?: boolean;
  is_visible_to_end_users?: boolean;
  updated_at?: string;
  updated_by_user_id?: string;
  trust_tier?: string;
};

export const AdminResources: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [tab, setTab] = useState<'resources' | 'events' | 'taxonomy'>(() => {
    const t = searchParams.get('tab');
    return (t === 'events' || t === 'taxonomy' ? t : 'resources') as 'resources' | 'events' | 'taxonomy';
  });
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [resources, setResources] = useState<ResourceItem[]>([]);
  const [categories, setCategories] = useState<{ id: string; key: string; label: string }[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const role = getAuthItem('relopass_role');
  const [filters, setFilters] = useState({
    country_code: searchParams.get('country') || '',
    city: searchParams.get('city') || '',
    category_id: searchParams.get('category') || '',
    status: searchParams.get('status') || '',
    audience: searchParams.get('audience') || '',
    featured: searchParams.get('featured') || '',
    family_friendly: searchParams.get('family_friendly') || '',
    search: searchParams.get('search') || '',
  });

  const loadCounts = async () => {
    if (role !== 'ADMIN') return;
    try {
      const c = await adminResourcesAPI.getCounts();
      setCounts(c);
    } catch {
      setCounts({});
    }
  };

  const loadResources = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminResourcesAPI.listResources({
        country_code: filters.country_code || undefined,
        city: filters.city || undefined,
        category_id: filters.category_id || undefined,
        status: filters.status || undefined,
        audience: filters.audience || undefined,
        featured: filters.featured === 'true' ? true : filters.featured === 'false' ? false : undefined,
        family_friendly: filters.family_friendly === 'true' ? true : filters.family_friendly === 'false' ? false : undefined,
        search: filters.search || undefined,
        limit: 50,
      });
      setResources(res.items || []);
      setTotal(res.total ?? 0);
    } catch {
      setResources([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const loadCategories = useCallback(async () => {
    try {
      const res = await adminResourcesAPI.listCategories();
      setCategories(res.categories || []);
    } catch {
      setCategories([]);
    }
  }, []);

  const handleResourceAction = useCallback(async (id: string, action: string, notes?: string) => {
    try {
      switch (action) {
        case 'submit':
          await adminResourcesAPI.submitForReview(id);
          break;
        case 'approve':
          await adminResourcesAPI.approveResource(id, notes);
          break;
        case 'publish':
          await adminResourcesAPI.publishResource(id);
          break;
        case 'unpublish':
          await adminResourcesAPI.unpublishResource(id);
          break;
        case 'archive':
          await adminResourcesAPI.archiveResource(id);
          break;
        case 'restore':
          await adminResourcesAPI.restoreResource(id);
          break;
        default:
          return;
      }
      loadCounts();
      loadResources();
    } catch (e) {
      alert((e as Error)?.message || 'Action failed');
      throw e;
    }
  }, []);

  useEffect(() => {
    loadCounts();
    loadCategories();
  }, [role]);

  useEffect(() => {
    if (tab === 'resources') loadResources();
  }, [tab, loadResources]);

  if (role !== 'ADMIN') {
    return (
      <AdminLayout title="Resources CMS" subtitle="Restricted">
        <Card padding="lg">
          You do not have access to the Resources CMS. Admin only.
        </Card>
      </AdminLayout>
    );
  }

  const categoryLabel = (cid?: string) =>
    categories.find((c) => c.id === cid)?.label || cid || '—';

  return (
    <AdminLayout title="Resources CMS" subtitle="Manage country resources, events, and taxonomy">
      <div className="mb-4 grid grid-cols-2 md:grid-cols-5 gap-3">
        <Card padding="md" className="bg-slate-50">
          <div className="text-xs text-slate-500">Resources – Draft</div>
          <div className="text-xl font-semibold">{counts.resources_draft ?? 0}</div>
        </Card>
        <Card padding="md" className="bg-amber-50">
          <div className="text-xs text-amber-700">Resources – In Review</div>
          <div className="text-xl font-semibold">{counts.resources_in_review ?? 0}</div>
        </Card>
        <Card padding="md" className="bg-green-50">
          <div className="text-xs text-green-700">Resources – Published</div>
          <div className="text-xl font-semibold">{counts.resources_published ?? 0}</div>
        </Card>
        <Card padding="md" className="bg-slate-100">
          <div className="text-xs text-slate-600">Resources – Archived</div>
          <div className="text-xl font-semibold">{counts.resources_archived ?? 0}</div>
        </Card>
        <Card padding="md" className="bg-blue-50">
          <div className="text-xs text-blue-700">Events – Published</div>
          <div className="text-xl font-semibold">{counts.events_published ?? 0}</div>
        </Card>
      </div>

      <div className="flex gap-2 mb-4 border-b border-slate-200">
        <button
          type="button"
          onClick={() => setTab('resources')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
            tab === 'resources'
              ? 'border-[#0b2b43] text-[#0b2b43]'
              : 'border-transparent text-slate-600 hover:text-[#0b2b43]'
          }`}
        >
          Resources
        </button>
        <button
          type="button"
          onClick={() => setTab('events')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
            tab === 'events'
              ? 'border-[#0b2b43] text-[#0b2b43]'
              : 'border-transparent text-slate-600 hover:text-[#0b2b43]'
          }`}
        >
          Events
        </button>
        <button
          type="button"
          onClick={() => setTab('taxonomy')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
            tab === 'taxonomy'
              ? 'border-[#0b2b43] text-[#0b2b43]'
              : 'border-transparent text-slate-600 hover:text-[#0b2b43]'
          }`}
        >
          Taxonomy
        </button>
      </div>

      {tab === 'resources' && (
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
            <input
              value={filters.city}
              onChange={(e) => setFilters((f) => ({ ...f, city: e.target.value }))}
              placeholder="City"
              className="rounded border border-slate-200 px-3 py-2 text-sm w-32"
            />
            <select
              value={filters.category_id}
              onChange={(e) => setFilters((f) => ({ ...f, category_id: e.target.value }))}
              className="rounded border border-slate-200 px-3 py-2 text-sm"
            >
              <option value="">Category</option>
              {[...categories].sort((a, b) => (a.label || '').localeCompare(b.label || '')).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
            <select
              value={filters.status}
              onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}
              className="rounded border border-slate-200 px-3 py-2 text-sm"
            >
              <option value="">All statuses</option>
              <option value="approved">Approved</option>
              <option value="archived">Archived</option>
              <option value="draft">Draft</option>
              <option value="in_review">In Review</option>
              <option value="published">Published</option>
            </select>
            <select
              value={filters.audience}
              onChange={(e) => setFilters((f) => ({ ...f, audience: e.target.value }))}
              className="rounded border border-slate-200 px-3 py-2 text-sm"
            >
              <option value="">Audience</option>
              <option value="all">All</option>
              <option value="couple">Couple</option>
              <option value="family">Family</option>
              <option value="single">Single</option>
            </select>
            <select
              value={filters.featured}
              onChange={(e) => setFilters((f) => ({ ...f, featured: e.target.value }))}
              className="rounded border border-slate-200 px-3 py-2 text-sm"
            >
              <option value="">Featured</option>
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
            <select
              value={filters.family_friendly}
              onChange={(e) => setFilters((f) => ({ ...f, family_friendly: e.target.value }))}
              className="rounded border border-slate-200 px-3 py-2 text-sm"
            >
              <option value="">Family friendly</option>
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
            <Button onClick={() => loadResources()} disabled={loading}>
              {loading ? 'Loading…' : 'Apply'}
            </Button>
            <Link to={buildRoute('adminResourcesNew')}>
              <Button variant="primary">New Resource</Button>
            </Link>
          </div>
          <div className="text-sm text-slate-500 mb-2">
            {total} resource{total !== 1 ? 's' : ''}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200">
                  <th className="text-left py-2">Title</th>
                  <th className="text-left py-2">Country</th>
                  <th className="text-left py-2">City</th>
                  <th className="text-left py-2">Category</th>
                  <th className="text-left py-2">Audience</th>
                  <th className="text-left py-2">Status</th>
                  <th className="text-left py-2">Visible</th>
                  <th className="text-left py-2">Featured</th>
                  <th className="text-left py-2">Updated</th>
                  <th className="text-left py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {resources.map((r) => (
                  <tr key={r.id} className="border-b border-slate-100">
                    <td className="py-2">
                      <Link
                        to={buildRoute('adminResourcesEdit', { id: r.id })}
                        className="text-[#0b2b43] hover:underline font-medium"
                      >
                        {r.title || 'Untitled'}
                      </Link>
                    </td>
                    <td className="py-2">{r.country_code || '—'}</td>
                    <td className="py-2">{r.city_name || '—'}</td>
                    <td className="py-2">{categoryLabel(r.category_id)}</td>
                    <td className="py-2">{r.audience_type || '—'}</td>
                    <td className="py-2">
                      <StatusBadge status={r.status} />
                    </td>
                    <td className="py-2">{r.is_visible_to_end_users ? 'Yes' : 'No'}</td>
                    <td className="py-2">{r.is_featured ? 'Yes' : 'No'}</td>
                    <td className="py-2 text-slate-500">
                      {r.updated_at ? new Date(r.updated_at).toLocaleDateString() : '—'}
                    </td>
                    <td className="py-2">
                      <ResourceRowActions
                        resourceId={r.id}
                        status={r.status}
                        onAction={(action, notes) => handleResourceAction(r.id, action, notes)}
                        disabled={loading}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {resources.length === 0 && !loading && (
            <div className="py-8 text-center text-slate-500">No resources found.</div>
          )}
        </Card>
      )}

      {tab === 'events' && (
        <Card padding="lg">
          <div className="flex justify-between items-center mb-4">
            <div>Events management</div>
            <Link to="/admin/events/new">
              <Button variant="primary">New Event</Button>
            </Link>
          </div>
          <p className="text-sm text-slate-600">
            <Link to="/admin/events" className="text-[#0b2b43] hover:underline">
              Open Events list →
            </Link>
          </p>
        </Card>
      )}

      {tab === 'taxonomy' && (
        <Card padding="lg">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Link
              to={buildRoute('adminCategories')}
              className="p-4 rounded-lg border border-slate-200 hover:border-[#0b2b43] hover:bg-slate-50 transition"
            >
              <div className="font-medium text-[#0b2b43]">Categories</div>
              <div className="text-sm text-slate-600">Manage resource categories</div>
            </Link>
            <Link
              to={buildRoute('adminTags')}
              className="p-4 rounded-lg border border-slate-200 hover:border-[#0b2b43] hover:bg-slate-50 transition"
            >
              <div className="font-medium text-[#0b2b43]">Tags</div>
              <div className="text-sm text-slate-600">Manage resource tags</div>
            </Link>
            <Link
              to={buildRoute('adminSources')}
              className="p-4 rounded-lg border border-slate-200 hover:border-[#0b2b43] hover:bg-slate-50 transition"
            >
              <div className="font-medium text-[#0b2b43]">Sources</div>
              <div className="text-sm text-slate-600">Manage source records</div>
            </Link>
          </div>
        </Card>
      )}
    </AdminLayout>
  );
};
