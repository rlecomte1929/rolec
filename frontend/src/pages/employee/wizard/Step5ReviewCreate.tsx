import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, Alert } from '../../../components/antigravity';
import type { CaseDraftDTO, CaseRequirementsDTO, RequirementItemDTO } from '../../../types';
import { createCase } from '../../../api/cases';
import { buildRequirementsFromMissingFields, getRelocationCase } from '../../../api/relocation';
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
  const navigate = useNavigate();
  const [requirements, setRequirements] = useState<CaseRequirementsDTO | null>(null);
  const [created, setCreated] = useState(false);
  const [error, setError] = useState('');
  const [snapshotWarning, setSnapshotWarning] = useState('');
  const [isCreating, setIsCreating] = useState(false);

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

  const handleCreate = async () => {
    setError('');
    setSnapshotWarning('');
    setIsCreating(true);
    try {
      // 1) Submit to HR (existing assignment state machine) — primary action.
      await employeeAPI.submitAssignment(caseId);

      // 2) Best-effort: snapshot requirements / create case artifact (wizard backend).
      // If this fails due to transient backend/CORS/network issues, we still consider the submission successful.
      try {
        await createCase(caseId);
      } catch {
        setSnapshotWarning(
          'Submitted to HR, but we could not save a requirements snapshot. You can continue; HR may still review your submission.'
        );
      }

      setCreated(true);
    } catch (err: any) {
      // Extract API error detail: axios uses err.response?.data?.detail; fetch uses err.detail
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
        setError('Unable to submit to HR. Please complete all wizard steps and try again.');
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
      {created && (
        <div className="mt-4">
          <Alert variant="success" title="Submitted to HR">
            Your case was successfully submitted for HR review. You can now browse Providers while HR reviews your submission.
          </Alert>
        </div>
      )}
      {snapshotWarning && (
        <div className="mt-3">
          <Alert variant="warning" title="Snapshot not saved">
            {snapshotWarning}
          </Alert>
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
        {!created ? (
          <Button onClick={handleCreate} disabled={!canCreate || isCreating}>
            {isCreating ? 'Submitting...' : 'Submit to HR for review'}
          </Button>
        ) : (
          <Button onClick={() => navigate('/employee/dashboard')}>Go to dashboard</Button>
        )}
      </div>
    </Card>
  );
};
