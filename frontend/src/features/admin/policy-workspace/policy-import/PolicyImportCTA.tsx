import React from 'react';
import { Button } from '../../../../components/antigravity';

export const PolicyImportCTA: React.FC = () => (
  <div className="flex flex-col items-start gap-1 pt-1">
    <Button type="button" variant="outline" size="sm" disabled className="pointer-events-none border-[#e2e8f0] text-[#94a3b8]">
      Upload internal policy
    </Button>
    <span className="text-[11px] text-[#cbd5e1]">Available soon</span>
  </div>
);
