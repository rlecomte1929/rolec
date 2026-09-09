/**
 * DataSheetView — the composed Document Data Sheet, one artifact for Employee and HR.
 *
 * Backed by GET /api/cases/{caseId}/datasheet (see api/datasheet.ts). Renders the corridor
 * header + completion, the non-obvious "moat" / hard-deadline banners, the consult-professional
 * panel, and the steps → fields with provenance. Employee and HR share this component via the
 * `audience` prop (matching DestinationRequirements); HR additionally sees responsible-party /
 * SLA / employer-action annotations.
 *
 * Mounted on the employee roadmap page and the HR case dossier page.
 */
import React, { useState } from 'react';
import { Card } from '../../components/antigravity/Card';
import { Alert } from '../../components/antigravity/Alert';
import { Badge } from '../../components/antigravity/Badge';
import { Button } from '../../components/antigravity/Button';
import { ProgressBar } from '../../components/antigravity/ProgressBar';
import { Skeleton } from '../../components/antigravity/Skeleton';
import { downloadDatasheetPdf, type DataSheetSection } from '../../api/datasheet';
import { useDataSheet } from './useDataSheet';
import { DataSheetFieldRow } from './DataSheetFieldRow';
import { buildDatasheetCsv, downloadDatasheetCsv, datasheetCsvFilename } from './datasheetCsv';

interface Props {
  caseId: string;
  audience?: 'employee' | 'hr';
}

const COPY = {
  employee: { heading: 'Your data sheet', subtitle: 'Everything we already know, and exactly what you still need to provide.' },
  hr: { heading: 'Employee data sheet', subtitle: 'What is on file for this employee, and what is still outstanding.' },
};

export const DataSheetView: React.FC<Props> = ({ caseId, audience = 'employee' }) => {
  const [lang, setLang] = useState<'en' | 'local'>('en');
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const { data, loading, error, saveField, saving } = useDataSheet(caseId, { audience, lang });
  const copy = COPY[audience];

  if (loading) {
    return (
      <Card>
        <Skeleton height="h-6" width="w-1/3" />
        <div className="mt-3 space-y-2">
          <Skeleton height="h-4" />
          <Skeleton height="h-4" width="w-2/3" />
        </div>
      </Card>
    );
  }

  if (error) {
    return <Alert variant="error" title="Couldn't load the data sheet">{error}</Alert>;
  }

  if (!data || !data.covered) {
    return (
      <Alert variant="info" title={copy.heading}>
        The data sheet isn&apos;t available for this case yet — it appears once the destination is confirmed.
      </Alert>
    );
  }

  const handleExportCsv = () => {
    downloadDatasheetCsv(buildDatasheetCsv(data), datasheetCsvFilename(data));
  };
  const handleDownloadPdf = async () => {
    setDownloadingPdf(true);
    try {
      await downloadDatasheetPdf(caseId);
    } catch {
      /* the browser surfaces a failed download; keep the sheet usable */
    } finally {
      setDownloadingPdf(false);
    }
  };

  return (
    <section aria-label={copy.heading} className="space-y-4">
      {/* Header */}
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">{copy.heading}</h2>
            <p className="text-sm text-slate-600 mt-0.5">{copy.subtitle}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-600">
              {data.corridorLabel && <Badge variant="neutral" size="sm">{data.corridorLabel}</Badge>}
              {audience === 'hr' && data.employeeName && <span>{data.employeeName}</span>}
            </div>
          </div>
          <div className="flex items-center gap-1 rounded-lg border border-slate-200 p-0.5" role="group" aria-label="Label language">
            <Button size="sm" variant={lang === 'en' ? 'primary' : 'ghost'} onClick={() => setLang('en')} aria-pressed={lang === 'en'}>English</Button>
            <Button size="sm" variant={lang === 'local' ? 'primary' : 'ghost'} onClick={() => setLang('local')} aria-pressed={lang === 'local'}>Local</Button>
          </div>
        </div>
        <div className="mt-3">
          <ProgressBar
            value={data.completionPct}
            color="green"
            label={`${data.completionPct}% complete · ${data.needsInputCount} still needed`}
          />
        </div>
        {/* Export */}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button size="sm" variant="outline" onClick={handleExportCsv}>Export CSV</Button>
          <Button size="sm" variant="outline" onClick={handleDownloadPdf} disabled={downloadingPdf}>
            {downloadingPdf ? 'Preparing…' : 'Download PDF'}
          </Button>
        </div>
      </Card>

      {/* Non-obvious traps + hard deadlines */}
      {data.banners.map((b, i) => (
        <Alert key={i} variant="warning" title={b.type === 'warning' ? 'Deadline' : 'Worth knowing'}>
          {b.text}
        </Alert>
      ))}

      {/* Steps → fields */}
      {data.sections.map((section: DataSheetSection) => (
        <Card key={section.stepId}>
          <div className="mb-3">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3 className="text-base font-semibold text-slate-900">{section.title}</h3>
              {section.authority && <span className="text-xs text-slate-500">{section.authority}</span>}
            </div>
            {audience === 'hr' && (section.responsibleParty || section.slaNote) && (
              <p className="mt-1 text-xs text-slate-600">
                {section.responsibleParty && <span className="font-medium">{section.responsibleParty}</span>}
                {section.slaNote && <span> · {section.slaNote}</span>}
              </p>
            )}
            {section.processNote && <p className="mt-1 text-xs leading-relaxed text-slate-600">{section.processNote}</p>}
            {section.sourceUrl && (
              <a
                href={section.sourceUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-accent-600 hover:text-accent-700 hover:underline"
              >
                Open the official portal <span aria-hidden="true">→</span>
              </a>
            )}
          </div>
          <div className="space-y-2">
            {section.fields.map((field) => (
              <DataSheetFieldRow
                key={field.fieldId}
                field={field}
                audience={audience}
                onSave={saveField}
                saving={saving}
              />
            ))}
          </div>
        </Card>
      ))}

      {/* Consult-professional panel */}
      {data.consultProfessional.length > 0 && (
        <Card>
          <h3 className="text-base font-semibold text-slate-900">For a regulated advisor</h3>
          <p className="text-sm text-slate-600 mt-0.5">
            These are tax, legal, and social-security determinations ReloPass does not make. Take them to a qualified professional.
          </p>
          <ul className="mt-2 space-y-1.5">
            {data.consultProfessional.map((c, i) => (
              <li key={i} className="text-sm text-slate-800">
                <span className="font-medium">{c.topic}</span>
                {c.reason && <span className="text-slate-600"> — {c.reason}</span>}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </section>
  );
};
