import React from 'react';
import { Button, Badge } from '../antigravity';
import type { RequirementItemDTO } from '../../types';
import { Citations } from './Citations';

interface RequirementListProps {
  items: RequirementItemDTO[];
  onAction?: (action: string, item: RequirementItemDTO) => void;
}

const statusVariant = (status: RequirementItemDTO['statusForCase']) => {
  if (status === 'PROVIDED') return 'success';
  if (status === 'MISSING') return 'error';
  return 'warning';
};

const ownerVariant = (owner: RequirementItemDTO['owner']) => {
  if (owner === 'HR') return 'info';
  if (owner === 'Employee') return 'warning';
  return 'neutral';
};

export const RequirementList: React.FC<RequirementListProps> = ({ items, onAction }) => {
  return (
    <div className="space-y-4">
      {items.map((item) => (
        <div key={item.id} className="border border-[#e2e8f0] rounded-xl p-4 bg-white">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-sm font-semibold text-[#0b2b43]">{item.title}</div>
              <div className="text-xs text-[#6b7280] mt-1">{item.description}</div>
              <div className="flex flex-wrap gap-2 mt-3">
                <Badge variant={statusVariant(item.statusForCase)} size="sm">
                  {item.statusForCase}
                </Badge>
                <Badge variant={ownerVariant(item.owner)} size="sm">
                  {item.owner}
                </Badge>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={() => onAction?.('Upload', item)}>
                Upload
              </Button>
              <Button variant="outline" size="sm" onClick={() => onAction?.('Answer', item)}>
                Answer
              </Button>
              <Button variant="outline" size="sm" onClick={() => onAction?.('Ask HR', item)}>
                Ask HR
              </Button>
              <Button size="sm" onClick={() => onAction?.('Mark Reviewed', item)}>
                Mark Reviewed
              </Button>
            </div>
          </div>
          <Citations sources={item.citations} />
        </div>
      ))}
    </div>
  );
};
