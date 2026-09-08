import '@testing-library/jest-dom/vitest';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { Textarea } from './Textarea';

afterEach(cleanup);

describe('Textarea', () => {
  it('associates the label with the control', () => {
    render(<Textarea label="Notes" value="" onChange={() => {}} />);
    expect(screen.getByLabelText('Notes')).toBeInTheDocument();
  });

  it('calls onChange with the value (not the event)', () => {
    const onChange = vi.fn();
    render(<Textarea label="Notes" value="" onChange={onChange} />);
    fireEvent.change(screen.getByLabelText('Notes'), { target: { value: 'hello' } });
    expect(onChange).toHaveBeenCalledWith('hello');
  });

  it('surfaces an error with aria-invalid + role=alert', () => {
    render(<Textarea label="Notes" value="" onChange={() => {}} error="Required" />);
    expect(screen.getByLabelText('Notes')).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByRole('alert')).toHaveTextContent('Required');
  });

  it('unstyled renders a bare textarea with only the passed className', () => {
    render(<Textarea unstyled className="custom" defaultValue="x" aria-label="bare" />);
    const el = screen.getByLabelText('bare');
    expect(el.tagName).toBe('TEXTAREA');
    expect(el.className).toBe('custom');
  });
});
