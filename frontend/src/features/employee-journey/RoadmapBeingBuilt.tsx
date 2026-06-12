/**
 * Employee Roadmap — "being built" empty state.
 *
 * Pure presentational first-class empty screen for the prod-default case where
 * the roadmap has no tracks yet. Matches the approved `roadmap-empty-E.html`
 * mockup: reassuring centerpiece, a low-contrast preview of the tracks that will
 * appear (skeletons only — NO fabricated data), and a reassurance row.
 */
import React from 'react';
import { Card, Button } from '../../components/antigravity';

interface RoadmapBeingBuiltProps {
  /** Optional CTA — omit to hide the "Message my relocation team" button. */
  onMessageTeam?: () => void;
}

const NAVY = '#0b2b43';
const TEAL = '#1f8e8b';

/** The tracks that will appear once the plan is built. Names only — no fabricated steps. */
const PREVIEW_TRACKS: { name: string; icon: React.ReactNode }[] = [
  {
    name: 'Immigration & visa',
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.6} d="M12 2l8 4v6c0 5-3.5 8-8 10-4.5-2-8-5-8-10V6l8-4z" />
    ),
  },
  {
    name: 'Housing',
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.6} d="M3 11l9-7 9 7M5 10v9h5v-5h4v5h5v-9" />
    ),
  },
  {
    name: 'Schooling',
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.6} d="M12 4L2 9l10 5 10-5-10-5zM6 12v5c0 1 2.5 2.5 6 2.5S18 18 18 17v-5" />
    ),
  },
  {
    name: 'Moving & setup',
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.6} d="M3 7h11v8H3V7zm11 2h4l3 3v3h-7V9zM7 19a1.5 1.5 0 100-3 1.5 1.5 0 000 3zm10 0a1.5 1.5 0 100-3 1.5 1.5 0 000 3z" />
    ),
  },
  {
    name: 'Banking',
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.6} d="M3 9l9-5 9 5M4 9v8h16V9M8 12v3m4-3v3m4-3v3M3 19h18" />
    ),
  },
];

const REASSURANCE: { label: string; icon: React.ReactNode }[] = [
  {
    label: "We'll email you when it's ready",
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.6} d="M3 7l9 6 9-6M3 7v10h18V7H3z" />
    ),
  },
  {
    label: 'You can message your relocation team any time',
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.6} d="M21 12a8 8 0 01-11.4 7.2L4 21l1.8-5.6A8 8 0 1121 12z" />
    ),
  },
  {
    label: 'Nothing you need to do right now',
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.6} d="M5 12l4 4 10-10" />
    ),
  },
];

export const RoadmapBeingBuilt: React.FC<RoadmapBeingBuiltProps> = ({ onMessageTeam }) => (
  <div className="space-y-5">
    {/* Centerpiece */}
    <Card padding="lg" className="text-center">
      <div className="relative mx-auto mb-5 flex h-20 w-20 items-center justify-center">
        <svg viewBox="0 0 64 64" fill="none" className="h-20 w-20" aria-hidden="true">
          <path
            d="M12 50c0-8 8-8 8-16S12 22 12 14"
            stroke={TEAL}
            strokeWidth={2.5}
            strokeLinecap="round"
            strokeDasharray="2 5"
          />
          <path
            d="M52 14c0 8-8 8-8 16s8 8 8 16"
            stroke={NAVY}
            strokeWidth={2.5}
            strokeLinecap="round"
            strokeDasharray="2 5"
          />
          <circle cx="12" cy="14" r="4" fill={NAVY} />
          <circle cx="52" cy="50" r="4" fill={NAVY} />
        </svg>
        {/* Teal pulse dot */}
        <span className="absolute right-1 top-1 flex h-3 w-3">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#1f8e8b] opacity-60" />
          <span className="relative inline-flex h-3 w-3 rounded-full bg-[#1f8e8b]" />
        </span>
      </div>

      <h1 className="text-2xl font-semibold text-navy-800">We're building your roadmap</h1>
      <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-[#475569]">
        Now that your intake and services are confirmed, our team is putting together your
        personalised relocation plan. You'll get an email the moment it's ready — usually within
        2 working days.
      </p>

      <span className="mt-5 inline-flex items-center gap-2 rounded-full border border-[#1f8e8b]/30 bg-[#1f8e8b]/10 px-3 py-1 text-xs font-semibold text-[#197c79]">
        <span className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-2 w-2 animate-ping rounded-full bg-[#1f8e8b] opacity-60" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-[#1f8e8b]" />
        </span>
        Preparing your plan
      </span>

      {onMessageTeam && (
        <div className="mt-6">
          <Button variant="primary" onClick={onMessageTeam}>
            Message my relocation team
          </Button>
        </div>
      )}
    </Card>

    {/* What will appear here — skeleton preview (no fabricated data) */}
    <Card padding="lg">
      <h2 className="text-sm font-semibold text-navy-800">What will appear here</h2>
      <ul className="mt-4 space-y-3">
        {PREVIEW_TRACKS.map((track) => (
          <li
            key={track.name}
            className="flex items-center gap-3 rounded-lg border border-[#e2e8f0] bg-[#f8fafc] px-4 py-3"
          >
            <span className="flex h-9 w-9 flex-none items-center justify-center rounded-lg bg-white text-[#94a3b8]">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" className="h-5 w-5" aria-hidden="true">
                {track.icon}
              </svg>
            </span>
            <span className="flex-none text-sm font-medium text-[#334155]">{track.name}</span>
            <span className="ml-auto flex flex-1 items-center justify-end gap-2" aria-hidden="true">
              <span className="h-2 w-24 rounded-full bg-[#e2e8f0]" />
              <span className="h-2 w-12 rounded-full bg-[#e2e8f0]" />
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-[#94a3b8]">Steps will appear here once your plan is ready.</p>
    </Card>

    {/* Reassurance row */}
    <div className="grid gap-3 sm:grid-cols-3">
      {REASSURANCE.map((item) => (
        <div
          key={item.label}
          className="flex items-start gap-2 rounded-lg border border-[#e2e8f0] bg-white px-4 py-3"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke={TEAL} className="mt-0.5 h-4 w-4 flex-none" aria-hidden="true">
            {item.icon}
          </svg>
          <span className="text-xs leading-snug text-[#475569]">{item.label}</span>
        </div>
      ))}
    </div>
  </div>
);
