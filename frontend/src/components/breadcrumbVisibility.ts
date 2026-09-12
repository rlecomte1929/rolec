/** Top-level pages have no parent crumb — the trail only repeats the H1 (AIQ-2296). */
export function shouldShowAppShellBreadcrumb(parent?: { label: string; href: string }): boolean {
  return Boolean(parent);
}
