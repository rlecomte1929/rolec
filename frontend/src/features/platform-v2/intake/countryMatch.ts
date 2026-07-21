// Pure matchers for the intake CountryCombo auto-commit (AIQ-1315).
//
// #1037 added auto-commit when the typed text exactly matches a country NAME or
// its 2-char CODE, to fix a silent-disabled-Continue bug. Browser QA later
// reproduced a worse bug in the other direction: committing a CODE match on
// every keystroke rewrote the input to the full country name WHILE the user was
// still typing ("No" hit code NO -> the field became "Norway"), so the next
// keystroke appended to the completed word ("Norwayr" -> "No match",
// recoverable only by backspacing). The same fired for "Fr" -> France
// ("Franceance").
//
// The matchers are therefore split by call site:
//   - matchCountryName — safe on EVERY keystroke: it only matches when the
//     typed text IS the full name, so the committed value is identical to what
//     the user typed and the input never rewrites under their caret.
//   - matchCountry — the full name-or-code matcher, for commit points where
//     typing has finished (blur / leaving the field). A full NAME match always
//     commits; a CODE match commits ONLY if the query is not also the prefix of
//     a *different* country's name (e.g. adding Austria/AT next to
//     Australia/AU: "au" must not commit Australia while the user may be typing
//     "Austria").

export interface CountryOption {
  code: string;
  name: string;
}

/** Full-NAME match only — the only auto-commit that is safe mid-keystroke. */
export function matchCountryName<T extends CountryOption>(
  query: string,
  countries: T[],
): T | undefined {
  const norm = query.trim().toLowerCase();
  if (!norm) return undefined;
  return countries.find((c) => c.name.toLowerCase() === norm);
}

/** The country to commit for a finished query (blur), or undefined if ambiguous / no match. */
export function matchCountry<T extends CountryOption>(
  query: string,
  countries: T[],
): T | undefined {
  const norm = query.trim().toLowerCase();
  if (!norm) return undefined;

  const byName = matchCountryName(norm, countries);
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
