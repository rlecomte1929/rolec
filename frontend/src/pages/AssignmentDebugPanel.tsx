/**
 * Assignment debug panel - dev only
 * Verify case_assignments visibility under RLS
 */

import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Card } from '../components/antigravity';
import { getAssignmentById } from '../api/assignmentDebug';
import { supabase } from '../api/supabase';

const DEV_TOOLS = import.meta.env.DEV || import.meta.env.VITE_DEV_TOOLS === 'true';

interface AssignmentDebugPanelProps {
  assignmentIdFromRoute?: string;
}

export const AssignmentDebugPanel: React.FC<AssignmentDebugPanelProps> = ({ assignmentIdFromRoute }) => {
  const [searchParams] = useSearchParams();
  const fromUrl = searchParams.get('assignmentId') || searchParams.get('caseId') || '';
  const prefill = assignmentIdFromRoute || fromUrl;
  const [assignmentId, setAssignmentId] = useState(prefill);
  const [result, setResult] = useState<{
    found: boolean;
    row?: { employee_user_id: string | null; hr_user_id: string };
    current_user_id?: string;
    error?: string;
  } | null>(null);
  const [authUid, setAuthUid] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

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
    <Card padding="lg" className="mt-6 border-2 border-amber-200 bg-amber-50/50">
      <div className="text-sm font-semibold text-[#0b2b43] mb-2">Assignment debug</div>
      <div className="text-xs text-[#6b7280] mb-3">
        Verify case_assignments visibility under RLS. Dev only.
      </div>
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <input
          type="text"
          value={assignmentId}
          onChange={(e) => setAssignmentId(e.target.value)}
          placeholder="Assignment ID"
          className="flex-1 min-w-[200px] rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
        />
        <button
          onClick={handleCheck}
          disabled={loading || !assignmentId.trim()}
          className="px-4 py-2 bg-[#0b2b43] text-white text-sm rounded-lg hover:bg-[#123651] disabled:opacity-50"
        >
          {loading ? 'Checking...' : 'Check as current user'}
        </button>
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
    </Card>
  );
};
