import React from 'react';
import { ProgressBar } from './antigravity';

interface ProgressHeaderProps {
  answeredCount: number;
  totalQuestions: number;
  percentComplete: number;
  currentStep?: string;
}

export const ProgressHeader: React.FC<ProgressHeaderProps> = ({
  answeredCount,
  totalQuestions,
  percentComplete,
  currentStep,
}) => {
  return (
    <div className="bg-white border-b border-gray-200 shadow-sm">
      <div className="max-w-4xl mx-auto px-4 py-4">
        <div className="flex items-center justify-between mb-2">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              {currentStep || 'Building Your Profile'}
            </h2>
            <p className="text-sm text-gray-500">
              {answeredCount} of {totalQuestions} questions answered
            </p>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-indigo-600">{Math.round(percentComplete)}%</div>
            <div className="text-xs text-gray-500">Complete</div>
          </div>
        </div>
        <ProgressBar value={percentComplete} showLabel={false} />
      </div>
    </div>
  );
};
