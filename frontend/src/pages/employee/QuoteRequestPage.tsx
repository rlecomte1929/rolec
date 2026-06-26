/**
 * QuoteRequestPage — Step 4 of the employee 5-step workflow.
 *
 * Employee selects service categories, adds notes and an optional budget
 * range, then submits a quote request that HR can see in their case detail.
 *
 * Route: /employee/quote-request  (see routes.ts → employeeQuoteRequest)
 */
import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Input } from '../../components/antigravity/Input';
import { AppShell } from '../../components/AppShell';
import { Card, Button } from '../../components/antigravity';
import { useEmployeeAssignment } from '../../contexts/EmployeeAssignmentContext';
import { employeeAPI, hrAPI } from '../../api/client';
import { buildRoute } from '../../navigation/routes';

const FALLBACK_CATEGORIES = [
  'Housing search',
  'Immigration/visa',
  'Moving & shipping',
  'School search',
  'Destination orientation',
  'Other',
];

export const QuoteRequestPage: React.FC = () => {
  const navigate = useNavigate();
  const { linkedSummaries, isLoading: assignmentLoading } = useEmployeeAssignment();

  // Derive case_id from the primary linked assignment
  const primarySummary = linkedSummaries[0] ?? null;
  const caseId = primarySummary?.case_id ?? null;

  // Form state
  const [categories, setCategories] = useState<string[]>([]);
  const [notes, setNotes] = useState('');
  const [budgetRange, setBudgetRange] = useState('');

  // Submission state
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load service categories from API (falls back to FALLBACK_CATEGORIES).
  const categoriesQuery = useQuery({
    queryKey: ['service-categories'],
    queryFn: () => hrAPI.getServiceCategories(),
  });
  const fetchedCategories = categoriesQuery.data?.service_categories;
  const availableCategories =
    fetchedCategories && fetchedCategories.length ? fetchedCategories : FALLBACK_CATEGORIES;

  const toggleCategory = (cat: string) => {
    setCategories((prev) =>
      prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!caseId) {
      setError('No active case found. Please link your assignment first.');
      return;
    }
    if (categories.length === 0) {
      setError('Please select at least one service category.');
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      await employeeAPI.createQuoteRequest({
        case_id: caseId,
        service_categories: categories,
        notes: notes.trim() || undefined,
        budget_range: budgetRange.trim() || undefined,
      });
      setSuccess(true);
      // Reset form
      setCategories([]);
      setNotes('');
      setBudgetRange('');
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : 'Failed to submit quote request. Please try again.';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  if (assignmentLoading) {
    return (
      <AppShell title="Request quotes" subtitle="Step 4 of your relocation journey">
        <Card padding="lg" className="border border-[#e2e8f0]">
          <div className="flex items-center gap-3 text-sm text-[#475569]" role="status" aria-live="polite">
            <div className="h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-[#0b2b43] border-t-transparent" />
            <span>Loading your assignment…</span>
          </div>
        </Card>
      </AppShell>
    );
  }

  if (!caseId) {
    return (
      <AppShell title="Request quotes" subtitle="Step 4 of your relocation journey">
        <Card padding="lg">
          <p className="text-sm text-[#6b7280] mb-4">
            No active relocation case found. Please complete Step 1 (fill your case) first.
          </p>
          <Button variant="outline" onClick={() => navigate(buildRoute('employeeJourney'))}>
            Back to journey
          </Button>
        </Card>
      </AppShell>
    );
  }

  if (success) {
    return (
      <AppShell title="Request quotes" subtitle="Step 4 of your relocation journey">
        <Card padding="lg" className="border border-[#bbf7d0] bg-[#f0fdf4]">
          <div className="flex items-start gap-3">
            <span className="text-2xl">✓</span>
            <div>
              <p className="font-semibold text-[#166534] mb-1">Quote request submitted</p>
              <p className="text-sm text-[#15803d]">
                Your HR contact will respond shortly. You can track requests or submit another
                for different service categories.
              </p>
            </div>
          </div>
          <div className="flex gap-3 mt-5">
            <Button onClick={() => setSuccess(false)}>Submit another request</Button>
            <Button variant="outline" onClick={() => navigate(buildRoute('employeeJourney'))}>
              Back to journey
            </Button>
          </div>
        </Card>
      </AppShell>
    );
  }

  return (
    <AppShell
      title="Request quotes"
      subtitle="Tell your HR team which services you need quotes for. They'll coordinate with vendors on your behalf."
    >
      <form onSubmit={handleSubmit} noValidate>
        <div className="space-y-6">
          {/* Service categories */}
          <Card padding="lg" className="border border-[#e2e8f0]">
            <p className="text-sm font-semibold text-[#0b2b43] mb-3">
              Which services do you need? <span className="text-[#ef4444]">*</span>
            </p>
            <p className="text-xs text-[#64748b] mb-4">Select all that apply.</p>
            <div className="flex flex-wrap gap-2">
              {availableCategories.map((cat) => {
                const selected = categories.includes(cat);
                return (
                  <Button unstyled
                    key={cat}
                    type="button"
                    onClick={() => toggleCategory(cat)}
                    className={[
                      'rounded-full border px-4 py-2 text-sm font-medium transition-colors',
                      selected
                        ? 'border-[#2563eb] bg-[#eff6ff] text-[#1d4ed8]'
                        : 'border-[#cbd5e1] bg-white text-[#374151] hover:bg-[#f8fafc]',
                    ].join(' ')}
                    aria-pressed={selected}
                  >
                    {cat}
                  </Button>
                );
              })}
            </div>
          </Card>

          {/* Notes */}
          <Card padding="lg" className="border border-[#e2e8f0]">
            <label className="block text-sm font-semibold text-[#0b2b43] mb-2" htmlFor="qr-notes">
              Notes / requirements
              <span className="ml-1 font-normal text-[#64748b]">(optional)</span>
            </label>
            <textarea
              id="qr-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              maxLength={2000}
              rows={4}
              placeholder="e.g. Move-in date mid-August, need furnished flat near city centre, 2 kids aged 6 and 9…"
              className="w-full rounded-lg border border-[#cbd5e1] px-3 py-2 text-sm text-[#374151] placeholder-[#94a3b8] focus:outline-none focus:ring-2 focus:ring-[#2563eb] resize-none"
            />
            <p className="text-xs text-[#94a3b8] mt-1 text-right">{notes.length}/2000</p>
          </Card>

          {/* Budget range */}
          <Card padding="lg" className="border border-[#e2e8f0]">
            <label className="block text-sm font-semibold text-[#0b2b43] mb-2" htmlFor="qr-budget">
              Budget range
              <span className="ml-1 font-normal text-[#64748b]">(optional)</span>
            </label>
            <Input unstyled
              id="qr-budget"
              type="text"
              value={budgetRange}
              onChange={(v) => setBudgetRange(v)}
              maxLength={100}
              placeholder="e.g. €1,500–€2,500/month for housing"
              className="w-full rounded-lg border border-[#cbd5e1] px-3 py-2 text-sm text-[#374151] placeholder-[#94a3b8] focus:outline-none focus:ring-2 focus:ring-[#2563eb]"
            />
          </Card>

          {/* Error */}
          {error && (
            <div className="rounded-lg border border-[#fecaca] bg-[#fef2f2] px-4 py-3 text-sm text-[#dc2626]" role="alert">
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3">
            <Button type="submit" disabled={submitting}>
              {submitting ? 'Submitting…' : 'Submit quote request'}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => navigate(buildRoute('employeeJourney'))}
            >
              Cancel
            </Button>
          </div>
        </div>
      </form>
    </AppShell>
  );
};
