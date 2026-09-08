import { useState, useEffect, useCallback } from 'react';
import {
  listTemplates,
  createTemplateApi,
  updateTemplateApi,
  deleteTemplateApi,
} from '../api/outreach';
import type { MessageTemplate, TemplateInsert } from '../types/outreach';

export interface UseTemplatesResult {
  templates: MessageTemplate[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  createTemplate: (data: TemplateInsert) => Promise<MessageTemplate>;
  updateTemplate: (id: string, patch: Partial<MessageTemplate>) => Promise<void>;
  deleteTemplate: (id: string) => Promise<void>;
}

export function useTemplates(): UseTemplatesResult {
  const [templates, setTemplates] = useState<MessageTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listTemplates();
      setTemplates(data ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load templates');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void fetch(); }, [fetch]);

  const createTemplate = useCallback(async (data: TemplateInsert): Promise<MessageTemplate> => {
    const t = await createTemplateApi(data);
    setTemplates((prev) => [...prev, t]);
    return t;
  }, []);

  const updateTemplate = useCallback(async (id: string, patch: Partial<MessageTemplate>): Promise<void> => {
    await updateTemplateApi(id, patch);
    setTemplates((prev) => prev.map((t) => (t.id === id ? { ...t, ...patch } : t)));
  }, []);

  const deleteTemplate = useCallback(async (id: string): Promise<void> => {
    await deleteTemplateApi(id);
    setTemplates((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return { templates, loading, error, refresh: fetch, createTemplate, updateTemplate, deleteTemplate };
}
