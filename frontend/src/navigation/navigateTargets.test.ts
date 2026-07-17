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
 * Scope: only literal, parameterless navigate('/…') calls. Template literals and
 * buildRoute() are already type-checked or dynamic; this targets exactly the hand-written
 * string that rots when a route is renamed.
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
});
