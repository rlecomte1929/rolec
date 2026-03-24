import React, { useCallback, useState } from 'react';
import { Card } from '../../../components/antigravity';

const STORAGE_KEY = 'policyWorkspace.introExpanded';

/**
 * Collapsible instruction panel. First visit: expanded; after user collapses, preference is stored.
 */
export const PolicyWorkspaceIntroCard: React.FC = () => {
  const [open, setOpen] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) !== '0';
    } catch {
      return true;
    }
  });

  const toggle = useCallback(() => {
    setOpen((v) => {
      const next = !v;
      try {
        localStorage.setItem(STORAGE_KEY, next ? '1' : '0');
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  return (
    <Card padding="sm" className="mb-3 border-[#e2e8f0] bg-white">
      <button
        type="button"
        onClick={toggle}
        className="flex w-full items-center justify-between gap-3 text-left py-0.5"
        aria-expanded={open}
      >
        <span className="text-sm font-semibold text-[#0b2b43]">How to use this workspace</span>
        <span className="text-xs font-medium text-[#64748b] shrink-0">{open ? 'Hide' : 'Show'}</span>
      </button>
      {open && (
        <div className="mt-2 pt-2 border-t border-[#f1f5f9]">
          <ul className="text-xs sm:text-sm text-[#475569] space-y-1 list-disc list-inside leading-snug">
            <li>Define the company baseline for relocation support across the main policy themes.</li>
            <li>Mark each item as included, excluded, or conditionally applicable.</li>
            <li>Set maximum caps where relevant. These values will later support service budget checks.</li>
            <li>Only the published version is used downstream for employee visibility and operational comparisons.</li>
            <li>Uploaded policy documents support traceability, but this structured workspace is the operational source of truth.</li>
          </ul>
        </div>
      )}
    </Card>
  );
};
