import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { AutosaveChip } from './AutosaveChip';

afterEach(cleanup);

describe('AutosaveChip', () => {
  it('shows "Draft saved" when saved', () => {
    render(<AutosaveChip state="saved" />);
    expect(screen.getByText('Draft saved')).toBeInTheDocument();
  });
  it('shows "Saving…" when saving', () => {
    render(<AutosaveChip state="saving" />);
    expect(screen.getByText(/Saving/)).toBeInTheDocument();
  });
  it('shows an error message when state is error', () => {
    render(<AutosaveChip state="error" />);
    expect(screen.getByText(/Couldn.t save/)).toBeInTheDocument();
  });
});
