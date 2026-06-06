/**
 * Assignment debug panel - dev only.
 *
 * Verify case_assignments visibility under RLS. Already gated by
 * import.meta.env.DEV || VITE_DEV_TOOLS so it never reaches production
 * builds. Cosmetic change here: collapse it by default so the panel
 * doesn't dominate the case-summary page even in dev. The header always
 * shows "DEV ONLY" so anyone seeing it on a deployed env immediately
 * knows it's tooling, not a feature.
 */

import React, { useEffect, useState } from 'react';
import { Input } from '../components/antigravity/Input';
import { Button } from '../components/antigravity/Button';
import { useSearchParams } from 'react-router-dom';
import { Card } from '../components/antigravity';
import { getAssignmentById } from '../api/assignmentDebug';
import { supabase } from '../api/supabase';

const DEV_TOOLS = import.meta.env.DEV || import.meta.env.VITE_DEV_TOOLS === 'true';

interface AssignmentDebugPanelProps {
  assignmentIdFromRoute?: string;
}

type DebugResult = {
  found: boolean;
  row?: { employee_user_id: string | null; hr_user_id: string };
  current_user_id?: string;
  error?: string;
};

export const AssignmentDebugPanel: React.FC<AssignmentDebugPanelProps> = ({ assignmentIdFromRoute }) => {
  const [searchParams] = useSearchParams();
  const fromUrl = searchParams.get('assignmentId') || searchParams.get('caseId') || '';
  const prefill = assignmentIdFromRoute || fromUrl;
  const [assignmentId, setAssignmentId] = useState(prefill);
  const [result, setResult] = useState<DebugResult | null>(null);
  const [authUid, setAuthUid] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (prefill) setAssignmentId(prefill);
  }, [prefill]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const { data } = await supabase.auth.getSession();
      const uid = data?.session?.user?.id ?? null;
      if (!cancelled) setAuthUid(uid);
    })();
    return () => { cancelled = true; };
  }, []);

  const handleCheck = async () => {
    if (!assignmentId.trim()) return;
    setLoading(true);
    setResult(null);
    const { data, error } = await getAssignmentById(assignmentId.trim());
    setLoading(false);
    if (error) {
      setResult({ found: false, error });
    } else if (data) {
      setResult({
        found: data.found,
        row: data.row,
        current_user_id: data.current_user_id,
        error: data.error,
      });
    }
  };

  if (!DEV_TOOLS) return null;

  return (
    <Card padding="md" className="mt-6 border border-amber-200 bg-amber-50/30">
      <Button unstyled
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between text-left"
        aria-expanded={open}
      >
        <span className="text-xs font-medium text-amber-900">
          🛠 DEV ONLY — Assignment debug (RLS check)
        </span>
        <span className="text-xs text-amber-700">{open ? '▾ collapse' : '▸ expand'}</span>
      </Button>
      {!open && (
        <p className="mt-1 text-[11px] text-amber-700/80">
          Hidden in production builds. This panel verifies RLS visibility for the active assignment.
        </p>
      )}
      {open && (
        <div className="mt-3">
          <div className="text-xs text-[#6b7280] mb-3">
            Verify case_assignments visibility under RLS. Dev only.
          </div>
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <Input unstyled
              type="text"
              value={assignmentId}
              onChange={(v) => setAssignmentId(v)}
              placeholder="Assignment ID"
              className="flex-1 min-w-[200px] rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
            />
            <Button unstyled
              onClick={handleCheck}
              disabled={loading || !assignmentId.trim()}
              className="px-4 py-2 bg-[#0b2b43] text-white text-sm rounded-lg hover:bg-[#123651] disabled:opacity-50"
            >
              {loading ? 'Checking...' : 'Check as current user'}
            </Button>
          </div>
          {(authUid || result?.current_user_id) && (
            <div className="text-xs text-[#6b7280] mb-2">
              <strong>{result?.current_user_id ? 'Current user:' : 'auth.uid():'}</strong>{' '}
              {result?.current_user_id ?? authUid}
            </div>
          )}
          {result && (
            <div className="text-sm space-y-2 mt-3 p-3 bg-white rounded-lg border border-[#e2e8f0]">
              {result.error && (
                <div className="text-red-600">{result.error}</div>
              )}
              {!result.error && (
                <>
                  <div>
                    <strong>found:</strong> {result.found ? 'true' : 'false'}
                  </div>
                  {result.found && result.row && (
                    <>
                      <div>
                        <strong>employee_user_id:</strong>{' '}
                        {result.row.employee_user_id ?? 'null'}
                        {(authUid || result.current_user_id) && result.row.employee_user_id && (
                          <span className={result.row.employee_user_id === (result.current_user_id ?? authUid) ? ' text-green-600' : ''}>
                            {result.row.employee_user_id === (result.current_user_id ?? authUid) ? ' ✓ (matches)' : ''}
                          </span>
                        )}
                      </div>
                      <div>
                        <strong>hr_user_id:</strong> {result.row.hr_user_id}
                        {(authUid || result.current_user_id) && (
                          <span className={result.row.hr_user_id === (result.current_user_id ?? authUid) ? ' text-green-600' : ''}>
                            {result.row.hr_user_id === (result.current_user_id ?? authUid) ? ' ✓ (matches)' : ''}
                          </span>
                        )}
                      </div>
                    </>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      )}
    </Card>
  );
};
