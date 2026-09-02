import '@testing-library/jest-dom/vitest';
import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PageHeader } from './PageHeader';

afterEach(cleanup);

function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe('PageHeader', () => {
  it('renders the title as an h1 with optional subtitle and eyebrow', () => {
    renderWithRouter(<PageHeader title="Companies" subtitle="Manage employers" eyebrow="Admin console" />);
    expect(screen.getByRole('heading', { level: 1, name: 'Companies' })).toBeInTheDocument();
    expect(screen.getByText('Manage employers')).toBeInTheDocument();
    const eyebrow = screen.getByText('Admin console');
    expect(eyebrow).toBeInTheDocument();
    expect(eyebrow.className).toMatch(/text-slate-600/);
  });

  it('renders breadcrumbs in a nav landmark; the last crumb is aria-current and not a link', () => {
    renderWithRouter(
      <PageHeader title="Acme" breadcrumbs={[{ label: 'Admin', href: '/admin' }, { label: 'Companies', href: '/admin/companies' }, { label: 'Acme' }]} />,
    );
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Admin' })).toHaveAttribute('href', '/admin');
    const current = screen.getByText('Acme', { selector: '[aria-current="page"]' });
    expect(current).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Acme' })).toBeNull();
  });

  it('renders an actions slot', () => {
    renderWithRouter(<PageHeader title="Users" actions={<button>New user</button>} />);
    expect(screen.getByRole('button', { name: 'New user' })).toBeInTheDocument();
  });
});
