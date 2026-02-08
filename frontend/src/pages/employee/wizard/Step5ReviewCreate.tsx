import React, { useEffect, useState } from 'react';
import { Button, Card } from '../../../components/antigravity';
import type { CaseDraftDTO, CaseRequirementsDTO, RequirementItemDTO } from '../../../types';
import { createCase, getRequirements } from '../../../api/cases';
import { RequirementList } from '../../../components/requirements/RequirementList';

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
    await createCase(caseId);
    setCreated(true);
  };

  return (
    <Card padding="lg">
      <div className="text-lg font-semibold text-[#0b2b43]">Review & Create</div>
      <div className="text-sm text-[#6b7280] mt-1">
        Requirements are generated from destination research and case details.
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
          <Button onClick={handleCreate}>Create Relocation Case</Button>
        ) : (
          <Button onClick={() => (window.location.href = '/employee/dashboard')}>Go to dashboard</Button>
        )}
      </div>
    </Card>
  );
};
