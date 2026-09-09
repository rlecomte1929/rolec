/**
 * Characterisation of the services API cluster before splitting client.ts (WS3 Task 3.8 slice 7).
 * Method names are the parity oracle: later slices must keep this list unless they intentionally change the API.
 */
import { describe, expect, it } from 'vitest';

import {
  rfqAPI as rfqAPIFromModule,
  servicesAPI as servicesAPIFromModule,
  timelineAPI as timelineAPIFromModule,
  vendorAPI as vendorAPIFromModule,
} from '../servicesApi';
import { rfqAPI, servicesAPI, timelineAPI, vendorAPI } from '../client';

const SERVICES_API_METHODS = [
  'getServicesContext',
  'getServiceAnswers',
  'getServiceQuestions',
  'saveServiceAnswers',
  'createRfq',
  'getTasks',
  'getTask',
  'submitTask',
] as const;

const RFQ_API_METHODS = [
  'listByAssignment',
  'get',
  'listQuotes',
  'getPayerView',
  'acceptQuote',
  'proposeQuote',
] as const;

const VENDOR_API_METHODS = ['listRfqs', 'getRfq', 'submitQuote'] as const;

const TIMELINE_API_METHODS = ['getByAssignment', 'getByCase', 'updateMilestone'] as const;

describe('services API cluster surface', () => {
  it('exposes the characterised servicesAPI method names', () => {
    expect(Object.keys(servicesAPI).sort()).toEqual([...SERVICES_API_METHODS].sort());
  });

  it('re-exports the same servicesAPI object as servicesApi.ts', () => {
    expect(servicesAPI).toBe(servicesAPIFromModule);
  });

  it('exposes the characterised rfqAPI method names', () => {
    expect(Object.keys(rfqAPI).sort()).toEqual([...RFQ_API_METHODS].sort());
  });

  it('re-exports the same rfqAPI object as servicesApi.ts', () => {
    expect(rfqAPI).toBe(rfqAPIFromModule);
  });

  it('exposes the characterised vendorAPI method names', () => {
    expect(Object.keys(vendorAPI).sort()).toEqual([...VENDOR_API_METHODS].sort());
  });

  it('re-exports the same vendorAPI object as servicesApi.ts', () => {
    expect(vendorAPI).toBe(vendorAPIFromModule);
  });

  it('exposes the characterised timelineAPI method names', () => {
    expect(Object.keys(timelineAPI).sort()).toEqual([...TIMELINE_API_METHODS].sort());
  });

  it('re-exports the same timelineAPI object as servicesApi.ts', () => {
    expect(timelineAPI).toBe(timelineAPIFromModule);
  });
});
