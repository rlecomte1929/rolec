import React from 'react';
import type { CountryProfileDTO } from '../../types';
import { Card, Button } from '../antigravity';

interface CountryDetailProps {
  profile: CountryProfileDTO;
  onRerun: () => void;
}

export const CountryDetail: React.FC<CountryDetailProps> = ({ profile, onRerun }) => {
  return (
    <div className="space-y-6">
      <Card padding="lg">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-lg font-semibold text-[#0b2b43]">{profile.countryCode}</div>
            <div className="text-xs text-[#6b7280]">
              Last updated: {profile.lastUpdatedAt ? new Date(profile.lastUpdatedAt).toLocaleString('en-US') : '—'}
            </div>
          </div>
          <Button onClick={onRerun}>Re-run research</Button>
        </div>
      </Card>

      <Card padding="lg">
        <div className="text-sm font-semibold text-[#0b2b43] mb-3">Sources</div>
        <div className="space-y-2 text-sm">
          {profile.sources.map((source) => (
            <div key={source.id} className="border border-[#e2e8f0] rounded-lg p-3">
              <div className="font-semibold text-[#0b2b43]">{source.title}</div>
              <div className="text-xs text-[#6b7280]">{source.publisherDomain}</div>
            </div>
          ))}
        </div>
      </Card>

      <Card padding="lg">
        <div className="text-sm font-semibold text-[#0b2b43] mb-3">Requirements</div>
        <div className="space-y-4">
          {profile.requirementGroups.map((group) => (
            <div key={group.pillar} className="border border-[#e2e8f0] rounded-lg p-4">
              <div className="text-sm font-semibold text-[#0b2b43]">{group.pillar}</div>
              <div className="text-xs text-[#6b7280] mt-1">{group.items.length} items</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
};
