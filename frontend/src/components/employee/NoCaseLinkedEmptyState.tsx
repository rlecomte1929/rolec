import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert } from '../antigravity/Alert';
import { Button } from '../antigravity/Button';
import { buildRoute } from '../../navigation/routes';

/**
 * Shared unlinked-case empty state (AIQ-2361). Matches the Services page pattern:
 * "No case linked" + one line of explanation + dashboard CTA.
 */
export const NoCaseLinkedEmptyState: React.FC<{
  explanation: string;
  children?: React.ReactNode;
}> = ({ explanation, children }) => {
  const navigate = useNavigate();
  return (
    <Alert variant="info" className="mb-6">
      {/* fix: AIQ-2361 — unified empty state when no case is linked */}
      <p className="mb-3">
        <span className="font-medium">No case linked.</span>{' '}
        <span className="text-slate-500">{explanation}</span>
      </p>
      <div className="flex flex-wrap gap-3">
        {children ?? (
          <Button variant="outline" onClick={() => navigate(buildRoute('employeeDashboard'))}>
            Back to Dashboard
          </Button>
        )}
      </div>
    </Alert>
  );
};
