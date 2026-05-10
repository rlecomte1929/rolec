import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Link } from 'react-router-dom';
import { AdminFreshnessLayout } from './AdminFreshnessLayout';
import { adminFreshnessAPI } from '../../../api/client';

type StaleResource = {
  id?: string;
  title?: string;
  country_code?: string;
  city_name?: string;
  status?: string;
  updated_at?: string;
  stale_reason?: string;
  days_since_update?: number;
};

type StaleEvent = {
  id?: string;
  title?: string;
  country_code?: string;
  city_name?: string;
  start_datetime?: string;
  stale_reason?: string;
};

export const AdminFreshnessStaleContent: React.FC = () => {
  const [searchParams] = useSearchParams();
  const countryCode = searchParams.get('country') || undefined;
  const cityName = searchParams.get('city') || undefined;
  const [tab, setTab] = useState<'resources' | 'events'>('resources');

  const [resources, setResources] = useState<StaleResource[]>([]);
  const [events, setEvents] = useState<StaleEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      adminFreshnessAPI.getStaleResources({
        country_code: countryCode,
        city_name: cityName,
        limit: 100,
      }),
      adminFreshnessAPI.getStaleEvents({
        country_code: countryCode,
        city_name: cityName,
        limit: 100,
      }),
    ])
      .then(([rRes, eRes]) => {
        setResources(rRes.items ?? []);
        setEvents(eRes.items ?? []);
      })
      .catch((e) => setError((e as Error)?.message || 'Failed'))
      .finally(() => setLoading(false));
  }, [countryCode, cityName]);

  if (loading) {
    return (
      <AdminFreshnessLayout title="Stale content" subtitle="Live resources and events needing review">
        <div className="py-12 text-center text-slate-500">Loading...</div>
      </AdminFreshnessLayout>
    );
  }
  if (error) {
    return (
      <AdminFreshnessLayout title="Stale content" subtitle="Live resources and events needing review">
        <div className="rounded-lg bg-red-50 p-4 text-red-700">{error}</div>
      </AdminFreshnessLayout>
    );
  }

  return (
    <AdminFreshnessLayout title="Stale content" subtitle="Live resources and events needing review">
      <div className="mb-4 flex gap-2">
        <button
          onClick={() => setTab('resources')}
          className={`rounded px-3 py-1.5 text-sm ${tab === 'resources' ? 'bg-[#0b2b43] text-white' : 'bg-slate-200 text-slate-700'}`}
        >
          Resources ({resources.length})
        </button>
        <button
          onClick={() => setTab('events')}
          className={`rounded px-3 py-1.5 text-sm ${tab === 'events' ? 'bg-[#0b2b43] text-white' : 'bg-slate-200 text-slate-700'}`}
        >
          Events ({events.length})
        </button>
      </div>

      {tab === 'resources' && (
        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-left text-slate-600">
                <th className="px-4 py-2">Title</th>
                <th className="px-4 py-2">Country / City</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Last updated</th>
                <th className="px-4 py-2">Stale reason</th>
                <th className="px-4 py-2">Action</th>
              </tr>
            </thead>
            <tbody>
              {resources.map((r) => (
                <tr key={String(r.id)} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-2 font-medium">{r.title ?? '-'}</td>
                  <td className="px-4 py-2">{r.country_code ?? '-'} / {r.city_name ?? '-'}</td>
                  <td className="px-4 py-2">{r.status ?? '-'}</td>
                  <td className="px-4 py-2">
                    {r.updated_at ? new Date(r.updated_at).toLocaleDateString() : '-'}
                    {r.days_since_update != null && (
                      <span className="ml-1 text-slate-500">({r.days_since_update}d ago)</span>
                    )}
                  </td>
                  <td className="px-4 py-2">{r.stale_reason ?? 'old_updated_at'}</td>
                  <td className="px-4 py-2">
                    <Link to={`/admin/resources/${r.id}`} className="text-[#0b2b43] hover:underline">
                      Edit
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'events' && (
        <div className="overflow-x-auto rounded-lg border border-slate-200">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50 text-left text-slate-600">
                <th className="px-4 py-2">Title</th>
                <th className="px-4 py-2">Country / City</th>
                <th className="px-4 py-2">Start</th>
                <th className="px-4 py-2">Stale reason</th>
                <th className="px-4 py-2">Action</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={String(e.id)} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-2 font-medium">{e.title ?? '-'}</td>
                  <td className="px-4 py-2">{e.country_code ?? '-'} / {e.city_name ?? '-'}</td>
                  <td className="px-4 py-2">
                    {e.start_datetime ? new Date(e.start_datetime).toLocaleString() : '-'}
                  </td>
                  <td className="px-4 py-2">{e.stale_reason ?? 'event_expired'}</td>
                  <td className="px-4 py-2">
                    <Link to={`/admin/events/${e.id}`} className="text-[#0b2b43] hover:underline">
                      Edit
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'resources' && resources.length === 0 && (
        <div className="py-8 text-center text-slate-500">No stale resources</div>
      )}
      {tab === 'events' && events.length === 0 && (
        <div className="py-8 text-center text-slate-500">No stale events</div>
      )}
    </AdminFreshnessLayout>
  );
};
