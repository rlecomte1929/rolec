import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { Tabs, tabPanelProps } from './Tabs';

afterEach(cleanup);

const TABS = [
  { id: 'a', label: 'Alpha' },
  { id: 'b', label: 'Beta' },
  { id: 'c', label: 'Gamma' },
];

describe('Tabs', () => {
  it('marks the active tab aria-selected and gives it the focusable tabindex', () => {
    render(<Tabs tabs={TABS} activeId="b" onChange={() => {}} aria-label="Sections" />);
    expect(screen.getByRole('tab', { name: 'Beta' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: 'Alpha' })).toHaveAttribute('tabindex', '-1');
    expect(screen.getByRole('tab', { name: 'Beta' })).toHaveAttribute('tabindex', '0');
  });

  it('selects on click', () => {
    const onChange = vi.fn();
    render(<Tabs tabs={TABS} activeId="a" onChange={onChange} aria-label="Sections" />);
    fireEvent.click(screen.getByRole('tab', { name: 'Gamma' }));
    expect(onChange).toHaveBeenCalledWith('c');
  });

  it('ArrowRight moves selection to the next tab (wraps)', () => {
    const onChange = vi.fn();
    render(<Tabs tabs={TABS} activeId="c" onChange={onChange} aria-label="Sections" />);
    fireEvent.keyDown(screen.getByRole('tab', { name: 'Gamma' }), { key: 'ArrowRight' });
    expect(onChange).toHaveBeenCalledWith('a');
  });

  it('tabPanelProps links the panel to its tab', () => {
    expect(tabPanelProps('b')).toEqual({
      role: 'tabpanel', id: 'panel-b', 'aria-labelledby': 'tab-b', tabIndex: 0,
    });
  });
});
