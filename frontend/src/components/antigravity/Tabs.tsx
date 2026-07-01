import React from 'react';

export interface TabItem {
  id: string;
  label: React.ReactNode;
  disabled?: boolean;
}

interface TabsProps {
  tabs: TabItem[];
  /** Currently-selected tab id (controlled). */
  activeId: string;
  onChange: (id: string) => void;
  /** Required: labels the tablist for screen readers. */
  'aria-label': string;
  className?: string;
}

/** Props to spread onto the caller's panel element so it links to its tab. */
export function tabPanelProps(activeId: string): {
  role: 'tabpanel';
  id: string;
  'aria-labelledby': string;
  tabIndex: 0;
} {
  return {
    role: 'tabpanel',
    id: `panel-${activeId}`,
    'aria-labelledby': `tab-${activeId}`,
    tabIndex: 0,
  };
}

/**
 * Antigravity Tabs — one accessible tablist (the app hand-rolled ≥9). WAI-ARIA
 * pattern: `role="tablist"` + roving tabindex + ArrowLeft/Right (and Home/End)
 * navigation; the active tab gets the navy underline. The caller renders the
 * panel content and spreads `tabPanelProps(activeId)` onto its container.
 */
export const Tabs: React.FC<TabsProps> = ({ tabs, activeId, onChange, 'aria-label': ariaLabel, className = '' }) => {
  const enabled = tabs.filter((t) => !t.disabled);

  const onKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>) => {
    const idx = enabled.findIndex((t) => t.id === activeId);
    if (idx < 0) return;
    let next = idx;
    if (e.key === 'ArrowRight') next = (idx + 1) % enabled.length;
    else if (e.key === 'ArrowLeft') next = (idx - 1 + enabled.length) % enabled.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = enabled.length - 1;
    else return;
    e.preventDefault();
    const target = enabled[next];
    if (target) onChange(target.id);
  };

  return (
    <div role="tablist" aria-label={ariaLabel} className={`flex items-center gap-1 border-b border-[#e2e8f0] ${className}`}>
      {tabs.map((tab) => {
        const selected = tab.id === activeId;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            id={`tab-${tab.id}`}
            aria-selected={selected}
            aria-controls={`panel-${tab.id}`}
            tabIndex={selected ? 0 : -1}
            disabled={tab.disabled}
            onClick={() => onChange(tab.id)}
            onKeyDown={onKeyDown}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-[#0b2b43] focus:ring-offset-1 ${
              selected
                ? 'border-[#0b2b43] text-[#0b2b43]'
                : 'border-transparent text-[#64748b] hover:text-[#0b2b43] hover:border-[#cbd5e1]'
            } ${tab.disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}`}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
};
