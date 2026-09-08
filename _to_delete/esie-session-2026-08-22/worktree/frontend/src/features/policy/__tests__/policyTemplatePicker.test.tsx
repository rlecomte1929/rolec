/**
 * PolicyTemplatePicker — HR "Start from a template" flow.
 * Covers:
 *   - template list fetched and rendered when modal opens
 *   - clicking a card applies that template + closes the modal
 *   - 409 draft_has_rows triggers the confirm-replace sub-view
 *   - confirm replace re-invokes the API with replace_existing_draft=true
 *   - generic error shown inline
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { PolicyTemplatePicker } from '../PolicyTemplatePicker';

const mocks = vi.hoisted(() => ({
  hrListTemplates: vi.fn(),
  hrApplyTemplate: vi.fn(),
}));

vi.mock('../../../api/client', () => ({
  policyConfigMatrixAPI: {
    hrListTemplates: (...args: unknown[]) => mocks.hrListTemplates(...args),
    hrApplyTemplate: (...args: unknown[]) => mocks.hrApplyTemplate(...args),
  },
}));

const TEMPLATES = [
  { key: 'conservative', label: 'Conservative', description: 'Lower caps — cautious defaults.' },
  { key: 'standard', label: 'Standard', description: 'Balanced, middle-market.' },
  { key: 'premium', label: 'Premium', description: 'Executive-grade caps.' },
];

afterEach(() => {
  cleanup();
  mocks.hrListTemplates.mockReset();
  mocks.hrApplyTemplate.mockReset();
});

describe('PolicyTemplatePicker', () => {
  it('fetches and renders templates when opened', async () => {
    mocks.hrListTemplates.mockResolvedValue({ templates: TEMPLATES });
    render(
      <PolicyTemplatePicker open onClose={() => {}} onApplied={() => {}} />
    );
    expect(await screen.findByTestId('template-card-conservative')).toBeInTheDocument();
    expect(screen.getByTestId('template-card-standard')).toBeInTheDocument();
    expect(screen.getByTestId('template-card-premium')).toBeInTheDocument();
  });

  it('applying a template closes the modal and fires onApplied', async () => {
    mocks.hrListTemplates.mockResolvedValue({ templates: TEMPLATES });
    mocks.hrApplyTemplate.mockResolvedValue({ status: 'draft', source: 'template_applied' });
    const onApplied = vi.fn();
    const onClose = vi.fn();
    render(
      <PolicyTemplatePicker open onClose={onClose} onApplied={onApplied} />
    );
    fireEvent.click(await screen.findByTestId('template-card-standard'));
    await waitFor(() => expect(mocks.hrApplyTemplate).toHaveBeenCalledTimes(1));
    expect(mocks.hrApplyTemplate).toHaveBeenCalledWith(
      { template_key: 'standard', replace_existing_draft: false },
      undefined
    );
    expect(onApplied).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it('on 409 draft_has_rows shows confirm-replace view', async () => {
    mocks.hrListTemplates.mockResolvedValue({ templates: TEMPLATES });
    mocks.hrApplyTemplate.mockRejectedValueOnce({
      response: {
        status: 409,
        data: {
          detail: {
            code: 'draft_has_rows',
            message: 'Draft already exists.',
          },
        },
      },
    });
    render(
      <PolicyTemplatePicker open onClose={() => {}} onApplied={() => {}} />
    );
    fireEvent.click(await screen.findByTestId('template-card-premium'));
    expect(
      await screen.findByRole('button', { name: /Replace draft with Premium/i })
    ).toBeInTheDocument();
    expect(
      screen.getByText(/A draft with pending rows is already in progress/i)
    ).toBeInTheDocument();
  });

  it('confirm replace retries with replace_existing_draft=true', async () => {
    mocks.hrListTemplates.mockResolvedValue({ templates: TEMPLATES });
    mocks.hrApplyTemplate
      .mockRejectedValueOnce({
        response: { status: 409, data: { detail: { code: 'draft_has_rows' } } },
      })
      .mockResolvedValueOnce({ status: 'draft', source: 'template_applied' });
    const onApplied = vi.fn();
    render(
      <PolicyTemplatePicker open onClose={() => {}} onApplied={onApplied} />
    );
    fireEvent.click(await screen.findByTestId('template-card-premium'));
    const replaceBtn = await screen.findByRole('button', {
      name: /Replace draft with Premium/i,
    });
    fireEvent.click(replaceBtn);
    await waitFor(() => expect(mocks.hrApplyTemplate).toHaveBeenCalledTimes(2));
    expect(mocks.hrApplyTemplate).toHaveBeenLastCalledWith(
      { template_key: 'premium', replace_existing_draft: true },
      undefined
    );
    expect(onApplied).toHaveBeenCalled();
  });

  it('generic API failure is surfaced inline', async () => {
    mocks.hrListTemplates.mockResolvedValue({ templates: TEMPLATES });
    mocks.hrApplyTemplate.mockRejectedValue({
      response: {
        status: 500,
        data: { detail: { message: 'Database unreachable' } },
      },
    });
    render(
      <PolicyTemplatePicker open onClose={() => {}} onApplied={() => {}} />
    );
    fireEvent.click(await screen.findByTestId('template-card-standard'));
    expect(await screen.findByText(/Database unreachable/i)).toBeInTheDocument();
  });
});
