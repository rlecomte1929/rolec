import { describe, it, expect } from 'vitest';
import { derivePathSummary, destinationPermitLabel } from './hrAssignmentPermit';

describe('destinationPermitLabel', () => {
  it('maps Singapore (name) to Employment Pass', () => {
    expect(destinationPermitLabel('Singapore')).toBe('Employment Pass (EP)');
  });

  it('maps the SG code to Employment Pass', () => {
    expect(destinationPermitLabel('SG')).toBe('Employment Pass (EP)');
  });

  it('is case/whitespace insensitive', () => {
    expect(destinationPermitLabel('  germany ')).toBe('EU Blue Card');
  });

  it('returns null for an unknown/unmapped destination', () => {
    expect(destinationPermitLabel('Atlantis')).toBeNull();
  });

  it('returns null for empty/undefined input', () => {
    expect(destinationPermitLabel('')).toBeNull();
    expect(destinationPermitLabel(undefined)).toBeNull();
    expect(destinationPermitLabel(null)).toBeNull();
  });
});

describe('derivePathSummary', () => {
  const req = (pillar: string, title: string) => ({ pillar, title });

  it('says "no permit mapping" NEVER when approved requirements exist', () => {
    // THE REGRESSION. Ireland is absent from DESTINATION_PERMIT_LABELS, so the card used to
    // read "No permit mapping for this destination yet" — while the platform held 14 approved
    // requirement_items for IRELAND and served them on the corridor endpoint.
    const summary = derivePathSummary('Ireland', {
      covered: true,
      requirements: [
        req('RESIDENCE', 'Critical Skills Employment Permit — eligibility'),
        req('RESIDENCE', 'Immigration permission – Stamp 1 / IRP registration'),
      ],
    });
    expect(summary.detail).not.toContain('No permit mapping');
    expect(summary.detail).toContain('2 requirements');
    expect(summary.label).toBe('Critical Skills Employment Permit — eligibility');
  });

  it('keeps the familiar static label for a mapped destination', () => {
    const summary = derivePathSummary('Germany', {
      covered: true,
      requirements: [req('RESIDENCE', 'Aufenthaltstitel')],
    });
    expect(summary.label).toBe('EU Blue Card');
    expect(summary.detail).toContain('1 requirement');
    expect(summary.detail).not.toContain('1 requirements');
  });

  it('awaits a destination before saying anything about coverage', () => {
    expect(derivePathSummary(null, null)).toEqual({
      label: null,
      detail: 'Awaiting destination from intake.',
    });
  });

  it('distinguishes "no catalogue" from "nothing applies"', () => {
    // covered=false → we hold no catalogue. An empty list under covered=true → we checked and
    // nothing is required. Collapsing these is the AIQ-1473c failure.
    expect(derivePathSummary('Atlantis', { covered: false, requirements: [] }).detail).toBe(
      'No requirements catalogue for this destination yet.',
    );
    expect(derivePathSummary('Ireland', { covered: true, requirements: [] }).detail).toBe(
      'No requirements apply to this case.',
    );
  });

  it('falls back to the static label while the fetch is still in flight', () => {
    const summary = derivePathSummary('Norway', null);
    expect(summary.label).toBe('Skilled Worker Permit (UDI)');
    expect(summary.detail).toContain('confirm with the relevant authority');
  });

  it('does not claim a mapping for an unmapped destination that has not loaded', () => {
    const summary = derivePathSummary('Ireland', null);
    expect(summary.label).toBeNull();
    expect(summary.detail).toBe('Checking requirements for this destination…');
  });

  it('uses a non-RESIDENCE title only when nothing better exists', () => {
    const summary = derivePathSummary('Ireland', {
      covered: true,
      requirements: [req('TAX', 'Revenue registration')],
    });
    expect(summary.label).toBe('Revenue registration');
  });
});
