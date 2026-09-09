// Country name / demonym / ISO-2 -> lowercase ISO 3166-1 alpha-2 (for flag-icons).
// Unknown input returns null (render no flag).
import { COUNTRY_OPTIONS } from '../features/policy-config/countryList';
import { DESTINATION_COUNTRIES } from '../utils/countries';

/** Demonyms and short forms that are not ISO names. */
const DEMONYMS: Record<string, string> = {
  german: 'de',
  french: 'fr',
  indian: 'in',
  polish: 'pl',
  spanish: 'es',
  italian: 'it',
  dutch: 'nl',
  usa: 'us',
  american: 'us',
  uk: 'gb',
  british: 'gb',
  japanese: 'jp',
  norwegian: 'no',
  swiss: 'ch',
  uae: 'ae',
  emirati: 'ae',
  singaporean: 'sg',
  brazilian: 'br',
  canadian: 'ca',
  irish: 'ie',
  portuguese: 'pt',
  swedish: 'se',
};

/** flag-icons uses GB for the Union Jack; ReloPass also stores UK. */
const CODE_ALIASES: Record<string, string> = { uk: 'gb' };

function foldName(s: string): string {
  return s
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/['’]/g, '')
    .trim();
}

const NAME_TO_CODE: Record<string, string> = {};

function addName(name: string, code: string): void {
  NAME_TO_CODE[foldName(name)] = code.toLowerCase();
}

for (const c of COUNTRY_OPTIONS) addName(c.name, c.code);
for (const c of DESTINATION_COUNTRIES) addName(c.name, c.code);
for (const [name, code] of Object.entries(DEMONYMS)) addName(name, code);

export function countryFlagCode(input: string | null | undefined): string | null {
  if (!input) return null;
  const key = foldName(input);
  if (!key) return null;
  if (CODE_ALIASES[key]) return CODE_ALIASES[key];
  // Any syntactically valid ISO 3166-1 alpha-2 — flag-icons ships the full set.
  if (/^[a-z]{2}$/.test(key)) return key;
  return NAME_TO_CODE[key] ?? null;
}

/** Regional-indicator pair for native <option> labels (CSS flags cannot render there). */
export function countryFlagEmoji(input: string | null | undefined): string {
  const code = countryFlagCode(input);
  if (!code) return '';
  const up = code.toUpperCase();
  return String.fromCodePoint(
    ...[...up].map((ch) => 0x1f1e6 + ch.charCodeAt(0) - 65),
  );
}
