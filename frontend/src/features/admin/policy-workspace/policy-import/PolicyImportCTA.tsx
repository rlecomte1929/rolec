import React, { useCallback, useRef, useState } from 'react';
import { Button } from '../../../../components/antigravity';
import { FileInput } from '../../../../components/antigravity/FileInput';
import { adminAPI } from '../../../../api/client';
import type { PolicyAnalysisResult } from '../../../../api/client';
import { PolicyWorkflowSummary } from './PolicyWorkflowSummary';

const ACCEPT = 'application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document';

export const PolicyImportCTA: React.FC = () => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PolicyAnalysisResult | null>(null);

  const handleFile = useCallback(async (file: File) => {
    setError(null);
    setResult(null);
    setAnalyzing(true);
    try {
      const res = await adminAPI.analyzePolicy(file);
      setResult(res);
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      setError(err?.response?.data?.detail ?? err?.message ?? 'Analysis failed.');
    } finally {
      setAnalyzing(false);
    }
  }, []);

  return (
    <div className="space-y-4 pt-1">
      <div className="flex items-center gap-3">
        <FileInput
          ref={fileInputRef}
          accept={ACCEPT}
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void handleFile(f);
            e.target.value = '';
          }}
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={analyzing}
          onClick={() => fileInputRef.current?.click()}
        >
          {analyzing ? 'Analyzing…' : 'Upload internal policy'}
        </Button>
        {analyzing && (
          <span className="text-[11px] text-slate-500">
            Extracting with Fable 5 — this may take up to 30 seconds for large documents.
          </span>
        )}
      </div>

      {error && (
        <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-[12px] text-rose-700">
          {error}
        </div>
      )}

      {result && (
        <PolicyWorkflowSummary
          summary={result.workflow_summary}
          elapsedMs={result.elapsed_ms}
          model={result.extraction.model}
        />
      )}
    </div>
  );
};
