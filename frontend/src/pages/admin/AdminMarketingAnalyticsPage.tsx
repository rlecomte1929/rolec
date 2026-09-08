import React, { useEffect, useState } from 'react';
import { Card } from '../../components/antigravity';
import { adminMarketingAnalyticsAPI, type MarketingFunnel } from '../../api/client';
import { AdminLayout } from './AdminLayout';

export const AdminMarketingAnalyticsPage: React.FC = () => {
  const [data, setData] = useState<MarketingFunnel | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    adminMarketingAnalyticsAPI
      .funnel(30)
      .then(setData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Failed to load'));
  }, []);

  return (
    <AdminLayout title="Marketing analytics" subtitle="Pre-signup acquisition funnel (last 30 days)">
      {error && (
        <Card>
          <p className="text-[#b91c1c] text-sm">{error}</p>
        </Card>
      )}
      {data && (
        <>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <Card>
              <div className="text-xs text-[#6b7280]">Landing views</div>
              <div className="text-2xl font-semibold text-[#0b2b43]">{data.events.landing_page_view}</div>
            </Card>
            <Card>
              <div className="text-xs text-[#6b7280]">CTA clicks · {data.rates.cta_rate_pct}%</div>
              <div className="text-2xl font-semibold text-[#0b2b43]">{data.events.landing_cta_click}</div>
            </Card>
            <Card>
              <div className="text-xs text-[#6b7280]">Leads captured · {data.rates.capture_rate_pct}%</div>
              <div className="text-2xl font-semibold text-[#0b2b43]">{data.events.lead_captured}</div>
            </Card>
          </div>
          <Card>
            <div className="text-sm font-medium text-[#0b2b43] mb-2">Daily breakdown</div>
            {data.daily.length === 0 ? (
              <p className="text-sm text-[#6b7280] py-4 text-center">No funnel events in the last 30 days yet.</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[#6b7280] border-b border-[#e5e7eb]">
                    <th className="py-2 pr-3">Date</th>
                    <th className="py-2 pr-3 text-right">Views</th>
                    <th className="py-2 pr-3 text-right">CTA clicks</th>
                    <th className="py-2 text-right">Leads</th>
                  </tr>
                </thead>
                <tbody>
                  {data.daily.map((d) => (
                    <tr key={d.date} className="border-b border-[#f3f4f6]">
                      <td className="py-2 pr-3 font-mono text-[#374151]">{d.date}</td>
                      <td className="py-2 pr-3 text-right">{d.landing_page_view}</td>
                      <td className="py-2 pr-3 text-right">{d.landing_cta_click}</td>
                      <td className="py-2 text-right">{d.lead_captured}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </>
      )}
    </AdminLayout>
  );
};
