import React from 'react';
import { CountryFlag } from './CountryFlag';
import { Button } from './Button';

export interface ConfirmRow {
  label: string;
  value: string;
  /** If set, render a flag next to the value (country name/demonym). */
  flag?: string;
}

interface ConfirmFromIntakeProps {
  title: string;
  subtitle?: string;
  rows: ConfirmRow[];
  onConfirmAll: () => void;
  onEdit?: () => void;
  className?: string;
}

/** Ask-once: shows already-known fields as read-only confirmable values, never blank inputs. */
export const ConfirmFromIntake: React.FC<ConfirmFromIntakeProps> = ({ title, subtitle, rows, onConfirmAll, onEdit, className = '' }) => (
  <section className={`overflow-hidden rounded-xl border border-[#e2e8f0] bg-white shadow-sm ${className}`}>
    <div className="flex items-start justify-between gap-3 border-b border-[#e2e8f0] bg-accent-50/60 px-6 py-4">
      <div>
        <h3 className="text-[15px] font-bold text-navy-800">{title}</h3>
        {subtitle && <p className="mt-0.5 text-[13px] text-[#6b7280]">{subtitle}</p>}
      </div>
      <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-500/10 px-2.5 py-1 text-[11.5px] font-semibold text-accent-600" aria-hidden="true">Already on file</span>
    </div>
    <dl>
      {rows.map((r) => (
        <div key={r.label} className="flex items-center justify-between gap-4 border-b border-[#e2e8f0] px-6 py-4 last:border-b-0">
          <div>
            <dt className="text-[12px] font-semibold uppercase tracking-wide text-[#9aa6b2]">{r.label}</dt>
            <dd className="mt-1 text-[15px] font-semibold text-navy-800">
              {r.flag ? <CountryFlag country={r.flag} label={r.value} /> : r.value}
            </dd>
          </div>
          <span className="inline-flex items-center gap-1 rounded-full bg-accent-500/10 px-2.5 py-1 text-[11.5px] font-semibold text-accent-600" aria-hidden="true">✓ On file</span>
        </div>
      ))}
    </dl>
    <div className="flex items-center justify-between gap-3 px-6 py-4">
      <p className="text-[12px] text-[#6b7280]">We never ask for the same thing twice — edit once and it updates everywhere.</p>
      <div className="flex items-center gap-3">
        {onEdit && <Button variant="ghost" size="sm" onClick={onEdit}>Edit a detail</Button>}
        <Button variant="primary" size="sm" onClick={onConfirmAll}>Confirm all — these are correct</Button>
      </div>
    </div>
  </section>
);
