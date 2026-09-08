import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { MobilityCasePanelsView } from './MobilityCasePanelsView';

afterEach(() => {
  cleanup();
});

describe('MobilityCasePanelsView', () => {
  const base = {
    routeOrigin: 'France',
    routeDestination: 'Norway',
    caseTypeLabel: 'work relocation',
    familyStatusLine: 'Spouse or partner listed',
  };

  it('renders full case with missing items and next actions (deterministic labels)', () => {
    render(
      <MobilityCasePanelsView
        {...base}
        missingItems={[
          { id: 'ev-1', code: 'passport_copy_uploaded', status: 'missing', detail: 'Please upload.' },
        ]}
        nextActions={[
          {
            id: 'na-1',
            title: 'Upload a valid passport copy',
            description: 'Add a clear copy of the passport photo page.',
            priority: 1,
          },
        ]}
        loadState="loaded"
      />
    );

    expect(screen.getByTestId('mobility-panels-root')).toBeInTheDocument();
    expect(screen.getByText('France')).toBeInTheDocument();
    expect(screen.getByText('Norway')).toBeInTheDocument();
    expect(screen.getByText('work relocation')).toBeInTheDocument();
    expect(screen.getByText('Spouse or partner listed')).toBeInTheDocument();
    expect(screen.getByTestId('missing-list')).toBeInTheDocument();
    expect(screen.getByText(/passport copy uploaded/i)).toBeInTheDocument();
    expect(screen.getByTestId('next-list')).toBeInTheDocument();
    expect(screen.getByText('Upload a valid passport copy')).toBeInTheDocument();
  });

  it('empty / unlinked: skipped state shows stable empty copy', () => {
    render(
      <MobilityCasePanelsView
        {...base}
        missingItems={[]}
        nextActions={[]}
        loadState="skipped"
      />
    );

    expect(screen.getByTestId('missing-empty-unlinked')).toBeInTheDocument();
    expect(screen.getByTestId('next-empty-unlinked')).toBeInTheDocument();
    expect(screen.queryByTestId('missing-list')).not.toBeInTheDocument();
  });

  it('loading state shows aria-busy placeholders', () => {
    render(
      <MobilityCasePanelsView
        {...base}
        missingItems={[]}
        nextActions={[]}
        loadState="loading"
      />
    );

    expect(screen.getByTestId('missing-loading')).toHaveAttribute('aria-busy', 'true');
    expect(screen.getByTestId('next-loading')).toHaveAttribute('aria-busy', 'true');
  });

  it('error state surfaces message in both panels', () => {
    render(
      <MobilityCasePanelsView
        {...base}
        missingItems={[]}
        nextActions={[]}
        loadState="error"
        errorMessage="Mobility case not found."
      />
    );

    expect(screen.getByTestId('missing-error')).toHaveTextContent('Mobility case not found.');
    expect(screen.getByTestId('next-error')).toHaveTextContent('Mobility case not found.');
  });
});
