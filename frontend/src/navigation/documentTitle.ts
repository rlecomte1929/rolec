/** Tab titles for authenticated admin screens. Never the marketing tagline. */
export function formatAdminDocumentTitle(screen?: string): string {
  const name = screen?.trim();
  return name ? `ReloPass admin — ${name}` : 'ReloPass admin';
}

/** Tab titles for in-app HR/employee pages (AIQ-2347). */
export function formatAppDocumentTitle(page?: string): string {
  const name = page?.trim();
  return name ? `${name} - ReloPass` : 'ReloPass';
}

/** Tab titles for /auth. */
export function formatAuthDocumentTitle(
  kind: 'login' | 'register' | 'invite' = 'login',
): string {
  if (kind === 'register') return 'ReloPass — Create account';
  if (kind === 'invite') return 'ReloPass — Set password';
  return 'ReloPass — Sign in';
}
