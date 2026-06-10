import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { Citations } from '../Citations';
import type { SourceRecordDTO } from '../../../types';

afterEach(cleanup);

function source(overrides: Partial<SourceRecordDTO> = {}): SourceRecordDTO {
  return {
    id: '1',
    url: 'https://udi.no/permit',
    title: 'Residence permit',
    publisherDomain: 'udi.no',
    retrievedAt: new Date().toISOString(), // fresh by default
    ...overrides,
  };
}

describe('Citations (I-2 freshness badge)', () => {
  it('renders the source domain link', () => {
    render(<Citations sources={[source()]} />);
    expect(screen.getByText('udi.no')).toBeInTheDocument();
  });

  it('shows a staleness badge for a source not verified in a long time', () => {
    render(<Citations sources={[source({ retrievedAt: '2020-01-01T00:00:00Z' })]} />);
    expect(screen.getByTestId('staleness-badge')).toBeInTheDocument();
  });

  it('shows no staleness badge for a freshly retrieved source', () => {
    render(<Citations sources={[source()]} />);
    expect(screen.queryByTestId('staleness-badge')).toBeNull();
  });

  it('renders nothing when there are no sources', () => {
    const { container } = render(<Citations sources={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
