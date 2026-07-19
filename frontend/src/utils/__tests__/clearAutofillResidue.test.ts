import { describe, it, expect } from 'vitest';
import { clearAutofillResidueIfStale } from '../clearAutofillResidue';

/**
 * AIQ-1628: the reproduced bug — a browser drops a value into the controlled
 * password DOM node without firing onChange (state stays ""), and the next
 * keystroke concatenates onto it. These tests pin the manager-safe guard:
 * clear residue ONLY when React state is empty (a chosen manager fill sets state).
 */
describe('clearAutofillResidueIfStale', () => {
  const inputWith = (domValue: string) => {
    const el = document.createElement('input');
    el.type = 'password';
    el.value = domValue; // simulate passive autofill: DOM value set out-of-band
    return el;
  };

  it('clears stale residue when the controlled state is empty', () => {
    const el = inputWith('STALEpass');
    const cleared = clearAutofillResidueIfStale('', el);
    expect(cleared).toBe(true);
    expect(el.value).toBe(''); // user now types into a clean field → no concatenation
  });

  it('leaves a manager-chosen fill untouched (state is non-empty)', () => {
    const el = inputWith('ManagerFilledPass');
    const cleared = clearAutofillResidueIfStale('ManagerFilledPass', el);
    expect(cleared).toBe(false);
    expect(el.value).toBe('ManagerFilledPass'); // do not break password managers
  });

  it('is a no-op when the field is already empty', () => {
    const el = inputWith('');
    expect(clearAutofillResidueIfStale('', el)).toBe(false);
    expect(el.value).toBe('');
  });

  it('is a no-op when the input ref is null/undefined', () => {
    expect(clearAutofillResidueIfStale('', null)).toBe(false);
    expect(clearAutofillResidueIfStale('', undefined)).toBe(false);
  });
});
