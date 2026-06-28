/**
 * RfqModal — AIQ-40-C
 *
 * Modal form HR fills out to send a structured quote request to a vendor.
 * Opens after clicking "Request quote" in VendorBrowsePanel.
 */
import React, { useEffect, useState } from 'react';
import { Input } from '../antigravity/Input';
import { Button } from '../antigravity/Button';
import { hrAPI } from '../../api/client';
import { buildImmigrationSummary, type ImmigrationContext } from './immigrationContext';

type Vendor = {
  id: string;
  name: string;
  service_categories: string[];
  contact_email: string;
};

interface Props {
  vendor: Vendor | null;
  caseId: string;
  /** IMM-15: when present, pre-fills the form from the immigration case */
  immigrationContext?: ImmigrationContext | null;
  onClose: () => void;
  onSent: (vendorName: string) => void;
}

export const RfqModal: React.FC<Props> = ({ vendor, caseId, immigrationContext, onClose, onSent }) => {
  const [serviceCategory, setServiceCategory] = useState(
    vendor?.service_categories?.[0] ?? ''
  );
  const [moveDate, setMoveDate] = useState('');
  const [budgetRange, setBudgetRange] = useState('');
  const [specialRequirements, setSpecialRequirements] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  // IMM-15: seed the form when the modal opens from the immigration panel.
  // HR can freely edit the pre-filled summary before sending.
  useEffect(() => {
    if (!vendor || !immigrationContext) return;
    setSpecialRequirements(buildImmigrationSummary(immigrationContext));
    if (immigrationContext.move_date) setMoveDate(immigrationContext.move_date);
    if (immigrationContext.visa_type) setServiceCategory('Immigration/visa');
    // Re-seed each time a new vendor is selected (i.e. each open).
  }, [vendor, immigrationContext]);

  if (!vendor) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!serviceCategory) {
      setError('Please select a service category.');
      return;
    }
    setError('');
    setSubmitting(true);
    try {
      await hrAPI.createRfqRequest({
        case_id: caseId,
        vendor_id: vendor.id,
        service_category: serviceCategory,
        move_date: moveDate || undefined,
        budget_range: budgetRange || undefined,
        special_requirements: specialRequirements || undefined,
        // IMM-15: carry the structured immigration context onto the RFQ row
        ...(immigrationContext
          ? {
              visa_type: immigrationContext.visa_type,
              corridor_from: immigrationContext.corridor_from,
              corridor_to: immigrationContext.corridor_to,
              employee_nationality: immigrationContext.employee_nationality,
              has_dependents: immigrationContext.has_dependents,
              risk_flags: immigrationContext.risk_flags?.map((f) => f.flag_type),
            }
          : {}),
      });
      onSent(vendor.name);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to send quote request.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      {/* Backdrop */}
      {/* eslint-disable-next-line local/no-clickable-div -- presentational mouse-dismiss backdrop (aria-hidden); the modal is keyboard-dismissible via its own controls */}
      <div
        className="fixed inset-0 bg-black/40 z-60"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal */}
      <div
        className="fixed inset-0 z-70 flex items-center justify-center p-4"
        role="dialog"
        aria-label={`Send quote request to ${vendor.name}`}
      >
        <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-[#e2e8f0]">
            <div>
              <h2 className="text-base font-semibold text-[#0b2b43]">Send quote request</h2>
              <p className="text-xs text-[#64748b] mt-0.5">to {vendor.name}</p>
            </div>
            <Button unstyled
              type="button"
              onClick={onClose}
              className="rounded-lg p-2 text-[#94a3b8] hover:bg-[#f1f5f9] transition-colors"
              aria-label="Close"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </Button>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
            {/* Service category */}
            <div>
              <label className="block text-xs font-medium text-[#374151] mb-1" htmlFor="rfq-category">
                Service needed <span className="text-[#ef4444]">*</span>
              </label>
              <select
                id="rfq-category"
                value={serviceCategory}
                onChange={(e) => setServiceCategory(e.target.value)}
                className="w-full rounded-lg border border-[#d1d5db] px-3 py-2 text-sm text-[#374151] focus:outline-none focus:ring-2 focus:ring-[#2563eb]"
                required
              >
                <option value="">Select…</option>
                {(vendor.service_categories.length > 0
                  ? vendor.service_categories
                  : ['Housing search', 'Immigration/visa', 'Moving & shipping', 'School search', 'Destination orientation']
                ).map((cat) => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
            </div>

            {/* Move date */}
            <div>
              <label className="block text-xs font-medium text-[#374151] mb-1" htmlFor="rfq-move-date">
                Move date <span className="text-[#94a3b8] font-normal">(optional)</span>
              </label>
              <Input unstyled
                id="rfq-move-date"
                type="date"
                value={moveDate}
                onChange={(v) => setMoveDate(v)}
                className="w-full rounded-lg border border-[#d1d5db] px-3 py-2 text-sm text-[#374151] focus:outline-none focus:ring-2 focus:ring-[#2563eb]"
              />
            </div>

            {/* Budget range */}
            <div>
              <label className="block text-xs font-medium text-[#374151] mb-1" htmlFor="rfq-budget">
                Budget range <span className="text-[#94a3b8] font-normal">(optional)</span>
              </label>
              <Input unstyled
                id="rfq-budget"
                type="text"
                value={budgetRange}
                onChange={(v) => setBudgetRange(v)}
                placeholder="e.g. €2,000–€3,000/month"
                maxLength={100}
                className="w-full rounded-lg border border-[#d1d5db] px-3 py-2 text-sm text-[#374151] placeholder-[#94a3b8] focus:outline-none focus:ring-2 focus:ring-[#2563eb]"
              />
            </div>

            {/* Special requirements */}
            <div>
              <label className="block text-xs font-medium text-[#374151] mb-1" htmlFor="rfq-requirements">
                Special requirements <span className="text-[#94a3b8] font-normal">(optional)</span>
              </label>
              <textarea
                id="rfq-requirements"
                value={specialRequirements}
                onChange={(e) => setSpecialRequirements(e.target.value)}
                rows={3}
                maxLength={500}
                placeholder="e.g. Employee has 2 children, needs furnished accommodation near city centre…"
                className="w-full rounded-lg border border-[#d1d5db] px-3 py-2 text-sm text-[#374151] placeholder-[#94a3b8] focus:outline-none focus:ring-2 focus:ring-[#2563eb] resize-none"
              />
            </div>

            {error && (
              <div className="rounded-lg border border-[#fecaca] bg-[#fef2f2] px-4 py-3 text-sm text-[#dc2626]" role="alert">
                {error}
              </div>
            )}

            <div className="flex gap-3 pt-1">
              <Button unstyled
                type="submit"
                disabled={submitting}
                className="flex-1 rounded-lg bg-[#0b2b43] px-4 py-2.5 text-sm font-medium text-white hover:bg-[#1e4d6b] disabled:opacity-50 transition-colors"
              >
                {submitting ? 'Sending…' : 'Send quote request'}
              </Button>
              <Button unstyled
                type="button"
                onClick={onClose}
                className="rounded-lg border border-[#d1d5db] px-4 py-2.5 text-sm font-medium text-[#374151] hover:bg-[#f8fafc] transition-colors"
              >
                Cancel
              </Button>
            </div>
          </form>
        </div>
      </div>
    </>
  );
};

export default RfqModal;
