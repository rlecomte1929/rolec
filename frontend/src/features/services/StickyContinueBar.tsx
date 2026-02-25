import React from 'react';
import { Button } from '../../components/antigravity';

interface StickyContinueBarProps {
  selectedCount: number;
  onContinue: () => void;
}

export const StickyContinueBar: React.FC<StickyContinueBarProps> = ({
  selectedCount,
  onContinue,
}) => (
  <div className="sticky bottom-0 left-0 right-0 z-10 py-4 -mx-4 px-4 md:-mx-8 md:px-8 bg-[#f5f7fa]/95 backdrop-blur-sm border-t border-[#e2e8f0] mt-8">
    <Button
      onClick={onContinue}
      disabled={selectedCount === 0}
      className="w-full md:w-auto md:min-w-[240px]"
    >
      Continue ({selectedCount} selected)
    </Button>
  </div>
);
