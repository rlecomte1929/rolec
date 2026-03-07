import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { GuidedQuestionCard } from '../GuidedQuestionCard';
import type { Question } from '../../types';

describe('GuidedQuestionCard Component', () => {
  const mockQuestion: Question = {
    id: 'q_test',
    title: 'What is your name?',
    whyThisMatters: 'We need this for identification',
    type: 'text',
    required: true,
    mapsTo: 'primaryApplicant.fullName',
    allowUnknown: false,
  };

  it('renders question title and explanation', () => {
    render(<GuidedQuestionCard question={mockQuestion} onAnswer={vi.fn()} />);
    
    expect(screen.getByText('What is your name?')).toBeInTheDocument();
    expect(screen.getByText(/We need this for identification/)).toBeInTheDocument();
    expect(screen.getByText('* Required')).toBeInTheDocument();
  });

  it('renders text input for text type', () => {
    render(<GuidedQuestionCard question={mockQuestion} onAnswer={vi.fn()} />);
    
    const input = screen.getByPlaceholderText('Enter your answer');
    expect(input).toBeInTheDocument();
  });

  it('calls onAnswer when submitted', async () => {
    const handleAnswer = vi.fn();
    render(<GuidedQuestionCard question={mockQuestion} onAnswer={handleAnswer} />);
    
    const input = screen.getByPlaceholderText('Enter your answer');
    fireEvent.change(input, { target: { value: 'John Doe' } });
    
    const button = screen.getByText('Continue');
    fireEvent.click(button);
    
    await waitFor(() => {
      expect(handleAnswer).toHaveBeenCalledWith('John Doe', false);
    });
  });

  it('renders single select options', () => {
    const selectQuestion: Question = {
      ...mockQuestion,
      type: 'single_select',
      options: [
        { value: 'opt1', label: 'Option 1' },
        { value: 'opt2', label: 'Option 2' },
      ],
    };

    render(<GuidedQuestionCard question={selectQuestion} onAnswer={vi.fn()} />);
    
    expect(screen.getByText('Option 1')).toBeInTheDocument();
    expect(screen.getByText('Option 2')).toBeInTheDocument();
  });

  it('shows unknown button when allowUnknown is true', () => {
    const unknownQuestion: Question = {
      ...mockQuestion,
      allowUnknown: true,
    };

    render(<GuidedQuestionCard question={unknownQuestion} onAnswer={vi.fn()} />);
    
    expect(screen.getByText("I don't know yet")).toBeInTheDocument();
  });

  it('calls onAnswer with isUnknown=true when unknown clicked', async () => {
    const handleAnswer = vi.fn();
    const unknownQuestion: Question = {
      ...mockQuestion,
      allowUnknown: true,
    };

    render(<GuidedQuestionCard question={unknownQuestion} onAnswer={handleAnswer} />);
    
    const unknownButton = screen.getByText("I don't know yet");
    fireEvent.click(unknownButton);
    
    await waitFor(() => {
      expect(handleAnswer).toHaveBeenCalledWith(null, true);
    });
  });

  it('renders boolean type with Yes/No buttons', () => {
    const boolQuestion: Question = {
      ...mockQuestion,
      type: 'boolean',
    };

    render(<GuidedQuestionCard question={boolQuestion} onAnswer={vi.fn()} />);
    
    expect(screen.getByText('Yes')).toBeInTheDocument();
    expect(screen.getByText('No')).toBeInTheDocument();
  });
});
