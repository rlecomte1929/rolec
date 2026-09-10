/**
 * BUG-260909-E7B1 — practical next steps on the form editor so the page is
 * not a blank PDF + unlabeled fields.
 */
import React from 'react';
import { Card } from '../../../components/antigravity';
import type { FormProceedBriefingModel } from './formEditorCopy';

interface FormProceedBriefingProps {
  model: FormProceedBriefingModel;
  officialUrl: string | null;
}

export const FormProceedBriefing: React.FC<FormProceedBriefingProps> = ({
  model,
  officialUrl,
}) => {
  return (
    <div data-testid="form-proceed-briefing">
    <Card padding="md" className="mb-4">
      {/* fix: BUG-260909-E7B1 — tell the employee what ReloPass already compiled */}
      <h2 className="text-sm font-semibold text-navy-800 mb-2">{model.title}</h2>
      <ol className="space-y-2 text-sm text-slate-700 list-decimal list-inside">
        <li>{model.filledLine}</li>
        <li>
          {model.youDoLine}
          {model.missingLabels.length > 0 && (
            <ul className="mt-1 ml-5 list-disc text-slate-600">
              {model.missingLabels.map((label, i) => (
                <li key={`${i}-${label}`}>{label}</li>
              ))}
              {model.missingOverflow > 0 && (
                <li>and {model.missingOverflow} more</li>
              )}
            </ul>
          )}
        </li>
        <li>
          {model.submitLine}
          {officialUrl && (
            <>
              {' '}
              <a
                href={officialUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-accent-600 hover:text-accent-700 hover:underline"
              >
                Open official site
              </a>
            </>
          )}
        </li>
      </ol>
    </Card>
    </div>
  );
};

export default FormProceedBriefing;
