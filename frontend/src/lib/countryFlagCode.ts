// Country name / demonym (nationality) -> ISO 3166-1 alpha-2 (lowercase, for flag-icons).
// Extend as new corridors are supported. Unknown input returns null (render no flag).
const MAP: Record<string, string> = {
  germany: 'de', german: 'de',
  france: 'fr', french: 'fr',
  india: 'in', indian: 'in',
  poland: 'pl', polish: 'pl',
  spain: 'es', spanish: 'es',
  italy: 'it', italian: 'it',
  netherlands: 'nl', dutch: 'nl',
  'united states': 'us', usa: 'us', american: 'us',
  'united kingdom': 'gb', uk: 'gb', british: 'gb',
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
};

/** flag-icons uses GB for the Union Jack; ReloPass also stores UK. */
const CODE_ALIASES: Record<string, string> = { uk: 'gb' };

export function countryFlagCode(input: string | null | undefined): string | null {
  if (!input) return null;
  const key = input.trim().toLowerCase();
  if (!key) return null;
  if (CODE_ALIASES[key]) return CODE_ALIASES[key];
  // Any syntactically valid ISO 3166-1 alpha-2 — flag-icons ships the full set.
  // Restricting to a corridor allowlist left most of the world without a flag.
  if (/^[a-z]{2}$/.test(key)) return key;
  return MAP[key] ?? null;
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
