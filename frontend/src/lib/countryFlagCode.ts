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

const ISO2 = new Set(Object.values(MAP));

export function countryFlagCode(input: string | null | undefined): string | null {
  if (!input) return null;
  const key = input.trim().toLowerCase();
  if (!key) return null;
  if (key.length === 2 && ISO2.has(key)) return key;
  return MAP[key] ?? null;
}
