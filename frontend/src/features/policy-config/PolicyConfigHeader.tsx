import React from 'react';
import { Badge, Button } from '../../components/antigravity';
import { statusBadgeVariant } from './policyConfigUtils';
import type { PolicyConfigWorkingPayload } from './types';
import type { PolicyReadOnlySnapshot } from './usePolicyConfigWorkspace';

function formatSavedAt(iso: string | null | undefined): string {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
  } catch {
    return String(iso);
  }
}

type Props = {
  meta: Pick<
    PolicyConfigWorkingPayload,
    'status' | 'source' | 'version_number' | 'effective_date' | 'published_at' | 'created_at' | 'updated_at'
  > & { policy_version?: string | null };
  readOnlySnapshot: PolicyReadOnlySnapshot | null;
  editingLocked: boolean;
  dirty: boolean;
  saving: boolean;
  publishing: boolean;
  lastSavedAt: string | null;
  onSaveDraft: () => void;
  onPublishClick: () => void;
  onReload: () => void;
  onViewPublished: () => void;
  onBackToDraft: () => void;
  onOpenHistory: () => void;
  onStartEditing: () => void;
  /** When false, Publish is disabled even if the draft is saved (e.g. missing effective date). */
  publishAllowed?: boolean;
  publishDisabledHint?: string;
};

export const PolicyConfigHeader: React.FC<Props> = ({
  meta,
  readOnlySnapshot,
  editingLocked,
  dirty,
  saving,
  publishing,
  lastSavedAt,
  onSaveDraft,
  onPublishClick,
  onReload,
  onViewPublished,
  onBackToDraft,
  onOpenHistory,
  onStartEditing,
  publishAllowed = true,
  publishDisabledHint,
}) => {
  const isReadOnly = Boolean(readOnlySnapshot);
  const badge = statusBadgeVariant(meta.status, meta.source);
  const toneClass =
    badge.tone === 'success'
      ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
      : badge.tone === 'warning'
        ? 'bg-amber-50 text-amber-900 border-amber-200'
        : badge.tone === 'neutral'
          ? 'bg-slate-100 text-slate-700 border-slate-200'
          : 'bg-[#eef4f8] text-[#0b2b43] border-[#cfe0eb]';

  const draftEditing =
    !isReadOnly && !editingLocked && (meta.status || '').toLowerCase() === 'draft';

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-[#0b2b43]">Compensation &amp; Allowance</h1>
          <p className="text-sm text-[#4b5563] mt-1 max-w-2xl">
            Configure structured allowances and caps. Save drafts as you go; publish when ready—published matrices
            are read-only for employees.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {isReadOnly ? (
            <span className="inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium bg-slate-100 text-slate-800 border-slate-200">
              {readOnlySnapshot?.title}
            </span>
          ) : (
            <>
              {(meta.status || '').toLowerCase() === 'draft' && (
                <Badge variant="warning">Draft — not yet published</Badge>
              )}
              <span
                className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium ${toneClass}`}
              >
                {badge.label}
              </span>
            </>
          )}
          {dirty && !isReadOnly && <Badge variant="warning">Unsaved changes</Badge>}
        </div>
      </div>

      {draftEditing && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
          You are editing a <strong>draft</strong>. Nothing is visible to employees until you publish. Save draft to
          persist your work; use Publish when the effective date and content are final.
        </div>
      )}

      {isReadOnly && readOnlySnapshot?.subtitle && (
        <div className="rounded-lg border border-[#e2e8f0] bg-[#f8fafc] px-4 py-3 text-sm text-[#475569]">
          {readOnlySnapshot.subtitle}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        {!isReadOnly && (
          <>
            <Button variant="primary" disabled={editingLocked || saving || !dirty} onClick={onSaveDraft}>
              {saving ? 'Saving…' : 'Save draft'}
            </Button>
            <Button
              variant="outline"
              disabled={editingLocked || publishing || dirty || !publishAllowed}
              onClick={onPublishClick}
              title={
                dirty
                  ? 'Save draft before publishing'
                  : !publishAllowed
                    ? publishDisabledHint || 'Complete publish requirements'
                    : undefined
              }
            >
              Publish…
            </Button>
            <Button variant="outline" disabled={saving} onClick={onReload}>
              Cancel changes / Reload
            </Button>
            <Button variant="outline" onClick={onViewPublished}>
              View published version
            </Button>
          </>
        )}
        {isReadOnly && (
          <Button variant="primary" onClick={onBackToDraft}>
            Back to draft workspace
          </Button>
        )}
        <Button variant="outline" onClick={onOpenHistory}>
          Version history
        </Button>
        {!isReadOnly && editingLocked && (
          <Button variant="outline" onClick={onStartEditing}>
            Create or open draft
          </Button>
        )}
      </div>

      <div className="rounded-lg border border-[#e2e8f0] bg-white p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
        <div>
          <div className="text-[#64748b] text-xs uppercase tracking-wide">Version #</div>
          <div className="font-medium text-[#0b2b43]">{meta.version_number ?? '—'}</div>
        </div>
        <div>
          <div className="text-[#64748b] text-xs uppercase tracking-wide">Policy version id</div>
          <div className="font-medium text-[#0b2b43] font-mono text-xs break-all">
            {meta.policy_version || '—'}
          </div>
        </div>
        <div>
          <div className="text-[#64748b] text-xs uppercase tracking-wide">Effective date</div>
          <div className="font-medium text-[#0b2b43]">{(meta.effective_date || '').slice(0, 10) || '—'}</div>
        </div>
        <div>
          <div className="text-[#64748b] text-xs uppercase tracking-wide">Published at</div>
          <div className="font-medium text-[#0b2b43]">{formatSavedAt(meta.published_at) || '—'}</div>
        </div>
        <div>
          <div className="text-[#64748b] text-xs uppercase tracking-wide">Created</div>
          <div className="font-medium text-[#0b2b43]">{formatSavedAt(meta.created_at) || '—'}</div>
        </div>
        <div>
          <div className="text-[#64748b] text-xs uppercase tracking-wide">Last updated (server)</div>
          <div className="font-medium text-[#0b2b43]">{formatSavedAt(meta.updated_at) || '—'}</div>
        </div>
        <div className="sm:col-span-2">
          <div className="text-[#64748b] text-xs uppercase tracking-wide">Last saved (this session)</div>
          <div className="font-medium text-[#0b2b43]">
            {lastSavedAt ? formatSavedAt(lastSavedAt) : '—'}
            {!lastSavedAt && (
              <span className="text-[#94a3b8] font-normal ml-1">(appears after a successful save)</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
