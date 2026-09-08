import { AlertTriangle, Info } from 'lucide-react';

export interface UnavailableFeatureProps {
  title: string;
  reason: string;
  detail?: string;
  unmappableId?: string;
}

/**
 * Surfaces imported features that cannot run on Audos yet instead of silently omitting them.
 */
export function UnavailableFeature({ title, reason, detail, unmappableId }: UnavailableFeatureProps) {
  return (
    <div className="min-h-full flex items-center justify-center p-8 bg-[var(--space-surface-page)]">
      <div
        className="max-w-xl w-full rounded-2xl border p-8"
        style={{
          backgroundColor: 'var(--space-surface-panel)',
          borderColor: 'var(--space-border-default)',
        }}
      >
        <div className="flex items-start gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-amber-500/15 flex items-center justify-center flex-shrink-0">
            <AlertTriangle className="w-5 h-5 text-amber-400" />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-[var(--space-text-muted)] mb-1">
              Not available in this preview
            </p>
            <h1 className="text-xl font-bold text-[var(--space-text-primary)]">{title}</h1>
          </div>
        </div>
        <p className="text-sm leading-relaxed text-[var(--space-text-secondary)] mb-4">{reason}</p>
        {detail && (
          <div
            className="flex gap-2 rounded-xl p-4 text-xs leading-relaxed text-[var(--space-text-muted)]"
            style={{ backgroundColor: 'var(--space-surface-muted)' }}
          >
            <Info className="w-4 h-4 flex-shrink-0 mt-0.5 text-[var(--space-brand-primary)]" />
            <span>{detail}</span>
          </div>
        )}
        {unmappableId && (
          <p className="mt-4 text-[10px] font-mono text-[var(--space-text-muted)]">Reference: {unmappableId}</p>
        )}
      </div>
    </div>
  );
}
