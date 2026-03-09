import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, Button } from '../../components/antigravity';
import { AdminLayout } from './AdminLayout';
import { StatusBadge } from '../../components/admin/resources/StatusBadge';
import { EventRowActions } from '../../components/admin/resources/EventRowActions';
import { adminResourcesAPI } from '../../api/client';
import { buildRoute } from '../../navigation/routes';
import { getAuthItem } from '../../utils/demo';

const EVENT_TYPES = ['cinema', 'concert', 'festival', 'sports', 'family_activity', 'networking', 'museum', 'theater'];

type EventItem = {
  id: string;
  title: string;
  country_code?: string;
  city_name?: string;
  event_type?: string;
  status?: string;
  start_datetime?: string;
  is_family_friendly?: boolean;
  is_free?: boolean;
  updated_at?: string;
};

export const AdminEvents: React.FC = () => {
  const [events, setEvents] = useState<EventItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({
    country_code: '',
    city: '',
    status: '',
    event_type: '',
    family_friendly: '',
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await adminResourcesAPI.listEvents({
        country_code: filters.country_code || undefined,
        city: filters.city || undefined,
        status: filters.status || undefined,
        event_type: filters.event_type || undefined,
        family_friendly: filters.family_friendly === 'true' ? true : filters.family_friendly === 'false' ? false : undefined,
        limit: 50,
      });
      setEvents(res.items || []);
      setTotal(res.total ?? 0);
    } catch {
      setEvents([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const handleEventAction = useCallback(async (eventId: string, action: string, notes?: string) => {
    try {
      switch (action) {
        case 'submit':
          await adminResourcesAPI.submitEventForReview(eventId);
          break;
        case 'approve':
          await adminResourcesAPI.approveEvent(eventId, notes);
          break;
        case 'publish':
          await adminResourcesAPI.publishEvent(eventId);
          break;
        case 'unpublish':
          await adminResourcesAPI.unpublishEvent(eventId);
          break;
        case 'archive':
          await adminResourcesAPI.archiveEvent(eventId);
          break;
        case 'restore':
          await adminResourcesAPI.restoreEvent(eventId);
          break;
        default:
          return;
      }
      load();
    } catch (e) {
      alert((e as Error)?.message || 'Action failed');
      throw e;
    }
  }, [load]);

  useEffect(() => {
    load();
  }, [load]);

  const role = getAuthItem('relopass_role');
  if (role !== 'ADMIN') {
    return (
      <AdminLayout title="Events" subtitle="Restricted">
        <div className="py-8 text-center text-slate-500">Admin only.</div>
      </AdminLayout>
    );
  }

  return (
    <AdminLayout title="Events" subtitle="Manage country events">
      <div className="flex flex-wrap gap-2 mb-4">
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
        <select value={filters.event_type} onChange={(e) => setFilters((f) => ({ ...f, event_type: e.target.value }))} className="rounded border border-slate-200 px-3 py-2 text-sm">
          <option value="">Event type</option>
          {EVENT_TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <select value={filters.status} onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))} className="rounded border border-slate-200 px-3 py-2 text-sm">
          <option value="">All statuses</option>
          <option value="draft">Draft</option>
          <option value="in_review">In Review</option>
          <option value="approved">Approved</option>
          <option value="published">Published</option>
          <option value="archived">Archived</option>
        </select>
        <select value={filters.family_friendly} onChange={(e) => setFilters((f) => ({ ...f, family_friendly: e.target.value }))} className="rounded border border-slate-200 px-3 py-2 text-sm">
          <option value="">Family friendly</option>
          <option value="true">Yes</option>
          <option value="false">No</option>
        </select>
        <Button onClick={() => load()} disabled={loading}>
          {loading ? 'Loading…' : 'Apply'}
        </Button>
        <Link to="/admin/events/new">
          <Button variant="primary">New Event</Button>
        </Link>
      </div>

      <Card padding="lg">
        <div className="text-sm text-slate-500 mb-2">{total} event{total !== 1 ? 's' : ''}</div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200">
                  <th className="text-left py-2">Title</th>
                  <th className="text-left py-2">Type</th>
                  <th className="text-left py-2">Country</th>
                  <th className="text-left py-2">City</th>
                  <th className="text-left py-2">Start</th>
                  <th className="text-left py-2">Free</th>
                  <th className="text-left py-2">Family</th>
                  <th className="text-left py-2">Status</th>
                  <th className="text-left py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {events.map((e) => (
                  <tr key={e.id} className="border-b border-slate-100">
                    <td className="py-2">
                      <Link to={buildRoute('adminEventsEdit', { id: e.id })} className="text-[#0b2b43] hover:underline font-medium">
                        {e.title || 'Untitled'}
                      </Link>
                    </td>
                    <td className="py-2">{e.event_type || '—'}</td>
                    <td className="py-2">{e.country_code || '—'}</td>
                    <td className="py-2">{e.city_name || '—'}</td>
                    <td className="py-2 text-slate-500">
                      {e.start_datetime ? new Date(e.start_datetime).toLocaleString() : '—'}
                    </td>
                    <td className="py-2">{e.is_free ? 'Yes' : 'No'}</td>
                    <td className="py-2">{e.is_family_friendly ? 'Yes' : 'No'}</td>
                    <td className="py-2">
                      <StatusBadge status={e.status} />
                    </td>
                    <td className="py-2">
                      <EventRowActions
                        eventId={e.id}
                        status={e.status}
                        onAction={(action, notes) => handleEventAction(e.id, action, notes)}
                        disabled={loading}
                      />
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        {events.length === 0 && !loading && (
          <div className="py-8 text-center text-slate-500">No events found.</div>
        )}
      </Card>
    </AdminLayout>
  );
};
