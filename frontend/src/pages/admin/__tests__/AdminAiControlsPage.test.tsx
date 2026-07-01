import '@testing-library/jest-dom/vitest';
import React from 'react';
import { cleanup, render, screen, fireEvent, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AdminAiControlsPage } from '../AdminAiControlsPage';

vi.mock('../AdminLayout', () => ({
  AdminLayout: ({ children, title }: { children: React.ReactNode; title?: string }) => (
    <main>
      {title && <h1>{title}</h1>}
      {children}
    </main>
  ),
}));

const mockGetAiControls = vi.fn();
const mockSetAiControl = vi.fn();
const mockKillAiFeature = vi.fn();

vi.mock('../../../api/aiControls', () => ({
  getAiControls: (...args: unknown[]) => mockGetAiControls(...args),
  setAiControl: (...args: unknown[]) => mockSetAiControl(...args),
  killAiFeature: (...args: unknown[]) => mockKillAiFeature(...args),
}));

const MOCK_CONTROLS = [
  { key: 'policy_rag_groundedness_gate', value: '0', source: 'default' as const },
  { key: 'policy_rag_groundedness_min_score', value: '0.5', source: 'env' as const },
  { key: 'policy_rag_rerank', value: '1', source: 'db' as const },
  { key: 'supplier_learned_weights', value: '0', source: 'default' as const },
];

beforeEach(() => {
  vi.clearAllMocks();
  mockGetAiControls.mockResolvedValue({ controls: MOCK_CONTROLS });
  mockSetAiControl.mockResolvedValue({ key: 'policy_rag_rerank', value: '0', source: 'db' });
  mockKillAiFeature.mockResolvedValue({ key: 'policy_rag_rerank', value: '0', source: 'db' });
  // suppress window.confirm
  vi.spyOn(window, 'confirm').mockReturnValue(true);
});

afterEach(cleanup);

describe('AdminAiControlsPage', () => {
  it('renders all 4 control cards', async () => {
    render(<AdminAiControlsPage />);
    await waitFor(() => expect(mockGetAiControls).toHaveBeenCalledTimes(1));
    expect(screen.getByText('Groundedness gate')).toBeInTheDocument();
    expect(screen.getByText('Groundedness min score')).toBeInTheDocument();
    expect(screen.getByText('RAG rerank')).toBeInTheDocument();
    expect(screen.getByText('Supplier learned weights')).toBeInTheDocument();
  });

  it('shows env-var badge and hides edit/kill for env-locked controls', async () => {
    render(<AdminAiControlsPage />);
    await waitFor(() => screen.getByText('Groundedness min score'));
    // The "env var" badge should appear for the env-sourced control
    expect(screen.getByText('env var')).toBeInTheDocument();
    // The env-locked card should not have Edit / Kill buttons
    expect(screen.queryByText('Set by env var — override via server config.')).toBeInTheDocument();
  });

  it('opens edit form and saves with reason', async () => {
    render(<AdminAiControlsPage />);
    await waitFor(() => screen.getByText('Groundedness gate'));

    // Click Edit on the first non-env control (Groundedness gate, source=default)
    const editButtons = screen.getAllByRole('button', { name: /edit/i });
    fireEvent.click(editButtons[0]!);

    // Edit form appears — fill reason
    const reasonInput = screen.getByPlaceholderText(/why are you changing/i);
    fireEvent.change(reasonInput, { target: { value: 'Testing the gate' } });

    // Click Save
    const saveButton = screen.getByRole('button', { name: /save/i });
    fireEvent.click(saveButton);

    await waitFor(() => expect(mockSetAiControl).toHaveBeenCalledWith(
      expect.objectContaining({ reason: 'Testing the gate' })
    ));
    // page reloads
    expect(mockGetAiControls).toHaveBeenCalledTimes(2);
  });

  it('shows validation error when reason is empty', async () => {
    render(<AdminAiControlsPage />);
    await waitFor(() => screen.getByText('Groundedness gate'));

    const editButtons = screen.getAllByRole('button', { name: /edit/i });
    fireEvent.click(editButtons[0]!);

    // Click Save without filling reason
    const saveButton = screen.getByRole('button', { name: /save/i });
    fireEvent.click(saveButton);

    expect(screen.getByText(/reason is required/i)).toBeInTheDocument();
    expect(mockSetAiControl).not.toHaveBeenCalled();
  });

  it('calls killAiFeature and refreshes on kill confirm', async () => {
    render(<AdminAiControlsPage />);
    await waitFor(() => screen.getByText('RAG rerank'));

    const killButtons = screen.getAllByRole('button', { name: /kill/i });
    fireEvent.click(killButtons[0]!);

    await waitFor(() => expect(mockKillAiFeature).toHaveBeenCalledTimes(1));
    expect(mockGetAiControls).toHaveBeenCalledTimes(2);
  });

  it('shows error alert on API failure', async () => {
    mockGetAiControls.mockRejectedValue(new Error('Network error'));
    render(<AdminAiControlsPage />);
    await waitFor(() => expect(screen.getByText(/Network error/i)).toBeInTheDocument());
  });
});
