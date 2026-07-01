import { useState, useEffect } from 'react';
import { PageHeader, Grid, Stack, StatCard, DataTable, Badge, BarChart, PieChart } from 'dashboard-blocks';
import { BarChart3, Eye, Mail, TrendingUp } from 'lucide-react';

interface TemplateProps {
  workspaceId: string;
  authToken?: string;
}

export function AnalyticsDashboard({ workspaceId, authToken }: TemplateProps) {
  const [summary, setSummary] = useState<any>(null);
  const [eventCounts, setEventCounts] = useState<any>({});
  const [dailyData, setDailyData] = useState<any[]>([]);
  const [recentEvents, setRecentEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const __dt = typeof localStorage !== 'undefined' ? localStorage.getItem('workspace_device_token') : null;
  const authHeaders: Record<string, string> = authToken ? { 'Authorization': 'Bearer ' + authToken } : __dt ? { 'x-device-token': __dt } : {};

  useEffect(() => {
    async function fetchData() {
      try {
        // Tiles read the unified /summary endpoint, which merges BOTH event
        // tables (funnel_events + analytics_events), aliases event-type names,
        // and dedupes visitors — the same source the standalone Analytics
        // window uses, so the two never disagree. The day chart / pie / table
        // come from the raw crm/events aggregations.
        const [summaryRes, byDayRes, byTypeRes, recentRes] = await Promise.all([
          fetch(`/api/analytics/${workspaceId}/summary`, { credentials: 'include', headers: authHeaders }),
          fetch(`/api/crm/events?workspaceId=${workspaceId}&aggregation=by_day&days=14&excludeType=scroll_depth`, { credentials: 'include', headers: authHeaders }),
          fetch(`/api/crm/events?workspaceId=${workspaceId}&aggregation=by_type&days=365&excludeType=scroll_depth`, { credentials: 'include', headers: authHeaders }),
          fetch(`/api/crm/events?workspaceId=${workspaceId}&limit=20&days=365`, { credentials: 'include', headers: authHeaders }),
        ]);

        const summaryJson = await summaryRes.json();
        setSummary(summaryJson.summary || null);

        const byTypeJson = await byTypeRes.json();
        const typeRows = Array.isArray(byTypeJson.data) ? byTypeJson.data : [];
        const counts: Record<string, number> = {};
        typeRows.forEach((r: any) => { counts[r.eventType] = Number(r.count) || 0; });
        setEventCounts(counts);

        const byDayJson = await byDayRes.json();
        const dayRows = Array.isArray(byDayJson.data) ? byDayJson.data : [];
        // by_day returns most-recent first; reverse to chronological and label
        // by real date so the chart no longer shows arbitrary weekday names.
        setDailyData(dayRows.slice().reverse().map((r: any) => ({
          label: new Date(r.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
          value: Number(r.count) || 0,
        })));

        const recentJson = await recentRes.json();
        const evts = (recentJson.data || recentJson.events || []).map((e: any) => ({
          ...e,
          eventType: e.eventType || e.type,
        }));
        setRecentEvents(evts);
      } catch (err) {
        console.error('Failed to fetch analytics:', err);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [workspaceId]);

  const s = summary || {};
  const totalEvents = (s.totalViews || 0) + (s.totalEmailClicks || 0) + (s.totalEmailCaptures || 0)
    + (s.totalAgentConversations || 0) + (s.totalPricingViews || 0) + (s.totalCheckoutStarts || 0);

  const pieData = Object.entries(eventCounts).map(([label, value]) => ({
    label,
    value: value as number
  }));

  return (
    <Stack>
      <PageHeader 
        title="Analytics Dashboard" 
        subtitle="Event tracking and funnel analysis"
      />
      
      <Grid cols={4}>
        <StatCard
          title="Total Events"
          value={totalEvents}
          icon={<BarChart3 className="w-5 h-5" />}
        />
        <StatCard 
          title="Page Views" 
          value={s.totalViews || 0}
          icon={<Eye className="w-5 h-5" />}
        />
        <StatCard 
          title="CTA Clicks" 
          value={s.totalEmailClicks || 0}
          icon={<TrendingUp className="w-5 h-5" />}
        />
        <StatCard 
          title="Email Submits" 
          value={s.totalEmailCaptures || 0}
          icon={<Mail className="w-5 h-5" />}
        />
      </Grid>

      <Grid cols={2}>
        <BarChart 
          title="Events by Day" 
          data={dailyData}
          color="#3b82f6"
        />
        <PieChart 
          title="Events by Type" 
          data={pieData}
        />
      </Grid>

      <DataTable
        title="Recent Events"
        data={recentEvents}
        columns={[
          { key: 'eventType', header: 'Event Type', render: (val: string) => <Badge variant="info">{val}</Badge> },
          { key: 'eventData', header: 'Details', render: (val: any) => {
            if (!val || typeof val !== 'object') return '-';
            const detail = val.source || val.page || val.email || val.path || '-';
            return String(detail);
          }},
          { key: 'createdAt', header: 'Time', render: (val: string) => {
            if (!val) return '-';
            const date = new Date(val);
            return isNaN(date.getTime()) ? '-' : date.toLocaleString();
          }}
        ]}
        pageSize={10}
        loading={loading}
        emptyMessage="No events tracked yet."
      />
    </Stack>
  );
}
