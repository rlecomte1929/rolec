/**
 * HrProviderGrid — Provider × Case status matrix for HR (AIQ-14).
 * Fetches the grid from the backend and renders ProviderStatusGrid.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { AppShell } from '../components/AppShell';
import { ProviderStatusGrid } from '../components/providers/ProviderStatusGrid';
import { hrAPI } from '../api/client';
import type { ProviderGridRow } from '../api/client';

export const HrProviderGrid: React.FC = () => {
  const [rows, setRows] = useState<ProviderGridRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchGrid = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await hrAPI.getProviderStatusGrid();
      setRows(data.rows);
      setLastRefreshed(new Date());
    } catch {
      setError('Failed to load provider grid. Please try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchGrid();
  }, [fetchGrid]);

  return (
    <AppShell>
      <div className="px-6 py-6 max-w-7xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold text-slate-900">Provider Status Grid</h1>
          <p className="text-sm text-slate-500 mt-1">
            Real-time status of all providers across active cases.
          </p>
        </div>

        {error && (
          <div className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <ProviderStatusGrid
          rows={rows}
          loading={loading}
          lastRefreshed={lastRefreshed}
          onRefresh={fetchGrid}
        />
      </div>
    </AppShell>
  );
};
