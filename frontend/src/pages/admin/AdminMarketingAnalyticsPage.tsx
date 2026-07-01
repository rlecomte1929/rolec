import React, { useEffect, useState } from 'react';
import { Card } from '../../components/antigravity';
import { adminMarketingAnalyticsAPI, type MarketingFunnel } from '../../api/client';
import { AdminLayout } from './AdminLayout';
import { MetricTimeSeriesChart } from './MetricTimeSeriesChart';

const ACCENT = '#1f8e8b';

export const AdminMarketingAnalyticsPage: React.FC = () => {
  const [data, setData] = useState<MarketingFunnel | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    adminMarketingAnalyticsAPI
      .funnel(30)
      .then(setData)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : 'Failed to load'));
  }, []);

  const points = (data?.daily || []).map((d) => ({
    date: d.date,
    aggregate: d.landing_cta_click,
    passes_threshold: true,
  }));

  return (
    <AdminLayout title="Marketing Analytics" subtitle="Pre-signup acquisition funnel (last 30 days)">
      {error && <Card><p className="text-[#b91c1c] text-sm">{error}</p></Card>}
      {data && (
        <>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <Card><div className="text-xs text-[#6b7280]">Landing views</div>
              <div className="text-2xl font-semibold text-[#0b2b43]">{data.events.landing_page_view}</div></Card>
            <Card><div className="text-xs text-[#6b7280]">CTA clicks · {data.rates.cta_rate_pct}%</div>
              <div className="text-2xl font-semibold text-[#0b2b43]">{data.events.landing_cta_click}</div></Card>
            <Card><div className="text-xs text-[#6b7280]">Leads captured · {data.rates.capture_rate_pct}%</div>
              <div className="text-2xl font-semibold text-[#0b2b43]">{data.events.lead_captured}</div></Card>
          </div>
          <Card>
            <MetricTimeSeriesChart points={points} threshold={0} color={ACCENT} label="CTA clicks / day" />
          </Card>
        </>
      )}
    </AdminLayout>
  );
};
