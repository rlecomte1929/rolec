import React, { useState } from 'react';
import { Button, Card } from '../../../components/antigravity';
import type { CaseDraftDTO } from '../../../types';

interface StepProps {
  draft: CaseDraftDTO;
  requiredFields: string[];
  onSave: (draft: CaseDraftDTO) => Promise<void>;
  onNext: (draft: CaseDraftDTO) => Promise<void>;
  onBack: () => void;
}

export const Step2EmployeeProfile: React.FC<StepProps> = ({ draft, requiredFields: _requiredFields, onSave, onNext, onBack }) => {
  const [local, setLocal] = useState(draft.employeeProfile);
  const [passportFileName, setPassportFileName] = useState('');
  const [pendingPassport, setPendingPassport] = useState(false);
  const [ocrMessage, setOcrMessage] = useState('');
  const [error, setError] = useState('');

  const update = (key: keyof typeof local, value: any) => {
    setLocal({ ...local, [key]: value });
  };

  const nextDraft: CaseDraftDTO = { ...draft, employeeProfile: local };
  const requiredMissing = {
    fullName: !local.fullName,
    nationality: !local.nationality,
    passportCountry: !local.passportCountry,
    passportExpiry: !local.passportExpiry,
    residenceCountry: !local.residenceCountry,
    email: !local.email,
  };
  const hasMissing = Object.values(requiredMissing).some(Boolean);

  return (
    <Card padding="lg">
      <div className="text-lg font-semibold text-[#0b2b43]">Employee Profile</div>
      <div className="text-sm text-[#6b7280] mt-1">Collect identity details required for compliance.</div>
      {error && (
        <div className="mt-4 rounded-lg border border-[#fecaca] bg-[#fff5f5] px-4 py-3 text-sm text-[#7a2a2a]">
          {error}
        </div>
      )}

      <div className="mt-5 border border-[#e2e8f0] rounded-lg p-4 bg-[#f8fafc]">
        <div className="text-sm font-semibold text-[#0b2b43]">Auto-fill with Passport</div>
        <div className="text-xs text-[#6b7280] mt-1">
          Upload a passport copy to populate identity details automatically.
        </div>
        <div className="mt-3 flex items-center gap-3">
          <input
            type="file"
            accept="image/*,.pdf"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (!file) return;
              setPassportFileName(file.name);
              setPendingPassport(true);
              setOcrMessage('');
            }}
            className="text-sm"
          />
          {passportFileName && <span className="text-xs text-[#6b7280]">{passportFileName}</span>}
          <Button
            variant="outline"
            size="sm"
            disabled={!pendingPassport}
            onClick={() => {
              setLocal((prev) => ({
                ...prev,
                fullName: prev.fullName || 'Auto-filled Employee',
                nationality: prev.nationality || 'Norwegian',
                passportCountry: prev.passportCountry || 'Norway',
                passportExpiry: prev.passportExpiry || '2026-10-01',
                ocr: { fileName: passportFileName, uploadedAt: new Date().toISOString() },
              }));
              setPendingPassport(false);
              setOcrMessage('Passport details populated. Review and continue.');
            }}
          >
            Confirm upload
          </Button>
        </div>
        {ocrMessage && <div className="mt-2 text-xs text-[#1f8e8b]">{ocrMessage}</div>}
      </div>

      <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
        <label className="text-sm text-[#0b2b43]">
          Full name
          {requiredMissing.fullName && <span className="text-red-600"> *</span>}
          <input
            value={local.fullName || ''}
            onChange={(event) => update('fullName', event.target.value)}
            className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
          />
        </label>
        <label className="text-sm text-[#0b2b43]">
          Nationality
          {requiredMissing.nationality && <span className="text-red-600"> *</span>}
          <input
            value={local.nationality || ''}
            onChange={(event) => update('nationality', event.target.value)}
            className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
          />
        </label>
        <label className="text-sm text-[#0b2b43]">
          Passport country
          {requiredMissing.passportCountry && <span className="text-red-600"> *</span>}
          <input
            value={local.passportCountry || ''}
            onChange={(event) => update('passportCountry', event.target.value)}
            className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
          />
        </label>
        <label className="text-sm text-[#0b2b43]">
          Passport expiry
          {requiredMissing.passportExpiry && <span className="text-red-600"> *</span>}
          <input
            type="date"
            value={local.passportExpiry || ''}
            onChange={(event) => update('passportExpiry', event.target.value)}
            className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
          />
        </label>
        <label className="text-sm text-[#0b2b43]">
          Residence country
          {requiredMissing.residenceCountry && <span className="text-red-600"> *</span>}
          <input
            value={local.residenceCountry || ''}
            onChange={(event) => update('residenceCountry', event.target.value)}
            className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
          />
        </label>
        <label className="text-sm text-[#0b2b43]">
          Email
          {requiredMissing.email && <span className="text-red-600"> *</span>}
          <input
            type="email"
            value={local.email || ''}
            onChange={(event) => update('email', event.target.value)}
            className="mt-1 w-full rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm"
          />
        </label>
      </div>

      <div className="mt-6 flex items-center justify-between">
        <Button variant="outline" onClick={onBack}>Back</Button>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={async () => {
              try {
                await onSave(nextDraft);
                window.location.href = '/employee/journey';
              } catch (err: any) {
                setError(err?.message || 'Unable to save draft. Please try again.');
              }
            }}
          >
            Save as draft & exit
          </Button>
          <Button
            onClick={() => {
              if (hasMissing) {
                setError('Please complete all required fields (marked with *).');
                return;
              }
              setError('');
              onNext(nextDraft);
            }}
          >
            Next
          </Button>
        </div>
      </div>
    </Card>
  );
};
