/**
 * Lightweight Nominatim (OpenStreetMap) geocoding, shared by the intake
 * "Verified" badge (AIQ-1345) and RichCommuteMap. Deliberately free of Leaflet
 * so importing the geocoder does not pull the map bundle into pages that only
 * need to resolve an address. The cache is module-level, so a resolve here is a
 * cache hit when RichCommuteMap later geocodes the same address.
 */
import { useEffect, useRef, useState } from 'react';

export interface LatLng {
  lat: number;
  lng: number;
}

const GEO_CACHE = new Map<string, LatLng>();

/**
 * Geocode a free-text address via Nominatim. Returns null when it can't resolve
 * (or on a network/parse error). Cached per trimmed address string.
 */
export async function geocodeAddress(address: string): Promise<LatLng | null> {
  const key = (address || '').trim();
  if (!key) return null;
  if (GEO_CACHE.has(key)) return GEO_CACHE.get(key)!;
  try {
    const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(key)}&format=json&limit=1`;
    const res = await fetch(url, {
      headers: { 'Accept-Language': 'en', 'User-Agent': 'ReloPass/1.0 (intake-map)' },
    });
    const data = (await res.json()) as Array<{ lat: string; lon: string }>;
    const first = data[0];
    if (!first) return null;
    const point: LatLng = { lat: parseFloat(first.lat), lng: parseFloat(first.lon) };
    GEO_CACHE.set(key, point);
    return point;
  } catch {
    return null;
  }
}

export type GeocodeStatus = 'idle' | 'loading' | 'ok' | 'notfound';

export interface GeocodeState {
  status: GeocodeStatus;
  coords: LatLng | null;
}

/**
 * Debounced geocoding hook. Resolves `address` via Nominatim after `debounceMs`
 * of quiet — respecting Nominatim's ≤1 req/sec usage policy. Returns:
 *  - 'idle'     : empty input
 *  - 'loading'  : a resolve is pending
 *  - 'ok'       : the address resolved (coords set)
 *  - 'notfound' : Nominatim returned nothing (NEVER report a false 'ok')
 * A newer address supersedes an in-flight one (stale results are dropped).
 */
export function useGeocodedAddress(address: string, debounceMs = 700): GeocodeState {
  const [state, setState] = useState<GeocodeState>({ status: 'idle', coords: null });
  const reqId = useRef(0);

  useEffect(() => {
    const trimmed = (address || '').trim();
    if (!trimmed) {
      setState({ status: 'idle', coords: null });
      return;
    }
    const id = ++reqId.current;
    setState((s) => ({ status: 'loading', coords: s.coords }));
    const timer = setTimeout(() => {
      void (async () => {
        const pt = await geocodeAddress(trimmed);
        if (id !== reqId.current) return; // superseded by a newer address
        setState(pt ? { status: 'ok', coords: pt } : { status: 'notfound', coords: null });
      })();
    }, debounceMs);
    return () => clearTimeout(timer);
  }, [address, debounceMs]);

  return state;
}
