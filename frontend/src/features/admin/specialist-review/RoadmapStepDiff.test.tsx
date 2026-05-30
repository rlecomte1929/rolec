import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { RoadmapStepDiff } from './RoadmapStepDiff';

const aiStep = {
  step_id: 'step-1',
  title: 'Apply for residence permit',
  description: 'Submit form UDI-123',
  source_url: 'https://udi.no/permit',
  confidence: 0.92,
};

describe('RoadmapStepDiff', () => {
  it('renders the AI step, confidence badge, and source url', () => {
    render(<RoadmapStepDiff step={aiStep} value={{ decision: 'approve' }} onChange={vi.fn()} />);
    expect(screen.getByText('Apply for residence permit')).toBeInTheDocument();
    expect(screen.getByText(/HIGH \(92%\)/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /source/i })).toHaveAttribute('href', 'https://udi.no/permit');
  });

  it('highlights an edited field and surfaces the reason-code selector', () => {
    const onChange = vi.fn();
    render(
      <RoadmapStepDiff
        step={aiStep}
        value={{ decision: 'edit', edited: { ...aiStep, title: 'Apply for work permit' }, reason_code: 'WRONG_PATHWAY' }}
        onChange={onChange}
      />,
    );
    expect(screen.getByTestId('diff-title')).toHaveAttribute('data-changed', 'true');
    expect(screen.getByLabelText(/reason code/i)).toBeInTheDocument();
  });

  it('fires onChange with reject when Reject is clicked', () => {
    const onChange = vi.fn();
    render(<RoadmapStepDiff step={aiStep} value={{ decision: 'approve' }} onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: /reject/i }));
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ decision: 'reject' }));
  });
});
