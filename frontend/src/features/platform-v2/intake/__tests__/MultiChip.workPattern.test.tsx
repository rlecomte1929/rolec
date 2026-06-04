import { useState } from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MultiChip } from '../EmployeeIntakePage';

const OPTIONS = ['Full in-office', 'Hybrid', 'Fully remote'];

// Mirrors how a single-select field is wired onto the multi-select MultiChip.
// `binding="old"` reproduces the shipped bug; `binding="fixed"` is the patch.
function WorkPatternHarness({ binding }: { binding: 'old' | 'fixed' }) {
  const [wp, setWp] = useState('');
  return (
    <div>
      <div data-testid="value">{wp || '(empty)'}</div>
      {binding === 'old' ? (
        <MultiChip value={[wp]} onChange={([v]) => setWp(v)} options={OPTIONS} />
      ) : (
        <MultiChip
          value={wp ? [wp] : []}
          onChange={(v) => setWp(v[v.length - 1] || '')}
          options={OPTIONS}
        />
      )}
    </div>
  );
}

const isSelected = (label: string) =>
  screen.getByRole('button', { name: label }).className.includes('bg-violet-600');

describe('Work pattern selector (single-select on MultiChip)', () => {
  it('OLD binding: clicking never sets the value (reproduces the blocker)', () => {
    render(<WorkPatternHarness binding="old" />);
    fireEvent.click(screen.getByRole('button', { name: 'Full in-office' }));
    expect(screen.getByTestId('value').textContent).toBe('(empty)');
    expect(isSelected('Full in-office')).toBe(false);
  });

  it('FIXED binding: clicking selects, switches, and deselects correctly', () => {
    render(<WorkPatternHarness binding="fixed" />);

    // select
    fireEvent.click(screen.getByRole('button', { name: 'Full in-office' }));
    expect(screen.getByTestId('value').textContent).toBe('Full in-office');
    expect(isSelected('Full in-office')).toBe(true);

    // switch to another option
    fireEvent.click(screen.getByRole('button', { name: 'Hybrid' }));
    expect(screen.getByTestId('value').textContent).toBe('Hybrid');
    expect(isSelected('Hybrid')).toBe(true);
    expect(isSelected('Full in-office')).toBe(false);

    // deselect by clicking the active one
    fireEvent.click(screen.getByRole('button', { name: 'Hybrid' }));
    expect(screen.getByTestId('value').textContent).toBe('(empty)');
  });

  it('FIXED binding: a selection satisfies the required-field check', () => {
    render(<WorkPatternHarness binding="fixed" />);
    fireEvent.click(screen.getByRole('button', { name: 'Fully remote' }));
    // Step 5 validation requires a truthy work_pattern (see canContinue in source)
    expect(Boolean(screen.getByTestId('value').textContent !== '(empty)')).toBe(true);
  });
});
