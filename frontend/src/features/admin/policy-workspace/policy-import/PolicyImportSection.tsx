import React from 'react';
import { PolicyImportCard } from './PolicyImportCard';
import { PolicyImportHeader } from './PolicyImportHeader';

/**
 * Future-facing placeholder: document upload will prefill the structured policy workspace.
 * Kept visually lighter than the operational workspace above.
 */
export const PolicyImportSection: React.FC = () => (
  <section className="mt-8 space-y-3" aria-labelledby="policy-import-heading">
    <PolicyImportHeader />
    <PolicyImportCard />
  </section>
);
