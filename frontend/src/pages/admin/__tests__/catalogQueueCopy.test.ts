import { describe, it, expect } from 'vitest';
import {
  CATALOG_QUEUE_INTRO,
  FIND_PROVIDERS_LABEL,
  fillProvidersOutcome,
} from '../catalogQueueCopy';

describe('catalogQueueCopy', () => {
  it('explains approved destinations without scraper jargon', () => {
    expect(CATALOG_QUEUE_INTRO.toLowerCase()).toContain('approved destinations');
    expect(CATALOG_QUEUE_INTRO.toLowerCase()).toContain('allowlist');
    expect(CATALOG_QUEUE_INTRO.toLowerCase()).not.toContain('scraper');
    expect(FIND_PROVIDERS_LABEL).toBe('Find providers');
  });

  it('reports providers added when lookup found rows', () => {
    expect(
      fillProvidersOutcome({
        city: 'Paris',
        category: 'movers',
        scrapedCount: 3,
        lookupRan: true,
      }),
    ).toBe(
      'Added 3 movers providers for Paris. Review them before employees see them.',
    );
  });

  it('explains lookup-off without saying scraper or API key', () => {
    const msg = fillProvidersOutcome({
      city: 'Oslo',
      category: 'banks',
      scrapedCount: 0,
      lookupRan: false,
    });
    expect(msg).toContain('Oslo is now an approved destination');
    expect(msg.toLowerCase()).not.toContain('scraper');
    expect(msg.toLowerCase()).not.toContain('api key');
    expect(msg.toLowerCase()).toContain('lookup is off');
  });

  it('explains empty result when lookup ran', () => {
    const msg = fillProvidersOutcome({
      city: 'Lyon',
      category: 'banks',
      scrapedCount: 0,
      lookupRan: true,
    });
    expect(msg).toContain('No banks providers were added');
    expect(msg.toLowerCase()).not.toContain('scraper');
  });
});
