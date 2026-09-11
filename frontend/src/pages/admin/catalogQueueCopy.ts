/**
 * Operator-facing copy for /admin/catalog-queue.
 * Avoids internal jargon ("scraper", "allowlist") in the primary action.
 */

export const CATALOG_QUEUE_TITLE = 'Destination catalog';

export const CATALOG_QUEUE_SUBTITLE =
  'Open cities for provider lookup, find local providers, and review HR requests.';

export const CATALOG_QUEUE_INTRO_HEADING = 'What this page can do';

export const CATALOG_QUEUE_INTRO = [
  'ReloPass shows employees local providers (movers, banks, schools, and similar) only in cities you have opened. This page is where you open those cities, try to find providers, and handle HR requests for new destinations.',
  'Approved destinations (sometimes called the allowlist) are cities ReloPass is allowed to look up. Opening a city is the permission step. Finding providers is a separate lookup for one service in that city.',
  'If lookup is not configured, the city can still be opened. No providers are added until lookup is on, or you import businesses from maps search above.',
].join(' ');

export const FIND_PROVIDERS_LABEL = 'Find providers';
export const FIND_PROVIDERS_BUSY = 'Looking up…';

export function findProvidersAriaLabel(category: string, city: string): string {
  return `Find ${category} providers in ${city}`;
}

export function fillProvidersOutcome(opts: {
  city: string;
  category: string;
  scrapedCount: number;
  lookupRan?: boolean;
}): string {
  const { city, category, scrapedCount, lookupRan } = opts;
  if (scrapedCount > 0) {
    const n = scrapedCount;
    const noun = n === 1 ? 'provider' : 'providers';
    return `Added ${n} ${category} ${noun} for ${city}. Review them before employees see them.`;
  }
  if (lookupRan === false) {
    return `${city} is now an approved destination. Automatic lookup is off on this environment, so no providers were added. Configure lookup, then try Find providers again.`;
  }
  return `${city} is now an approved destination. No ${category} providers were added this time. Try again later, or search maps above and import businesses.`;
}
