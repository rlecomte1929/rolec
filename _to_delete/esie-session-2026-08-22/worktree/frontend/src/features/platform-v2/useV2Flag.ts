import { useEffect, useState } from 'react';
import { isV2FlagOn, setV2FlagOverride, type V2FlagKey } from './flags';

/**
 * React hook that returns the current value of a platform-v2 flag and
 * re-renders when the value changes via either:
 *   - cross-tab localStorage updates (the browser `storage` event)
 *   - same-tab overrides made through `setOverride` below
 *
 * The hook deliberately does not poll. If you toggle a flag from the
 * DevTools console with raw `localStorage.setItem`, you need to also
 * dispatch a `platform-v2-flag-change` event or simply call
 * `setOverride` (recommended) to make components react.
 */
export function useV2Flag(key: V2FlagKey): {
  on: boolean;
  setOverride: (value: boolean | null) => void;
} {
  const [on, setOn] = useState<boolean>(() => isV2FlagOn(key));

  useEffect(() => {
    const sync = () => setOn(isV2FlagOn(key));

    const onStorage = (e: StorageEvent) => {
      if (!e.key || e.key === `platform_v2_${key}`) sync();
    };
    const onCustom = (e: Event) => {
      const detail = (e as CustomEvent<{ key?: string }>).detail;
      if (!detail?.key || detail.key === key) sync();
    };

    window.addEventListener('storage', onStorage);
    window.addEventListener('platform-v2-flag-change', onCustom);
    return () => {
      window.removeEventListener('storage', onStorage);
      window.removeEventListener('platform-v2-flag-change', onCustom);
    };
  }, [key]);

  const setOverride = (value: boolean | null) => {
    setV2FlagOverride(key, value);
    window.dispatchEvent(new CustomEvent('platform-v2-flag-change', { detail: { key } }));
  };

  return { on, setOverride };
}
