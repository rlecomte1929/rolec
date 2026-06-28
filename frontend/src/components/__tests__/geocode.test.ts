import { describe, it, expect, vi, afterEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { geocodeAddress, useGeocodedAddress } from '../geocode';

// Each test uses a unique address so the module-level GEO_CACHE can't leak hits.
const uniq = (s: string) => `${s} ${Math.random().toString(36).slice(2)}`;
const fetchReturning = (json: unknown) =>
  vi.fn().mockResolvedValue({ json: () => Promise.resolve(json) });

afterEach(() => vi.restoreAllMocks());

describe('geocodeAddress', () => {
  it('resolves {lat,lng} from the first Nominatim result', async () => {
    vi.stubGlobal('fetch', fetchReturning([{ lat: '52.37', lon: '4.89' }]));
    expect(await geocodeAddress(uniq('Dam, Amsterdam'))).toEqual({ lat: 52.37, lng: 4.89 });
  });

  it('returns null when Nominatim returns nothing', async () => {
    vi.stubGlobal('fetch', fetchReturning([]));
    expect(await geocodeAddress(uniq('nowhere-xyz'))).toBeNull();
  });

  it('returns null on a network/parse error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net')));
    expect(await geocodeAddress(uniq('boom'))).toBeNull();
  });

  it('returns null for empty input without calling fetch', async () => {
    const f = vi.fn();
    vi.stubGlobal('fetch', f);
    expect(await geocodeAddress('   ')).toBeNull();
    expect(f).not.toHaveBeenCalled();
  });
});

describe('useGeocodedAddress', () => {
  it('is idle for empty input', () => {
    const { result } = renderHook(() => useGeocodedAddress('', 5));
    expect(result.current.status).toBe('idle');
  });

  it('reaches ok with coords on a resolvable address', async () => {
    vi.stubGlobal('fetch', fetchReturning([{ lat: '52.37', lon: '4.89' }]));
    // NB: compute the address ONCE — calling uniq() inside the render callback
    // would change the hook input every render and loop forever.
    const addr = uniq('Amsterdam');
    const { result } = renderHook(() => useGeocodedAddress(addr, 5));
    await waitFor(() => expect(result.current.status).toBe('ok'));
    expect(result.current.coords).toEqual({ lat: 52.37, lng: 4.89 });
  });

  it('reaches notfound (never a false ok) on an unresolvable address', async () => {
    vi.stubGlobal('fetch', fetchReturning([]));
    const addr = uniq('zzzz');
    const { result } = renderHook(() => useGeocodedAddress(addr, 5));
    await waitFor(() => expect(result.current.status).toBe('notfound'));
    expect(result.current.coords).toBeNull();
  });
});
