/**
 * useBrandingConfig — GAP 10
 *
 * Fetches the company's portal branding config from GET /api/company/branding-config
 * and applies primary/secondary colour CSS variables to :root so Tailwind arbitrary
 * values like `text-[var(--brand-primary)]` pick them up automatically.
 *
 * Side-effects are only applied when the branding values differ from the last run,
 * so re-renders are cheap.
 */
import { useEffect, useRef, useState } from 'react';
import { getBrandingConfig, type BrandingConfigResponse } from '../api/branding';
import { getAuthItem } from '../utils/demo';

const CACHE_TTL_MS = 5 * 60 * 1000; // 5 min

let _cache: { data: BrandingConfigResponse; ts: number } | null = null;

function applyBrandingCssVars(branding: BrandingConfigResponse['branding']): void {
  const root = document.documentElement;
  if (branding.primary_colour) {
    root.style.setProperty('--brand-primary', branding.primary_colour);
  } else {
    root.style.removeProperty('--brand-primary');
  }
  if (branding.secondary_colour) {
    root.style.setProperty('--brand-secondary', branding.secondary_colour);
  } else {
    root.style.removeProperty('--brand-secondary');
  }
  if (branding.accent_colour) {
    root.style.setProperty('--brand-accent', branding.accent_colour);
  } else {
    root.style.removeProperty('--brand-accent');
  }
}

export interface UseBrandingConfigResult {
  branding: BrandingConfigResponse | null;
  loading: boolean;
}

export function useBrandingConfig(): UseBrandingConfigResult {
  const [result, setResult] = useState<BrandingConfigResponse | null>(
    _cache && Date.now() - _cache.ts < CACHE_TTL_MS ? _cache.data : null,
  );
  const [loading, setLoading] = useState(!result);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  useEffect(() => {
    const token = getAuthItem('relopass_token');
    if (!token) {
      setLoading(false);
      return;
    }

    // Serve from cache if fresh
    if (_cache && Date.now() - _cache.ts < CACHE_TTL_MS) {
      applyBrandingCssVars(_cache.data.branding);
      setResult(_cache.data);
      setLoading(false);
      return;
    }

    setLoading(true);
    getBrandingConfig()
      .then((data) => {
        if (!mountedRef.current) return;
        _cache = { data, ts: Date.now() };
        applyBrandingCssVars(data.branding);
        setResult(data);
      })
      .catch(() => {
        // Branding is non-critical — fail silently, keep defaults.
      })
      .finally(() => {
        if (mountedRef.current) setLoading(false);
      });
  }, []);

  return { branding: result, loading };
}
