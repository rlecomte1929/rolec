import React, { useCallback, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { policyConfigMatrixAPI } from '../../../api/client';
import type { PolicyConfigHistoryVersion } from '../../policy-config/types';

type Props = { companyId: string; policyConfigHref: string };

/** Lazy-loaded structured (Compensation & Allowance) matrix version list — secondary traceability. */
export const PolicyWorkspaceStructuredHistoryDetails: React.FC<Props> = ({ companyId, policyConfigHref }) => {
  const [rows, setRows] = useState<PolicyConfigHistoryVersion[]>([]);
  const [loading, setLoading] = useState(false);
  const loaded = useRef(false);

  const onOpen = useCallback(async () => {
    if (loaded.current || !companyId) return;
    loaded.current = true;
    setLoading(true);
    try {
      const res = await policyConfigMatrixAPI.adminHistory(companyId);
      setRows((res.versions ?? []) as PolicyConfigHistoryVersion[]);
    } catch {
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [companyId]);

  return (
    <details
      className="rounded-lg border border-[#e8ecf1] bg-[#fafbfc] text-sm"
      onToggle={(e) => {
        if ((e.target as HTMLDetailsElement).open) void onOpen();
      }}
    >
      <summary className="cursor-pointer select-none px-3 py-2 font-medium text-[#0b2b43] text-sm">
        Structured matrix version history
      </summary>
      <div className="px-3 pb-3 border-t border-[#eef2f7] pt-2">
        {loading ? (
          <p className="text-xs text-[#64748b]">Loading…</p>
        ) : rows.length === 0 ? (
          <p className="text-xs text-[#64748b]">No versions on file yet.</p>
        ) : (
          <div className="overflow-x-auto max-h-44 overflow-y-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-[#64748b] border-b border-[#e2e8f0]">
                  <th className="py-1.5 pr-2">Ver.</th>
                  <th className="py-1.5 pr-2">Status</th>
                  <th className="py-1.5 pr-2">Effective</th>
                  <th className="py-1.5 pr-2">Published</th>
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, 15).map((v) => (
                  <tr key={v.id} className="border-b border-[#f1f5f9]">
                    <td className="py-1.5 pr-2">{v.version_number}</td>
                    <td className="py-1.5 pr-2">{v.status}</td>
                    <td className="py-1.5 pr-2">{v.effective_date ?? '—'}</td>
                    <td className="py-1.5 pr-2">
                      {v.published_at ? String(v.published_at).slice(0, 10) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Link to={policyConfigHref} className="inline-block mt-2 text-xs text-[#0b2b43] hover:underline">
          Full editor &amp; publish flow
        </Link>
      </div>
    </details>
  );
};
