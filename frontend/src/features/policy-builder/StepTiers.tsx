/**
 * Step 1 — Define relocation tiers.
 * HR adds/edits/removes tiers and assigns which employee levels qualify.
 */
import React, { useState } from 'react';
import type { PolicyTier } from '../../types/relocationPolicy';
import { Button, Input } from '../../components/antigravity';

// Canonical employee levels used across the policy config module.
const EMPLOYEE_LEVELS = [
  { value: 'entry',    label: 'Entry level' },
  { value: 'manager',  label: 'Manager' },
  { value: 'director', label: 'Director' },
  { value: 'vp',       label: 'VP' },
  { value: 'c_suite',  label: 'C-Suite / Executive' },
];

function emptyTier(): PolicyTier {
  return { id: crypto.randomUUID(), name: '', qualifying_levels: [], description: '' };
}

type ValidationErrors = Partial<Record<string, string>>;

function validateTiers(tiers: PolicyTier[]): ValidationErrors {
  const errs: ValidationErrors = {};
  if (tiers.length === 0) {
    errs['_root'] = 'Add at least one relocation tier before continuing.';
  }
  tiers.forEach((t, i) => {
    if (!t.name.trim()) errs[`name_${i}`] = 'Tier name is required.';
    if (t.qualifying_levels.length === 0) errs[`levels_${i}`] = 'Select at least one level.';
  });
  return errs;
}

// Tooltip component for inline help text.
const Tip: React.FC<{ text: string }> = ({ text }) => (
  <span className="relative group ml-1 inline-flex items-center cursor-help">
    <span className="w-4 h-4 rounded-full bg-slate-200 text-slate-500 text-xs flex items-center justify-center font-bold select-none">?</span>
    <span className="absolute left-6 top-0 z-20 hidden group-hover:block bg-[#0b2b43] text-white text-xs rounded px-2 py-1 w-56 shadow-lg pointer-events-none">
      {text}
    </span>
  </span>
);

type Props = {
  tiers: PolicyTier[];
  onChange: (tiers: PolicyTier[]) => void;
  onNext: () => void;
};

export const StepTiers: React.FC<Props> = ({ tiers, onChange, onNext }) => {
  const [errors, setErrors] = useState<ValidationErrors>({});

  const addTier = () => onChange([...tiers, emptyTier()]);

  const removeTier = (idx: number) =>
    onChange(tiers.filter((_, i) => i !== idx));

  const updateTier = (idx: number, patch: Partial<PolicyTier>) =>
    onChange(tiers.map((t, i) => (i === idx ? { ...t, ...patch } : t)));

  const toggleLevel = (idx: number, level: string) => {
    const t = tiers[idx];
    const has = t.qualifying_levels.includes(level);
    updateTier(idx, {
      qualifying_levels: has
        ? t.qualifying_levels.filter((l) => l !== level)
        : [...t.qualifying_levels, level],
    });
  };

  const handleNext = () => {
    const errs = validateTiers(tiers);
    setErrors(errs);
    if (Object.keys(errs).length === 0) onNext();
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-[#0b2b43]">
          Define relocation tiers
          <Tip text="Tiers group employees into benefit levels. For example: Standard, Senior, Executive." />
        </h2>
        <p className="text-sm text-slate-500 mt-1">
          Each tier sets a benefit level for a group of employees. You can create as many tiers as you need.
        </p>
      </div>

      {errors['_root'] && (
        <p className="text-sm text-red-600">{errors['_root']}</p>
      )}

      <div className="space-y-4">
        {tiers.map((tier, idx) => (
          <div
            key={tier.id}
            className="border border-slate-200 rounded-lg p-4 bg-white space-y-4"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
                Tier {idx + 1}
              </span>
              {tiers.length > 1 && (
                <Button unstyled
                  type="button"
                  onClick={() => removeTier(idx)}
                  className="text-xs text-red-500 hover:text-red-700 transition-colors"
                  aria-label={`Remove tier ${idx + 1}`}
                >
                  Remove
                </Button>
              )}
            </div>

            {/* Tier name */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Tier name
                <Tip text='A short name visible to HR, e.g. "Standard", "Senior Hire", "Executive".' />
              </label>
              <Input
                value={tier.name}
                onChange={(value) => updateTier(idx, { name: value })}
                placeholder='e.g. "Standard relocation"'
              />
              {errors[`name_${idx}`] && (
                <p className="text-xs text-red-600 mt-1">{errors[`name_${idx}`]}</p>
              )}
            </div>

            {/* Description (optional) */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                Description
                <span className="ml-1 text-xs font-normal text-slate-400">(optional)</span>
                <Tip text="A short note for HR explaining who this tier covers." />
              </label>
              <Input
                value={tier.description ?? ''}
                onChange={(value) => updateTier(idx, { description: value })}
                placeholder='e.g. "For individual contributors and associates"'
              />
            </div>

            {/* Qualifying employee levels */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Who qualifies for this tier?
                <Tip text="Employees at these levels will be assigned this tier's benefits when a relocation case is created." />
              </label>
              <div className="flex flex-wrap gap-2">
                {EMPLOYEE_LEVELS.map((lvl) => {
                  const selected = tier.qualifying_levels.includes(lvl.value);
                  return (
                    <Button unstyled
                      key={lvl.value}
                      type="button"
                      onClick={() => toggleLevel(idx, lvl.value)}
                      className={[
                        'px-3 py-1.5 rounded-full text-sm font-medium transition-colors border',
                        selected
                          ? 'bg-[#0b2b43] text-white border-[#0b2b43]'
                          : 'bg-white text-slate-600 border-slate-300 hover:border-[#0b2b43] hover:text-[#0b2b43]',
                      ].join(' ')}
                      aria-pressed={selected}
                    >
                      {lvl.label}
                    </Button>
                  );
                })}
              </div>
              {errors[`levels_${idx}`] && (
                <p className="text-xs text-red-600 mt-1">{errors[`levels_${idx}`]}</p>
              )}
            </div>
          </div>
        ))}
      </div>

      <Button variant="outline" size="sm" onClick={addTier} type="button">
        + Add another tier
      </Button>

      <div className="flex justify-end pt-2">
        <Button onClick={handleNext} type="button">
          Next: Budgets →
        </Button>
      </div>
    </div>
  );
};
