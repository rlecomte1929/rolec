export type OverviewLoadKind = 'network' | 'unauthorized' | 'forbidden' | 'server' | 'unknown';

export function classifyOverviewLoadError(err: unknown): { kind: OverviewLoadKind; message: string } {
  const status = (err as { response?: { status?: number } } | null)?.response?.status;
  if (!status) {
    return {
      kind: 'network',
      message: 'We could not reach ReloPass. Check your connection and try again.',
    };
  }
  if (status === 401) {
    return {
      kind: 'unauthorized',
      message: 'Your session is no longer valid. Sign in again to continue.',
    };
  }
  if (status === 403) {
    return {
      kind: 'forbidden',
      message: 'This account cannot open employee assignments. Switch to a role that can, or ask HR to check your access.',
    };
  }
  if (status >= 500) {
    return {
      kind: 'server',
      message: 'Something went wrong on our side. Try again in a minute.',
    };
  }
  return { kind: 'unknown', message: 'Overview did not load. Try again.' };
}

/** Alert heading — must not say "could not load" when the failure is session or access. */
export function overviewLoadAlertTitle(kind: OverviewLoadKind | null | undefined): string {
  switch (kind) {
    case 'unauthorized':
      return 'Sign in again';
    case 'forbidden':
      return 'This account cannot open assignments';
    case 'network':
      return 'Could not reach ReloPass';
    case 'server':
      return 'Something went wrong';
    default:
      return 'Could not load assignments';
  }
}
