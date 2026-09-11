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

  it('marks the recommended step with a teal ring and a navy filled CTA', () => {
    const { container } = render(
      <MemoryRouter>
        <WelcomeStepCard
          step={1}
          title="Configure your company"
          description="Add your company name."
          href="/hr/company-profile"
          badge="Start here"
          ctaLabel="Open company profile →"
          emphasized
        />
      </MemoryRouter>,
    );
    const card = container.querySelector('.ring-accent-500');
    expect(card).not.toBeNull();
    const link = screen.getByRole('link', { name: 'Open company profile →' });
    expect(link.className).toContain('bg-navy-800');
    expect(link.className).toContain('text-white');
  });

  it('keeps later steps as quiet text links without a teal ring', () => {
    const { container } = render(
      <MemoryRouter>
        <WelcomeStepCard
          step={2}
          title="Build your relocation policy"
          description="Define tiers."
          href="/hr/policy"
          ctaLabel="Open policy →"
        />
      </MemoryRouter>,
    );
    expect(container.querySelector('.ring-accent-500')).toBeNull();
    expect(screen.getByRole('link', { name: 'Open policy →' }).className).toContain('text-accent-600');
  });

  it('uses a distinct ctaLabel as the accessible name', () => {
    render(
      <MemoryRouter>
        <WelcomeStepCard
          step={1}
          title="Configure your company"
          description="Add your company name."
          href="/hr/company-profile"
          ctaLabel="Open company profile →"
        />
      </MemoryRouter>,
    );
    expect(screen.getByRole('link', { name: 'Open company profile →' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /get started/i })).toBeNull();
  });
});
