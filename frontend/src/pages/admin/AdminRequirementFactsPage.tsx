/**
 * [AIQ-1092 / P4-03] Admin review UI for LLM-extracted requirement facts.
 * Lists candidates by status; an admin approves or rejects each (human-in-the-loop).
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Alert, Badge, Button, Card } from '../../components/antigravity';
import {
  listRequirementFacts,
  reviewRequirementFact,
  type RequirementFactCandidate,
  type RequirementFactStatus,
} from '../../api/requirementFacts';
import { AdminLayout } from './AdminLayout';

const STATUS_TABS: { value: RequirementFactStatus; label: string }[] = [
  { value: 'pending', label: 'Pending' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
];

// Confidence tiers (AIQ-1092 brief): green ≥0.8, yellow 0.5–0.8, red <0.5.
function confidenceVariant(score: number | null): 'success' | 'warning' | 'error' {
  const s = score ?? 0;
  if (s >= 0.8) return 'success';
  if (s >= 0.5) return 'warning';
  return 'error';
}

export const AdminRequirementFactsPage: React.FC = () => {
  const [tab, setTab] = useState<RequirementFactStatus>('pending');
  const [facts, setFacts] = useState<RequirementFactCandidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resolvingId, setResolvingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setFacts(await listRequirementFacts(tab));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load requirement facts.');
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    void load();
  }, [load]);

  const review = async (id: string, status: 'approved' | 'rejected') => {
    setResolvingId(id);
    setError(null);
    try {
      await reviewRequirementFact(id, status);
      setFacts((prev) => prev.filter((f) => f.id !== id)); // drops out of the current list
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Could not update this fact.');
    } finally {
      setResolvingId(null);
    }
  };

  return (
    <AdminLayout
      title="Requirement facts"
      subtitle="LLM extracts into requirement_fact_candidates. Approving a row here does not publish anything employees or HR see. The served catalog is Country requirements (requirement_items)."
    >
      {error && <Alert variant="error" className="mb-4">{error}</Alert>}

      <Card padding="lg">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <h2 className="text-lg font-semibold text-[#0b2b43]">Extracted facts</h2>
            <p className="text-sm text-[#6b7280] mt-1">
              Each fact was extracted from an official source. Check the confidence and source quote,
              then approve or reject.
            </p>
          </div>
          <div className="flex flex-wrap gap-1">
            {STATUS_TABS.map((s) => (
              <Button unstyled
                key={s.value}
                onClick={() => setTab(s.value)}
                className={`px-3 py-1 rounded-full border text-sm ${
                  tab === s.value
                    ? 'border-[#0b2b43] bg-[#0b2b43] text-white'
                    : 'border-[#cbd5e1] text-[#475569] hover:bg-[#f1f5f9]'
                }`}
              >
                {s.label}
              </Button>
            ))}
          </div>
        </div>

        {loading && facts.length === 0 ? (
          <div className="space-y-2 py-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-20 rounded-lg bg-[#f1f5f9] animate-pulse" />
            ))}
          </div>
        ) : facts.length === 0 ? (
          <div className="rounded-lg border border-dashed border-[#cbd5e1] py-6 text-center text-sm text-[#6b7280]">
            No {tab} facts.
          </div>
        ) : (
          <ul className="divide-y divide-[#e2e8f0] border border-[#e2e8f0] rounded-lg overflow-hidden bg-white">
            {facts.map((f) => {
              const saving = resolvingId === f.id;
              return (
                <li key={f.id} className="p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        {f.corridor && <Badge variant="info" size="sm">{f.corridor}</Badge>}
                        <Badge variant="neutral" size="sm">{f.requirement_type}</Badge>
                        <Badge variant={confidenceVariant(f.confidence_score)} size="sm">
                          {f.confidence_score != null ? `${Math.round(f.confidence_score * 100)}%` : 'n/a'}
                        </Badge>
                      </div>
                      <p className="mt-2 text-sm font-medium text-[#0b2b43]">{f.fact_text}</p>
                      {f.source_quote && (
                        <blockquote className="mt-2 border-l-2 border-[#cbd5e1] pl-3 text-sm italic text-[#475569]">
                          {f.source_quote}
                        </blockquote>
                      )}
                      <a
                        href={f.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-2 inline-block text-xs text-[#1f8e8b] hover:underline break-all"
                      >
                        {f.source_url}
                      </a>
                    </div>
                    {f.status === 'pending' && (
                      <div className="flex flex-wrap gap-2">
                        <Button variant="outline" onClick={() => void review(f.id, 'rejected')} disabled={saving}>
                          Reject
                        </Button>
                        <Button onClick={() => void review(f.id, 'approved')} disabled={saving}>
                          {saving ? 'Saving…' : 'Approve'}
                        </Button>
                      </div>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Card>
    </AdminLayout>
  );
};
