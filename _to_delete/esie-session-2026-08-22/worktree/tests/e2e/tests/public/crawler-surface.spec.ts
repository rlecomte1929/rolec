import { test, expect, request as pwRequest } from '@playwright/test';

/**
 * The unauthenticated, crawler-facing surface.
 *
 * WHY THIS PROJECT EXISTS
 * -----------------------
 * On 2026-08-10 seven defects of one shape landed in a single evening: ad landing pages
 * serving a 1,677-byte empty shell to every crawler, five guides published at no URL, a
 * sitemap that returned HTML, a robots.txt TODO for a sitemap that never shipped.
 *
 * The Sentinel was enabled and green through all of it. It could not have caught any of
 * them: every other project in playwright.config.ts is `provision` / `readiness` /
 * `setup` or carries a `storageState`, so 100% of the coverage sat behind a login — and
 * every one of those defects lived in front of it.
 *
 * THE RULE HERE: ASSERT CONTENT, NEVER STATUS
 * -------------------------------------------
 * `/mobility-teams` returned HTTP 200 for the entire time it was serving a blank page.
 * A Render SPA catch-all answers *every* unmatched path with index.html, so 200 means
 * "the server is up", not "the page exists". Every assertion below therefore checks for
 * page-specific text and a byte floor. A test that would pass against the SPA shell is
 * worse than no test, because it certifies the exact failure it was written to catch.
 *
 * No auth, no fixtures, no DATABASE_URL — which also makes this the fastest and least
 * flaky project in the campaign, and the one safe to run anywhere.
 */

const ORIGIN = process.env.E2E_APP_URL || 'https://relopass.com';

/** The shell is ~1.7 kB. A real page is several kB of markup. */
const SHELL_CEILING = 4000;

/** Requests must not carry the app's session or SPA assumptions — we are a crawler. */
async function fetchRaw(path: string, userAgent?: string) {
  const ctx = await pwRequest.newContext({
    baseURL: ORIGIN,
    extraHTTPHeaders: userAgent ? { 'User-Agent': userAgent } : {},
  });
  try {
    const res = await ctx.get(path);
    return { status: res.status(), body: await res.text() };
  } finally {
    await ctx.dispose();
  }
}

function assertNotTheShell(path: string, body: string) {
  expect(
    body.length,
    `${path} returned ${body.length} bytes — at or below the ${SHELL_CEILING}-byte floor, ` +
      'which means the SPA shell. A crawler sees an empty document here.',
  ).toBeGreaterThan(SHELL_CEILING);
  expect(body, `${path} has an empty #root — prerendering did not run for this route`).not.toMatch(
    /<div id="root">\s*<div[^>]*>\s*Loading ReloPass/,
  );
}

// Every test below carries a leading [TAG] and a matching entry in scripts/scoring_map.json.
// That is not decoration: the ingester drops any spec without a tag, and the scorer only
// iterates ids present in the map, so an untagged or unmapped spec runs and reports to
// nobody. This file shipped untagged and spent a day failing on the Cloudflare 403s while
// the campaign went green — see AIQ-1804. Add both when you add a test here.
test.describe('public crawler surface', () => {
  // The two paid-ad destinations. Both URL forms: the trailing-slash one is what the ad
  // platform is given, the bare one is what a human types or links to. Before #1761 the
  // bare form was the shell, and every URL in ADS-4 used it.
  for (const [path, needle] of [
    ['/mobility-teams', 'Mobility teams'],
    ['/relocation-checklist', 'Relocation checklist'],
  ] as const) {
    for (const variant of [path, `${path}/`]) {
      test(`[SEO-LANDING] ad landing page ${variant} serves prerendered HTML`, async () => {
        const { body } = await fetchRaw(variant);
        assertNotTheShell(variant, body);
        expect(body, `${variant} is missing its own <title> — got the generic SPA one`).toContain(
          `<title>${needle}`,
        );
      });
    }
  }

  // Crawlers whose access a USER-AGENT can actually test. Real production UA strings.
  //
  // OAI-SearchBot, ChatGPT-User and GPTBot are deliberately NOT here — see the block below.
  const UA_TESTABLE_CRAWLERS: Array<[string, string]> = [
    ['OAI-AdsBot', 'Mozilla/5.0 (compatible; OAI-AdsBot/1.0; +https://openai.com/adsbot)'],
    ['Googlebot', 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'],
    ['facebookexternalhit', 'facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)'],
  ];

  for (const [name, ua] of UA_TESTABLE_CRAWLERS) {
    test(`[AEO-CRAWLER-FETCH] ${name} can actually fetch a published page`, async () => {
      const path = '/blog/relocate-employee-france-norway-2026/';
      const { status, body } = await fetchRaw(path, ua);
      expect(status, `${name} got HTTP ${status} for ${path}`).toBe(200);
      // The real assertion. A crawler-shaped request must get the prerendered document,
      // not the SPA shell — that is the defect class this whole file exists for.
      assertNotTheShell(`${path} as ${name}`, body);
    });
  }

  /* WHY OAI-SearchBot, ChatGPT-User AND GPTBot ARE NOT TESTED HERE
   * -------------------------------------------------------------
   * They were, and the tests could never have passed. Removed 2026-08-11.
   *
   * Cloudflare identifies a named bot by CRYPTOGRAPHIC SIGNATURE (Web Bot Auth), PUBLISHED
   * IP RANGE, or REVERSE DNS — never by the user-agent string. An "allow" rule is therefore
   * only honoured for traffic that proves its identity. A Playwright request from a GitHub
   * Actions runner carrying `User-Agent: ...OAI-SearchBot...` proves nothing and is refused,
   * and measurement confirms it: with OAI-SearchBot and ChatGPT-User both set to ALLOW in
   * AI Crawl Control, a spoofed request still gets 403 / 25 bytes, while the three UAs above
   * get 200 / 13,870 bytes on the same path in the same second.
   *
   * A PASSING VERSION OF THAT TEST WOULD BE A SECURITY DEFECT. If CI could fetch this
   * content by claiming to be OAI-SearchBot, so could anyone. We were asserting that
   * bot impersonation works.
   *
   * The old failure message asked the reader to "fix it in the Cloudflare dashboard". That
   * advice was wrong and cost real time: the dashboard was already correct, and the
   * telemetry proved it — OAI-SearchBot showed Allowed: 3 and 21.48 kB transferred while
   * these tests were red. Worse, the ~110 "Unsuccessful" requests attributed to OpenAI
   * crawlers in that dashboard were mostly THIS TEST and the curls run to debug it. We were
   * generating the evidence we then read as a fault.
   *
   * It also broke this file's own rule, stated at the top: ASSERT CONTENT, NEVER STATUS.
   *
   * GPTBot additionally is blocked ON PURPOSE. It feeds model training only (OpenAI:
   * "content that may be used in training our generative AI foundation models") and returns
   * no citation benefit, unlike OAI-SearchBot (Search) and ChatGPT-User (Agent). Ruled
   * 2026-08-11: be citable, don't be training data. Do not "fix" that by allowing it.
   *
   * THE REAL SIGNAL is Cloudflare's own per-crawler telemetry: AI Crawl Control -> Metrics,
   * Allowed vs Unsuccessful. To confirm the Agent path positively, ask ChatGPT to open a
   * published URL and watch ChatGPT-User's Allowed count increment — that is a verified
   * request from OpenAI's infrastructure, which is the only kind that can prove it.
   */

  test('[SEO-ROBOTS] robots.txt still allows the OpenAI crawlers and points at the sitemap', async () => {
    const { body } = await fetchRaw('/robots.txt');
    expect(body, 'robots.txt is returning the SPA shell, not a robots file').not.toContain('<html');
    expect(body).toContain('OAI-AdsBot');
    expect(body).toContain('OAI-SearchBot');
    expect(body, 'the Sitemap: line is gone — crawlers lose the index of every guide').toMatch(
      /^Sitemap:\s*https?:\/\/\S+sitemap\.xml/m,
    );
  });

  test('[SEO-BLOG-INDEX] the blog index lists posts and each one resolves to its own page', async () => {
    const { body: index } = await fetchRaw('/blog/');
    assertNotTheShell('/blog/', index);

    const slugs = [...index.matchAll(/href="\/blog\/([a-z0-9-]+)\/"/g)].map((m) => m[1]);
    expect(slugs.length, '/blog/ links no posts — the index rendered but is empty').toBeGreaterThan(0);

    for (const slug of slugs) {
      const { body } = await fetchRaw(`/blog/${slug}/`);
      assertNotTheShell(`/blog/${slug}/`, body);
      expect(body, `/blog/${slug}/ inherited the generic title instead of its own`).not.toContain(
        '<title>ReloPass — The operating layer for cross-border relocation</title>',
      );
    }
  });

  test('[SEO-SITEMAP] sitemap.xml parses as XML and every URL in it resolves to real content', async () => {
    const { body } = await fetchRaw('/sitemap.xml');
    expect(
      body.trimStart().startsWith('<?xml'),
      'sitemap.xml is not XML — it is being answered by the SPA catch-all',
    ).toBe(true);

    expect(body, 'sitemap.xml is missing the <urlset> root').toContain('<urlset');

    // Regex rather than a parser: one assertion does not justify a dependency in a
    // project whose only dep today is @playwright/test, and the XML declaration plus a
    // <urlset> root already rule out the shell — which is the failure being guarded.
    const urls = [...body.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1].trim());
    expect(urls.length, 'sitemap.xml has no <loc> entries').toBeGreaterThan(0);

    // Self-maintaining: publish a post, the sitemap grows, this covers it with no edit here.
    for (const loc of urls) {
      const path = new URL(loc).pathname;
      const { status, body: page } = await fetchRaw(path);
      expect(status, `sitemap advertises ${loc} but it returns ${status}`).toBe(200);
      // Every sitemap URL, `/` included. This line used to read
      //   if (path !== '/') assertNotTheShell(loc, page);
      // with the comment "the bare origin legitimately IS the SPA". That exemption was made
      // obsolete by AIQ-1797 (which prerendered the homepage) but left in place, so when the
      // rewrite serving `/` turned out to be unreachable and prod went back to shipping the
      // shell at priority 1.0, the one test iterating the sitemap was the one told to skip it.
      assertNotTheShell(loc, page);
    }
  });
});
