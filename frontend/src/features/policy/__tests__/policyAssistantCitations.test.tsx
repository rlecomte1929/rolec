/**
 * Sprint C — citation chip parser tests for the Policy Assistant.
 *
 * Covers:
 *  - extractChunkIdsInOrder: dedup + order preservation
 *  - formatAnswerWithCitations: chips for known chunks, muted superscript
 *    for unknown ids, bold span preservation, click-to-scroll wiring
 *  - scrollToSourceRef: locates a `data-policy-source-ref` row and adds
 *    the highlight class
 */
import '@testing-library/jest-dom/vitest';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

import {
  extractChunkIdsInOrder,
  formatAnswerWithCitations,
  scrollToSourceRef,
} from '../policyAssistantCitations';
import type { PolicyAssistantCitedChunk } from '../../../types/policyAssistant';

afterEach(cleanup);

describe('extractChunkIdsInOrder', () => {
  it('returns ids in citation order, deduped', () => {
    const text = 'A [chunk:abc] then B [chunk:def] then A again [chunk:abc].';
    expect(extractChunkIdsInOrder(text)).toEqual(['abc', 'def']);
  });

  it('returns empty for plain text', () => {
    expect(extractChunkIdsInOrder('No citations here.')).toEqual([]);
  });

  it('handles uuids with dashes', () => {
    const text = '[chunk:550e8400-e29b-41d4-a716-446655440000]';
    expect(extractChunkIdsInOrder(text)).toEqual([
      '550e8400-e29b-41d4-a716-446655440000',
    ]);
  });
});

describe('formatAnswerWithCitations', () => {
  const chunks: PolicyAssistantCitedChunk[] = [
    {
      id: 'ch-1',
      source_type: 'matrix_benefit',
      source_ref: 'policy_config_benefits.b-housing',
      chunk_text: 'Housing allowance: USD 4,500 per month.',
    },
    {
      id: 'ch-2',
      source_type: 'matrix_benefit',
      source_ref: 'policy_config_benefits.b-shipment',
      chunk_text: 'Household goods shipment: USD 12,000 one time.',
    },
  ];

  it('renders one clickable chip per known citation, indexed in order', () => {
    render(
      <div>
        {formatAnswerWithCitations(
          'Housing covers USD 4500 [chunk:ch-1]. Shipment is USD 12000 [chunk:ch-2].',
          chunks
        )}
      </div>
    );
    const chips = screen.getAllByTestId('policy-citation-chip');
    expect(chips).toHaveLength(2);
    expect(chips[0]).toHaveTextContent('[1]');
    expect(chips[1]).toHaveTextContent('[2]');
    expect(chips[0]).toHaveAttribute('data-source-ref', 'policy_config_benefits.b-housing');
    expect(chips[1]).toHaveAttribute('data-source-ref', 'policy_config_benefits.b-shipment');
  });

  it('reuses the same index when a chunk id appears multiple times', () => {
    render(
      <div>
        {formatAnswerWithCitations(
          'See [chunk:ch-1] and again [chunk:ch-1].',
          chunks
        )}
      </div>
    );
    const chips = screen.getAllByTestId('policy-citation-chip');
    expect(chips).toHaveLength(2);
    expect(chips[0]).toHaveTextContent('[1]');
    expect(chips[1]).toHaveTextContent('[1]'); // same chunk → same index
  });

  it('falls back to muted superscript when chunk metadata is missing', () => {
    const { container } = render(
      <div>
        {formatAnswerWithCitations('Without metadata [chunk:unknown123].', undefined)}
      </div>
    );
    expect(screen.queryByTestId('policy-citation-chip')).toBeNull();
    expect(container.querySelector('sup')).not.toBeNull();
    expect(container.textContent).toContain('[1]');
  });

  it('preserves bold spans (**text**) in non-citation segments', () => {
    render(
      <div>
        {formatAnswerWithCitations('The **housing** cap is USD 4500 [chunk:ch-1].', chunks)}
      </div>
    );
    expect(screen.getByText('housing').tagName).toBe('STRONG');
    expect(screen.getByTestId('policy-citation-chip')).toBeInTheDocument();
  });

  it('invokes onActivate with the chunk when chip is clicked', () => {
    const onActivate = vi.fn();
    render(
      <div>
        {formatAnswerWithCitations('Click me [chunk:ch-1].', chunks, onActivate)}
      </div>
    );
    fireEvent.click(screen.getByTestId('policy-citation-chip'));
    expect(onActivate).toHaveBeenCalledTimes(1);
    expect(onActivate.mock.calls[0][0].id).toBe('ch-1');
  });
});

describe('scrollToSourceRef', () => {
  let row: HTMLElement;
  let scrollSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    row = document.createElement('div');
    row.setAttribute('data-policy-source-ref', 'policy_config_benefits.b-housing');
    document.body.appendChild(row);
    // jsdom doesn't implement scrollIntoView; stub it.
    scrollSpy = vi.fn();
    row.scrollIntoView = scrollSpy as unknown as typeof row.scrollIntoView;
  });

  afterEach(() => {
    document.body.removeChild(row);
  });

  it('scrolls to and highlights the matching row', () => {
    expect(scrollToSourceRef('policy_config_benefits.b-housing')).toBe(true);
    expect(scrollSpy).toHaveBeenCalledTimes(1);
    expect(row.classList.contains('policy-source-highlight')).toBe(true);
  });

  it('returns false when the row is not present', () => {
    expect(scrollToSourceRef('policy_config_benefits.does-not-exist')).toBe(false);
  });

  it('clicking a chip with no onActivate scrolls to the source row', () => {
    const chunk: PolicyAssistantCitedChunk = {
      id: 'ch-h',
      source_type: 'matrix_benefit',
      source_ref: 'policy_config_benefits.b-housing',
      chunk_text: 'Housing.',
    };
    render(
      <div>{formatAnswerWithCitations('See [chunk:ch-h].', [chunk])}</div>
    );
    fireEvent.click(screen.getByTestId('policy-citation-chip'));
    expect(scrollSpy).toHaveBeenCalled();
  });
});
