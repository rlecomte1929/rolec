import { useState, useEffect } from 'react';
import { PageHeader, Grid, Stack, StatCard, DataTable, Badge } from 'dashboard-blocks';
import { Users, BarChart3, Mail, TrendingUp } from 'lucide-react';

interface TemplateProps {
  workspaceId: string;
  authToken?: string;
}

export function CRMDashboard({ workspaceId, authToken }: TemplateProps) {
  const [contacts, setContacts] = useState<any[]>([]);
  const [stats, setStats] = useState({ total: 0, thisWeek: 0, withEmail: 0, avgEvents: 0 });
  const [loading, setLoading] = useState(true);
  const __dt = typeof localStorage !== 'undefined' ? localStorage.getItem('workspace_device_token') : null;
  const authHeaders: Record<string, string> = authToken ? { 'Authorization': 'Bearer ' + authToken } : __dt ? { 'x-device-token': __dt } : {};

  useEffect(() => {
    async function fetchData() {
      try {
        const [contactsRes, eventsRes] = await Promise.all([
          fetch(`/api/crm/contacts/${workspaceId}?limit=100`, { credentials: 'include', headers: authHeaders }),
          fetch(`/api/crm/events?workspaceId=${workspaceId}&days=30&aggregation=summary`, { credentials: 'include', headers: authHeaders })
        ]);
        const contactsData = await contactsRes.json();
        const contactsList = contactsData.contacts || [];
        setContacts(contactsList);
        
        const now = new Date();
        const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
        const thisWeek = contactsList.filter((c: any) => new Date(c.createdAt) > weekAgo).length;
        const withEmail = contactsList.filter((c: any) => c.email).length;
        const totalEvents = contactsList.reduce((sum: number, c: any) => sum + (c.journeyStats?.totalEvents || 0), 0);
        
        setStats({
          total: contactsList.length,
          thisWeek,
          withEmail,
          avgEvents: contactsList.length > 0 ? totalEvents / contactsList.length : 0
        });
      } catch (err) {
        console.error('Failed to fetch CRM data:', err);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [workspaceId]);

  const columns = [
    { key: 'email', header: 'Email', sortable: true },
    { key: 'firstName', header: 'First Name', sortable: true },
    { key: 'lastName', header: 'Last Name', sortable: true },
    { 
      key: 'tags', 
      header: 'Tags',
      render: (tags: any[]) => tags?.length ? (
        <div className="flex gap-1 flex-wrap">
          {tags.slice(0, 3).map((tag, i) => (
            <Badge key={i} variant="info">
              {typeof tag === 'string' ? tag : tag?.name || 'Tag'}
            </Badge>
          ))}
          {tags.length > 3 && <Badge variant="default">+{tags.length - 3}</Badge>}
        </div>
      ) : '-'
    },
    { 
      key: 'createdAt', 
      header: 'Created',
      sortable: true,
      render: (val: string) => {
        if (!val) return '-';
        const date = new Date(val);
        return isNaN(date.getTime()) ? '-' : date.toLocaleDateString();
      }
    }
  ];

  return (
    <Stack>
      <PageHeader 
        title="CRM Dashboard" 
        subtitle="Contacts and lead management"
      />
      
      <Grid cols={4}>
        <StatCard 
          title="Total Contacts" 
          value={stats.total} 
          icon={<Users className="w-5 h-5" />}
        />
        <StatCard 
          title="New This Week" 
          value={stats.thisWeek}
          trend={stats.thisWeek > 0 ? 'up' : 'neutral'}
          trendValue={stats.thisWeek > 0 ? 'New leads' : 'No change'}
          icon={<TrendingUp className="w-5 h-5" />}
        />
        <StatCard 
          title="With Email" 
          value={stats.withEmail}
          subtitle={`${stats.total > 0 ? Math.round((stats.withEmail / stats.total) * 100) : 0}% of contacts`}
          icon={<Mail className="w-5 h-5" />}
        />
        <StatCard 
          title="Avg Events/Contact" 
          value={stats.avgEvents?.toFixed(1) || '0'}
          icon={<BarChart3 className="w-5 h-5" />}
        />
      </Grid>

      <DataTable
        title="All Contacts"
        data={contacts}
        columns={columns}
        searchable
        searchKeys={['email', 'firstName', 'lastName']}
        pageSize={15}
        loading={loading}
        emptyMessage="No contacts yet. Contacts will appear here when visitors identify themselves."
      />
    </Stack>
  );
}
