import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { CountryDetail } from '../../components/admin/CountryDetail';
import { AdminLayout } from './AdminLayout';
import {
  getCountryProfile,
  listCountryRequirements,
  rerunCountryResearch,
  reviewCountryRequirement,
  reviewCountryRequirementsBatch,
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
      setRequirements((prev) => {
        const next = prev.map((r) => (r.id === id ? updated : r));
        setPendingCount(next.filter((r) => r.reviewStatus === 'pending').length);
        return next;
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not update this requirement');
    } finally {
      setBusyId(null);
    }
  };

  const handleReviewBatch = async (ids: string[], status: Exclude<ReviewStatus, 'pending'>) => {
    if (!countryCode || ids.length === 0) return;
    setBusyId('batch');
    setError(null);
    try {
      const updated = await reviewCountryRequirementsBatch(countryCode, ids, status);
      const byId = new Map(updated.items.map((item) => [item.id, item]));
      setRequirements((prev) => {
        const next = prev.map((row) => byId.get(row.id) ?? row);
        setPendingCount(next.filter((r) => r.reviewStatus === 'pending').length);
        return next;
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not update the selected requirements');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <AdminLayout
      title="Country requirements"
      subtitle="This list is what employees and HR are served. Approve publishes the row; withhold keeps it out of the live catalog."
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
          onReviewBatch={handleReviewBatch}
        />
      )}
    </AdminLayout>
  );
};
