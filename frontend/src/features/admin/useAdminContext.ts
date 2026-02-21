import { useEffect, useState } from 'react';
import { adminAPI } from '../../api/client';
import type { AdminContextResponse } from '../../types';

export const useAdminContext = () => {
  const [context, setContext] = useState<AdminContextResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    setLoading(true);
    try {
      const res = await adminAPI.getContext();
      setContext(res);
    } catch {
      setContext(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  return { context, loading, refresh };
};
