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

  it('empty variant: shows the empty headline + a Check again retry', () => {
    const onRetry = vi.fn();
    render(<RoadmapBeingBuilt variant="empty" onRetry={onRetry} />);
    expect(screen.getByText(/No roadmap steps yet/i)).toBeInTheDocument();
    // still informative — the preview is shown
    expect(screen.getByText('Immigration & visa')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Check again/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('failed variant: shows the error headline + a Try again retry, and hides the preview', () => {
    const onRetry = vi.fn();
    render(<RoadmapBeingBuilt variant="failed" onRetry={onRetry} />);
    expect(screen.getByText(/couldn't load your roadmap/i)).toBeInTheDocument();
    // the "what will appear here" preview must NOT show on an error screen
    expect(screen.queryByText('Immigration & visa')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Try again/i }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('generating variant is the default and shows the preparing pill (no retry)', () => {
    render(<RoadmapBeingBuilt variant="generating" />);
    expect(screen.getByText(/Preparing your plan/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Try again|Check again/i })).not.toBeInTheDocument();
  });
});
