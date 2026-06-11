import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { SegmentedOptionCards } from './SegmentedOptionCards';

afterEach(cleanup);

const OPTIONS = [
  { value: 'solo', label: 'Just me' },
  { value: 'partner', label: 'My partner' },
  { value: 'family', label: 'Partner & children' },
];

describe('SegmentedOptionCards', () => {
  it('renders every option label', () => {
    render(<SegmentedOptionCards options={OPTIONS} value="family" onChange={() => {}} />);
    OPTIONS.forEach((o) => expect(screen.getByText(o.label)).toBeInTheDocument());
  });
  it('marks the selected option with aria-pressed', () => {
    render(<SegmentedOptionCards options={OPTIONS} value="family" onChange={() => {}} />);
    expect(screen.getByRole('button', { name: /Partner & children/ }).getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByRole('button', { name: /Just me/ }).getAttribute('aria-pressed')).toBe('false');
  });
  it('calls onChange with the value when an option is clicked', () => {
    const onChange = vi.fn();
    render(<SegmentedOptionCards options={OPTIONS} value="family" onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: /My partner/ }));
    expect(onChange).toHaveBeenCalledWith('partner');
  });
});
