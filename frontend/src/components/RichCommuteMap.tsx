/**
 * RichCommuteMap — Real Leaflet map with enriched overlays.
 *
 * Features:
 *  - Geocodes office address via Nominatim (OSM, free)
 *  - Draws commute-radius circle scaled to mode + minutes
 *  - Fetches schools from Overpass API when hasChildren = true
 *  - Fetches transit stops from Overpass API when transit in commuteMode
 *  - No API key required — uses 100% open data
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import {
  MapContainer,
  TileLayer,
  Marker,
  Circle,
  Popup,
  CircleMarker,
} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// ── Fix Leaflet default icon for Vite (no webpack loader) ─────────────────────
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

// ── Custom purple office icon ──────────────────────────────────────────────────
const officeIcon = L.divIcon({
  className: '',
  html: `<div style="
    width:32px;height:40px;
    background:url('https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png') no-repeat center/contain;
    filter: hue-rotate(260deg) saturate(2);
  "></div>`,
  iconSize: [32, 40],
  iconAnchor: [16, 40],
  popupAnchor: [0, -40],
});

// ── Speed estimates (metres per minute) for radius calculation ────────────────
const SPEED: Record<string, number> = {
  walking: 75,
  bike: 220,
  public_transit: 380,
  car: 550,
  no_pref: 300,
};

function computeRadiusM(commuteMins: number, modes: string[]): number {
  const effective = modes.filter((m) => m !== 'no_pref');
  const speed = effective.length
    ? Math.max(...effective.map((m) => SPEED[m] ?? 300))
    : 300;
  return Math.round(speed * commuteMins);
}

// ── Geocode with Nominatim ─────────────────────────────────────────────────────
interface LatLng { lat: number; lng: number }

const GEO_CACHE = new Map<string, LatLng>();

async function geocodeAddress(address: string): Promise<LatLng | null> {
  if (GEO_CACHE.has(address)) return GEO_CACHE.get(address)!;
  try {
    const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(address)}&format=json&limit=1`;
    const res = await fetch(url, {
      headers: { 'Accept-Language': 'en', 'User-Agent': 'ReloPass/1.0 (intake-map)' },
    });
    const data = await res.json();
    if (!data?.length) return null;
    const point: LatLng = { lat: parseFloat(data[0].lat), lng: parseFloat(data[0].lon) };
    GEO_CACHE.set(address, point);
    return point;
  } catch {
    return null;
  }
}

// ── Overpass API helper ────────────────────────────────────────────────────────
interface OverpassNode {
  id: number;
  lat: number;
  lon: number;
  tags: Record<string, string>;
}

const OVERPASS_CACHE = new Map<string, OverpassNode[]>();

async function overpassQuery(query: string): Promise<OverpassNode[]> {
  const key = query.slice(0, 200);
  if (OVERPASS_CACHE.has(key)) return OVERPASS_CACHE.get(key)!;
  try {
    const res = await fetch('https://overpass-api.de/api/interpreter', {
      method: 'POST',
      body: query,
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    const json = await res.json();
    const nodes: OverpassNode[] = (json.elements ?? []).filter(
      (e: any) => e.type === 'node' && e.lat && e.lon,
    );
    OVERPASS_CACHE.set(key, nodes);
    return nodes;
  } catch {
    return [];
  }
}

async function fetchSchools(lat: number, lng: number, radiusM: number): Promise<OverpassNode[]> {
  const r = Math.min(radiusM, 8000); // cap at 8 km
  const q = `[out:json][timeout:20];
(node["amenity"~"^(school|kindergarten|university|college)$"](around:${r},${lat},${lng}););
out body;`;
  const nodes = await overpassQuery(q);
  return nodes.slice(0, 15);
}

async function fetchSports(lat: number, lng: number, radiusM: number): Promise<OverpassNode[]> {
  const r = Math.min(radiusM, 6000); // cap at 6 km
  const q = `[out:json][timeout:20];
(node["leisure"~"^(sports_centre|fitness_centre|stadium|swimming_pool|ice_rink)$"](around:${r},${lat},${lng});
node["amenity"~"^(swimming_pool|gym)$"](around:${r},${lat},${lng}););
out body;`;
  const nodes = await overpassQuery(q);
  return nodes.slice(0, 20);
}

async function fetchTransit(lat: number, lng: number): Promise<OverpassNode[]> {
  const q = `[out:json][timeout:20];
(node["highway"="bus_stop"](around:3000,${lat},${lng});
node["railway"~"^(station|stop|tram_stop|subway_entrance)$"](around:3000,${lat},${lng});
node["public_transport"="stop_position"](around:3000,${lat},${lng}););
out body;`;
  const nodes = await overpassQuery(q);
  return nodes.slice(0, 25);
}

// ── Props ──────────────────────────────────────────────────────────────────────
interface RichCommuteMapProps {
  officeAddress: string;
  commuteMins: number;
  commuteMode: string[];
  hasChildren: boolean;
  showSports?: boolean;
  housingAreaCoords?: LatLng | null;
  housingAreaLabel?: string;
}

// ── Custom housing icon ────────────────────────────────────────────────────────
const housingIcon = L.divIcon({
  className: '',
  html: `<div style="
    width:32px;height:40px;
    background:url('https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png') no-repeat center/contain;
    filter: hue-rotate(120deg) saturate(2);
  "></div>`,
  iconSize: [32, 40],
  iconAnchor: [16, 40],
  popupAnchor: [0, -40],
});

// ── Component ──────────────────────────────────────────────────────────────────
export function RichCommuteMap({ officeAddress, commuteMins, commuteMode, hasChildren, showSports, housingAreaCoords, housingAreaLabel }: RichCommuteMapProps) {
  const [center, setCenter] = useState<LatLng | null>(null);
  const [schools, setSchools] = useState<OverpassNode[]>([]);
  const [transit, setTransit] = useState<OverpassNode[]>([]);
  const [sports, setSports] = useState<OverpassNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const prevAddress = useRef('');
  const prevChildren = useRef(false);

  const hasTransit = commuteMode.some((m) => m === 'public_transit');
  const radiusM = computeRadiusM(commuteMins, commuteMode);

  const load = useCallback(async (address: string) => {
    setLoading(true);
    setError(false);
    try {
      const pt = await geocodeAddress(address);
      if (!pt) { setError(true); setLoading(false); return; }
      setCenter(pt);

      const [schoolData, transitData, sportsData] = await Promise.all([
        hasChildren ? fetchSchools(pt.lat, pt.lng, radiusM) : Promise.resolve([]),
        hasTransit ? fetchTransit(pt.lat, pt.lng) : Promise.resolve([]),
        showSports ? fetchSports(pt.lat, pt.lng, radiusM) : Promise.resolve([]),
      ]);
      setSchools(schoolData);
      setTransit(transitData);
      setSports(sportsData);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Reload when address changes
  useEffect(() => {
    if (!officeAddress || officeAddress === prevAddress.current) return;
    prevAddress.current = officeAddress;
    void load(officeAddress);
  }, [officeAddress, load]);

  // Reload overlays when family profile changes (children added)
  useEffect(() => {
    if (!center || hasChildren === prevChildren.current) return;
    prevChildren.current = hasChildren;
    const fetch = async () => {
      if (hasChildren) {
        const data = await fetchSchools(center.lat, center.lng, radiusM);
        setSchools(data);
      } else {
        setSchools([]);
      }
    };
    void fetch();
  }, [hasChildren, center, radiusM]);

  // Reload transit overlay when mode changes
  useEffect(() => {
    if (!center) return;
    const fetch = async () => {
      if (hasTransit) {
        const data = await fetchTransit(center.lat, center.lng);
        setTransit(data);
      } else {
        setTransit([]);
      }
    };
    void fetch();
  }, [hasTransit, center]); // eslint-disable-line react-hooks/exhaustive-deps

  const schoolCount = schools.length;
  const transitCount = transit.length;
  const sportsCount = sports.length;

  // ── Fallback shell while loading ────────────────────────────────────────────
  if (loading) {
    return (
      <div className="relative rounded-xl overflow-hidden border border-gray-100 bg-gray-950 flex items-center justify-center" style={{ height: 300 }}>
        <div className="text-center text-gray-400">
          <div className="text-2xl mb-2 animate-pulse">🗺️</div>
          <div className="text-xs">Loading map…</div>
          {officeAddress && <div className="text-[10px] text-gray-500 mt-1">{officeAddress}</div>}
        </div>
      </div>
    );
  }

  if (error || !center) {
    return (
      <div className="relative rounded-xl overflow-hidden border border-amber-100 bg-amber-50 flex items-center justify-center" style={{ height: 300 }}>
        <div className="text-center text-amber-700">
          <div className="text-2xl mb-2">⚠️</div>
          <div className="text-xs font-semibold">Could not geocode office address</div>
          <div className="text-[10px] text-amber-600 mt-1">Check the address in step 3 and try again</div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative rounded-xl overflow-hidden border border-gray-200 shadow-sm" style={{ height: 320 }}>
      {/* Live badge */}
      <div className="absolute top-2 right-2 z-[1000] flex items-center gap-1 px-2 py-0.5 rounded-full bg-accent-600 text-white text-[10px] font-medium shadow">
        <span className="w-1.5 h-1.5 rounded-full bg-green-300 animate-pulse inline-block" />
        live
      </div>

      {/* Legend */}
      <div className="absolute bottom-2 left-2 z-[1000] flex flex-col gap-1 bg-white/90 backdrop-blur-sm rounded-lg px-2.5 py-2 text-[10px] shadow">
        <div className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-accent-500 opacity-30 border border-accent-500 inline-block" />
          <span className="text-gray-600">{commuteMins}min radius ({(radiusM / 1000).toFixed(1)} km)</span>
        </div>
        {hasChildren && schoolCount > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-green-500 inline-block" />
            <span className="text-gray-600">{schoolCount} school{schoolCount !== 1 ? 's' : ''} nearby</span>
          </div>
        )}
        {hasTransit && transitCount > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-blue-500 inline-block" />
            <span className="text-gray-600">{transitCount} transit stop{transitCount !== 1 ? 's' : ''}</span>
          </div>
        )}
        {showSports && sportsCount > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-orange-500 inline-block" />
            <span className="text-gray-600">{sportsCount} sports venue{sportsCount !== 1 ? 's' : ''}</span>
          </div>
        )}
        {housingAreaCoords && (
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-teal-500 inline-block" />
            <span className="text-gray-600">{housingAreaLabel || 'Preferred area'}</span>
          </div>
        )}
        {hasChildren && schoolCount === 0 && !loading && (
          <div className="text-amber-600">No schools found within radius</div>
        )}
      </div>

      <MapContainer
        center={[center.lat, center.lng]}
        zoom={13}
        style={{ width: '100%', height: '100%' }}
        scrollWheelZoom={false}
        attributionControl={false}
      >
        {/* OSM tile layer */}
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        />

        {/* Commute radius */}
        <Circle
          center={[center.lat, center.lng]}
          radius={radiusM}
          pathOptions={{ color: '#1f8e8b', fillColor: '#1f8e8b', fillOpacity: 0.08, weight: 1.5 }}
        />

        {/* Office marker */}
        <Marker position={[center.lat, center.lng]} icon={officeIcon}>
          <Popup>
            <div className="text-xs">
              <div className="font-semibold text-accent-700 mb-0.5">📍 Your office</div>
              <div className="text-gray-600">{officeAddress}</div>
            </div>
          </Popup>
        </Marker>

        {/* School markers */}
        {hasChildren && schools.map((s) => (
          <CircleMarker
            key={s.id}
            center={[s.lat, s.lon]}
            radius={7}
            pathOptions={{ color: '#16a34a', fillColor: '#22c55e', fillOpacity: 0.85, weight: 1.5 }}
          >
            <Popup>
              <div className="text-xs">
                <div className="font-semibold text-green-700 mb-0.5">🏫 {s.tags.name || 'School'}</div>
                {s.tags.amenity && <div className="text-gray-500 capitalize">{s.tags.amenity.replace('_', ' ')}</div>}
                {s.tags['addr:street'] && (
                  <div className="text-gray-400 mt-0.5">{s.tags['addr:street']}</div>
                )}
              </div>
            </Popup>
          </CircleMarker>
        ))}

        {/* Transit stop markers */}
        {hasTransit && transit.map((t) => (
          <CircleMarker
            key={t.id}
            center={[t.lat, t.lon]}
            radius={5}
            pathOptions={{ color: '#1d4ed8', fillColor: '#3b82f6', fillOpacity: 0.75, weight: 1.5 }}
          >
            <Popup>
              <div className="text-xs">
                <div className="font-semibold text-blue-700 mb-0.5">
                  {t.tags.railway?.includes('station') ? '🚉' : '🚌'} {t.tags.name || 'Transit stop'}
                </div>
                {t.tags.ref && <div className="text-gray-500">Line {t.tags.ref}</div>}
                {t.tags.network && <div className="text-gray-400">{t.tags.network}</div>}
              </div>
            </Popup>
          </CircleMarker>
        ))}

        {/* Sports venue markers */}
        {showSports && sports.map((s) => (
          <CircleMarker
            key={s.id}
            center={[s.lat, s.lon]}
            radius={7}
            pathOptions={{ color: '#c2410c', fillColor: '#f97316', fillOpacity: 0.85, weight: 1.5 }}
          >
            <Popup>
              <div className="text-xs">
                <div className="font-semibold text-orange-700 mb-0.5">
                  {s.tags.leisure === 'swimming_pool' ? '🏊' : s.tags.leisure === 'stadium' ? '🏟️' : '🏋️'}{' '}
                  {s.tags.name || 'Sports venue'}
                </div>
                {s.tags.leisure && (
                  <div className="text-gray-500 capitalize">{s.tags.leisure.replace(/_/g, ' ')}</div>
                )}
                {s.tags['addr:street'] && (
                  <div className="text-gray-400 mt-0.5">{s.tags['addr:street']}</div>
                )}
              </div>
            </Popup>
          </CircleMarker>
        ))}

        {/* Housing area marker */}
        {housingAreaCoords && (
          <Marker position={[housingAreaCoords.lat, housingAreaCoords.lng]} icon={housingIcon}>
            <Popup>
              <div className="text-xs">
                <div className="font-semibold mb-0.5" style={{ color: '#0d9488' }}>
                  🏠 Preferred housing area
                </div>
                <div className="text-gray-600">{housingAreaLabel}</div>
              </div>
            </Popup>
          </Marker>
        )}
      </MapContainer>
    </div>
  );
}
