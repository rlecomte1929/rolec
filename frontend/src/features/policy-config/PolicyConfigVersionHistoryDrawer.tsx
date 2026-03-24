import React from 'react';
import { Button } from '../../components/antigravity';
import type { PolicyConfigHistoryVersion } from './types';

function formatTs(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
  } catch {
    return iso;
  }
}

type Props = {
  open: boolean;
  onClose: () => void;
  versions: PolicyConfigHistoryVersion[];
  loading: boolean;
  onViewVersion: (versionId: string, meta: Pick<PolicyConfigHistoryVersion, 'version_number' | 'status' | 'effective_date'>) => void;
};

export const PolicyConfigVersionHistoryDrawer: React.FC<Props> = ({
  open,
  onClose,
  versions,
  loading,
  onViewVersion,
}) => {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        type="button"
        className="absolute inset-0 bg-black/30"
        aria-label="Close history"
        onClick={onClose}
      />
      <div className="relative w-full max-w-md h-full bg-white shadow-xl border-l border-[#e2e8f0] flex flex-col">
        <div className="p-4 border-b border-[#e2e8f0] flex items-center justify-between gap-2">
          <h2 className="text-lg font-semibold text-[#0b2b43]">Version history</h2>
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          {loading ? (
            <p className="text-sm text-[#64748b]">Loading…</p>
          ) : versions.length === 0 ? (
            <p className="text-sm text-[#64748b]">No versions yet.</p>
          ) : (
            <ul className="space-y-3">
              {versions.map((v) => {
                const st = (v.status || '').toLowerCase();
                const canOpenSnapshot = st === 'published' || st === 'archived';
                return (
                  <li
                    key={v.id}
                    className="rounded-lg border border-[#e2e8f0] p-3 text-sm bg-[#fafbfc] space-y-2"
                  >
                    <div className="font-medium text-[#0b2b43]">
                      Version {v.version_number}{' '}
                      <span className="text-[#64748b] font-normal">· {v.status}</span>
                    </div>
                    <div className="text-[#64748b] text-xs space-y-0.5">
                      <div>
                        <span className="text-[#94a3b8]">Effective date:</span> {v.effective_date || '—'}
                      </div>
                      <div>
                        <span className="text-[#94a3b8]">Created:</span> {formatTs(v.created_at)}
                      </div>
                      <div>
                        <span className="text-[#94a3b8]">Published:</span> {formatTs(v.published_at)}
                      </div>
                      <div>
                        <span className="text-[#94a3b8]">Created by:</span> {v.created_by || '—'}
                      </div>
                    </div>
                    {canOpenSnapshot && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="w-full"
                        onClick={() =>
                          onViewVersion(v.id, {
                            version_number: v.version_number,
                            status: v.status,
                            effective_date: v.effective_date,
                          })
                        }
                      >
                        View read-only
                      </Button>
                    )}
                    {st === 'draft' && (
                      <p className="text-xs text-[#64748b]">Current draft is edited in the main workspace.</p>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
};
