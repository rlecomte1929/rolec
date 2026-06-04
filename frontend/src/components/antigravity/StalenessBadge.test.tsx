/**
 * [P2-08b] StalenessBadge.test.tsx
 *
 * The badge is additive: it renders only when a source is stale for its tier,
 * links to the official source URL, and is accessible. A fixed `now` keeps the
 * boundary assertions wall-clock-free.
 */
import { describe, it, expect, afterEach } from 'vitest';
import * as matchers from '@testing-library/jest-dom/matchers';
import React from 'react';
import { render, screen, cleanup } from '@testing-library/react';
import { StalenessBadge, isSourceStale } from './StalenessBadge';

expect.extend(matchers);
afterEach(cleanup);

// Reference "now". Defaults: tier1_critical=30, tier1_stable=60, tier2=90 days.
const NOW = new Date('2026-06-04T12:00:00Z');
const SOURCE = 'https://www.example.gov/official';

describe('StalenessBadge', () => {
  it('renders nothing when the source is fresh (under the tier threshold)', () => {
    render(<StalenessBadge lastVerified="2026-05-20T00:00:00Z" sourceUrl={SOURCE} now={NOW} />);
    expect(screen.queryByTestId('staleness-badge')).toBeNull();
  });

  it('renders the advisory when the source exceeds the default 30-day threshold', () => {
    render(<StalenessBadge lastVerified="2026-04-01T00:00:00Z" sourceUrl={SOURCE} now={NOW} />);
    const badge = screen.getByTestId('staleness-badge');
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent(/Source last verified/i);
    expect(badge).toHaveTextContent(/verifying directly at the source/i);
  });

  it('links directly to the official source URL (new tab, safe rel)', () => {
    render(<StalenessBadge lastVerified="2026-04-01T00:00:00Z" sourceUrl={SOURCE} now={NOW} />);
    const link = screen.getByRole('link', { name: /verifying directly at the source/i });
    expect(link).toHaveAttribute('href', SOURCE);
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  });

  it('falls back to plain text (no link) when no source URL is given', () => {
    render(<StalenessBadge lastVerified="2026-04-01T00:00:00Z" now={NOW} />);
    expect(screen.getByTestId('staleness-badge')).toHaveTextContent(/the official source/i);
    expect(screen.queryByRole('link')).toBeNull();
  });

  it('exposes an accessible live-region role for assistive tech', () => {
    render(<StalenessBadge lastVerified="2026-04-01T00:00:00Z" sourceUrl={SOURCE} now={NOW} />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('renders nothing when the last-verified date is missing or unparseable', () => {
    const { rerender } = render(<StalenessBadge lastVerified={null} sourceUrl={SOURCE} now={NOW} />);
    expect(screen.queryByTestId('staleness-badge')).toBeNull();
    rerender(<StalenessBadge lastVerified="not-a-date" sourceUrl={SOURCE} now={NOW} />);
    expect(screen.queryByTestId('staleness-badge')).toBeNull();
  });

  it('honours non-default tiers (tier2 = 90 days)', () => {
    // 45 days old: stale for tier1_critical (30) but fresh for tier2 (90).
    render(<StalenessBadge lastVerified="2026-04-20T00:00:00Z" sourceUrl={SOURCE} tier="tier2" now={NOW} />);
    expect(screen.queryByTestId('staleness-badge')).toBeNull();
  });
});

describe('isSourceStale', () => {
  it('treats exactly-N-days-old as the first stale day (boundary)', () => {
    // tier1_critical threshold = 30 days. 2026-05-05 → exactly 30 days before NOW.
    expect(isSourceStale('2026-05-05T12:00:00Z', 'tier1_critical', NOW)).toBe(true);
    // 29 days old → still fresh.
    expect(isSourceStale('2026-05-06T12:00:00Z', 'tier1_critical', NOW)).toBe(false);
  });

  it('is fail-open on missing / unparseable input', () => {
    expect(isSourceStale(null, 'tier1_critical', NOW)).toBe(false);
    expect(isSourceStale(undefined, 'tier1_critical', NOW)).toBe(false);
    expect(isSourceStale('garbage', 'tier1_critical', NOW)).toBe(false);
  });
});
