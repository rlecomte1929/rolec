import '@testing-library/jest-dom/vitest';
import React from 'react';
import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

// Leaflet needs real DOM/canvas — mock react-leaflet so the component's data
// logic (which points to plot) is what we test, not the map engine.
vi.mock('leaflet/dist/leaflet.css', () => ({}));
vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => <div data-testid="map">{children}</div>,
  TileLayer: () => null,
  CircleMarker: ({ children }: { children: React.ReactNode }) => <div data-testid="marker">{children}</div>,
  Popup: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  useMap: () => ({ setView: vi.fn(), fitBounds: vi.fn() }),
}));

import { HousingNeighborhoodMap } from '../HousingNeighborhoodMap';
import type { RecommendationItem } from '../types';

const mkItem = (id: string, meta: Partial<RecommendationItem['metadata']> = {}): RecommendationItem => ({
  item_id: id,
  name: `N-${id}`,
  score: 80,
  tier: 'best_match',
  summary: 'summary',
  rationale: 'rationale',
  breakdown: {},
  pros: [],
  cons: [],
  metadata: { ...meta },
});

afterEach(() => cleanup());

describe('HousingNeighborhoodMap', () => {
  it('renders nothing when no neighborhood has coordinates', () => {
    const { container } = render(<HousingNeighborhoodMap items={[mkItem('a')]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders one marker per geocoded neighborhood plus the office', () => {
    render(
      <HousingNeighborhoodMap
        items={[mkItem('a', { lat: 1.3, lng: 103.8 }), mkItem('b', { lat: 1.31, lng: 103.82 })]}
        office={{ lat: 1.28, lng: 103.85, address: 'CBD' }}
      />,
    );
    expect(screen.getByTestId('map')).toBeInTheDocument();
    // two neighborhoods + one office
    expect(screen.getAllByTestId('marker')).toHaveLength(3);
    expect(screen.getByText('N-a')).toBeInTheDocument();
    expect(screen.getByText('Your office')).toBeInTheDocument();
  });

  it('skips un-geocoded neighborhoods but keeps geocoded ones', () => {
    render(
      <HousingNeighborhoodMap
        items={[mkItem('a', { lat: 1.3, lng: 103.8 }), mkItem('b')]}
        office={null}
      />,
    );
    expect(screen.getAllByTestId('marker')).toHaveLength(1);
  });

  it('offers a schools toggle and renders school markers only when toggled on', () => {
    render(
      <HousingNeighborhoodMap
        items={[
          mkItem('a', {
            lat: 1.3,
            lng: 103.8,
            nearby_schools: [{ item_id: 's1', name: 'Sch One', lat: 1.31, lng: 103.81, commute_min: 12 }],
          }),
        ]}
      />,
    );
    // one neighborhood marker; school hidden by default
    expect(screen.getAllByTestId('marker')).toHaveLength(1);
    const toggle = screen.getByRole('button', { name: /Show schools/ });
    fireEvent.click(toggle);
    // neighborhood + school
    expect(screen.getAllByTestId('marker')).toHaveLength(2);
    expect(screen.getByText('Sch One')).toBeInTheDocument();
  });
});
