import { useState, useEffect, useCallback } from 'react';
import { supabase } from '../api/supabase';
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
    const { data, error: err } = await supabase
      .from('message_templates')
      .select('*')
      .order('created_at', { ascending: true });
    if (err) {
      setError(err.message);
    } else {
      setTemplates((data as MessageTemplate[]) ?? []);
    }
    setLoading(false);
  }, []);

  useEffect(() => { void fetch(); }, [fetch]);

  const createTemplate = useCallback(async (data: TemplateInsert): Promise<MessageTemplate> => {
    const resp = await supabase
      .from('message_templates')
      .insert(data)
      .select()
      .single();
    if (resp.error) throw new Error(resp.error.message);
    const t = resp.data as MessageTemplate;
    setTemplates((prev) => [...prev, t]);
    return t;
  }, []);

  const updateTemplate = useCallback(async (id: string, patch: Partial<MessageTemplate>): Promise<void> => {
    const { error: err } = await supabase
      .from('message_templates')
      .update(patch)
      .eq('id', id);
    if (err) throw new Error(err.message);
    setTemplates((prev) => prev.map((t) => (t.id === id ? { ...t, ...patch } : t)));
  }, []);

  const deleteTemplate = useCallback(async (id: string): Promise<void> => {
    const { error: err } = await supabase
      .from('message_templates')
      .delete()
      .eq('id', id);
    if (err) throw new Error(err.message);
    setTemplates((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return { templates, loading, error, refresh: fetch, createTemplate, updateTemplate, deleteTemplate };
}
