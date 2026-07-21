// Pure matcher for the intake CountryCombo auto-commit (AIQ-1315).
//
// #1037 added auto-commit when the typed text exactly matches a country NAME or
// its 2-char CODE, to fix a silent-disabled-Continue bug.
//
// AIQ-1643: the original CODE rule only excluded *other* countries' names from the
// prefix check, so "fr" committed France even though the user was mid-typing
// "France" — the commit truncated the word to "France" and the browser appended the
// remaining keystrokes to the committed name ("France" → "Franceance", "Nor" →
// "Norwayr"). A 2-char code is almost always also the start of some country NAME,
// so committing on it is inherently ambiguous with mid-typing.
//
// Rule: a full NAME match always commits; a CODE match commits ONLY when the query
// is not the prefix of ANY country's name (including its own). This keeps
// "type the full name → commit" and "type a genuinely unambiguous code → commit"
// (e.g. "us" commits United States — no name starts with "us") while never cutting
// a user off in the middle of typing a name.

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
    // Only commit the code match if the query isn't the start of ANY country's name
    // (incl. this code's own name). If it is, the user is probably still typing that
    // name — committing here would truncate it and the browser would append the rest
    // of the keystrokes to the committed name (AIQ-1643).
    const prefixesSomeName = countries.some((c) => c.name.toLowerCase().startsWith(norm));
    if (!prefixesSomeName) return byCode;
  }

  return undefined;
}
