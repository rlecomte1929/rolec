/**
 * Characterisation of the misc API cluster before splitting client.ts (WS3 Task 3.8 slice 10).
 * Method names are the parity oracle: later slices must keep this list unless they intentionally change the API.
 */
import { describe, expect, it } from 'vitest';

import {
  dossierAPI as dossierAPIFromModule,
  guidanceAPI as guidanceAPIFromModule,
  resourcesAPI as resourcesAPIFromModule,
  specialistReviewAPI as specialistReviewAPIFromModule,
} from '../miscApi';
import { dossierAPI, guidanceAPI, resourcesAPI, specialistReviewAPI } from '../client';

const RESOURCES_API_METHODS = [
  'getCountryResources',
  'getPage',
  'getContext',
  'getDestinations',
  'getHrPreviewPage',
  'getCityActivities',
  'getResources',
  'getEvents',
  'getRecommended',
] as const;

const DOSSIER_API_METHODS = [
  'getQuestions',
  'saveAnswers',
  'searchSuggestions',
  'addCaseQuestion',
] as const;

const GUIDANCE_API_METHODS = ['generate', 'getLatest', 'explain'] as const;

const SPECIALIST_REVIEW_API_METHODS = ['getRoadmap', 'submit'] as const;

describe('misc API cluster surface', () => {
  it('exposes the characterised resourcesAPI method names', () => {
    expect(Object.keys(resourcesAPI).sort()).toEqual([...RESOURCES_API_METHODS].sort());
  });
  it('re-exports the same resourcesAPI object as miscApi.ts', () => {
    expect(resourcesAPI).toBe(resourcesAPIFromModule);
  });

  it('exposes the characterised dossierAPI method names', () => {
    expect(Object.keys(dossierAPI).sort()).toEqual([...DOSSIER_API_METHODS].sort());
  });
  it('re-exports the same dossierAPI object as miscApi.ts', () => {
    expect(dossierAPI).toBe(dossierAPIFromModule);
  });

  it('exposes the characterised guidanceAPI method names', () => {
    expect(Object.keys(guidanceAPI).sort()).toEqual([...GUIDANCE_API_METHODS].sort());
  });
  it('re-exports the same guidanceAPI object as miscApi.ts', () => {
    expect(guidanceAPI).toBe(guidanceAPIFromModule);
  });

  it('exposes the characterised specialistReviewAPI method names', () => {
    expect(Object.keys(specialistReviewAPI).sort()).toEqual([...SPECIALIST_REVIEW_API_METHODS].sort());
  });
  it('re-exports the same specialistReviewAPI object as miscApi.ts', () => {
    expect(specialistReviewAPI).toBe(specialistReviewAPIFromModule);
  });
});
