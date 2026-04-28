/**
 * PolicyAssistantFab — pure trigger button (no modal, no sheet).
 *
 * Sprint 2 reduced this to a fixed-position button that flips the
 * page-level open flag. The actual panel chrome lives in
 * PolicyAssistantDockedShell. So all we test here is:
 *   - Accessible name + aria-expanded reflects parent state
 *   - Click invokes the onClick handler
 *   - hideOnPanelOpenLg adds `lg:hidden` when the panel is open
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { PolicyAssistantFab } from '../PolicyAssistantFab';

afterEach(() => cleanup());

describe('PolicyAssistantFab (trigger-only)', () => {
  it('renders an accessible trigger with aria-expanded=false when panel closed', () => {
    render(<PolicyAssistantFab onClick={() => {}} label="Ask about this policy" />);
    const fab = screen.getByRole('button', { name: /Ask about this policy/i });
    expect(fab).toBeInTheDocument();
    expect(fab).toHaveAttribute('aria-expanded', 'false');
  });

  it('reflects open state via aria-expanded=true when panel is open', () => {
    render(
      <PolicyAssistantFab
        onClick={() => {}}
        label="Ask about this policy"
        isPanelOpen
      />
    );
    const fab = screen.getByRole('button', { name: /Ask about this policy/i });
    expect(fab).toHaveAttribute('aria-expanded', 'true');
  });

  it('invokes onClick when clicked', () => {
    const onClick = vi.fn();
    render(<PolicyAssistantFab onClick={onClick} label="Open policy assistant" />);
    fireEvent.click(screen.getByRole('button', { name: /Open policy assistant/i }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('adds lg:hidden when the panel is open and hideOnPanelOpenLg is default true', () => {
    render(
      <PolicyAssistantFab onClick={() => {}} label="Ask about this policy" isPanelOpen />
    );
    const fab = screen.getByRole('button', { name: /Ask about this policy/i });
    expect(fab.className).toMatch(/\blg:hidden\b/);
  });

  it('does not add lg:hidden when hideOnPanelOpenLg is explicitly false', () => {
    render(
      <PolicyAssistantFab
        onClick={() => {}}
        label="Ask about this policy"
        isPanelOpen
        hideOnPanelOpenLg={false}
      />
    );
    const fab = screen.getByRole('button', { name: /Ask about this policy/i });
    expect(fab.className).not.toMatch(/\blg:hidden\b/);
  });

  it('does not add lg:hidden when the panel is closed', () => {
    render(
      <PolicyAssistantFab onClick={() => {}} label="Ask about this policy" />
    );
    const fab = screen.getByRole('button', { name: /Ask about this policy/i });
    expect(fab.className).not.toMatch(/\blg:hidden\b/);
  });
});
