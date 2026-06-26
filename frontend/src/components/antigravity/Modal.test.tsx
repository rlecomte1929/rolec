import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { Modal } from './Modal';

afterEach(cleanup);

describe('antigravity Modal (A11Y-5)', () => {
  it('exposes dialog semantics and an accessible name from the title', () => {
    render(
      <Modal open onClose={() => {}} title="Approve event">
        <button>Approve</button>
      </Modal>,
    );
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    // aria-labelledby points at the rendered title.
    expect(dialog).toHaveAccessibleName('Approve event');
  });

  it('renders nothing when closed', () => {
    render(
      <Modal open={false} onClose={() => {}} title="Hidden">
        <button>x</button>
      </Modal>,
    );
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('closes on Escape', () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="T">
        <button>x</button>
      </Modal>,
    );
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('closes on backdrop click but not on panel click', () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="T">
        <button>x</button>
      </Modal>,
    );
    const dialog = screen.getByRole('dialog');
    fireEvent.click(dialog); // panel — should NOT close
    expect(onClose).not.toHaveBeenCalled();
    // backdrop is the dialog's parent (presentation wrapper)
    fireEvent.click(dialog.parentElement as HTMLElement);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('moves focus into the dialog on open and restores it to the trigger on close', () => {
    const trigger = document.createElement('button');
    trigger.textContent = 'open';
    document.body.appendChild(trigger);
    trigger.focus();
    expect(document.activeElement).toBe(trigger);

    const { rerender } = render(
      <Modal open onClose={() => {}} title="T">
        <button>first</button>
      </Modal>,
    );
    // focus moved to the first focusable inside the dialog
    expect(screen.getByText('first')).toHaveFocus();

    rerender(
      <Modal open={false} onClose={() => {}} title="T">
        <button>first</button>
      </Modal>,
    );
    // focus restored to the original trigger
    expect(document.activeElement).toBe(trigger);
    trigger.remove();
  });
});
