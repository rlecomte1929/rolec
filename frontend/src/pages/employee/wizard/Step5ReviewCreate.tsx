import React, { useEffect, useState } from 'react';
import { Button, Card } from '../../../components/antigravity';
import type { CaseDraftDTO, CaseRequirementsDTO, RequirementItemDTO } from '../../../types';
import { createCase, getRequirements } from '../../../api/cases';
import { RequirementList } from '../../../components/requirements/RequirementList';
import { employeeAPI } from '../../../api/client';

interface StepProps {
  caseId: string;
  draft: CaseDraftDTO;
  requiredFields: string[];
  onSave: (draft: CaseDraftDTO) => Promise<void>;
  onNext: (draft: CaseDraftDTO) => Promise<void>;
  onBack: () => void;
}

export const Step5ReviewCreate: React.FC<StepProps> = ({ caseId, onBack }) => {
  const [requirements, setRequirements] = useState<CaseRequirementsDTO | null>(null);
  const [created, setCreated] = useState(false);
  const [error, setError] = useState('');
  const [isCreating, setIsCreating] = useState(false);

  useEffect(() => {
    if (!caseId) return;
    getRequirements(caseId).then(setRequirements);
  }, [caseId]);

  const grouped = requirements?.requirements.reduce<Record<string, RequirementItemDTO[]>>((acc, item) => {
    acc[item.pillar] = acc[item.pillar] || [];
    acc[item.pillar].push(item);
    return acc;
  }, {}) || {};

  const handleCreate = async () => {
    setError('');
    setIsCreating(true);
    try {
      // 1) Snapshot requirements / create case artifact (wizard backend)
      await createCase(caseId);
      // 2) Submit to HR (existing assignment state machine)
      await employeeAPI.submitAssignment(caseId);
      setCreated(true);
    } catch (err: any) {
      // Prefer structured API error detail when present.
      const detail = err?.detail;
      if (detail && typeof detail === 'object' && detail.message) {
        const missing = Array.isArray(detail.missingFields) ? detail.missingFields : [];
        if (missing.length) {
          setError(`${detail.message}. Please complete Step 1 (Relocation Basics) required fields.`);
        } else {
          setError(detail.message);
        }
      } else {
        setError(err?.message || 'Unable to submit to HR.');
      }
    } finally {
      setIsCreating(false);
    }
  };

  const blockingMissing =
    requirements?.requirements.filter(
      (item) => item.severity === 'BLOCKER' && item.statusForCase !== 'PROVIDED'
    ) || [];
  const canCreate = blockingMissing.length === 0;

  return (
    <Card padding="lg">
      <div className="text-lg font-semibold text-[#0b2b43]">Review & Submit</div>
      {error && (
        <div className="mt-4 rounded-lg border border-[#fecaca] bg-[#fff5f5] px-4 py-3 text-sm text-[#7a2a2a]">
          {error}
        </div>
      )}

      {!created && blockingMissing.length > 0 && (
        <div className="mt-4 rounded-lg border border-[#fecaca] bg-[#fff5f5] px-4 py-3">
          <div className="text-sm font-semibold text-[#7a2a2a]">
            Cannot create case yet
          </div>
          <div className="text-xs text-[#6b7280] mt-1">
            Resolve the blocker requirements below (marked as missing).
          </div>
        </div>
      )}
      <div className="text-sm text-[#6b7280] mt-1">
        Review the requirements generated from destination research. When you submit, your case becomes read-only for HR review.
      </div>

      {localStorage.getItem('demo_role') === 'admin' && (
        <button
          className="mt-3 text-xs text-[#0b2b43] underline"
          onClick={() => (window.location.href = '/admin/countries')}
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
        {!created ? (
          <Button onClick={handleCreate} disabled={!canCreate || isCreating}>
            {isCreating ? 'Submitting...' : 'Submit to HR for review'}
          </Button>
        ) : (
          <Button onClick={() => (window.location.href = '/employee/dashboard')}>Go to dashboard</Button>
        )}
      </div>
    </Card>
  );
};
