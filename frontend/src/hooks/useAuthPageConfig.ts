import { useCallback, useEffect, useState } from 'react';
import { getAuthPageConfig } from '../api/authPageConfig';
import { DEFAULT_GLOBE_NETWORK_CONFIG, type GlobeNetworkConfig } from '../components/auth/GlobeNetwork';

export interface UseAuthPageConfigResult {
  config: GlobeNetworkConfig;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

/**
 * Fetches the server-persisted, admin-tunable GlobeNetwork config for the
 * public /auth page. Never blocks rendering: falls back to the hard-coded
 * defaults while loading and on any error (the globe is purely decorative).
 */
export function useAuthPageConfig(): UseAuthPageConfigResult {
  const [config, setConfig] = useState<GlobeNetworkConfig>(DEFAULT_GLOBE_NETWORK_CONFIG);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getAuthPageConfig()
      .then((remote) => {
        if (cancelled) return;
        setConfig({ ...DEFAULT_GLOBE_NETWORK_CONFIG, ...remote });
      })
      .catch((e) => {
        if (cancelled) return;
        setConfig(DEFAULT_GLOBE_NETWORK_CONFIG);
        setError((e as Error)?.message ?? 'Failed to load auth page config');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => load(), [load]);

  return { config, loading, error, refetch: load };
}
