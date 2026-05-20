/**
 * Step 3 — Configure required documents per visa type.
 * HR selects which documents must be uploaded for each visa/permit category.
 */
import React, { useState } from 'react';
import type { PolicyDocuments } from '../../types/relocationPolicy';
import { Button } from '../../components/antigravity';

// Visa types mapped to human-readable labels.
const VISA_TYPES: { key: string; label: string; description: string }[] = [
  {
    key: 'work_permit',
    label: 'Work permit',
    description: 'Standard employment-based work authorisation',
  },
  {
    key: 'eu_blue_card',
    label: 'EU Blue Card',
    description: 'Highly-skilled worker permit within the European Union',
  },
  {
    key: 'intra_company_transfer',
    label: 'Intra-company transfer',
    description: 'Employee moves within the same multinational group',
  },
  {
    key: 'dependent_visa',
    label: 'Dependent / family visa',
    description: 'For accompanying family members',
  },
  {
    key: 'business_visa',
    label: 'Business visa (short-stay)',
    description: 'Short-term assignment or business trip',
  },
  {
    key: 'permanent_residence',
    label: 'Permanent residence',
    description: 'Long-term settlement permit',
  },
];

// Common documents — HR can also type custom ones.
const COMMON_DOCUMENTS: { key: string; label: string }[] = [
  { key: 'passport_copy',          label: 'Passport copy' },
  { key: 'employment_contract',    label: 'Employment contract' },
  { key: 'offer_letter',           label: 'Offer letter' },
  { key: 'cv_resume',              label: 'CV / Résumé' },
  { key: 'educational_qualifications', label: 'Educational qualifications' },
  { key: 'proof_of_accommodation', label: 'Proof of accommodation' },
  { key: 'medical_clearance',      label: 'Medical clearance certificate' },
  { key: 'background_check',       label: 'Background check' },
  { key: 'tax_registration',       label: 'Tax registration number' },
  { key: 'social_security_number', label: 'Social security / NI number' },
  { key: 'bank_account_details',   label: 'Bank account details' },
  { key: 'relocation_agreement',   label: 'Signed relocation agreement' },
];

const Tip: React.FC<{ text: string }> = ({ text }) => (
  <span className="relative group ml-1 inline-flex items-center cursor-help">
    <span className="w-4 h-4 rounded-full bg-slate-200 text-slate-500 text-xs flex items-center justify-center font-bold select-none">?</span>
    <span className="absolute left-6 top-0 z-20 hidden group-hover:block bg-[#0b2b43] text-white text-xs rounded px-2 py-1 w-60 shadow-lg pointer-events-none">
      {text}
    </span>
  </span>
);

type Props = {
  documents: PolicyDocuments;
  onChange: (documents: PolicyDocuments) => void;
  onBack: () => void;
  onNext: () => void;
};

export const StepDocuments: React.FC<Props> = ({
  documents,
  onChange,
  onBack,
  onNext,
}) => {
  const [customInputs, setCustomInputs] = useState<Record<string, string>>({});
  const [expandedVisa, setExpandedVisa] = useState<string | null>(VISA_TYPES[0].key);

  const getList = (visaKey: string): string[] => documents[visaKey] ?? [];

  const toggleDoc = (visaKey: string, docKey: string) => {
    const current = getList(visaKey);
    const updated = current.includes(docKey)
      ? current.filter((d) => d !== docKey)
      : [...current, docKey];
    onChange({ ...documents, [visaKey]: updated });
  };

  const addCustomDoc = (visaKey: string) => {
    const val = (customInputs[visaKey] ?? '').trim();
    if (!val) return;
    const current = getList(visaKey);
    if (!current.includes(val)) {
      onChange({ ...documents, [visaKey]: [...current, val] });
    }
    setCustomInputs({ ...customInputs, [visaKey]: '' });
  };

  const removeDoc = (visaKey: string, docKey: string) => {
    onChange({
      ...documents,
      [visaKey]: getList(visaKey).filter((d) => d !== docKey),
    });
  };

  const docLabel = (docKey: string): string =>
    COMMON_DOCUMENTS.find((d) => d.key === docKey)?.label ?? docKey;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-[#0b2b43]">
          Required documents by visa type
          <Tip text="Set which documents employees must submit depending on their visa or permit type. These will appear as a checklist in the employee portal." />
        </h2>
        <p className="text-sm text-slate-500 mt-1">
          For each visa or permit type, choose which documents employees must
          provide. Click a visa type to expand it.
        </p>
      </div>

      <div className="space-y-3">
        {VISA_TYPES.map((visa) => {
          const isOpen = expandedVisa === visa.key;
          const selected = getList(visa.key);

          return (
            <div
              key={visa.key}
              className="border border-slate-200 rounded-lg overflow-hidden"
            >
              {/* Accordion header */}
              <button
                type="button"
                onClick={() => setExpandedVisa(isOpen ? null : visa.key)}
                className="w-full flex items-center justify-between px-4 py-3 bg-white hover:bg-slate-50 transition-colors text-left"
                aria-expanded={isOpen}
              >
                <div>
                  <span className="font-medium text-slate-800">{visa.label}</span>
                  <span className="ml-2 text-xs text-slate-400">{visa.description}</span>
                </div>
                <div className="flex items-center gap-2">
                  {selected.length > 0 && (
                    <span className="text-xs bg-[#0b2b43] text-white rounded-full px-2 py-0.5">
                      {selected.length} required
                    </span>
                  )}
                  <svg
                    className={`w-4 h-4 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                  </svg>
                </div>
              </button>

              {/* Accordion body */}
              {isOpen && (
                <div className="px-4 pb-4 pt-2 bg-white border-t border-slate-100 space-y-4">
                  {/* Common document checkboxes */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {COMMON_DOCUMENTS.map((doc) => {
                      const checked = selected.includes(doc.key);
                      return (
                        <label
                          key={doc.key}
                          className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer hover:text-[#0b2b43] transition-colors"
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleDoc(visa.key, doc.key)}
                            className="w-4 h-4 accent-[#0b2b43] cursor-pointer"
                          />
                          {doc.label}
                        </label>
                      );
                    })}
                  </div>

                  {/* Custom document tags */}
                  {selected.filter((d) => !COMMON_DOCUMENTS.find((c) => c.key === d)).length > 0 && (
                    <div className="flex flex-wrap gap-2 pt-1">
                      {selected
                        .filter((d) => !COMMON_DOCUMENTS.find((c) => c.key === d))
                        .map((d) => (
                          <span
                            key={d}
                            className="inline-flex items-center gap-1 bg-slate-100 text-slate-700 text-xs rounded-full px-2 py-1"
                          >
                            {d}
                            <button
                              type="button"
                              onClick={() => removeDoc(visa.key, d)}
                              className="text-slate-400 hover:text-red-500 transition-colors ml-0.5"
                              aria-label={`Remove ${d}`}
                            >
                              ×
                            </button>
                          </span>
                        ))}
                    </div>
                  )}

                  {/* Add custom document */}
                  <div className="flex gap-2 items-center pt-1">
                    <input
                      type="text"
                      value={customInputs[visa.key] ?? ''}
                      onChange={(e) =>
                        setCustomInputs({ ...customInputs, [visa.key]: e.target.value })
                      }
                      onKeyDown={(e) => e.key === 'Enter' && addCustomDoc(visa.key)}
                      placeholder="Add a custom document…"
                      className="flex-1 border border-slate-200 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#0b2b43] focus:ring-offset-1"
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => addCustomDoc(visa.key)}
                      type="button"
                    >
                      Add
                    </Button>
                  </div>

                  {/* Summary */}
                  {selected.length > 0 && (
                    <p className="text-xs text-slate-400">
                      Required:{' '}
                      {selected.map((d) => docLabel(d)).join(', ')}
                    </p>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="flex justify-between pt-2">
        <Button variant="outline" onClick={onBack} type="button">
          ← Back
        </Button>
        <Button onClick={onNext} type="button">
          Next: Vendors →
        </Button>
      </div>
    </div>
  );
};
