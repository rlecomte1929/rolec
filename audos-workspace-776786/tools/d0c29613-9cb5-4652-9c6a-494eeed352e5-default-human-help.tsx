import { useState, useEffect } from 'react';
import { PageHeader, Grid, Stack, StatCard, DataTable, Badge, Button, Card, EmptyState } from 'dashboard-blocks';
import { Users, Clock, CheckCircle, DollarSign, AlertCircle, X, Check, ThumbsUp, Inbox, History } from 'lucide-react';

interface TemplateProps {
  workspaceId: string;
  authToken?: string;
}

interface HumanTask {
  id: string;
  title: string;
  description: string;
  status: string;
  approvalStatus: string;
  priority: 'low' | 'medium' | 'high';
  estimatedHours: string;
  hourlyRate: string;
  quotedBudget: string;
  finalCost?: string;
  actualHours?: string;
  approvedAt?: string;
  approvedBy?: string;
  completedAt?: string;
  createdAt: string;
  dueDate?: string;
  channel: string;
  completionNotes?: string | null;
  rejectionReason?: string | null;
}

const fmtUsd = (cents: number) => '$' + (cents / 100).toFixed(2);

export function HumanHelpDashboard({ workspaceId, authToken }: TemplateProps) {
  const [tasks, setTasks] = useState<HumanTask[]>([]);
  const [walletBalance, setWalletBalance] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const __dt = typeof localStorage !== 'undefined' ? localStorage.getItem('workspace_device_token') : null;
  const authHeaders: Record<string, string> = authToken ? { 'Authorization': 'Bearer ' + authToken } : __dt ? { 'x-device-token': __dt } : {};

  async function fetchData() {
    try {
      const [tasksRes, walletRes] = await Promise.all([
        fetch(`/api/human-tasks?workspaceId=${workspaceId}&includeCompleted=true`, { credentials: 'include', headers: authHeaders }),
        fetch(`/api/workspaces/${workspaceId}/wallet`, { credentials: 'include', headers: authHeaders }),
      ]);
      const tasksData = await tasksRes.json();
      setTasks(tasksData.tasks || []);
      try {
        const wd = await walletRes.json();
        setWalletBalance(Number(wd?.balance) || 0);
      } catch {}
    } catch (err) {
      console.error('Failed to fetch human tasks:', err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchData(); }, [workspaceId]);

  const callTaskAction = async (
    taskId: string,
    path: 'approve' | 'reject' | 'complete',
    body: any = {}
  ) => {
    setActionLoading(taskId + ':' + path);
    setErrorMsg(null);
    try {
      const res = await fetch(`/api/human-tasks/${taskId}/${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify({ workspaceId, ...body }),
        credentials: 'include',
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setErrorMsg(err.error || `Failed to ${path} task`);
      } else {
        await fetchData();
      }
    } catch (err: any) {
      setErrorMsg(err?.message || `Failed to ${path} task`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleApprove = (taskId: string) => callTaskAction(taskId, 'approve');
  const handleReject = (taskId: string) => {
    const reason = window.prompt('Reason for rejection (optional):') || '';
    callTaskAction(taskId, 'reject', { reason });
  };
  const handleComplete = (taskId: string) => {
    const hoursStr = window.prompt('Actual hours worked (leave blank to use quoted budget):') || '';
    const actualHours = hoursStr.trim() ? Number(hoursStr) : undefined;
    if (hoursStr.trim() && (Number.isNaN(actualHours!) || actualHours! <= 0)) {
      setErrorMsg('Actual hours must be a positive number.');
      return;
    }
    const notes = window.prompt('Completion notes (optional):') || '';
    callTaskAction(taskId, 'complete', { actualHours, notes });
  };

  // Stats
  const now = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
  const pending = tasks.filter(t => t.approvalStatus === 'pending').length;
  const inProgress = tasks.filter(t => t.status === 'pending' && t.approvalStatus === 'approved').length;
  const completedThisMonth = tasks.filter(t => t.status === 'completed' && t.completedAt && new Date(t.completedAt) >= monthStart);
  const spendCentsMTD = completedThisMonth.reduce((sum, t) => sum + (Number(t.finalCost) || 0), 0);
  const pendingBudgetCents = tasks
    .filter(t => t.approvalStatus === 'pending')
    .reduce((sum, t) => sum + (Number(t.quotedBudget) || 0), 0);

  const priorityVariant = (p: string) => p === 'high' ? 'danger' : p === 'low' ? 'default' : 'warning';

  // Bucket tasks into the three explicit sections
  const pendingTasks = tasks.filter(t => t.approvalStatus === 'pending' && t.status !== 'completed' && t.status !== 'cancelled');
  const inProgressTasks = tasks.filter(t => t.approvalStatus === 'approved' && t.status !== 'completed' && t.status !== 'cancelled');
  const historyTasks = tasks
    .filter(t => t.status === 'completed' || t.status === 'cancelled' || t.approvalStatus === 'rejected')
    .sort((a, b) => {
      const aT = new Date(a.completedAt || a.createdAt).getTime();
      const bT = new Date(b.completedAt || b.createdAt).getTime();
      return bT - aT;
    });

  const renderPendingActions = (id: string, row: HumanTask) => {
    const quoted = Number(row.quotedBudget) || 0;
    const insufficient = walletBalance < quoted;
    return (
      <div className="flex flex-col gap-1">
        <div className="flex gap-1">
          <Button
            size="sm"
            variant="primary"
            onClick={() => handleApprove(id)}
            loading={actionLoading === id + ':approve'}
            icon={<Check className="w-3 h-3" />}
          >
            Approve
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={() => handleReject(id)}
            loading={actionLoading === id + ':reject'}
            icon={<X className="w-3 h-3" />}
          >
            Reject
          </Button>
        </div>
        {insufficient && (
          <span className="text-[10px] text-amber-600 leading-tight">
            ⚠ Wallet ({fmtUsd(walletBalance)}) is below quoted budget ({fmtUsd(quoted)}). Approving may be rejected by the server.
          </span>
        )}
      </div>
    );
  };

  const renderInProgressActions = (id: string, _row: HumanTask) => (
    <Button
      size="sm"
      variant="primary"
      onClick={() => handleComplete(id)}
      loading={actionLoading === id + ':complete'}
      icon={<ThumbsUp className="w-3 h-3" />}
    >
      Mark complete
    </Button>
  );

  const titleColumn = {
    key: 'title', header: 'Task', sortable: true,
    render: (val: string, row: HumanTask) => (
      <div>
        <div className="font-medium">{val}</div>
        <div className="text-xs text-gray-500 max-w-md truncate">{row.description}</div>
      </div>
    ),
  };
  const priorityColumn = {
    key: 'priority', header: 'Priority', sortable: true,
    render: (val: string) => <Badge variant={priorityVariant(val)}>{val}</Badge>,
  };

  return (
    <Stack>
      <PageHeader
        title="Human Help"
        subtitle="Tasks where a real person — you or a VA — needs to do the work. Approve before any human picks it up; the wallet is only charged on completion."
        icon={<Users className="w-5 h-5 text-indigo-600" />}
      />

      {errorMsg && (
        <Card>
          <div className="flex items-center gap-2 text-red-600 text-sm">
            <AlertCircle className="w-4 h-4" />
            <span>{errorMsg}</span>
          </div>
        </Card>
      )}

      <Grid cols={4}>
        <StatCard
          title="Awaiting Approval"
          value={pending}
          subtitle={pending > 0 ? `Quoted: ${fmtUsd(pendingBudgetCents)}` : 'All caught up'}
          icon={<AlertCircle className="w-5 h-5" />}
        />
        <StatCard
          title="Open / In Progress"
          value={inProgress}
          icon={<Clock className="w-5 h-5" />}
        />
        <StatCard
          title="Completed This Month"
          value={completedThisMonth.length}
          icon={<CheckCircle className="w-5 h-5" />}
        />
        <StatCard
          title="Spend This Month"
          value={fmtUsd(spendCentsMTD)}
          subtitle={`Wallet: ${fmtUsd(walletBalance)}`}
          icon={<DollarSign className="w-5 h-5" />}
        />
      </Grid>

      {/* Section 1: Pending your approval */}
      {pendingTasks.length === 0 ? (
        <Card>
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Inbox className="w-4 h-4" />
            <span className="font-medium">Pending your approval</span>
            <span className="text-gray-400">— nothing waiting on you</span>
          </div>
        </Card>
      ) : (
        <DataTable
          title="Pending your approval"
          data={pendingTasks}
          columns={[
            titleColumn,
            priorityColumn,
            { key: 'estimatedHours', header: 'Est. hours', sortable: true, render: (val: string) => <span>~{val}h</span> },
            { key: 'quotedBudget', header: 'Quoted budget', sortable: true, render: (val: string) => <span>{fmtUsd(Number(val) || 0)}</span> },
            { key: 'createdAt', header: 'Requested', sortable: true, render: (val: string) => val ? new Date(val).toLocaleDateString() : '—' },
            { key: 'id', header: 'Actions', render: renderPendingActions },
          ]}
          loading={loading}
          emptyMessage="No tasks awaiting approval."
        />
      )}

      {/* Section 2: In progress (approved, not yet completed) */}
      {inProgressTasks.length === 0 ? (
        <Card>
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Clock className="w-4 h-4" />
            <span className="font-medium">In progress</span>
            <span className="text-gray-400">— no approved work in flight</span>
          </div>
        </Card>
      ) : (
        <DataTable
          title="In progress"
          data={inProgressTasks}
          columns={[
            titleColumn,
            priorityColumn,
            { key: 'estimatedHours', header: 'Est. hours', sortable: true, render: (val: string) => <span>~{val}h</span> },
            { key: 'quotedBudget', header: 'Quoted budget', sortable: true, render: (val: string) => <span>{fmtUsd(Number(val) || 0)}</span> },
            { key: 'approvedAt', header: 'Approved', sortable: true, render: (val: string) => val ? new Date(val).toLocaleDateString() : '—' },
            { key: 'id', header: 'Actions', render: renderInProgressActions },
          ]}
          loading={loading}
          emptyMessage="No approved tasks in flight."
        />
      )}

      {/* Section 3: Completed history (with deliverable notes / final cost / rejection reason) */}
      {historyTasks.length === 0 ? (
        <Card>
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <History className="w-4 h-4" />
            <span className="font-medium">Completed history</span>
            <span className="text-gray-400">— no completed or rejected tasks yet</span>
          </div>
        </Card>
      ) : (
        <DataTable
          title="Completed history"
          data={historyTasks}
          columns={[
            titleColumn,
            { key: 'status', header: 'Outcome', render: (_v: any, row: HumanTask) => (
              row.status === 'completed'
                ? <Badge variant="success">completed</Badge>
                : <Badge variant="default">rejected</Badge>
            )},
            { key: 'actualHours', header: 'Hours', sortable: true, render: (_v: any, row: HumanTask) => (
              <span>{row.actualHours ? `${row.actualHours}h actual` : (row.estimatedHours ? `~${row.estimatedHours}h` : '—')}</span>
            )},
            { key: 'finalCost', header: 'Final cost', sortable: true, render: (_v: any, row: HumanTask) => (
              <span>{row.finalCost ? fmtUsd(Number(row.finalCost)) : (row.status === 'completed' ? fmtUsd(Number(row.quotedBudget) || 0) : '—')}</span>
            )},
            { key: 'completionNotes', header: 'Deliverable notes', render: (_v: any, row: HumanTask) => {
              if (row.status === 'completed') {
                return (
                  <div className="text-xs text-gray-700 max-w-sm whitespace-pre-wrap">
                    {row.completionNotes && row.completionNotes.trim().length > 0
                      ? row.completionNotes
                      : <span className="text-gray-400 italic">No notes recorded</span>}
                  </div>
                );
              }
              return (
                <div className="text-xs text-gray-700 max-w-sm whitespace-pre-wrap">
                  {row.rejectionReason && row.rejectionReason.trim().length > 0
                    ? <span><span className="font-medium">Reason:</span> {row.rejectionReason}</span>
                    : <span className="text-gray-400 italic">No reason recorded</span>}
                </div>
              );
            }},
            { key: 'completedAt', header: 'Closed', sortable: true, render: (val: string, row: HumanTask) => (
              val ? new Date(val).toLocaleDateString() : (row.createdAt ? new Date(row.createdAt).toLocaleDateString() : '—')
            )},
          ]}
          searchable
          searchKeys={['title', 'description', 'completionNotes', 'rejectionReason']}
          loading={loading}
          emptyMessage="No completed or rejected tasks yet."
        />
      )}

      {tasks.length === 0 && !loading && (
        <Card>
          <EmptyState
            icon={<Users className="w-8 h-8" />}
            title="No human help requests yet"
            description="Otto can request one for you, or you can create one from chat by saying 'I need a human to handle X for me'."
          />
        </Card>
      )}
    </Stack>
  );
}
