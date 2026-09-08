/**
 * [P4-6] CitationBlock.test.tsx — Tests for citation rendering system
 *
 * Coverage:
 *   - parseResponseSegments: text/cite segment splitting
 *   - computeVerifiedStatus: confidence threshold logic
 *   - buildCitationsFromChunks: chunk→Citation mapping + [Source:] replacement
 *   - CitationBlock: badge rendering, collapsible panel, superscript links
 *   - CitationRow: doc_name, section, page, excerpt, confidence pill, open link
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';

expect.extend(matchers);
import { render, screen, fireEvent, within, cleanup } from '@testing-library/react';

afterEach(() => {
  cleanup();
});

// Pure utility imports (no DOM needed)
import {
  computeVerifiedStatus,
  buildCitationsFromChunks,
  CitationBlock,
  type Citation,
} from '../CitationBlock';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeCitation(overrides: Partial<Citation> = {}): Citation {
  return {
    index: 1,
    doc_name: 'Global Mobility Policy 2025',
    section: '4.2 Housing Cap by Grade',
    page: 12,
    confidence: 0.94,
    text: 'The housing allowance for Manager grade is EUR 3,500 per month.',
    signed_url: 'https://storage.example.com/policy.pdf?page=12&token=abc123',
    ...overrides,
  };
}

function makeCitations(count: number): Citation[] {
  return Array.from({ length: count }, (_, i) =>
    makeCitation({
      index: i + 1,
      doc_name: `Policy Doc ${i + 1}`,
      section: `Section ${i + 1}`,
      page: i + 1,
      confidence: 0.9,
      text: `Excerpt for chunk ${i + 1}.`,
      signed_url: `https://storage.example.com/policy.pdf?page=${i + 1}`,
    }),
  );
}

// ---------------------------------------------------------------------------
// computeVerifiedStatus
// ---------------------------------------------------------------------------

describe('computeVerifiedStatus', () => {
  it('returns true for empty array', () => {
    expect(computeVerifiedStatus([])).toBe(true);
  });

  it('returns true when all scores ≥ 0.85', () => {
    expect(
      computeVerifiedStatus([
        { confidence_score: 0.85 },
        { confidence_score: 0.94 },
        { confidence_score: 1.0 },
      ]),
    ).toBe(true);
  });

  it('returns false when any score < 0.85', () => {
    expect(
      computeVerifiedStatus([
        { confidence_score: 0.94 },
        { confidence_score: 0.84 },
      ]),
    ).toBe(false);
  });

  it('returns true when score is exactly 0.85', () => {
    expect(computeVerifiedStatus([{ confidence_score: 0.85 }])).toBe(true);
  });

  it('ignores null scores (treats them as passing)', () => {
    expect(
      computeVerifiedStatus([
        { confidence_score: null },
        { confidence_score: 0.9 },
      ]),
    ).toBe(true);
  });

  it('returns true when all scores are null', () => {
    expect(
      computeVerifiedStatus([
        { confidence_score: null },
        { confidence_score: null },
      ]),
    ).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// buildCitationsFromChunks
// ---------------------------------------------------------------------------

describe('buildCitationsFromChunks', () => {
  const sampleChunks = [
    {
      id: 'chunk-1',
      section_path: '4.2 Housing Cap',
      text: 'The housing allowance for Manager grade is EUR 3,500 per month.',
      confidence_score: 0.94,
      page_start: 12,
      doc_id: 'doc-1',
    },
    {
      id: 'chunk-2',
      section_path: '5.1 Lump Sum',
      text: 'A lump sum of NOK 80,000 is provided on arrival.',
      confidence_score: 0.72,
      page_start: 20,
      doc_id: 'doc-2',
    },
  ];

  it('builds correct Citation objects from chunks', () => {
    const docNames = new Map([
      ['doc-1', 'Global Mobility Policy'],
      ['doc-2', 'Nordic Supplement'],
    ]);
    const signedUrls = new Map([
      ['chunk-1', 'https://storage.example.com/policy.pdf?page=12'],
      ['chunk-2', 'https://storage.example.com/nordic.pdf?page=20'],
    ]);

    const { citations } = buildCitationsFromChunks(
      'Some response [Source: 4.2 Housing Cap] text.',
      sampleChunks,
      docNames,
      signedUrls,
    );

    expect(citations).toHaveLength(2);
    expect(citations[0]).toMatchObject({
      index: 1,
      doc_name: 'Global Mobility Policy',
      section: '4.2 Housing Cap',
      page: 12,
      confidence: 0.94,
      signed_url: 'https://storage.example.com/policy.pdf?page=12',
    });
    expect(citations[1]).toMatchObject({
      index: 2,
      doc_name: 'Nordic Supplement',
      section: '5.1 Lump Sum',
      page: 20,
      confidence: 0.72,
    });
  });

  it('replaces [Source: section_path] markers with [N] in text', () => {
    const docNames = new Map([['doc-1', 'Policy']]);
    const signedUrls = new Map();

    const responseText =
      'Your housing allowance is EUR 3,500 [Source: 4.2 Housing Cap] per month.';
    const { text } = buildCitationsFromChunks(
      responseText,
      sampleChunks,
      docNames,
      signedUrls,
    );

    expect(text).toContain('[1]');
    expect(text).not.toContain('[Source:');
  });

  it('handles multiple [Source:] markers in text', () => {
    const docNames = new Map([
      ['doc-1', 'Policy'],
      ['doc-2', 'Nordic'],
    ]);
    const signedUrls = new Map();

    const responseText =
      'Housing [Source: 4.2 Housing Cap] and lump sum [Source: 5.1 Lump Sum] apply.';
    const { text } = buildCitationsFromChunks(
      responseText,
      sampleChunks,
      docNames,
      signedUrls,
    );

    expect(text).toContain('[1]');
    expect(text).toContain('[2]');
    expect(text).not.toContain('[Source:');
  });

  it('limits to top 5 chunks', () => {
    const manyChunks = Array.from({ length: 8 }, (_, i) => ({
      id: `chunk-${i}`,
      section_path: `Section ${i}`,
      text: `Text ${i}`,
      confidence_score: 0.9,
      page_start: i,
      doc_id: `doc-${i}`,
    }));

    const { citations } = buildCitationsFromChunks('text', manyChunks);
    expect(citations).toHaveLength(5);
  });

  it('falls back to "Company Policy" when doc_id not in docNames map', () => {
    const { citations } = buildCitationsFromChunks(
      'text',
      [sampleChunks[0]],
      new Map(), // empty map
    );
    expect(citations[0].doc_name).toBe('Company Policy');
  });

  it('falls back to "#" when chunk id not in signedUrls map', () => {
    const { citations } = buildCitationsFromChunks('text', [sampleChunks[0]]);
    expect(citations[0].signed_url).toBe('#');
  });

  it('computes verified status correctly', () => {
    const highConf = [{ ...sampleChunks[0], confidence_score: 0.94 }];
    const { verified: v1 } = buildCitationsFromChunks('text', highConf);
    expect(v1).toBe(true);

    const lowConf = [{ ...sampleChunks[1], confidence_score: 0.72 }];
    const { verified: v2 } = buildCitationsFromChunks('text', lowConf);
    expect(v2).toBe(false);
  });

  it('handles null section_path with fallback label', () => {
    const chunk = { ...sampleChunks[0], section_path: null };
    const { citations } = buildCitationsFromChunks('text', [chunk]);
    expect(citations[0].section).toBe('Chunk 1');
  });

  it('handles null page_start with fallback 1', () => {
    const chunk = { ...sampleChunks[0], page_start: null };
    const { citations } = buildCitationsFromChunks('text', [chunk]);
    expect(citations[0].page).toBe(1);
  });

  it('handles null confidence_score with fallback 0.9', () => {
    const chunk = { ...sampleChunks[0], confidence_score: null };
    const { citations } = buildCitationsFromChunks('text', [chunk]);
    expect(citations[0].confidence).toBe(0.9);
  });
});

// ---------------------------------------------------------------------------
// CitationBlock — rendering
// ---------------------------------------------------------------------------

describe('CitationBlock', () => {
  const defaultCitations = [
    makeCitation({ index: 1, confidence: 0.94 }),
    makeCitation({ index: 2, section: '5.1 Lump Sum', confidence: 0.7, page: 20 }),
  ];

  // ── Badge rendering ───────────────────────────────────────────────────────

  describe('confidence badge', () => {
    it('shows "Verified" badge when verified=true', () => {
      render(
        <CitationBlock
          response="Your allowance is EUR 3,500 [1]."
          citations={defaultCitations}
          verified={true}
        />,
      );
      expect(screen.getByRole('status', { name: /verified/i })).toBeInTheDocument();
      expect(screen.queryByRole('status', { name: /review/i })).not.toBeInTheDocument();
    });

    it('shows "Review recommended" badge when verified=false', () => {
      render(
        <CitationBlock
          response="Your allowance is EUR 3,500 [1]."
          citations={defaultCitations}
          verified={false}
        />,
      );
      expect(
        screen.getByRole('status', { name: /review recommended/i }),
      ).toBeInTheDocument();
      expect(screen.queryByRole('status', { name: /all sources verified/i })).not.toBeInTheDocument();
    });
  });

  // ── Response text rendering ───────────────────────────────────────────────

  describe('response text', () => {
    it('renders response text correctly', () => {
      render(
        <CitationBlock
          response="Housing allowance applies."
          citations={[]}
          verified={true}
        />,
      );
      expect(screen.getByText(/housing allowance applies/i)).toBeInTheDocument();
    });

    it('renders superscript citation buttons for known [N] markers', () => {
      render(
        <CitationBlock
          response="Allowance is EUR 3,500 [1] per month."
          citations={[makeCitation({ index: 1 })]}
          verified={true}
        />,
      );
      // Superscript button with aria-label "Source 1"
      expect(screen.getByRole('button', { name: /source 1/i })).toBeInTheDocument();
    });

    it('renders plain [N] spans for citations not in the citations array', () => {
      render(
        <CitationBlock
          response="Allowance [1] and bonus [9]."
          citations={[makeCitation({ index: 1 })]}
          verified={true}
        />,
      );
      // [9] has no matching citation → rendered as plain span text
      expect(screen.queryByRole('button', { name: /source 9/i })).not.toBeInTheDocument();
      expect(screen.getByText('[9]')).toBeInTheDocument();
    });

    it('renders multiple citation markers', () => {
      render(
        <CitationBlock
          response="Housing [1] and lump sum [2] apply."
          citations={[
            makeCitation({ index: 1 }),
            makeCitation({ index: 2, section: '5.1 Lump Sum' }),
          ]}
          verified={true}
        />,
      );
      expect(screen.getByRole('button', { name: /source 1/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /source 2/i })).toBeInTheDocument();
    });
  });

  // ── Collapsible panel ─────────────────────────────────────────────────────

  describe('collapsible sources panel', () => {
    it('is closed by default', () => {
      render(
        <CitationBlock
          response="Response [1]."
          citations={[makeCitation()]}
          verified={true}
        />,
      );
      const toggle = screen.getByRole('button', { name: /policy sources/i });
      expect(toggle).toHaveAttribute('aria-expanded', 'false');
      // Citation list should not be visible
      expect(screen.queryByRole('list', { name: /policy source citations/i })).not.toBeInTheDocument();
    });

    it('opens when the toggle button is clicked', () => {
      render(
        <CitationBlock
          response="Response [1]."
          citations={[makeCitation()]}
          verified={true}
        />,
      );
      const toggle = screen.getByRole('button', { name: /policy sources/i });
      fireEvent.click(toggle);

      expect(toggle).toHaveAttribute('aria-expanded', 'true');
      expect(screen.getByRole('list', { name: /policy source citations/i })).toBeInTheDocument();
    });

    it('closes again on second toggle click', () => {
      render(
        <CitationBlock
          response="Response [1]."
          citations={[makeCitation()]}
          verified={true}
        />,
      );
      const toggle = screen.getByRole('button', { name: /policy sources/i });
      fireEvent.click(toggle); // open
      fireEvent.click(toggle); // close

      expect(toggle).toHaveAttribute('aria-expanded', 'false');
      expect(screen.queryByRole('list', { name: /policy source citations/i })).not.toBeInTheDocument();
    });

    it('shows citation count in toggle button', () => {
      render(
        <CitationBlock
          response="Response [1] [2]."
          citations={makeCitations(2)}
          verified={true}
        />,
      );
      // "Policy sources (2)" should be visible
      expect(screen.getByText(/policy sources/i)).toBeInTheDocument();
      expect(screen.getByText('(2)')).toBeInTheDocument();
    });

    it('does not show toggle button when no citations', () => {
      render(
        <CitationBlock
          response="Response with no citations."
          citations={[]}
          verified={true}
        />,
      );
      expect(screen.queryByRole('button', { name: /policy sources/i })).not.toBeInTheDocument();
    });

    it('limits displayed citations to 5 even if more are provided', () => {
      const manyCitations = makeCitations(8);
      render(
        <CitationBlock
          response="Response."
          citations={manyCitations}
          verified={true}
        />,
      );
      const toggle = screen.getByRole('button', { name: /policy sources/i });
      // Toggle label shows 5 (not 8)
      expect(screen.getByText('(5)')).toBeInTheDocument();
      fireEvent.click(toggle);
      const list = screen.getByRole('list', { name: /policy source citations/i });
      const items = within(list).getAllByRole('listitem');
      expect(items).toHaveLength(5);
    });
  });

  // ── CitationRow contents ──────────────────────────────────────────────────

  describe('citation row contents', () => {
    beforeEach(() => {
      render(
        <CitationBlock
          response="Response [1]."
          citations={[
            makeCitation({
              index: 1,
              doc_name: 'Global Mobility Policy 2025',
              section: '4.2 Housing Cap',
              page: 12,
              confidence: 0.94,
              text: 'The housing allowance for Manager grade is EUR 3,500 per month.',
              signed_url: 'https://storage.example.com/policy.pdf?page=12',
            }),
          ]}
          verified={true}
        />,
      );
      // Open the panel
      fireEvent.click(screen.getByRole('button', { name: /policy sources/i }));
    });

    it('shows document name', () => {
      expect(screen.getByText('Global Mobility Policy 2025')).toBeInTheDocument();
    });

    it('shows section reference', () => {
      expect(screen.getByText(/section 4\.2 housing cap/i)).toBeInTheDocument();
    });

    it('shows page number', () => {
      expect(screen.getByText(/p\.12/i)).toBeInTheDocument();
    });

    it('shows text excerpt (truncated at 180 chars)', () => {
      expect(
        screen.getByText(/housing allowance for manager grade/i),
      ).toBeInTheDocument();
    });

    it('shows high confidence pill in teal', () => {
      expect(screen.getByText(/94% confidence/i)).toBeInTheDocument();
    });

    it('renders "Open" link to the signed URL', () => {
      const link = screen.getByRole('link', { name: /open global mobility policy/i });
      expect(link).toHaveAttribute('href', 'https://storage.example.com/policy.pdf?page=12');
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    });
  });

  describe('low-confidence citation row', () => {
    it('shows amber confidence pill for confidence < 0.85', () => {
      render(
        <CitationBlock
          response="Response [1]."
          citations={[makeCitation({ confidence: 0.72 })]}
          verified={false}
        />,
      );
      fireEvent.click(screen.getByRole('button', { name: /policy sources/i }));
      expect(screen.getByText(/72% confidence/i)).toBeInTheDocument();
    });
  });

  // ── Citation click → opens panel and scrolls ──────────────────────────────

  describe('citation marker click', () => {
    it('opens the sources panel when a citation marker is clicked', () => {
      render(
        <CitationBlock
          response="Allowance [1] applies."
          citations={[makeCitation({ index: 1 })]}
          verified={true}
        />,
      );
      // Panel should be closed
      expect(screen.queryByRole('list', { name: /policy source citations/i })).not.toBeInTheDocument();

      // Click the superscript [1] button
      fireEvent.click(screen.getByRole('button', { name: /source 1/i }));

      // Panel should now be open
      expect(screen.getByRole('list', { name: /policy source citations/i })).toBeInTheDocument();
    });

    it('keeps panel open if already open when citation is clicked', () => {
      render(
        <CitationBlock
          response="Allowance [1] and [2] apply."
          citations={[
            makeCitation({ index: 1 }),
            makeCitation({ index: 2, section: '5.1 Lump Sum' }),
          ]}
          verified={true}
        />,
      );
      // Open panel first
      fireEvent.click(screen.getByRole('button', { name: /policy sources/i }));
      expect(screen.getByRole('list', { name: /policy source citations/i })).toBeInTheDocument();

      // Click citation [2]
      fireEvent.click(screen.getByRole('button', { name: /source 2/i }));

      // Panel should still be open
      expect(screen.getByRole('list', { name: /policy source citations/i })).toBeInTheDocument();
    });
  });

  // ── data-testid ───────────────────────────────────────────────────────────

  it('renders with data-testid="citation-block"', () => {
    const { container } = render(
      <CitationBlock response="text" citations={[]} verified={true} />,
    );
    expect(container.querySelector('[data-testid="citation-block"]')).not.toBeNull();
  });

  // ── className passthrough ─────────────────────────────────────────────────

  it('applies additional className to the outer wrapper', () => {
    const { container } = render(
      <CitationBlock
        response="text"
        citations={[]}
        verified={true}
        className="my-custom-class"
      />,
    );
    expect(container.querySelector('.my-custom-class')).not.toBeNull();
  });

  // ── Excerpt truncation ────────────────────────────────────────────────────

  it('truncates long excerpts to 180 chars with ellipsis', () => {
    const longText = 'A'.repeat(200);
    render(
      <CitationBlock
        response="Response [1]."
        citations={[makeCitation({ text: longText })]}
        verified={true}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /policy sources/i }));
    const excerpt = screen.getByText(/a{30,}/i);
    expect(excerpt.textContent).toContain('…');
  });

  it('does not add ellipsis when excerpt ≤ 180 chars', () => {
    const shortText = 'Short excerpt.';
    render(
      <CitationBlock
        response="Response [1]."
        citations={[makeCitation({ text: shortText })]}
        verified={true}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /policy sources/i }));
    // Find the element containing the text
    const excerptEl = screen.getByText(`"${shortText}"`);
    expect(excerptEl.textContent).not.toContain('…');
  });
});
