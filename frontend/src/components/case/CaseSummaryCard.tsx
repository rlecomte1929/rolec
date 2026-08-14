import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Badge } from '../antigravity';
import { getCaseAiSummary } from '../../api/caseSummary';

// AIQ-1697: AI-generated, PII-safe case summary for the HR case detail page.
// Fed by GET /api/hr/cases/{id}/ai-summary (backend proxy → case-summary Edge Function).
// Renders explicit loading / error / empty states so a live LLM hiccup (or an
// unconfigured key) degrades gracefully instead of blanking the page.
const Section: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div className="mt-3">
    <div className="text-xs font-semibold uppercase tracking-wide text-[#6b7280]">{label}</div>
    <div className="mt-1 text-sm text-[#0b2b43]">{children}</div>
  </div>
);

const List: React.FC<{ items: string[]; empty: string }> = ({ items, empty }) =>
  items.length === 0 ? (
    <span className="text-[#6b7280]">{empty}</span>
  ) : (
    <ul className="list-disc pl-5 space-y-1">
      {items.map((it, i) => <li key={i}>{it}</li>)}
    </ul>
  );

export const CaseSummaryCard: React.FC<{ caseId: string }> = ({ caseId }) => {
  const query = useQuery({
    queryKey: ['hr', 'case-ai-summary', caseId],
    enabled: !!caseId,
    retry: false, // a summary failure is shown as a state, not retried in a loop
    queryFn: () => getCaseAiSummary(caseId),
  });

  return (
    <Card padding="lg">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-sm font-semibold text-[#0b2b43]">AI case summary</span>
        <Badge variant="info">AI</Badge>
      </div>
      <p className="text-xs text-[#6b7280]">
        Generated from this case&apos;s structured status — a human reviews every case.
      </p>

      {query.isLoading && (
        <div className="mt-3 text-sm text-[#6b7280]">Generating summary…</div>
      )}

      {query.isError && (
        <div className="mt-3 text-sm text-[#6b7280]">
          Summary isn&apos;t available right now.
        </div>
      )}

      {query.data && (
        <>
          <Section label="Status">{query.data.summary.status}</Section>
          <Section label="Blockers">
            <List items={query.data.summary.blockers} empty="None flagged." />
          </Section>
          <Section label="Next actions">
            <List items={query.data.summary.next_actions} empty="Nothing outstanding." />
          </Section>
          <Section label="Cost variance">{query.data.summary.cost_variance}</Section>
        </>
      )}
    </Card>
  );
};
