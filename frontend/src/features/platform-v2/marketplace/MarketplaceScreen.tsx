/**
 * T12 — Marketplace Screen (S6) /marketplace
 * Employee-facing vendor directory with slide-over detail panel.
 */

import { useState, useMemo } from 'react';
import { Input } from '../../../components/antigravity/Input';
import { Button } from '../../../components/antigravity/Button';
import {
  Avatar,
  CountryFlag,
  EmptyState,
  FilterChips,
  Pill,
} from '../shared';

// ─── Types ────────────────────────────────────────────────────────────────────

export type ServiceType = 'Housing' | 'Immigration' | 'Tax' | 'Moving' | 'School';

export interface Vendor {
  id: string;
  name: string;
  service_type: ServiceType;
  corridors: string[]; // ISO-2 codes
  rating: number; // 1–5
  description: string;
  contact_email: string;
  contact_phone: string | null;
  services: string[];
  logo_url?: string;
}

export interface MarketplaceScreenProps {
  vendors?: Vendor[];
  onAssign?: (vendorId: string) => void;
}

// ─── Mock data ────────────────────────────────────────────────────────────────

const MOCK_VENDORS: Vendor[] = [
  {
    id: 'v1',
    name: 'NestFinder Europe',
    service_type: 'Housing',
    corridors: ['FR', 'DE', 'NL', 'BE'],
    rating: 4.8,
    description: 'Expert relocation housing search across Western Europe. Dedicated property hunters with 10+ years experience finding homes for expats.',
    contact_email: 'hello@nestfinder.eu',
    contact_phone: '+33 1 23 45 67 89',
    services: ['Property search', 'Rental negotiation', 'Lease review', 'Move-in support'],
  },
  {
    id: 'v2',
    name: 'VisaTrack',
    service_type: 'Immigration',
    corridors: ['US', 'GB', 'CA', 'AU'],
    rating: 4.6,
    description: 'End-to-end immigration management for global talent. We handle visa applications, work permit renewals, and compliance.',
    contact_email: 'support@visatrack.io',
    contact_phone: '+1 415 000 0000',
    services: ['Visa applications', 'Work permits', 'Compliance audits', 'Family visas'],
  },
  {
    id: 'v3',
    name: 'TaxBridge',
    service_type: 'Tax',
    corridors: ['FR', 'US', 'DE', 'GB'],
    rating: 4.5,
    description: 'Cross-border tax advisory for internationally mobile employees. Specialising in shadow payroll and split-year returns.',
    contact_email: 'advisors@taxbridge.com',
    contact_phone: null,
    services: ['Tax equalisation', 'Shadow payroll', 'Year-end filing', 'Treaty analysis'],
  },
  {
    id: 'v4',
    name: 'MoveFast Logistics',
    service_type: 'Moving',
    corridors: ['FR', 'DE', 'ES', 'IT', 'NL'],
    rating: 4.3,
    description: 'Door-to-door international moving with real-time shipment tracking. Specialist in fragile goods and vehicle transport.',
    contact_email: 'quote@movefast.eu',
    contact_phone: '+49 30 000 0000',
    services: ['Full-service packing', 'Storage', 'Vehicle shipping', 'Pet relocation'],
  },
  {
    id: 'v5',
    name: 'SchoolBridge',
    service_type: 'School',
    corridors: ['GB', 'FR', 'DE', 'CH', 'NL'],
    rating: 4.7,
    description: 'School placement consultants for international families. From curriculum matching to enrollment support.',
    contact_email: 'enrol@schoolbridge.co',
    contact_phone: '+44 20 0000 0000',
    services: ['School search', 'Admissions support', 'Education assessment', 'Settling-in workshops'],
  },
  {
    id: 'v6',
    name: 'HouseHunt Paris',
    service_type: 'Housing',
    corridors: ['FR'],
    rating: 4.2,
    description: 'Paris-based housing specialists with curated listings across all arrondissements. Perfect for corporate relocations.',
    contact_email: 'bonjour@househuntparis.fr',
    contact_phone: '+33 1 99 88 77 66',
    services: ['Apartment search', 'Temporary housing', 'Furnished rentals', 'Neighbourhood tours'],
  },
];

const FILTER_CHIPS = [
  { id: 'all', label: 'All' },
  { id: 'Housing', label: 'Housing' },
  { id: 'Immigration', label: 'Immigration' },
  { id: 'Tax', label: 'Tax' },
  { id: 'Moving', label: 'Moving' },
  { id: 'School', label: 'School' },
];

const SERVICE_TYPE_VARIANT: Record<ServiceType, 'info' | 'success' | 'warning' | 'danger' | 'default'> = {
  Housing: 'info',
  Immigration: 'warning',
  Tax: 'default',
  Moving: 'success',
  School: 'danger',
};

// ─── StarRating ───────────────────────────────────────────────────────────────

function StarRating({ value }: { value: number }) {
  return (
    <div style={{ display: 'flex', gap: '2px', alignItems: 'center' }}>
      {[1, 2, 3, 4, 5].map(i => (
        <svg
          key={i}
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill={i <= Math.round(value) ? 'var(--warning)' : 'var(--border)'}
          stroke="none"
        >
          <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
        </svg>
      ))}
      <span style={{ fontSize: '12px', color: 'var(--text-muted)', marginLeft: '4px' }}>{value.toFixed(1)}</span>
    </div>
  );
}

// ─── VendorCard ───────────────────────────────────────────────────────────────

interface VendorCardProps {
  vendor: Vendor;
  onView: () => void;
}

function VendorCard({ vendor, onView }: VendorCardProps) {
  return (
    <div
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)',
        padding: '20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        transition: 'border-color 0.15s, box-shadow 0.15s',
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLElement).style.borderColor = 'var(--accent)';
        (e.currentTarget as HTMLElement).style.boxShadow = '0 2px 12px rgba(29,191,162,0.1)';
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLElement).style.borderColor = 'var(--border)';
        (e.currentTarget as HTMLElement).style.boxShadow = 'none';
      }}
    >
      {/* Header row */}
      <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
        <Avatar name={vendor.name} src={vendor.logo_url} size={44} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{ margin: '0 0 4px', fontSize: '14px', fontWeight: 700, color: 'var(--text)' }}>
            {vendor.name}
          </p>
          <Pill variant={SERVICE_TYPE_VARIANT[vendor.service_type]} size="sm">
            {vendor.service_type}
          </Pill>
        </div>
      </div>

      {/* Corridors */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
        {vendor.corridors.slice(0, 6).map(code => (
          <CountryFlag key={code} code={code} showCode style={{ fontSize: '13px' }} />
        ))}
        {vendor.corridors.length > 6 && (
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>+{vendor.corridors.length - 6}</span>
        )}
      </div>

      {/* Rating */}
      <StarRating value={vendor.rating} />

      {/* Description (2 lines) */}
      <p
        style={{
          margin: 0,
          fontSize: '13px',
          color: 'var(--text-secondary)',
          lineHeight: 1.5,
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
        }}
      >
        {vendor.description}
      </p>

      {/* CTA */}
      <Button unstyled
        onClick={onView}
        style={{
          marginTop: 'auto',
          padding: '8px 14px',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border)',
          background: 'var(--surface)',
          color: 'var(--accent)',
          fontSize: '13px',
          fontWeight: 600,
          cursor: 'pointer',
          textAlign: 'left',
        }}
      >
        View details →
      </Button>
    </div>
  );
}

// ─── SlideOver ────────────────────────────────────────────────────────────────

interface VendorSlideOverProps {
  vendor: Vendor | null;
  onClose: () => void;
  onAssign: (id: string) => void;
}

function VendorSlideOver({ vendor, onClose, onAssign }: VendorSlideOverProps) {
  if (!vendor) return null;
  return (
    <>
      <div
        aria-hidden="true"
        onClick={onClose}
        style={{ position: 'fixed', inset: 0, background: 'var(--overlay)', zIndex: 40 }}
      />
      <div
        role="dialog"
        aria-label={`${vendor.name} details`}
        style={{
          position: 'fixed',
          top: 0,
          right: 0,
          bottom: 0,
          width: '400px',
          background: 'var(--surface)',
          borderLeft: '1px solid var(--border)',
          zIndex: 50,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div style={{ padding: '20px 24px 16px', borderBottom: '1px solid var(--border)', display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
          <Avatar name={vendor.name} size={52} />
          <div style={{ flex: 1 }}>
            <p style={{ margin: '0 0 4px', fontSize: '16px', fontWeight: 700, color: 'var(--text)' }}>{vendor.name}</p>
            <Pill variant={SERVICE_TYPE_VARIANT[vendor.service_type]} size="sm">{vendor.service_type}</Pill>
          </div>
          <Button unstyled
            onClick={onClose}
            aria-label="Close"
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '4px' }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </Button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <StarRating value={vendor.rating} />

          <div>
            <p style={{ margin: '0 0 8px', fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)' }}>About</p>
            <p style={{ margin: 0, fontSize: '14px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>{vendor.description}</p>
          </div>

          <div>
            <p style={{ margin: '0 0 8px', fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)' }}>Services</p>
            <ul style={{ margin: 0, paddingLeft: '16px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {vendor.services.map(s => (
                <li key={s} style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>{s}</li>
              ))}
            </ul>
          </div>

          <div>
            <p style={{ margin: '0 0 8px', fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)' }}>Supported Corridors</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {vendor.corridors.map(code => (
                <CountryFlag key={code} code={code} showCode />
              ))}
            </div>
          </div>

          <div>
            <p style={{ margin: '0 0 8px', fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-muted)' }}>Contact</p>
            <p style={{ margin: '0 0 4px', fontSize: '14px', color: 'var(--link)' }}>{vendor.contact_email}</p>
            {vendor.contact_phone && (
              <p style={{ margin: 0, fontSize: '14px', color: 'var(--text-secondary)' }}>{vendor.contact_phone}</p>
            )}
          </div>
        </div>

        {/* Footer */}
        <div style={{ padding: '16px 24px', borderTop: '1px solid var(--border)' }}>
          <Button unstyled
            onClick={() => onAssign(vendor.id)}
            style={{
              width: '100%',
              padding: '10px',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              background: 'var(--accent)',
              color: '#fff',
              fontSize: '14px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Assign to my case
          </Button>
        </div>
      </div>
    </>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export function MarketplaceScreen({ vendors = MOCK_VENDORS, onAssign }: MarketplaceScreenProps) {
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<Vendor | null>(null);

  const filtered = useMemo(() => {
    return vendors.filter(v => {
      const matchType = filter === 'all' || v.service_type === filter;
      const q = search.toLowerCase();
      const matchSearch = !q || v.name.toLowerCase().includes(q) || v.description.toLowerCase().includes(q);
      return matchType && matchSearch;
    });
  }, [vendors, filter, search]);

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      {/* Page header */}
      <h1 style={{ margin: '0 0 20px', fontSize: '22px', fontWeight: 700, color: 'var(--text)' }}>Vendor Marketplace</h1>

      {/* Toolbar */}
      <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: '0 0 280px' }}>
          <svg
            width="16" height="16" viewBox="0 0 24 24" fill="none"
            stroke="var(--text-muted)" strokeWidth="2"
            style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}
          >
            <path d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" />
          </svg>
          <Input unstyled
            type="search"
            placeholder="Search vendors…"
            value={search}
            onChange={v => setSearch(v)}
            style={{
              width: '100%',
              padding: '8px 12px 8px 34px',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border)',
              background: 'var(--surface)',
              color: 'var(--text)',
              fontSize: '14px',
              outline: 'none',
              boxSizing: 'border-box',
            }}
          />
        </div>
        <FilterChips chips={FILTER_CHIPS} selected={filter} onSelect={setFilter} />
      </div>

      {/* Grid */}
      {filtered.length === 0 ? (
        <EmptyState
          icon="M3 7h18M3 12h18M3 17h18"
          title="No vendors match your filter"
          description="Try changing the category or clearing your search."
          action={{ label: 'Clear filters', onClick: () => { setFilter('all'); setSearch(''); } }}
        />
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: '16px',
          }}
        >
          {filtered.map(v => (
            <VendorCard key={v.id} vendor={v} onView={() => setSelected(v)} />
          ))}
        </div>
      )}

      {/* Slide-over */}
      <VendorSlideOver
        vendor={selected}
        onClose={() => setSelected(null)}
        onAssign={(id) => { onAssign?.(id); setSelected(null); }}
      />
    </div>
  );
}
