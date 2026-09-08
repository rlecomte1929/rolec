import { useRef, useState } from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

/**
 * Contract test for the intake wizard's force-save-on-navigation + onBlur flush
 * (EmployeeIntakePage). The page holds this logic inline, so — as with the
 * MultiChip test in this folder — the harness mirrors the exact contract:
 *
 *  - a debounced edit holds a pending payload;
 *  - flushSave() clears the timer and AWAITS a real save, returning the outcome;
 *  - goTo() awaits flushSave() and only advances on success (blocks + surfaces an
 *    error on failure);
 *  - field blur flushes the pending save.
 */
function Harness({ save }: { save: (p: string) => Promise<boolean> }) {
  const [step, setStep] = useState(1);
  const [value, setValue] = useState('');
  const [error, setError] = useState(false);
  const pending = useRef<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const setField = (v: string) => {
    setValue(v);
    pending.current = v;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => { void runSave(v); }, 700);
  };
  const runSave = async (payload: string): Promise<boolean> => {
    const ok = await save(payload);
    if (ok) { if (pending.current === payload) pending.current = null; setError(false); }
    else { pending.current = payload; setError(true); }
    return ok;
  };
  const flushSave = async (): Promise<boolean> => {
    if (timer.current) clearTimeout(timer.current);
    const p = pending.current;
    if (p == null) return true;
    return runSave(p);
  };
  const goTo = async (s: number) => {
    const ok = await flushSave();
    if (!ok) return;
    setStep(s);
  };

  return (
    <div>
      <div data-testid="step">{step}</div>
      {error && <div data-testid="error">Couldn&apos;t save — retry</div>}
      <div onBlur={() => { void flushSave(); }}>
        <input data-testid="field" value={value} onChange={(e) => setField(e.target.value)} />
      </div>
      <button type="button" onClick={() => void goTo(step + 1)}>Continue</button>
    </div>
  );
}

describe('intake force-save-on-navigation', () => {
  it('flushes the pending debounced save and awaits a 2xx before advancing', async () => {
    const save = vi.fn().mockResolvedValue(true);
    render(<Harness save={save} />);
    fireEvent.change(screen.getByTestId('field'), { target: { value: 'Paris' } });
    fireEvent.click(screen.getByText('Continue'));
    await waitFor(() => expect(save).toHaveBeenCalledWith('Paris'));
    await waitFor(() => expect(screen.getByTestId('step').textContent).toBe('2'));
  });

  it('blocks navigation and shows an error when the save fails', async () => {
    const save = vi.fn().mockResolvedValue(false);
    render(<Harness save={save} />);
    fireEvent.change(screen.getByTestId('field'), { target: { value: 'Berlin' } });
    fireEvent.click(screen.getByText('Continue'));
    await waitFor(() => expect(screen.getByTestId('error')).toBeTruthy());
    expect(screen.getByTestId('step').textContent).toBe('1'); // stayed put
  });

  it('flushes the pending save on field blur', async () => {
    const save = vi.fn().mockResolvedValue(true);
    render(<Harness save={save} />);
    fireEvent.change(screen.getByTestId('field'), { target: { value: 'Lyon' } });
    fireEvent.blur(screen.getByTestId('field'));
    await waitFor(() => expect(save).toHaveBeenCalledWith('Lyon'));
  });

  it('does not save on blur when nothing is pending', async () => {
    const save = vi.fn().mockResolvedValue(true);
    render(<Harness save={save} />);
    fireEvent.blur(screen.getByTestId('field'));
    await new Promise((r) => setTimeout(r, 0));
    expect(save).not.toHaveBeenCalled();
  });
});
