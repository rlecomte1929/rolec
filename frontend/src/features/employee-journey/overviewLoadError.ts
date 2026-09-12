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
