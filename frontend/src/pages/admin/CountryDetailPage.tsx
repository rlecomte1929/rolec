import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { AppShell } from '../../components/AppShell';
import { CountryDetail } from '../../components/admin/CountryDetail';
import {
  getCountryProfile,
  listCountryRequirements,
  rerunCountryResearch,
  reviewCountryRequirement,
} from '../../api/admin';
import type { AdminRequirementReview, ReviewStatus } from '../../api/admin';
import type { CountryProfileDTO } from '../../types';

export const CountryDetailPage: React.FC = () => {
  const { countryCode } = useParams();
  const [profile, setProfile] = useState<CountryProfileDTO | null>(null);
  const [requirements, setRequirements] = useState<AdminRequirementReview[]>([]);
  const [pendingCount, setPendingCount] = useState(0);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    if (!countryCode) return;
    setError(null);
    // Two calls on purpose: the profile endpoint is the legacy source/confidence view, while
    // the requirements endpoint is the only one that returns UNAPPROVED rows — which are
    // precisely the ones this page exists to act on.
    const [profileData, reqData] = await Promise.all([
      getCountryProfile(countryCode),
      listCountryRequirements(countryCode),
    ]);
    setProfile(profileData);
    setRequirements(reqData.items);
    setPendingCount(reqData.pendingCount);
  };

  useEffect(() => {
    void load().catch((e) => setError(e instanceof Error ? e.message : 'Failed to load country'));
  }, [countryCode]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleReview = async (id: string, status: Exclude<ReviewStatus, 'pending'>) => {
    if (!countryCode) return;
    setBusyId(id);
    setError(null);
    try {
      const updated = await reviewCountryRequirement(countryCode, id, status);
      setRequirements((prev) => prev.map((r) => (r.id === id ? updated : r)));
      setPendingCount((prev) => (status === 'approved' || status === 'rejected' ? Math.max(0, prev - 1) : prev));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not update this requirement');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <AppShell
      title="Country Requirements"
      subtitle="Review the evidence, then publish or withhold each requirement."
    >
      {error && <div className="text-sm text-[#b91c1c] mb-4">{error}</div>}
      {!profile && !error && <div className="text-sm text-[#6b7280]">Loading country profile...</div>}
      {profile && (
        <CountryDetail
          profile={profile}
          requirements={requirements}
          pendingCount={pendingCount}
          busyId={busyId}
          onRerun={async () => {
            await rerunCountryResearch(profile.countryCode);
            await load();
          }}
          onReview={handleReview}
        />
      )}
    </AppShell>
  );
};
