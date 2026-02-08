import React, { useState } from 'react';
import { Button, Card } from '../../../components/antigravity';
import type { CaseDraftDTO } from '../../../types';

interface StepProps {
  caseId: string;
  draft: CaseDraftDTO;
  requiredFields: string[];
  banner?: string;
  onSave: (draft: CaseDraftDTO) => Promise<void>;
  onNext: (draft: CaseDraftDTO) => Promise<void>;
}

const isRequired = (requiredFields: string[], key: string) => requiredFields.includes(key);

const COUNTRY_OPTIONS = [
  { code: 'NO', name: 'Norway', cities: ['Oslo', 'Bergen'] },
  { code: 'SG', name: 'Singapore', cities: ['Singapore'] },
  { code: 'US', name: 'United States', cities: ['New York', 'San Francisco'] },
  { code: 'UK', name: 'United Kingdom', cities: ['London', 'Manchester'] },
  { code: 'DE', name: 'Germany', cities: ['Berlin', 'Munich'] },
];

export const Step1RelocationBasics: React.FC<StepProps> = ({ draft, requiredFields, banner, onSave, onNext }) => {
  const [local, setLocal] = useState(draft.relocationBasics);
  const [customOriginCity, setCustomOriginCity] = useState('');
  const [customDestCity, setCustomDestCity] = useState('');

  const update = (key: keyof typeof local, value: any) => {
    setLocal({ ...local, [key]: value });
  };

  const nextDraft: CaseDraftDTO = {
    ...draft,
    relocationBasics: local,
  };

  return (
    <Card padding="lg">
      <div className="text-lg font-semibold text-[#0b2b43]">Relocation Basics</div>
      <div className="text-sm text-[#6b7280] mt-1">
        Capture the core details first. Destination research runs after this step.
      </div>
      {banner && <div className="mt-3 text-xs text-[#1f8e8b]">{banner}</div>}

      <div className="mt-6 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label className="text-sm text-[#0b2b43]">
            Origin Country{isRequired(requiredFields, 'relocationBasics.originCountry') && ' *'}
            <select
              value={local.originCountry || ''}
              onChange={(event) => update('originCountry', event.target.value)}
              className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
            >
              <option value="">Select country</option>
              {COUNTRY_OPTIONS.map((country) => (
                <option key={country.code} value={country.name}>
                  {country.name}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm text-[#0b2b43]">
            Origin City{isRequired(requiredFields, 'relocationBasics.originCity') && ' *'}
            <select
              value={local.originCity || ''}
              onChange={(event) => {
                if (event.target.value === 'Other') {
                  update('originCity', '');
                } else {
                  update('originCity', event.target.value);
                }
              }}
              className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
            >
              <option value="">Select city</option>
              {(COUNTRY_OPTIONS.find((c) => c.name === local.originCountry)?.cities || []).map((city) => (
                <option key={city} value={city}>
                  {city}
                </option>
              ))}
              <option value="Other">Other</option>
            </select>
            {!local.originCity && (
              <input
                value={customOriginCity}
                onChange={(event) => {
                  setCustomOriginCity(event.target.value);
                  update('originCity', event.target.value);
                }}
                className="mt-2 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
                placeholder="Enter city"
              />
            )}
          </label>
          <label className="text-sm text-[#0b2b43]">
            Destination Country{isRequired(requiredFields, 'relocationBasics.destCountry') && ' *'}
            <select
              value={local.destCountry || ''}
              onChange={(event) => update('destCountry', event.target.value)}
              className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
            >
              <option value="">Select country</option>
              {COUNTRY_OPTIONS.map((country) => (
                <option key={country.code} value={country.name}>
                  {country.name}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm text-[#0b2b43]">
            Destination City{isRequired(requiredFields, 'relocationBasics.destCity') && ' *'}
            <select
              value={local.destCity || ''}
              onChange={(event) => {
                if (event.target.value === 'Other') {
                  update('destCity', '');
                } else {
                  update('destCity', event.target.value);
                }
              }}
              className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
            >
              <option value="">Select city</option>
              {(COUNTRY_OPTIONS.find((c) => c.name === local.destCountry)?.cities || []).map((city) => (
                <option key={city} value={city}>
                  {city}
                </option>
              ))}
              <option value="Other">Other</option>
            </select>
            {!local.destCity && (
              <input
                value={customDestCity}
                onChange={(event) => {
                  setCustomDestCity(event.target.value);
                  update('destCity', event.target.value);
                }}
                className="mt-2 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
                placeholder="Enter city"
              />
            )}
          </label>
        </div>

        <label className="text-sm text-[#0b2b43]">
          Purpose{isRequired(requiredFields, 'relocationBasics.purpose') && ' *'}
          <select
            value={local.purpose || ''}
            onChange={(event) => update('purpose', event.target.value)}
            className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
          >
            <option value="">Select</option>
            <option value="employment">Employment</option>
            <option value="study">Study</option>
            <option value="family">Family</option>
            <option value="other">Other</option>
          </select>
        </label>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label className="text-sm text-[#0b2b43]">
            Target Move Date{isRequired(requiredFields, 'relocationBasics.targetMoveDate') && ' *'}
            <input
              type="date"
              value={local.targetMoveDate || ''}
              onChange={(event) => update('targetMoveDate', event.target.value)}
              className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
            />
          </label>
          <label className="text-sm text-[#0b2b43]">
            Duration (months)
            <input
              type="number"
              value={local.durationMonths || ''}
              onChange={(event) => update('durationMonths', Number(event.target.value))}
              className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
            />
          </label>
        </div>

        <label className="text-sm text-[#0b2b43] flex items-center gap-2">
          <input
            type="checkbox"
            checked={Boolean(local.hasDependents)}
            onChange={(event) => update('hasDependents', event.target.checked)}
          />
          Relocating with dependents?
        </label>
      </div>

      <div className="mt-6 flex items-center justify-between">
        <Button
          variant="outline"
          onClick={async () => {
            await onSave(nextDraft);
            window.location.href = '/employee/dashboard';
          }}
        >
          Save as draft & exit
        </Button>
        <Button onClick={() => onNext(nextDraft)}>Next</Button>
      </div>
    </Card>
  );
};
