import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ProgressHeader } from '../ProgressHeader';

describe('ProgressHeader Component', () => {
  it('renders progress information', () => {
    render(
      <ProgressHeader
        answeredCount={5}
        totalQuestions={20}
        percentComplete={25}
        currentStep="Building Profile"
      />
    );
    
    expect(screen.getByText('Building Profile')).toBeInTheDocument();
    expect(screen.getByText('5 of 20 questions answered')).toBeInTheDocument();
    expect(screen.getByText('25%')).toBeInTheDocument();
  });

  it('displays default step when not provided', () => {
    render(
      <ProgressHeader
        answeredCount={0}
        totalQuestions={20}
        percentComplete={0}
      />
    );
    
    expect(screen.getByText('Building Your Profile')).toBeInTheDocument();
  });

  it('calculates percentage correctly', () => {
    render(
      <ProgressHeader
        answeredCount={10}
        totalQuestions={20}
        percentComplete={50}
      />
    );
    
    expect(screen.getByText('50%')).toBeInTheDocument();
  });
});
