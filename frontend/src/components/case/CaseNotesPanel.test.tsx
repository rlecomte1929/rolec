import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';

const listCaseNotes = vi.fn();
const addCaseNote = vi.fn();

vi.mock('../../api/caseNotes', () => ({
  listCaseNotes: (...a: unknown[]) => listCaseNotes(...a),
  addCaseNote: (...a: unknown[]) => addCaseNote(...a),
}));

import { CaseNotesPanel } from './CaseNotesPanel';

beforeEach(() => {
  listCaseNotes.mockReset();
  addCaseNote.mockReset();
});
afterEach(cleanup);

describe('CaseNotesPanel · load failure is not an empty list', () => {
  it('surfaces an error when notes fail to load', async () => {
    listCaseNotes.mockRejectedValue(new Error('Could not load notes.'));
    render(<CaseNotesPanel caseId="case-1" />);
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Could not load notes.'));
    expect(screen.queryByText(/No notes yet/i)).not.toBeInTheDocument();
  });

  it('still shows the empty state when the load genuinely returns nothing', async () => {
    listCaseNotes.mockResolvedValue([]);
    render(<CaseNotesPanel caseId="case-1" />);
    await waitFor(() => expect(screen.getByText(/No notes yet/i)).toBeInTheDocument());
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
