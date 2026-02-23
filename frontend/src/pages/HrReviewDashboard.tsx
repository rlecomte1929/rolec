/**
 * Block 5: HR Review - Assigned cases from Supabase (case_assignments + wizard_cases)
 */

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '../components/AppShell';
import { Alert, Button, Card } from '../components/antigravity';
import { listAssignedCasesForReview } from '../api/review';
import type { AssignedCaseForReview } from '../api/review';
import { buildRoute } from '../navigation/routes';

export const HrReviewDashboard: React.FC = () => {
  const navigate = useNavigate();
  const [cases, setCases] = useState<AssignedCaseForReview[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const load = async () => {
    setIsLoading(true);
    setError('');
    const { data, error: err } = await listAssignedCasesForReview();
    if (err) {
      setError(err);
      setCases([]);
    } else {
      setCases(data ?? []);
    }
    setIsLoading(false);
  };

  useEffect(() => {
    load();
  }, []);

  const formatDate = (s: string | null) => {
    if (!s) return '—';
    try {
      return new Date(s).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return s;
    }
  };

  return (
    <AppShell title="Review Cases" subtitle="Assigned cases for feedback and review.">
      {error && <Alert variant="error">{error}</Alert>}
      {isLoading && <div className="text-sm text-[#6b7280]">Loading assigned cases...</div>}
      {!isLoading && cases.length === 0 && !error && (
        <Card padding="lg">
          <div className="text-[#0b2b43] font-medium">No assigned cases</div>
          <div className="text-sm text-[#6b7280] mt-1">
            Cases will appear here once you assign them to employees. Use the main HR Dashboard to create and assign cases.
          </div>
        </Card>
      )}
      {!isLoading && cases.length > 0 && (
        <div className="space-y-3">
          {cases.map((c) => (
            <Card key={c.id} padding="lg">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <div className="font-semibold text-[#0b2b43]">{c.caseName}</div>
                  <div className="text-sm text-[#6b7280] mt-1">
                    {c.origin} → {c.destination}
                  </div>
                  <div className="text-xs text-[#9ca3af] mt-1">
                    Target: {formatDate(c.targetMoveDate)} · Updated: {formatDate(c.lastUpdated)}
                  </div>
                </div>
                <Button onClick={() => navigate(buildRoute('hrReviewCase', { caseId: c.case_id }))}>
                  Open
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </AppShell>
  );
};
