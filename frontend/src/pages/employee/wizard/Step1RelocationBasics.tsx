import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Checkbox } from '../../../components/antigravity/Checkbox';
import { Input } from '../../../components/antigravity/Input';
import { Button, Card, LoadingButton } from '../../../components/antigravity';
import { logger } from '../../../lib/logger';
import type { CaseDraftDTO, RelocationBasicsDTO } from '../../../types';
import { ROUTES } from '../../../routes';
import { getApiErrorMessage } from '../../../utils/apiDetail';
import { DESTINATION_COUNTRIES, getCitiesForCountry, isCityInList } from '../../../utils/countries';

interface StepProps {
  caseId: string;
  draft: CaseDraftDTO;
  requiredFields: string[];
  banner?: string;
  onSave: (draft: CaseDraftDTO) => Promise<void>;
  onNext: (draft: CaseDraftDTO) => Promise<void>;
  isSaving?: boolean;
  /** Fields pre-filled by variant A smart-defaults — show a chip on those fields */
  preFilled?: Set<string>;
}

const PreFilledChip: React.FC = () => (
  <span className="ml-2 inline-flex items-center gap-1 rounded-full bg-[#e6f7f7] px-2 py-0.5 text-[10px] font-medium text-[#1f8e8b]">
    Pre-filled from your profile
  </span>
);

export const Step1RelocationBasics: React.FC<StepProps> = ({ draft, requiredFields: _requiredFields, banner, onSave, onNext, isSaving, preFilled }) => {
  const navigate = useNavigate();
  const [local, setLocal] = useState(draft.relocationBasics);
  const [error, setError] = useState('');
  const [draftExitSaving, setDraftExitSaving] = useState(false);

  useEffect(() => {
    setLocal(draft.relocationBasics || {});
  }, [draft.relocationBasics]);

  const originCities = getCitiesForCountry(local.originCountry || '');
  const destCities = getCitiesForCountry(local.destCountry || '');
  const showOriginOtherInput = !local.originCity || !isCityInList(local.originCountry || '', local.originCity || '');
  const showDestOtherInput = !local.destCity || !isCityInList(local.destCountry || '', local.destCity || '');

  const update = (key: keyof RelocationBasicsDTO, value: RelocationBasicsDTO[keyof RelocationBasicsDTO]) => {
    setLocal({ ...local, [key]: value });
  };

  const nextDraft: CaseDraftDTO = {
    ...draft,
    relocationBasics: local,
  };
  const missing = {
    originCountry: !local.originCountry,
    originCity: !local.originCity,
    destCountry: !local.destCountry,
    destCity: !local.destCity,
    purpose: !local.purpose,
    targetMoveDate: !local.targetMoveDate,
  };
  const hasMissing = Object.values(missing).some(Boolean);

  return (
    <Card padding="lg">
      <div className="text-lg font-semibold text-[#0b2b43]">Relocation Basics</div>
      <div className="text-sm text-[#6b7280] mt-1">
        Capture the core details first. Destination research runs after this step.
      </div>
      {banner && <div className="mt-3 text-xs text-[#1f8e8b]">{banner}</div>}
      {error && (
        <div className="mt-4 rounded-lg border border-[#fecaca] bg-[#fff5f5] px-4 py-3 text-sm text-[#7a2a2a]">
          {error}
        </div>
      )}

      <div className="mt-6 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label className="text-sm text-[#0b2b43]">
            Origin Country{missing.originCountry && <span className="text-red-600"> *</span>}
            {preFilled?.has('originCountry') && <PreFilledChip />}
            <select
              value={local.originCountry || ''}
              onChange={(event) => update('originCountry', event.target.value)}
              className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
            >
              <option value="">Select country</option>
              {DESTINATION_COUNTRIES.map((country) => (
                <option key={country.code} value={country.name}>
                  {country.name}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm text-[#0b2b43]">
            Origin City{missing.originCity && <span className="text-red-600"> *</span>}
            <select
              value={originCities.includes(local.originCity || '') ? local.originCity! : (local.originCity ? 'Other' : '')}
              onChange={(event) => {
                if (event.target.value === 'Other') {
                  update('originCity', originCities.includes(local.originCity || '') ? '' : (local.originCity || ''));
                } else {
                  update('originCity', event.target.value);
                }
              }}
              className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
            >
              <option value="">Select city</option>
              {originCities.map((city) => (
                <option key={city} value={city}>{city}</option>
              ))}
              <option value="Other">Other</option>
            </select>
            {showOriginOtherInput && (
              <Input unstyled
                value={local.originCity || ''}
                onChange={(event) => update('originCity', event)}
                className="mt-2 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
                placeholder="Enter city name"
              />
            )}
          </label>
          <label className="text-sm text-[#0b2b43]">
            Destination Country{missing.destCountry && <span className="text-red-600"> *</span>}
            {preFilled?.has('destCountry') && <PreFilledChip />}
            {!preFilled?.has('destCountry') && local.destCountry && (
              <span className="ml-2 text-xs text-[#1f8e8b]">(Set by HR: you can change if needed)</span>
            )}
            <select
              value={local.destCountry || ''}
              onChange={(event) => update('destCountry', event.target.value)}
              className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
            >
              <option value="">Select country</option>
              {DESTINATION_COUNTRIES.map((country) => (
                <option key={country.code} value={country.name}>
                  {country.name}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm text-[#0b2b43]">
            Destination City{missing.destCity && <span className="text-red-600"> *</span>}
            <select
              value={destCities.includes(local.destCity || '') ? local.destCity! : (local.destCity ? 'Other' : '')}
              onChange={(event) => {
                if (event.target.value === 'Other') {
                  update('destCity', destCities.includes(local.destCity || '') ? '' : (local.destCity || ''));
                } else {
                  update('destCity', event.target.value);
                }
              }}
              className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
            >
              <option value="">Select city</option>
              {destCities.map((city) => (
                <option key={city} value={city}>{city}</option>
              ))}
              <option value="Other">Other</option>
            </select>
            {showDestOtherInput && (
              <Input unstyled
                value={local.destCity || ''}
                onChange={(event) => update('destCity', event)}
                className="mt-2 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
                placeholder="Enter city name"
              />
            )}
          </label>
        </div>

        <label className="text-sm text-[#0b2b43]">
          Purpose{missing.purpose && <span className="text-red-600"> *</span>}
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
            Target Move Date{missing.targetMoveDate && <span className="text-red-600"> *</span>}
            <Input unstyled
              type="date"
              value={local.targetMoveDate || ''}
              onChange={(event) => update('targetMoveDate', event)}
              className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
            />
          </label>
          <label className="text-sm text-[#0b2b43]">
            Duration (months)
            <Input unstyled
              type="number"
              value={local.durationMonths || ''}
              onChange={(event) => update('durationMonths', Number(event))}
              className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
            />
          </label>
        </div>

        <label className="text-sm text-[#0b2b43] flex items-center gap-2">
          <Checkbox
            checked={Boolean(local.hasDependents)}
            onChange={(event) => update('hasDependents', event.target.checked)}
          />
          Relocating with dependents?
        </label>
      </div>

      <div className="mt-6 flex items-center justify-between">
        <LoadingButton
          variant="outline"
          loading={draftExitSaving}
          loadingLabel="Saving…"
          disabled={isSaving}
          onClick={async () => {
            setDraftExitSaving(true);
            setError('');
            try {
              await onSave(nextDraft);
              if (import.meta.env.DEV) {
                logger.debug('Save & Exit -> /employee/dashboard');
              }
              navigate(ROUTES.EMP_DASH);
            } catch (err) {
              setError(getApiErrorMessage(err, "Couldn't save draft. Try again."));
            } finally {
              setDraftExitSaving(false);
            }
          }}
        >
          Save as draft & exit
        </LoadingButton>
        <Button
          disabled={isSaving || draftExitSaving}
          onClick={() => {
            if (hasMissing) {
              setError('Complete required fields (marked with *).');
              return;
            }
            setError('');
            void onNext(nextDraft);
          }}
        >
          {isSaving ? 'Saving…' : 'Next'}
        </Button>
      </div>
    </Card>
  );
};
