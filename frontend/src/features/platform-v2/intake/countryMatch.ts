// Pure matcher for the intake CountryCombo auto-commit (AIQ-1315).
//
// #1037 added auto-commit when the typed text exactly matches a country NAME or
// its 2-char CODE, to fix a silent-disabled-Continue bug. A bare exact-code match
// is fragile as COUNTRIES grows: if a future country NAME's first 2 chars equal a
// DIFFERENT country's CODE (e.g. adding Austria/AT next to Australia/AU), typing
// "au" would commit Australia before the user finishes "Austria".
//
// Rule: a full NAME match always commits; a CODE match commits ONLY if the query
// is not also the prefix of a *different* country's name. This preserves both
// "type the full name → commit" and "type a complete unambiguous code → commit"
// (e.g. "fr" still commits France — no other name starts with "fr").

export interface CountryOption {
  code: string;
  name: string;
}

/** The country to auto-commit for a typed query, or undefined if ambiguous / no match. */
export function matchCountry<T extends CountryOption>(
  query: string,
  countries: T[],
): T | undefined {
  const norm = query.trim().toLowerCase();
  if (!norm) return undefined;

  const byName = countries.find((c) => c.name.toLowerCase() === norm);
  if (byName) return byName; // full name → always commit

  const byCode = countries.find((c) => c.code.toLowerCase() === norm);
  if (byCode) {
    // Only commit the code match if the query isn't the start of a different
    // country's name (the user may be mid-typing that other country).
    const prefixesOtherName = countries.some(
      (c) => c.code !== byCode.code && c.name.toLowerCase().startsWith(norm),
    );
    if (!prefixesOtherName) return byCode;
  }

  return undefined;
}
