import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ImmigrationDisclaimer } from '../ImmigrationDisclaimer';
import {
  IMMIGRATION_DISCLAIMER_TITLE,
  IMMIGRATION_DISCLAIMER_BODY,
} from '../../../features/immigration/immigrationDisclaimerContent';

describe('ImmigrationDisclaimer', () => {
  it('renders the non-liability title + body', () => {
    render(<ImmigrationDisclaimer />);
    expect(screen.getByText(IMMIGRATION_DISCLAIMER_TITLE)).toBeTruthy();
    // body asserts the legal posture: recommendation, not advice, validate with a professional
    expect(screen.getByText(IMMIGRATION_DISCLAIMER_BODY)).toBeTruthy();
    expect(IMMIGRATION_DISCLAIMER_BODY).toContain('not legal advice');
    expect(IMMIGRATION_DISCLAIMER_BODY.toLowerCase()).toContain('licensed immigration professional');
  });
});
