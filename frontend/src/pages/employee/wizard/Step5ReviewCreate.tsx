import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, Alert } from '../../../components/antigravity';
import type { CaseDraftDTO, CaseRequirementsDTO, RequirementItemDTO } from '../../../types';
import { buildRequirementsFromMissingFields, getRelocationCase } from '../../../api/relocation';
import { RequirementList } from '../../../components/requirements/RequirementList';

interface StepProps {
  caseId: string;
  draft: CaseDraftDTO;
  requiredFields: string[];
  onSave: (draft: CaseDraftDTO) => Promise<void>;
  onNext: (draft: CaseDraftDTO) => Promise<void>;
  onBack: () => void;
}

export const Step5ReviewCreate: React.FC<StepProps> = ({ caseId, draft, onSave, onBack }) => {
  const navigate = useNavigate();
  const [requirements, setRequirements] = useState<CaseRequirementsDTO | null>(null);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!caseId) return;
    getRelocationCase(caseId)
      .then((relocation) =>
        setRequirements(buildRequirementsFromMissingFields(caseId, relocation.missing_fields || []))
      )
      .catch(() => setRequirements(null));
  }, [caseId]);

  const grouped = requirements?.requirements.reduce<Record<string, RequirementItemDTO[]>>((acc, item) => {
    acc[item.pillar] = acc[item.pillar] || [];
    acc[item.pillar].push(item);
    return acc;
  }, {}) || {};

  const handleSave = async () => {
    setError('');
    setIsSaving(true);
    try {
      await onSave(draft);
      setSaved(true);
    } catch (err: any) {
      const resData = err?.response?.data;
      const detail = err?.detail ?? resData?.detail;
      if (detail && typeof detail === 'object' && detail.message) {
        const missing = Array.isArray(detail.missingFields) ? detail.missingFields : [];
        setError(missing.length
          ? `${detail.message}. Please complete Step 1 (Relocation Basics) required fields.`
          : detail.message);
      } else if (detail && typeof detail === 'string') {
        setError(detail);
      } else if (resData && typeof resData === 'object' && resData.message) {
        setError(resData.message);
      } else {
        setError('Unable to save. Please try again.');
      }
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Card padding="lg">
      <div className="text-lg font-semibold text-[#0b2b43]">Review & Save</div>
      {error && (
        <div className="mt-4 rounded-lg border border-[#fecaca] bg-[#fff5f5] px-4 py-3 text-sm text-[#7a2a2a]">
          {error}
        </div>
      )}
      {saved && (
        <div className="mt-4">
          <Alert variant="success" title="Saved">
            Your data has been saved successfully. You can continue editing or go to the dashboard.
          </Alert>
        </div>
      )}

      <div className="text-sm text-[#6b7280] mt-1">
        Review the requirements generated from destination research. Save to persist your data.
      </div>

      {localStorage.getItem('demo_role') === 'admin' && (
        <button
          className="mt-3 text-xs text-[#0b2b43] underline"
          onClick={() => navigate('/admin/countries')}
        >
          View Country Requirements DB
        </button>
      )}

      <div className="mt-6 space-y-6">
        {Object.entries(grouped).map(([pillar, items]) => (
          <div key={pillar}>
            <div className="text-sm font-semibold text-[#0b2b43] mb-3">{pillar}</div>
            <RequirementList items={items} />
          </div>
        ))}
      </div>

      <div className="mt-6 flex items-center justify-between">
        <Button variant="outline" onClick={onBack}>Back</Button>
        <Button onClick={handleSave} disabled={isSaving}>
          {isSaving ? 'Saving...' : 'Save'}
        </Button>
        {saved && (
          <Button onClick={() => navigate('/employee/dashboard')}>Go to dashboard</Button>
        )}
      </div>
    </Card>
  );
};
