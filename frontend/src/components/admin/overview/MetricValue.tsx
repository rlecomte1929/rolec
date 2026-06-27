import React from 'react';

// Renders a metric value, or a clear 'Unavailable' marker when the source failed
// (null) — never a bare dash that reads as a real zero.
export const MetricValue: React.FC<{ value: string | number | null }> = ({ value }) =>
  value === null ? <span className="text-base font-medium text-amber-700">Unavailable</span> : <>{value}</>;
