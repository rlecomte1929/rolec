import '@testing-library/jest-dom/vitest';
import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PetRequirementsSection } from '../PetRequirementsSection';

// AIQ-1344: the pet section showed a red "Could not load pet import data" banner
// whenever the pets read failed — including the common no-pets case (the pets table
// has no SELECT grant for authenticated, so the read errors). The banner must only
// appear for a genuine failure once pets are known to exist (the rules lookup).

interface MockState {
  pets: { data: unknown[]; error: unknown };
  rules: () => Promise<{ data: unknown }>;
}

// Mutable mock state (hoisted so the vi.mock factory can close over it).
const h = vi.hoisted(
  (): MockState => ({
    pets: { data: [], error: null },
    rules: () => Promise.resolve({ data: null }),
  }),
);

interface QueryStub {
  select: () => QueryStub;
  eq: () => QueryStub;
  maybeSingle?: () => Promise<{ data: unknown }>;
  then?: (
    onFulfilled: (v: { data: unknown[]; error: unknown }) => void,
    onRejected: (e: unknown) => void,
  ) => void;
}

vi.mock('../../../api/supabase', () => ({
  supabase: {
    from: (table: string): QueryStub => {
      if (table === 'pets') {
        const b: QueryStub = {
          select: () => b,
          eq: () => b,
          then: (onFulfilled, onRejected) => {
            void Promise.resolve(h.pets).then(onFulfilled, onRejected);
          },
        };
        return b;
      }
      const b: QueryStub = {
        select: () => b,
        eq: () => b,
        maybeSingle: () => h.rules(),
      };
      return b;
    },
  },
}));

const BANNER = /Could not load pet import data/i;

describe('PetRequirementsSection (AIQ-1344)', () => {
  beforeEach(() => {
    h.pets = { data: [], error: null };
    h.rules = () => Promise.resolve({ data: null });
  });
  afterEach(() => cleanup());

  it('shows no error banner when the pets read fails (treated as no pets)', async () => {
    h.pets = { data: [], error: { message: 'permission denied for table pets' } };
    const { container } = render(<PetRequirementsSection caseId="c1" destCountry="NO" />);
    await waitFor(() =>
      expect(screen.queryByText(/Loading pet requirements/i)).not.toBeInTheDocument(),
    );
    expect(screen.queryByText(BANNER)).not.toBeInTheDocument();
    expect(container).toBeEmptyDOMElement(); // hidden entirely
  });

  it('shows the error banner when pets exist but the rules lookup fails', async () => {
    h.pets = { data: [{ id: 'p1', name: 'Rex', species: 'dog', breed: null }], error: null };
    h.rules = () => Promise.reject(new Error('rules boom'));
    render(<PetRequirementsSection caseId="c1" destCountry="NO" />);
    await waitFor(() => expect(screen.getByText(BANNER)).toBeInTheDocument());
  });

  it('renders nothing when the case has zero pets (success)', async () => {
    h.pets = { data: [], error: null };
    const { container } = render(<PetRequirementsSection caseId="c1" destCountry="NO" />);
    await waitFor(() =>
      expect(screen.queryByText(/Loading pet requirements/i)).not.toBeInTheDocument(),
    );
    expect(screen.queryByText(BANNER)).not.toBeInTheDocument();
    expect(container).toBeEmptyDOMElement();
  });
});
