import { describe, it, expect } from 'vitest';
import { parseSubmitError } from '../parseSubmitError';

const GENERIC = 'Submission failed. Please try again.';

describe('parseSubmitError', () => {
  it('extracts message + suggestedStep from an axios 400 (response.data.detail object)', () => {
    // Exactly what POST /submit returns and axios wraps (AIQ-1311).
    const axiosErr = {
      message: 'Request failed with status code 400',
      response: {
        data: {
          detail: {
            message: 'Profile is not complete. Please complete the required wizard fields.',
            missingFields: ['relocationBasics.destCity'],
            suggestedStep: 1,
          },
        },
      },
    };
    expect(parseSubmitError(axiosErr)).toEqual({
      message: 'Profile is not complete. Please complete the required wizard fields.',
      suggestedStep: 1,
    });
  });

  it('extracts from a fetch/buildApiError-style error (err.detail object)', () => {
    const fetchErr = {
      message: 'Profile is not complete.',
      detail: { message: 'Profile is not complete.', suggestedStep: 2 },
    };
    expect(parseSubmitError(fetchErr)).toEqual({
      message: 'Profile is not complete.',
      suggestedStep: 2,
    });
  });

  it('uses a string detail directly', () => {
    expect(parseSubmitError({ response: { data: { detail: 'Please finish all steps.' } } })).toEqual({
      message: 'Please finish all steps.',
      suggestedStep: null,
    });
  });

  it('never surfaces the raw axios "Request failed with status code 400"', () => {
    expect(parseSubmitError({ message: 'Request failed with status code 400' })).toEqual({
      message: GENERIC,
      suggestedStep: null,
    });
  });

  it('keeps a meaningful non-axios error message (e.g. a client-side save failure)', () => {
    expect(parseSubmitError({ message: "Couldn't save your latest changes." })).toEqual({
      message: "Couldn't save your latest changes.",
      suggestedStep: null,
    });
  });

  it('falls back to a friendly default for null/undefined/unknown', () => {
    expect(parseSubmitError(null)).toEqual({ message: GENERIC, suggestedStep: null });
    expect(parseSubmitError(undefined)).toEqual({ message: GENERIC, suggestedStep: null });
    expect(parseSubmitError({})).toEqual({ message: GENERIC, suggestedStep: null });
  });
});
