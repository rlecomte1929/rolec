import React from 'react';

// Renders a metric value, or a fallback when the source failed (null). The
// default fallback is a clear amber 'Unavailable' marker — never a bare dash
// that reads as a real zero. Callers can override `fallback` where an amber
// 'broken' marker would over-alarm (e.g. module cards use a muted '—').
export const MetricValue: React.FC<{ value: string | number | null; fallback?: React.ReactNode }> = ({
  value,
  fallback,
}) =>
  value === null ? (
    <>{fallback ?? <span className="text-base font-medium text-amber-700">Unavailable</span>}</>
  ) : (
    <>{value}</>
  );
