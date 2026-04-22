/**
 * PolicyAssistantFab — floating button + right-anchored sheet pattern.
 *
 * Regression targets:
 *   - FAB is discoverable by screen readers (has an accessible name)
 *   - Clicking opens a dialog and the caller's render-prop body
 *   - Escape closes and returns focus to the FAB
 *   - Clicking the overlay (outside the sheet) closes
 *   - Clicking inside the sheet does NOT close
 *
 * These tests use testing-library role queries so we catch a11y
 * regressions in the same pass as behavioral ones.
 */
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { PolicyAssistantFab } from '../PolicyAssistantFab';

afterEach(() => cleanup());

function setup() {
  return render(
    <PolicyAssistantFab label="Open Policy Assistant — ask about this HR policy">
      {({ close }) => (
        <div data-testid="assistant-body">
          <p>Ask me about your policy</p>
          <button type="button" onClick={close} data-testid="child-close">
            Close from child
          </button>
        </div>
      )}
    </PolicyAssistantFab>
  );
}

describe('PolicyAssistantFab', () => {
  it('renders an accessible FAB trigger', () => {
    setup();
    const fab = screen.getByRole('button', {
      name: /Open Policy Assistant — ask about this HR policy/i,
    });
    expect(fab).toBeInTheDocument();
    expect(fab).toHaveAttribute('aria-expanded', 'false');
    expect(fab).toHaveAttribute('aria-haspopup', 'dialog');
    // Body is not yet rendered when the sheet is closed.
    expect(screen.queryByTestId('assistant-body')).not.toBeInTheDocument();
  });

  it('opens the sheet and shows the render-prop body', () => {
    setup();
    fireEvent.click(
      screen.getByRole('button', { name: /Open Policy Assistant/i })
    );
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByTestId('assistant-body')).toBeInTheDocument();
    expect(screen.getByText(/Ask me about your policy/i)).toBeInTheDocument();
  });

  it('closes on Escape and returns focus to the FAB', async () => {
    setup();
    const fab = screen.getByRole('button', { name: /Open Policy Assistant/i });
    fireEvent.click(fab);
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    fireEvent.keyDown(window, { key: 'Escape' });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
    expect(document.activeElement).toBe(fab);
  });

  it('closes when the overlay is clicked', async () => {
    setup();
    fireEvent.click(
      screen.getByRole('button', { name: /Open Policy Assistant/i })
    );
    const dialog = screen.getByRole('dialog');
    fireEvent.click(dialog);
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  it('does not close when clicking inside the sheet', () => {
    setup();
    fireEvent.click(
      screen.getByRole('button', { name: /Open Policy Assistant/i })
    );
    const sheet = screen.getByTestId('policy-assistant-fab-sheet');
    fireEvent.click(sheet);
    // Dialog still present
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('caller render-prop close() dismisses the sheet', async () => {
    setup();
    fireEvent.click(
      screen.getByRole('button', { name: /Open Policy Assistant/i })
    );
    fireEvent.click(screen.getByTestId('child-close'));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });
});
