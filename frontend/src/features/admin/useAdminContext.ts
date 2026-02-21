import { useEffect, useState } from 'react';
import { adminAPI } from '../../api/client';
import { getAuthItem } from '../../utils/demo';
import type { AdminContextResponse } from '../../types';

export const useAdminContext = () => {
  const [context, setContext] = useState<AdminContextResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    setLoading(true);
    const token = getAuthItem('relopass_token');
    const role = getAuthItem('relopass_role');
    const isPrivileged = role === 'ADMIN' || role === 'HR';
    if (!token || !isPrivileged) {
      setContext(null);
      setLoading(false);
      return;
    }
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
