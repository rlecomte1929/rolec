import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';
import { hrAPI, employeeAPI } from '../../../api/client';
import { ComposeNewMessage } from './ComposeNewMessage';

vi.mock('../../../api/client', () => ({
  hrAPI: { listAssignments: vi.fn(), sendMessage: vi.fn() },
  employeeAPI: { getAssignmentsOverview: vi.fn(), sendMessage: vi.fn() },
}));

const mockHr = hrAPI as unknown as {
  listAssignments: ReturnType<typeof vi.fn>;
  sendMessage: ReturnType<typeof vi.fn>;
};
const mockEmp = employeeAPI as unknown as {
  getAssignmentsOverview: ReturnType<typeof vi.fn>;
  sendMessage: ReturnType<typeof vi.fn>;
};

afterEach(cleanup);
beforeEach(() => vi.clearAllMocks());

const hrAssignment = (over: Record<string, unknown> = {}) => ({
  id: 'aid-1',
  caseId: 'c1',
  employeeIdentifier: 'e1',
  status: 'assigned',
  employeeFirstName: 'Alice',
  employeeLastName: 'Dupont',
  case: { home_country: 'France', host_country: 'Netherlands' },
  ...over,
});

describe('ComposeNewMessage (AIQ-1326 — Inbox new-thread compose)', () => {
  it('HR: loads assigned employees and sends to the chosen recipient via hrAPI.sendMessage', async () => {
    mockHr.listAssignments.mockResolvedValue({
      assignments: [
        hrAssignment(),
        hrAssignment({ id: 'aid-2', employeeFirstName: 'Bob', employeeLastName: 'Martin' }),
      ],
      total: 2,
    });
    mockHr.sendMessage.mockResolvedValue({ ok: true, message: {} });
    const onSent = vi.fn();
    const onClose = vi.fn();

    render(<ComposeNewMessage open isHr onClose={onClose} onSent={onSent} />);

    const select = await screen.findByRole('combobox');
    fireEvent.change(select, { target: { value: 'r-1' } });
    fireEvent.change(screen.getByLabelText('Message'), { target: { value: 'Welcome aboard' } });
    fireEvent.click(screen.getByRole('button', { name: /send/i }));

    await waitFor(() => expect(mockHr.sendMessage).toHaveBeenCalledWith('aid-2', 'Welcome aboard'));
    await waitFor(() => expect(onSent).toHaveBeenCalledWith('aid-2'));
    expect(onClose).toHaveBeenCalled();
  });

  it('Employee: auto-selects the single HR recipient and sends via employeeAPI.sendMessage', async () => {
    mockEmp.getAssignmentsOverview.mockResolvedValue({
      linked: [{ assignment_id: 'aid-emp', company: { name: 'Wave1 Tech' } }],
      pending: [],
    });
    mockEmp.sendMessage.mockResolvedValue({ ok: true, message: {} });
    const onSent = vi.fn();

    render(<ComposeNewMessage open isHr={false} onClose={() => {}} onSent={onSent} />);

    expect(await screen.findByText('HR · Wave1 Tech')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Message'), { target: { value: 'Quick question' } });
    fireEvent.click(screen.getByRole('button', { name: /send/i }));

    await waitFor(() => expect(mockEmp.sendMessage).toHaveBeenCalledWith('aid-emp', 'Quick question'));
    expect(onSent).toHaveBeenCalledWith('aid-emp');
  });

  it('keeps the modal open and shows an error when send fails (never calls onSent)', async () => {
    mockEmp.getAssignmentsOverview.mockResolvedValue({
      linked: [{ assignment_id: 'aid-emp', company: { name: 'X' } }],
      pending: [],
    });
    mockEmp.sendMessage.mockRejectedValue(new Error('boom'));
    const onSent = vi.fn();
    const onClose = vi.fn();

    render(<ComposeNewMessage open isHr={false} onClose={onClose} onSent={onSent} />);
    fireEvent.change(await screen.findByLabelText('Message'), { target: { value: 'hi' } });
    fireEvent.click(screen.getByRole('button', { name: /send/i }));

    expect(await screen.findByText(/couldn't send/i)).toBeInTheDocument();
    expect(onSent).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it('disables Send until a recipient and a non-empty body are present', async () => {
    mockHr.listAssignments.mockResolvedValue({
      assignments: [hrAssignment(), hrAssignment({ id: 'aid-2' })],
      total: 2,
    });
    render(<ComposeNewMessage open isHr onClose={() => {}} onSent={() => {}} />);
    const sendBtn = await screen.findByRole('button', { name: /send/i });
    expect(sendBtn).toBeDisabled(); // nothing selected, empty body
  });

  it('shows an empty-state when HR has no assignable employees', async () => {
    mockHr.listAssignments.mockResolvedValue({ assignments: [], total: 0 });
    render(<ComposeNewMessage open isHr onClose={() => {}} onSent={() => {}} />);
    expect(await screen.findByText(/no assigned employees to message yet/i)).toBeInTheDocument();
  });

  it('does not put assignment UUIDs in option values', async () => {
    const uuid = '11111111-2222-4333-8444-555555555555';
    mockHr.listAssignments.mockResolvedValue({
      assignments: [
        hrAssignment({ id: uuid }),
        hrAssignment({ id: 'aid-2', employeeFirstName: 'Bob', employeeLastName: 'Martin' }),
      ],
      total: 2,
    });
    render(<ComposeNewMessage open isHr onClose={() => {}} onSent={() => {}} />);
    const select = await screen.findByRole('combobox');
    expect(select.innerHTML).not.toContain(uuid);
    expect(select.innerHTML).toContain('value="r-0"');
  });

  it('points an unlinked employee at their dashboard', async () => {
    mockEmp.getAssignmentsOverview.mockResolvedValue({ linked: [], pending: [] });
    render(<ComposeNewMessage open isHr={false} onClose={() => {}} onSent={() => {}} />);
    expect(await screen.findByText(/no HR contact is linked/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /go to your dashboard/i })).toHaveAttribute(
      'href',
      '/employee/dashboard'
    );
  });
});
