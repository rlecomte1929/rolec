import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { WelcomeStepCard } from './WelcomeStepCard';

describe('WelcomeStepCard', () => {
  it('gives Get started a 24px-tall hit area without changing the text size', () => {
    render(
      <MemoryRouter>
        <WelcomeStepCard
          step={1}
          title="Configure your company"
          description="Add your company name."
          href="/hr/company-profile"
        />
      </MemoryRouter>,
    );
    const link = screen.getByRole('link', { name: /get started/i });
    expect(link.className).toContain('min-h-6');
    expect(link.className).toContain('text-sm');
  });
});
