/**
 * AIQ-1568 (TD-BUG-1) — every hardcoded navigate('/…') target must be a real route.
 *
 * The bug: the HR command centre's primary CTA, "Add your first relocation", called
 * navigate('/employees/new'). That route does not exist. React Router fell through to
 * <Route path="*"> → NotFoundRedirect → roleHomePath('HR') = /hr/dashboard →
 * useWelcomeRedirect → /hr/welcome. So the most prominent "start here" action on the HR
 * side silently bounced the tester into the onboarding wizard, every time, with no error
 * anywhere. Nothing failed loudly — the app just quietly went somewhere else.
 *
 * A dead path is invisible to tsc (it's a string) and invisible at runtime (the catch-all
 * swallows it). This is the cheap net: a static check that every literal navigate target
 * resolves against the real route table.
 *
 * The route table is BOTH sources — ROUTE_DEFS *and* the literal <Route path="…"> entries
 * in App.tsx. Checking only ROUTE_DEFS flags /journey and /dashboard as dead when they are
 * perfectly real, which is how a guard like this earns a reputation for crying wolf and
 * gets deleted.
 *
 * Scope (widened by AIQ-1950): literal navigate('/…'), template-literal navigate(`/…`),
 * and literal <Link to>/<a href> targets. The original scope note claimed template
 * literals were "already type-checked or dynamic" — they are neither. A template literal
 * is still a hand-written string; only the `${…}` segments are dynamic, and the literal
 * parts around them rot exactly like any other. That gap hid two live bugs:
 *
 *   - `/employee/case/${id}/summary` in EmployeeJourney.tsx (x3) — a route that has never
 *     existed, on the invite-claim and case-link flows, so accepting an HR invite bounced
 *     the employee to their role home.
 *   - `/terms` on signup consent — historically on the unreachable platform-v2 AuthScreen;
 *     the live check is `pages/Auth.tsx`.
 *
 * `${…}` is normalised to a single path segment before matching, so a template target is
 * checked on its literal skeleton and its params are ignored — which is the part that can
 * actually be wrong.
 */
import { readFileSync, readdirSync, statSync } from 'fs';
import { join } from 'path';
import { describe, it, expect } from 'vitest';

const SRC = join(__dirname, '..');

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (entry === 'node_modules' || entry === 'dist') continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (/\.tsx?$/.test(entry) && !/\.test\.tsx?$/.test(entry)) out.push(full);
  }
  return out;
}

/** Every path the router can actually match: ROUTE_DEFS + literal <Route path="…">. */
function knownRoutePaths(): string[] {
  const routes = readFileSync(join(SRC, 'navigation/routes.ts'), 'utf8');
  const app = readFileSync(join(SRC, 'App.tsx'), 'utf8');
  const fromDefs = [...routes.matchAll(/path:\s*'([^']+)'/g)].map((m) => m[1]!);
  const fromApp = [...app.matchAll(/<Route\s+path="([^"]+)"/g)].map((m) => m[1]!);
  return [...fromDefs, ...fromApp];
}

/** True when `target` matches a route, allowing for :params. */
function resolves(target: string, routePaths: string[]): boolean {
  return routePaths.some((r) => {
    if (r === '*') return false; // the catch-all is what HIDES the bug — never counts
    const rx = new RegExp('^' + r.replace(/:[^/]+/g, '[^/]+').replace(/\//g, '\\/') + '$');
    return rx.test(target);
  });
}

describe('navigate() targets resolve to real routes', () => {
  const routePaths = knownRoutePaths();

  it('the route table was actually parsed (guards against a silently-passing test)', () => {
    expect(routePaths.length).toBeGreaterThan(50);
    expect(routePaths).toContain('/hr/dashboard');
    expect(routePaths).toContain('/journey'); // literal in App.tsx, absent from ROUTE_DEFS
  });

  it('no navigate() sends the user to a path the router cannot match', () => {
    const dead: string[] = [];
    for (const file of walk(SRC)) {
      const src = readFileSync(file, 'utf8');
      for (const m of src.matchAll(/navigate\(\s*'(\/[a-zA-Z0-9/_-]*)'\s*\)/g)) {
        const target = m[1]!;
        if (!resolves(target, routePaths)) {
          dead.push(`${file.replace(SRC, 'src')} → navigate('${target}')`);
        }
      }
    }
    expect(dead,
      'These navigate() calls target paths with no matching <Route>. React Router will ' +
      'fall through to the catch-all and silently send the user somewhere else — the ' +
      'TD-BUG-1 failure. Use buildRoute(<key>) so a rename is a type error, or add the route.',
    ).toEqual([]);
  });

  /**
   * A template literal is a hand-written path with holes in it. Normalising `${…}` to one
   * segment leaves the skeleton, which is the part that rots when a route is renamed.
   */
  it('no navigate(`/…`) template literal targets a path the router cannot match', () => {
    const dead: string[] = [];
    for (const file of walk(SRC)) {
      const src = readFileSync(file, 'utf8');
      for (const m of src.matchAll(/navigate\(\s*`(\/[^`]*)`/g)) {
        const raw = m[1]!;
        const target = raw.replace(/\$\{[^}]*\}/g, 'X').split('?')[0]!.replace(/\/$/, '') || '/';
        if (!resolves(target, routePaths)) {
          dead.push(`${file.replace(SRC, 'src')} → navigate(\`${raw}\`)`);
        }
      }
    }
    expect(dead,
      'These template-literal navigate() calls target paths with no matching <Route>. ' +
      'The catch-all swallows them, so the user is silently sent to their role home ' +
      'instead of where the button said. Fix the target, do not widen the catch-all.',
    ).toEqual([]);
  });

  /**
   * `<Link to>` and `<a href>` fail the same way navigate() does, and were never covered.
   *
   * KNOWN_BROKEN is now EMPTY, as its own instruction required: "delete this entry when
   * the page exists or the copy changes". [AIQ-2059] changed the copy — the signup form no
   * longer claims the user agreed to a Terms of Service that was never written — so the
   * one entry is retired rather than carried. Do not add to it; a dead link is a bug to
   * fix, not an exception to register.
   */
  const KNOWN_BROKEN = new Set<string>();

  it('no <Link to>/<a href> points at a path the router cannot match', () => {
    const dead: string[] = [];
    for (const file of walk(SRC)) {
      const src = readFileSync(file, 'utf8');
      for (const m of src.matchAll(/(?:to|href)=\{?["'`](\/[^"'`]*)["'`]/g)) {
        const raw = m[1]!;
        const target = raw.replace(/\$\{[^}]*\}/g, 'X').split('?')[0]!.replace(/\/$/, '') || '/';
        if (KNOWN_BROKEN.has(target)) continue;
        if (!resolves(target, routePaths)) {
          dead.push(`${file.replace(SRC, 'src')} → ${raw}`);
        }
      }
    }
    expect(dead,
      'These link targets have no matching <Route>. A dead <Link> is invisible to tsc ' +
      'and silent at runtime — the user just lands somewhere else.',
    ).toEqual([]);
  });

  it('the signup form does not claim agreement to terms that do not exist', () => {
    // [AIQ-2059] The inverse of the assertion this replaces. That one pinned the broken
    // link in place so KNOWN_BROKEN could not become a lie; this one stops the claim
    // coming back while /terms still resolves to nothing.
    const authPage = readFileSync(join(SRC, 'pages/Auth.tsx'), 'utf8');
    expect(authPage).not.toContain('href="/terms"');
    expect(authPage).not.toContain('Terms of Service');
    expect(resolves('/privacy', routePaths)).toBe(true);
  });
});
