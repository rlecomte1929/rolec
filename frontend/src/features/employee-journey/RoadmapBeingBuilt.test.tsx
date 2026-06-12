import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { RoadmapBeingBuilt } from './RoadmapBeingBuilt';

afterEach(cleanup);

describe('RoadmapBeingBuilt', () => {
  it('renders the "being built" headline', () => {
    render(<RoadmapBeingBuilt />);
    expect(screen.getByText(/We're building your roadmap/i)).toBeInTheDocument();
  });

  it('renders the 5 preview track names', () => {
    render(<RoadmapBeingBuilt />);
    expect(screen.getByText('Immigration & visa')).toBeInTheDocument();
    expect(screen.getByText('Housing')).toBeInTheDocument();
    expect(screen.getByText('Schooling')).toBeInTheDocument();
    expect(screen.getByText('Moving & setup')).toBeInTheDocument();
    expect(screen.getByText('Banking')).toBeInTheDocument();
  });

  it('shows the message-team button and fires the callback when onMessageTeam is provided', () => {
    const onMessageTeam = vi.fn();
    render(<RoadmapBeingBuilt onMessageTeam={onMessageTeam} />);
    const btn = screen.getByRole('button', { name: /Message my relocation team/i });
    expect(btn).toBeInTheDocument();
    fireEvent.click(btn);
    expect(onMessageTeam).toHaveBeenCalledTimes(1);
  });

  it('hides the message-team button when onMessageTeam is omitted', () => {
    render(<RoadmapBeingBuilt />);
    expect(screen.queryByRole('button', { name: /Message my relocation team/i })).not.toBeInTheDocument();
  });
});
