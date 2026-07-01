import React from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import type { LatLngBoundsExpression } from 'leaflet';
import type { RecommendationItem } from './types';

// [Phase 2] Neighborhood-first housing map: office pinned + one marker per
// recommended neighborhood, sized/coloured by fit score. Coordinates come from
// item.metadata.lat/lng (geocoded server-side, Phase 1) and criteria_echo
// office_lat/lng. Renders nothing when no coords are available so the card list
// below stays the fallback. Uses only CircleMarkers (no default-marker icon
// assets) so there is no Leaflet icon-url wiring to break under Vite.

// DESIGN.md: navy #0b2b43 (office), teal #1f8e8b (best match / accent).
const TIER_COLOR: Record<string, string> = {
  best_match: '#1f8e8b',
  good_fit: '#2563eb',
  ok: '#d97706',
  weak: '#64748b',
};

function FitBounds({ points }: { points: [number, number][] }) {
  const map = useMap();
  React.useEffect(() => {
    const first = points[0];
    if (points.length === 0 || !first) return;
    if (points.length === 1) {
      map.setView(first, 13);
    } else {
      map.fitBounds(points as LatLngBoundsExpression, { padding: [40, 40] });
    }
  }, [map, points]);
  return null;
}

interface Props {
  items: RecommendationItem[];
  office?: { lat: number; lng: number; address?: string } | null;
  /** Highlight + notify when a neighborhood marker is clicked (Phase 4 shortlist). */
  selectedId?: string | null;
  onSelect?: (itemId: string) => void;
}

export const HousingNeighborhoodMap: React.FC<Props> = ({ items, office, selectedId, onSelect }) => {
  const points = items
    .map((item) => ({ item, lat: Number(item.metadata?.lat), lng: Number(item.metadata?.lng) }))
    .filter((p) => Number.isFinite(p.lat) && Number.isFinite(p.lng));

  if (points.length === 0) return null; // no coords → card list is the fallback

  const hasOffice = !!office && Number.isFinite(office.lat) && Number.isFinite(office.lng);
  const allCoords: [number, number][] = points.map((p) => [p.lat, p.lng]);
  if (hasOffice && office) allCoords.push([office.lat, office.lng]);

  return (
    <div className="rounded-xl overflow-hidden border border-[#e2e8f0] mb-4" style={{ height: 360 }}>
      <MapContainer
        center={allCoords[0]}
        zoom={12}
        scrollWheelZoom={false}
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          attribution="&copy; OpenStreetMap contributors"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitBounds points={allCoords} />

        {hasOffice && office && (
          <CircleMarker
            center={[office.lat, office.lng]}
            radius={9}
            pathOptions={{ color: '#ffffff', weight: 2, fillColor: '#0b2b43', fillOpacity: 1 }}
          >
            <Popup>
              <strong>Your office</strong>
              {office.address ? <div style={{ fontSize: 12 }}>{office.address}</div> : null}
            </Popup>
          </CircleMarker>
        )}

        {points.map(({ item, lat, lng }) => {
          const color = TIER_COLOR[item.tier] ?? TIER_COLOR.ok;
          const radius = 8 + (Math.max(0, Math.min(100, item.score)) / 100) * 10;
          const selected = selectedId === item.item_id;
          const cost = item.metadata?.estimated_cost_local;
          const currency = item.metadata?.currency;
          return (
            <CircleMarker
              key={item.item_id}
              center={[lat, lng]}
              radius={radius}
              pathOptions={{
                color: selected ? '#0b2b43' : color,
                weight: selected ? 3 : 1.5,
                fillColor: color,
                fillOpacity: 0.75,
              }}
              eventHandlers={onSelect ? { click: () => onSelect(item.item_id) } : undefined}
            >
              <Popup>
                <strong>{item.name}</strong>
                <div style={{ fontSize: 12 }}>Fit {item.score}/100</div>
                {cost != null && currency ? <div style={{ fontSize: 12 }}>{currency} {cost}/mo</div> : null}
                <div style={{ fontSize: 12 }}>{item.summary}</div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>
    </div>
  );
};
