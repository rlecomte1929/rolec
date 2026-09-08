import { DESTINATION_COUNTRIES } from '../utils/countries';

/**
 * Country name / demonym / ISO-2 → lowercase ISO 3166-1 alpha-2 for flag-icons.
 *
 * A two-letter code is accepted even when it is not in the name map: the admin
 * country table keys rows by ISO, and flag-icons already has the glyph. `uk` is
 * the one exception — it is not an ISO alpha-2; the flag class is `fi-gb`.
 */
const ALIASES: Record<string, string> = {
  germany: 'de', german: 'de',
  france: 'fr', french: 'fr',
  india: 'in', indian: 'in',
  poland: 'pl', polish: 'pl',
  spain: 'es', spanish: 'es',
  italy: 'it', italian: 'it',
  netherlands: 'nl', dutch: 'nl', holland: 'nl',
  'united states': 'us', usa: 'us', american: 'us',
  'united kingdom': 'gb', uk: 'gb', british: 'gb', britain: 'gb',
  japan: 'jp', japanese: 'jp',
  norway: 'no', norwegian: 'no',
  switzerland: 'ch', swiss: 'ch',
  'united arab emirates': 'ae', uae: 'ae', emirati: 'ae',
  singapore: 'sg', singaporean: 'sg',
  brazil: 'br', brazilian: 'br',
  canada: 'ca', canadian: 'ca',
  ireland: 'ie', irish: 'ie',
  portugal: 'pt', portuguese: 'pt',
  sweden: 'se', swedish: 'se',
  ecuador: 'ec',
  denmark: 'dk', danish: 'dk',
  finland: 'fi', finnish: 'fi',
  greece: 'gr', greek: 'gr',
  austria: 'at', austrian: 'at',
  belgium: 'be', belgian: 'be',
  china: 'cn', chinese: 'cn',
  'hong kong': 'hk',
  'south korea': 'kr', korea: 'kr', korean: 'kr',
  mexico: 'mx', mexican: 'mx',
  australia: 'au', australian: 'au',
  'new zealand': 'nz',
  'south africa': 'za',
  turkey: 'tr', türkiye: 'tr', turkish: 'tr',
};

function toFlagIso(code: string): string {
  const k = code.toLowerCase();
  if (k === 'uk') return 'gb';
  return k;
}

for (const country of DESTINATION_COUNTRIES) {
  ALIASES[country.name.toLowerCase()] = toFlagIso(country.code);
}

export function countryFlagCode(input: string | null | undefined): string | null {
  if (!input) return null;
  const key = input.trim().toLowerCase();
  if (!key) return null;
  if (ALIASES[key]) return ALIASES[key];
  if (key.length === 2 && /^[a-z]{2}$/.test(key)) return toFlagIso(key);
  return null;
}
