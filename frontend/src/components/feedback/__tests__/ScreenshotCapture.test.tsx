import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ScreenshotCapture } from '../ScreenshotCapture';

// html2canvas is lazy-imported inside the component — mock the module.
vi.mock('html2canvas', () => ({
  default: vi.fn(() => Promise.resolve({ toDataURL: () => 'data:image/png;base64,MOCKSHOT' })),
}));

describe('ScreenshotCapture', () => {
  beforeEach(() => vi.clearAllMocks());

  it('offers full-page, select-region and skip', () => {
    render(<ScreenshotCapture onCapture={() => {}} onCancel={() => {}} />);
    expect(screen.getByRole('button', { name: /full page/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /select region/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /skip/i })).toBeInTheDocument();
  });

  it('full-page capture emits the captured data URL', async () => {
    const onCapture = vi.fn();
    render(<ScreenshotCapture onCapture={onCapture} onCancel={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /full page/i }));
    await waitFor(() => expect(onCapture).toHaveBeenCalledWith('data:image/png;base64,MOCKSHOT'));
  });

  it('select-region shows the drag overlay', () => {
    render(<ScreenshotCapture onCapture={() => {}} onCancel={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /select region/i }));
    expect(screen.getByTestId('region-overlay')).toBeInTheDocument();
  });

  it('skip cancels', () => {
    const onCancel = vi.fn();
    render(<ScreenshotCapture onCapture={() => {}} onCancel={onCancel} />);
    fireEvent.click(screen.getByRole('button', { name: /skip/i }));
    expect(onCancel).toHaveBeenCalled();
  });
});
