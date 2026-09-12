/**
 * Show the AppShell trail when there is a parent to go back to, or a section
 * crumb (ReloPass / HR Operations / Cases). A title-only trail that merely
 * repeats the H1 stays hidden (AIQ-2296); Cases and other HR landings pass
 * `section` so the trail is three segments (AIQ-2351).
 */
export function shouldShowAppShellBreadcrumb(
  parent?: { label: string; href: string },
  section?: string,
): boolean {
  return Boolean(parent) || Boolean(section?.trim());
}
