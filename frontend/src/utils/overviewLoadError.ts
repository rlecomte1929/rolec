import { getClientTransportErrorMessage } from './apiDetail';

export type OverviewLoadKind = 'network' | 'unauthorized' | 'forbidden' | 'server';

export interface OverviewLoadFailure {
  kind: OverviewLoadKind;
  message: string;
}

/**
 * Map an employee-overview failure to copy that matches the cause.
 * The previous path used one "check your connection" string for every error.
 */
export function classifyOverviewLoadError(err: unknown): OverviewLoadFailure {
  const status = (err as { response?: { status?: number } } | null)?.response?.status;

  if (status === 401) {
    return {
      kind: 'unauthorized',
      message: 'Your session has expired. Sign in again to continue.',
    };
  }
  if (status === 403) {
    return {
      kind: 'forbidden',
      message: "Your account can't open this area. Ask your HR team to check your access.",
    };
  }
  if (typeof status === 'number' && status >= 500) {
    return {
      kind: 'server',
      message: 'Something went wrong on our side. Try again in a minute.',
    };
  }
  if (typeof status === 'number') {
    return {
      kind: 'server',
      message: 'Something went wrong on our side. Try again in a minute.',
    };
  }

  const transport = getClientTransportErrorMessage(err);
  if (transport || !status) {
    return {
      kind: 'network',
      message: "We couldn't reach ReloPass. Check your connection and try again.",
    };
  }

  return {
    kind: 'server',
    message: 'Something went wrong on our side. Try again in a minute.',
  };
}
