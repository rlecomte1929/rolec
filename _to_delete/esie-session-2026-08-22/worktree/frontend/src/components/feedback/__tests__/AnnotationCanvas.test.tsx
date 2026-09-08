import { createRef } from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { AnnotationCanvas, type AnnotationCanvasHandle } from '../AnnotationCanvas';

const IMG = 'data:image/png;base64,iVBORw0KGgo='; // tiny stub (drawing is browser-verified)

describe('AnnotationCanvas', () => {
  it('renders the pen / rectangle / arrow / undo / clear toolbar', () => {
    render(<AnnotationCanvas imageSrc={IMG} />);
    expect(screen.getByRole('button', { name: /pen/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /rect/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /arrow/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /undo/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /clear/i })).toBeInTheDocument();
  });

  it('selecting a tool marks it pressed (pen is the default)', () => {
    render(<AnnotationCanvas imageSrc={IMG} />);
    expect(screen.getByRole('button', { name: /pen/i })).toHaveAttribute('aria-pressed', 'true');
    fireEvent.click(screen.getByRole('button', { name: /rect/i }));
    expect(screen.getByRole('button', { name: /rect/i })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: /pen/i })).toHaveAttribute('aria-pressed', 'false');
  });

  it('exposes getAnnotatedDataURL() returning an image data URL', () => {
    const ref = createRef<AnnotationCanvasHandle>();
    render(<AnnotationCanvas ref={ref} imageSrc={IMG} />);
    const url = ref.current!.getAnnotatedDataURL();
    expect(typeof url).toBe('string');
    expect(url.startsWith('data:image')).toBe(true); // real toDataURL, or the imageSrc fallback
  });

  it('undo and clear are safe to click with no strokes (no throw)', () => {
    render(<AnnotationCanvas imageSrc={IMG} />);
    expect(() => {
      fireEvent.click(screen.getByRole('button', { name: /undo/i }));
      fireEvent.click(screen.getByRole('button', { name: /clear/i }));
    }).not.toThrow();
  });
});
