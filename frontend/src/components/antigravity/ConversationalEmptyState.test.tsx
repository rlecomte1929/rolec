import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { PlaneTakeoff } from 'lucide-react';
import { ConversationalEmptyState } from './ConversationalEmptyState';

afterEach(cleanup);

describe('ConversationalEmptyState', () => {
  it('renders the heading, body, and hint', () => {
    render(
      <ConversationalEmptyState
        heading="Ready to set up your first relocation?"
        body="Add your first employee's move."
        hint="Takes about 2 minutes"
      />,
    );
    expect(screen.getByRole('heading', { name: /Ready to set up your first relocation/ })).toBeInTheDocument();
    expect(screen.getByText("Add your first employee's move.")).toBeInTheDocument();
    expect(screen.getByText('Takes about 2 minutes')).toBeInTheDocument();
  });

  it('renders quick actions and fires the matching onClick', () => {
    const primary = vi.fn();
    const secondary = vi.fn();
    render(
      <ConversationalEmptyState
        icon={PlaneTakeoff}
        heading="Heading"
        body="Body"
        actions={[
          { label: 'Add your first relocation', onClick: primary },
          { label: 'Import your team roster', onClick: secondary },
        ]}
      />,
    );

    fireEvent.click(screen.getByText('Import your team roster'));
    expect(secondary).toHaveBeenCalledTimes(1);
    expect(primary).not.toHaveBeenCalled();

    fireEvent.click(screen.getByText('Add your first relocation'));
    expect(primary).toHaveBeenCalledTimes(1);
  });

  it('styles the first action as the primary (navy) CTA by default', () => {
    render(
      <ConversationalEmptyState
        heading="Heading"
        body="Body"
        actions={[
          { label: 'Primary', onClick: vi.fn() },
          { label: 'Secondary', onClick: vi.fn() },
        ]}
      />,
    );
    // primary variant carries the navy background token; outline does not
    expect(screen.getByText('Primary').className).toContain('bg-[#0b2b43]');
    expect(screen.getByText('Secondary').className).not.toContain('bg-[#0b2b43]');
  });

  it('omits the action row when no actions are given', () => {
    render(<ConversationalEmptyState heading="Heading" body="Body" />);
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});
