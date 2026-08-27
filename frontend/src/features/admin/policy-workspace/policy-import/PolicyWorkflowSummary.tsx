import React from 'react';
import { Card } from '../../../../components/antigravity';
import type { PolicyWorkflowSummary as Summary } from '../../../../api/client';

interface Props {
  summary: Summary;
  elapsedMs: number;
  model: string | null;
}

export const PolicyWorkflowSummary: React.FC<Props> = ({ summary, elapsedMs, model }) => {
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-[15px] font-semibold text-slate-900">
            {summary.policy_title ?? 'Policy Analysis'}
          </h3>
          {summary.effective_date && (
            <p className="text-[12px] text-slate-500">Effective: {summary.effective_date}</p>
          )}
        </div>
        <div className="flex items-center gap-3 text-[11px] text-slate-500">
          <span>{summary.benefits_count} benefits extracted</span>
          <span>{(elapsedMs / 1000).toFixed(1)}s</span>
          {model && <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono">{model}</span>}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Tiers */}
        <Card padding="sm" className="border-slate-200">
          <SectionHeader icon="layers" title="Detected Policy Tiers" count={summary.tiers.length} />
          <div className="mt-2 space-y-1.5">
            {summary.tiers.map((tier, i) => (
              <div key={i} className="flex items-center justify-between rounded-md bg-slate-50 px-3 py-2">
                <span className="text-[13px] font-medium text-slate-800">{tier.name}</span>
                <span className="text-[11px] text-slate-500">
                  {tier.benefits_count} benefit{tier.benefits_count !== 1 ? 's' : ''}
                </span>
              </div>
            ))}
          </div>
        </Card>

        {/* Timeline */}
        <Card padding="sm" className="border-slate-200">
          <SectionHeader icon="clock" title="Timeline Estimate" count={summary.timeline.length} />
          <div className="mt-2 space-y-2">
            {summary.timeline.map((phase, i) => (
              <div key={i} className="rounded-md border border-slate-100 bg-white px-3 py-2">
                <div className="flex items-center justify-between">
                  <span className="text-[13px] font-medium text-slate-800">{phase.phase}</span>
                  <span className="text-[11px] text-accent-600">{phase.duration}</span>
                </div>
                <div className="mt-1 flex flex-wrap gap-1">
                  {phase.tasks.map((task, j) => (
                    <span key={j} className="rounded bg-accent-50 px-1.5 py-0.5 text-[10px] text-accent-700">
                      {task}
                    </span>
                  ))}
                </div>
              </div>
            ))}
            {summary.timeline.length === 0 && (
              <p className="text-[12px] text-slate-500">No timeline phases derived from policy.</p>
            )}
          </div>
        </Card>

        {/* Task List */}
        <Card padding="sm" className="border-slate-200 lg:col-span-2">
          <SectionHeader icon="list" title="Task List with Owners" count={summary.tasks.length} />
          <div className="mt-2 overflow-hidden rounded-md border border-slate-100">
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50/80 text-left text-[11px] font-medium uppercase tracking-wider text-slate-500">
                  <th className="px-3 py-2">Category</th>
                  <th className="px-3 py-2">Task</th>
                  <th className="px-3 py-2">Owner</th>
                  <th className="px-3 py-2 text-right">Confidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {summary.tasks.map((task, i) => (
                  <tr key={i} className="hover:bg-slate-50/50">
                    <td className="px-3 py-2 text-slate-500">{task.category}</td>
                    <td className="px-3 py-2 font-medium text-slate-800">{task.task}</td>
                    <td className="px-3 py-2 text-slate-600">{task.owner}</td>
                    <td className="px-3 py-2 text-right">
                      <ConfidenceBadge value={task.confidence} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Cost Summary */}
        <Card padding="sm" className="border-slate-200 lg:col-span-2">
          <SectionHeader icon="dollar" title="Cost Range Estimate" count={summary.cost_summary.by_category.length} />
          {summary.cost_summary.total_range && (
            <div className="mt-2 rounded-md bg-navy-50 px-4 py-3">
              <div className="text-[11px] font-medium uppercase tracking-wider text-navy-500">
                Estimated Total
              </div>
              <div className="mt-0.5 text-[20px] font-semibold text-navy-900">
                {formatCurrency(summary.cost_summary.total_range.min, summary.cost_summary.total_range.currency)}
                {' – '}
                {formatCurrency(summary.cost_summary.total_range.max, summary.cost_summary.total_range.currency)}
              </div>
            </div>
          )}
          {summary.cost_summary.by_category.length > 0 && (
            <div className="mt-2 space-y-1">
              {summary.cost_summary.by_category.map((cat, i) => (
                <div key={i} className="flex items-center justify-between rounded-md bg-slate-50 px-3 py-2">
                  <span className="text-[12.5px] text-slate-700">{cat.category}</span>
                  <span className="text-[12.5px] font-medium text-slate-900">
                    {formatCurrency(cat.estimated_range.min, cat.estimated_range.currency)}
                    {' – '}
                    {formatCurrency(cat.estimated_range.max, cat.estimated_range.currency)}
                  </span>
                </div>
              ))}
            </div>
          )}
          <p className="mt-2 text-[11px] text-slate-500">{summary.cost_summary.note}</p>
        </Card>
      </div>
    </div>
  );
};

function SectionHeader({ icon, title, count }: { icon: string; title: string; count: number }) {
  const iconMap: Record<string, string> = {
    layers: '◇',
    clock: '◷',
    list: '☰',
    dollar: '$',
  };
  return (
    <div className="flex items-center gap-2">
      <span className="flex h-5 w-5 items-center justify-center rounded bg-accent-100 text-[11px] text-accent-700">
        {iconMap[icon] ?? '•'}
      </span>
      <span className="text-[13px] font-semibold text-slate-900">{title}</span>
      <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500">
        {count}
      </span>
    </div>
  );
}

function ConfidenceBadge({ value }: { value: number }) {
  const label = value >= 0.8 ? 'High' : value >= 0.4 ? 'Medium' : 'Low';
  const cx =
    value >= 0.8
      ? 'bg-emerald-50 text-emerald-700 ring-emerald-200'
      : value >= 0.4
        ? 'bg-amber-50 text-amber-700 ring-amber-200'
        : 'bg-slate-50 text-slate-500 ring-slate-200';
  return (
    <span className={`inline-flex rounded-full px-1.5 py-0.5 text-[10px] font-medium ring-1 ring-inset ${cx}`}>
      {label}
    </span>
  );
}

function formatCurrency(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency,
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${currency} ${amount.toLocaleString()}`;
  }
}
