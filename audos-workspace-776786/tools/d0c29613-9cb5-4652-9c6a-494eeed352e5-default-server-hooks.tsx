import { useState, useEffect, useCallback } from 'react';
import { PageHeader, Stack, Badge, Card, EmptyState } from 'dashboard-blocks';
import { Webhook, Clock, Code, Shield, AlertTriangle, ChevronDown, ChevronRight, Calendar, Hash, Zap, Play, RotateCw, CheckCircle, XCircle, Terminal } from 'lucide-react';

interface TemplateProps {
  workspaceId: string;
  authToken?: string;
}

interface Hook {
  id: string;
  name: string;
  description?: string;
  code: string;
  language: string;
  enabled: boolean;
  hasSecret: boolean;
  lastExecutedAt?: string;
  executionCount: number;
  lastError?: string;
  createdAt: string;
  updatedAt: string;
}

interface Schedule {
  id: string;
  name: string;
  description?: string;
  actionType: string;
  actionPayload?: any;
  scheduleType: string;
  rrule?: string;
  timezone?: string;
  status: string;
  nextRun?: string;
  lastRun?: string;
  runCount: number;
  lastError?: string;
  createdAt: string;
}

interface InterceptedAction {
  type: string;
  description: string;
  payload?: any;
}

interface TestResult {
  success: boolean;
  statusCode: number;
  durationMs?: number;
  body?: any;
  logs?: string[];
  error?: string;
  dryRun?: boolean;
  interceptedActions?: InterceptedAction[];
}

function ActionIcon({ type }: { type: string }) {
  switch (type) {
    case 'db_insert': return <span className="text-blue-500">➕</span>;
    case 'db_update': return <span className="text-amber-500">✏️</span>;
    case 'db_delete': return <span className="text-red-500">➖</span>;
    case 'send_email': return <span className="text-purple-500">✉</span>;
    case 'post_message': return <span className="text-indigo-500">💬</span>;
    case 'create_contact': return <span className="text-green-500">👤</span>;
    case 'external_fetch': return <span className="text-cyan-500">🌐</span>;
    default: return <span>⚠</span>;
  }
}

function TestResultPanel({ result, onClose }: { result: TestResult; onClose: () => void }) {
  const [showBody, setShowBody] = useState(false);
  const [expandedAction, setExpandedAction] = useState<number | null>(null);

  return (
    <div className={`rounded-md border p-3 text-xs space-y-2 ${
      result.success
        ? 'border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-950'
        : 'border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950'
    }`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {result.success
            ? <CheckCircle className="w-4 h-4 text-green-600 dark:text-green-400" />
            : <XCircle className="w-4 h-4 text-red-600 dark:text-red-400" />
          }
          <span className="font-semibold">
            {result.success ? 'Success' : 'Failed'} — HTTP {result.statusCode}
          </span>
          {result.durationMs != null && (
            <span className="text-gray-500">{result.durationMs}ms</span>
          )}
          {result.dryRun && (
            <span className="px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 dark:bg-amber-900/50 dark:text-amber-200 font-medium text-[10px] uppercase tracking-wide">
              Dry Run
            </span>
          )}
        </div>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
          ✕
        </button>
      </div>

      {result.dryRun && (
        <div className="text-amber-700 dark:text-amber-300 text-[11px]">
          No data was modified. DB writes, emails, and messages were intercepted.
        </div>
      )}

      {result.error && (
        <div className="text-red-700 dark:text-red-300 font-mono break-all">{result.error}</div>
      )}

      {result.interceptedActions && result.interceptedActions.length > 0 && (
        <div>
          <div className="flex items-center gap-1 text-gray-600 dark:text-gray-400 mb-1.5">
            <Shield className="w-3 h-3" />
            <span className="font-medium">Intercepted actions ({result.interceptedActions.length})</span>
          </div>
          <div className="space-y-1">
            {result.interceptedActions.map((action, i) => (
              <div key={i} className="bg-white dark:bg-gray-900 rounded border border-gray-200 dark:border-gray-700">
                <div
                  className="flex items-center gap-2 px-2 py-1.5 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800"
                  onClick={() => setExpandedAction(expandedAction === i ? null : i)}
                >
                  <ActionIcon type={action.type} />
                  <span className="flex-1 truncate">{action.description}</span>
                  <span className="text-[10px] text-gray-400 font-mono">{action.type}</span>
                  {action.payload && (expandedAction === i ? <ChevronDown className="w-3 h-3 text-gray-400" /> : <ChevronRight className="w-3 h-3 text-gray-400" />)}
                </div>
                {expandedAction === i && action.payload && (
                  <pre className="px-2 pb-2 text-[10px] font-mono text-gray-600 dark:text-gray-400 overflow-x-auto whitespace-pre-wrap">
                    {JSON.stringify(action.payload, null, 2)}
                  </pre>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {result.logs && result.logs.length > 0 && (
        <div>
          <div className="flex items-center gap-1 text-gray-600 dark:text-gray-400 mb-1">
            <Terminal className="w-3 h-3" />
            <span className="font-medium">Console output ({result.logs.length} lines)</span>
          </div>
          <pre className="bg-gray-900 text-gray-100 rounded p-2 text-xs font-mono overflow-x-auto max-h-40 overflow-y-auto whitespace-pre-wrap">
            {result.logs.join('\n')}
          </pre>
        </div>
      )}

      {result.body && (
        <div>
          <div
            className="flex items-center gap-1 text-gray-600 dark:text-gray-400 cursor-pointer"
            onClick={() => setShowBody(!showBody)}
          >
            {showBody ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            <span className="font-medium">Response body</span>
          </div>
          {showBody && (
            <pre className="bg-gray-900 text-gray-100 rounded p-2 text-xs font-mono overflow-x-auto max-h-48 overflow-y-auto mt-1 whitespace-pre-wrap">
              {typeof result.body === 'string' ? result.body : JSON.stringify(result.body, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

function CollapsibleCode({ code, language }: { code: string; language: string }) {
  const [expanded, setExpanded] = useState(false);
  const lines = code.split('\n');
  const preview = lines.slice(0, 3).join('\n');
  const needsCollapse = lines.length > 3;

  return (
    <div className="relative">
      <div
        className="cursor-pointer flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 mb-1"
        onClick={() => setExpanded(!expanded)}
      >
        {needsCollapse && (expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />)}
        <span className="font-mono">{language}</span>
        <span>· {lines.length} lines</span>
      </div>
      <pre className="bg-gray-900 text-gray-100 dark:bg-gray-950 rounded-md p-3 text-xs font-mono overflow-x-auto max-h-96 overflow-y-auto whitespace-pre-wrap break-all">
        {expanded || !needsCollapse ? code : preview + '\n...'}
      </pre>
    </div>
  );
}

function HookCard({ hook, workspaceId, authToken }: { hook: Hook; workspaceId: string; authToken?: string }) {
  const endpointUrl = `/api/workspaces/${workspaceId}/hooks/${hook.name}/execute`;
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const __dt = typeof localStorage !== 'undefined' ? localStorage.getItem('workspace_device_token') : null;
  const authHeaders: Record<string, string> = authToken ? { 'Authorization': 'Bearer ' + authToken } : __dt ? { 'x-device-token': __dt } : {};

  const handleTest = useCallback(async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const startTime = Date.now();
      const res = await fetch(endpointUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify({ _test: true }),
        credentials: 'include',
      });
      const elapsed = Date.now() - startTime;
      const data = await res.json().catch(() => null);
      const meta = data?._meta || {};
      setTestResult({
        success: meta.success !== undefined ? meta.success : res.ok,
        statusCode: res.status,
        durationMs: meta.durationMs || elapsed,
        body: data,
        logs: meta.logs || [],
        error: meta.error || (!res.ok ? `HTTP ${res.status}` : undefined),
        dryRun: meta.dryRun || false,
        interceptedActions: meta.interceptedActions || [],
      });
    } catch (err: any) {
      setTestResult({
        success: false,
        statusCode: 0,
        error: err.message || 'Network error',
      });
    } finally {
      setTesting(false);
    }
  }, [endpointUrl]);

  return (
    <Card className="p-4 space-y-3">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <Webhook className="w-4 h-4 text-indigo-500 flex-shrink-0" />
          <div>
            <h3 className="font-semibold text-sm">{hook.name}</h3>
            {hook.description && (
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{hook.description}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={hook.enabled ? 'success' : 'default'}>
            {hook.enabled ? 'Enabled' : 'Disabled'}
          </Badge>
        </div>
      </div>

      <CollapsibleCode code={hook.code} language={hook.language} />

      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
        <div className="flex items-center gap-1.5 text-gray-600 dark:text-gray-400">
          <Shield className="w-3 h-3" />
          <span>Secret:</span>
          <span className="font-medium">{hook.hasSecret ? '•••••••• (set)' : 'None'}</span>
        </div>
        <div className="flex items-center gap-1.5 text-gray-600 dark:text-gray-400">
          <Hash className="w-3 h-3" />
          <span>Runs:</span>
          <span className="font-medium">{hook.executionCount}</span>
        </div>
        <div className="flex items-center gap-1.5 text-gray-600 dark:text-gray-400">
          <Clock className="w-3 h-3" />
          <span>Last run:</span>
          <span className="font-medium">
            {hook.lastExecutedAt ? new Date(hook.lastExecutedAt).toLocaleString() : 'Never'}
          </span>
        </div>
        {hook.lastError && (
          <div className="flex items-center gap-1.5 text-red-600 dark:text-red-400 col-span-2">
            <AlertTriangle className="w-3 h-3" />
            <span className="truncate">{hook.lastError}</span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2">
        <div className="bg-gray-100 dark:bg-gray-800 rounded px-2 py-1.5 flex-1 flex items-center gap-2 min-w-0">
          <Code className="w-3 h-3 text-gray-500 flex-shrink-0" />
          <code className="text-xs font-mono text-gray-700 dark:text-gray-300 break-all truncate">{endpointUrl}</code>
        </div>
        <div className="relative group">
          <button
            onClick={handleTest}
            disabled={testing || !hook.enabled}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors ${
              testing
                ? 'bg-gray-200 text-gray-500 dark:bg-gray-700 dark:text-gray-400 cursor-wait'
                : !hook.enabled
                ? 'bg-gray-100 text-gray-400 dark:bg-gray-800 dark:text-gray-500 cursor-not-allowed'
                : 'bg-indigo-100 text-indigo-700 hover:bg-indigo-200 dark:bg-indigo-900/40 dark:text-indigo-300 dark:hover:bg-indigo-900/60'
            }`}
          >
            {testing
              ? <><RotateCw className="w-3 h-3 animate-spin" /> Running...</>
              : <><Play className="w-3 h-3" /> Dry Run</>
            }
          </button>
        </div>
      </div>

      {testResult && (
        <TestResultPanel result={testResult} onClose={() => setTestResult(null)} />
      )}
    </Card>
  );
}

function ScheduleCard({ schedule, workspaceId, authToken }: { schedule: Schedule; workspaceId: string; authToken?: string }) {
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [showPayload, setShowPayload] = useState(false);
  const [showError, setShowError] = useState(false);
  const __dt = typeof localStorage !== 'undefined' ? localStorage.getItem('workspace_device_token') : null;
  const authHeaders: Record<string, string> = authToken ? { 'Authorization': 'Bearer ' + authToken } : __dt ? { 'x-device-token': __dt } : {};

  const statusVariant = (() => {
    switch (schedule.status) {
      case 'pending': return 'warning';
      case 'processing': return 'info';
      case 'completed': return 'success';
      case 'failed': return 'danger';
      case 'cancelled': return 'default';
      default: return 'default';
    }
  })();

  const actionIcon = (() => {
    switch (schedule.actionType) {
      case 'hook': return <Webhook className="w-3 h-3" />;
      case 'webhook': return <Zap className="w-3 h-3" />;
      case 'email': return <Play className="w-3 h-3" />;
      default: return <Play className="w-3 h-3" />;
    }
  })();

  const canTest = schedule.actionType === 'hook' && schedule.actionPayload?.hookName;

  const handleTestHook = useCallback(async () => {
    if (!canTest) return;
    const hookName = schedule.actionPayload.hookName;
    setTesting(true);
    setTestResult(null);
    try {
      const startTime = Date.now();
      const res = await fetch(`/api/workspaces/${workspaceId}/hooks/${hookName}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify({ _test: true, _scheduledTask: schedule.name }),
        credentials: 'include',
      });
      const elapsed = Date.now() - startTime;
      const data = await res.json().catch(() => null);
      const meta = data?._meta || {};
      setTestResult({
        success: meta.success !== undefined ? meta.success : res.ok,
        statusCode: res.status,
        durationMs: meta.durationMs || elapsed,
        body: data,
        logs: meta.logs || [],
        error: meta.error || (!res.ok ? `HTTP ${res.status}` : undefined),
        dryRun: meta.dryRun || false,
        interceptedActions: meta.interceptedActions || [],
      });
    } catch (err: any) {
      setTestResult({
        success: false,
        statusCode: 0,
        error: err.message || 'Network error',
      });
    } finally {
      setTesting(false);
    }
  }, [workspaceId, schedule, canTest]);

  return (
    <Card className="p-4 space-y-3">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <Calendar className="w-4 h-4 text-amber-500 flex-shrink-0" />
          <div>
            <h3 className="font-semibold text-sm">{schedule.name}</h3>
            {schedule.description && (
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{schedule.description}</p>
            )}
          </div>
        </div>
        <Badge variant={statusVariant}>{schedule.status}</Badge>
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
        <div className="flex items-center gap-1.5 text-gray-600 dark:text-gray-400">
          {actionIcon}
          <span>Type:</span>
          <span className="font-medium">{schedule.actionType}</span>
          {schedule.actionType === 'hook' && schedule.actionPayload?.hookName && (
            <span className="font-mono text-indigo-600 dark:text-indigo-400">({schedule.actionPayload.hookName})</span>
          )}
        </div>
        <div className="flex items-center gap-1.5 text-gray-600 dark:text-gray-400">
          <Clock className="w-3 h-3" />
          <span>Frequency:</span>
          <span className="font-medium font-mono">{schedule.rrule || schedule.scheduleType}</span>
        </div>
        {schedule.timezone && (
          <div className="flex items-center gap-1.5 text-gray-600 dark:text-gray-400">
            <Clock className="w-3 h-3" />
            <span>Timezone:</span>
            <span className="font-medium">{schedule.timezone}</span>
          </div>
        )}
        <div className="flex items-center gap-1.5 text-gray-600 dark:text-gray-400">
          <Hash className="w-3 h-3" />
          <span>Runs:</span>
          <span className="font-medium">{schedule.runCount}</span>
        </div>
        <div className="flex items-center gap-1.5 text-gray-600 dark:text-gray-400">
          <Clock className="w-3 h-3" />
          <span>Next run:</span>
          <span className="font-medium">
            {schedule.nextRun ? new Date(schedule.nextRun).toLocaleString() : '—'}
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-gray-600 dark:text-gray-400">
          <Clock className="w-3 h-3" />
          <span>Last run:</span>
          <span className="font-medium">
            {schedule.lastRun ? new Date(schedule.lastRun).toLocaleString() : 'Never'}
          </span>
        </div>
      </div>

      {schedule.lastError && (
        <div
          className="flex items-start gap-1.5 text-red-600 dark:text-red-400 text-xs cursor-pointer"
          onClick={() => setShowError(!showError)}
        >
          <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" />
          <div className="min-w-0">
            <span className={showError ? '' : 'truncate block'}>{schedule.lastError}</span>
          </div>
        </div>
      )}

      <div className="flex items-center gap-2">
        {schedule.actionPayload && (
          <button
            onClick={() => setShowPayload(!showPayload)}
            className="inline-flex items-center gap-1.5 px-2 py-1 rounded text-xs text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          >
            {showPayload ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            Action config
          </button>
        )}
        <div className="flex-1" />
        {canTest && (
          <button
            onClick={handleTestHook}
            disabled={testing}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors ${
              testing
                ? 'bg-gray-200 text-gray-500 dark:bg-gray-700 dark:text-gray-400 cursor-wait'
                : 'bg-amber-100 text-amber-700 hover:bg-amber-200 dark:bg-amber-900/40 dark:text-amber-300 dark:hover:bg-amber-900/60'
            }`}
          >
            {testing
              ? <><RotateCw className="w-3 h-3 animate-spin" /> Running...</>
              : <><Play className="w-3 h-3" /> Dry Run Hook</>
            }
          </button>
        )}
      </div>

      {showPayload && schedule.actionPayload && (
        <pre className="bg-gray-900 text-gray-100 rounded-md p-2 text-xs font-mono overflow-x-auto max-h-32 overflow-y-auto whitespace-pre-wrap">
          {JSON.stringify(schedule.actionPayload, null, 2)}
        </pre>
      )}

      {testResult && (
        <TestResultPanel result={testResult} onClose={() => setTestResult(null)} />
      )}
    </Card>
  );
}

export function ServerHooksDashboard({ workspaceId, authToken }: TemplateProps) {
  const [hooks, setHooks] = useState<Hook[]>([]);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [loading, setLoading] = useState(true);
  const __dt = typeof localStorage !== 'undefined' ? localStorage.getItem('workspace_device_token') : null;
  const authHeaders: Record<string, string> = authToken ? { 'Authorization': 'Bearer ' + authToken } : __dt ? { 'x-device-token': __dt } : {};

  useEffect(() => {
    async function fetchData() {
      try {
        const [hooksRes, schedulesRes] = await Promise.all([
          fetch(`/api/workspaces/${workspaceId}/hooks`, { credentials: 'include', headers: authHeaders }),
          fetch(`/api/workspaces/${workspaceId}/schedules`, { credentials: 'include', headers: authHeaders })
        ]);
        const hooksData = await hooksRes.json();
        setHooks(Array.isArray(hooksData) ? hooksData : []);

        const schedulesData = await schedulesRes.json();
        setSchedules(schedulesData.schedules || []);
      } catch (err) {
        console.error('Failed to fetch hooks/schedules:', err);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [workspaceId]);

  if (loading) {
    return (
      <Stack>
        <PageHeader
          title="Server Hooks & Scheduled Tasks"
          subtitle="Loading..."
          icon={<Webhook className="w-5 h-5 text-indigo-600" />}
        />
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-500" />
        </div>
      </Stack>
    );
  }

  const hasHooks = hooks.length > 0;
  const hasSchedules = schedules.length > 0;

  return (
    <Stack>
      <PageHeader
        title="Server Hooks & Scheduled Tasks"
        subtitle={`${hooks.length} hook${hooks.length !== 1 ? 's' : ''} · ${schedules.length} scheduled task${schedules.length !== 1 ? 's' : ''}`}
        icon={<Webhook className="w-5 h-5 text-indigo-600" />}
      />

      <div className="rounded-md border border-indigo-200 bg-indigo-50 dark:border-indigo-900 dark:bg-indigo-950/40 p-3 text-sm text-indigo-900 dark:text-indigo-100">
        <div className="flex items-start gap-2">
          <Zap className="w-4 h-4 mt-0.5 shrink-0" />
          <div className="space-y-1">
            <div className="font-medium">How to create hooks and scheduled tasks</div>
            <div className="text-indigo-800/90 dark:text-indigo-200/90 leading-relaxed">
              This dashboard is a <span className="font-medium">monitor</span> — there is no "new hook" button by design. To create one, open the Agent panel and ask Otto, e.g.{' '}
              <span className="italic">"Create a hook called <code className="font-mono text-xs">stripe-webhook</code> that verifies the Stripe signature and inserts <code className="font-mono text-xs">checkout.session.completed</code> events into my <code className="font-mono text-xs">orders</code> table"</span> or{' '}
              <span className="italic">"Schedule the <code className="font-mono text-xs">daily-summary</code> hook every weekday at 9am Eastern."</span>{' '}
              New hooks appear here with their callable URL{' '}
              (<code className="font-mono text-xs">POST /api/workspaces/:wsId/hooks/:name/execute</code>),{' '}
              an execution counter, the last error, and a <span className="font-medium">Dry Run</span> button to test in place.
            </div>
          </div>
        </div>
      </div>

      <div>
        <h2 className="text-base font-semibold mb-3 flex items-center gap-2">
          <Webhook className="w-4 h-4 text-indigo-500" />
          Server Hooks
          <Badge variant="default">{hooks.length}</Badge>
        </h2>
        {hasHooks ? (
          <div className="grid gap-3">
            {hooks.map(hook => (
              <HookCard key={hook.id} hook={hook} workspaceId={workspaceId} authToken={authToken} />
            ))}
          </div>
        ) : (
          <EmptyState
            icon={<Webhook className="w-8 h-8 text-gray-400" />}
            title="No server hooks"
            description="Server hooks will appear here when created through the agent. Hooks are custom code endpoints that respond to HTTP requests."
          />
        )}
      </div>

      <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
        <h2 className="text-base font-semibold mb-3 flex items-center gap-2">
          <Calendar className="w-4 h-4 text-amber-500" />
          Scheduled Tasks
          <Badge variant="default">{schedules.length}</Badge>
        </h2>
        {hasSchedules ? (
          <div className="grid gap-3">
            {schedules.map(schedule => (
              <ScheduleCard key={schedule.id} schedule={schedule} workspaceId={workspaceId} authToken={authToken} />
            ))}
          </div>
        ) : (
          <EmptyState
            icon={<Calendar className="w-8 h-8 text-gray-400" />}
            title="No scheduled tasks"
            description="Scheduled tasks will appear here when created through the agent. Tasks can run on a recurring schedule or at a specific time."
          />
        )}
      </div>
    </Stack>
  );
}
