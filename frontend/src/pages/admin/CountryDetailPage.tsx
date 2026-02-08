import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { CountryDetail } from '../../components/admin/CountryDetail';
import { getCountryProfile, rerunCountryResearch } from '../../api/admin';
import type { CountryProfileDTO } from '../../types';

export const CountryDetailPage: React.FC = () => {
  const { countryCode } = useParams();
  const [profile, setProfile] = useState<CountryProfileDTO | null>(null);

  const loadProfile = async () => {
    if (!countryCode) return;
    const data = await getCountryProfile(countryCode);
    setProfile(data);
  };

  useEffect(() => {
    loadProfile();
  }, [countryCode]);

  return (
    <AppShell title="Country Requirements" subtitle="Review source evidence and requirements.">
      {!profile && <div className="text-sm text-[#6b7280]">Loading country profile...</div>}
      {profile && (
        <CountryDetail
          profile={profile}
          onRerun={async () => {
            await rerunCountryResearch(profile.countryCode);
            await loadProfile();
          }}
        />
      )}
    </AppShell>
  );
};
