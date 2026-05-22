/**
 * useAiGuardrail
 *
 * Reads and writes the AI spend guardrail flag stored in rp_debug_kv
 * (key = "ai_guardrail_enabled").
 *
 * Usage:
 *   const { enabled, loading, toggle } = useAiGuardrail();
 */
import { useCallback, useEffect, useState } from 'react';
import { supabase } from '../../api/supabase';

const KV_KEY = 'ai_guardrail_enabled';

export function useAiGuardrail() {
  const [enabled, setEnabled] = useState<boolean>(true); // default: on
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      const { data, error: fetchErr } = await supabase
        .from('rp_debug_kv')
        .select('value')
        .eq('key', KV_KEY)
        .maybeSingle();
      if (cancelled) return;
      if (fetchErr) setError(fetchErr.message);
      else setEnabled(data?.value === 'true');
      setLoading(false);
    })();
    return () => { cancelled = true; };
  }, []);

  const toggle = useCallback(async (newValue: boolean) => {
    setSaving(true);
    setError(null);
    const { error: upsertErr } = await supabase
      .from('rp_debug_kv')
      .upsert({ key: KV_KEY, value: String(newValue) }, { onConflict: 'key' });
    if (upsertErr) setError(upsertErr.message);
    else setEnabled(newValue);
    setSaving(false);
  }, []);

  return { enabled, loading, saving, error, toggle };
}
