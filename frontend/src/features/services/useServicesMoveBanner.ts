/**
 * useServicesMoveBanner (AIQ-1249d)
 *
 * Lightweight fetch of the move corridor + date for the ServicesContextBanner on
 * pages that don't otherwise load the full services context (Recommendations,
 * Estimate). ServicesQuestions derives the same fields from its primary
 * getServicesContext call and doesn't need this hook.
 */
import { useEffect, useState } from 'react';
import { servicesAPI } from '../../api/client';

export interface ServicesMoveBanner {
  originCity: string | null;
  destCity: string | null;
  date: string | null;
}

export function useServicesMoveBanner(assignmentId: string | null): ServicesMoveBanner | null {
  const [banner, setBanner] = useState<ServicesMoveBanner | null>(null);

  useEffect(() => {
    if (!assignmentId) {
      setBanner(null);
      return;
    }
    let cancelled = false;
    servicesAPI
      .getServicesContext(assignmentId)
      .then((res) => {
        if (cancelled) return;
        const ctx = res.case_context || {};
        setBanner({
          originCity: ctx.originCity || ctx.originCountry || null,
          destCity: ctx.destCity || ctx.destCountry || null,
          date: res.target_start_date || null,
        });
      })
      .catch(() => {
        if (!cancelled) setBanner(null);
      });
    return () => {
      cancelled = true;
    };
  }, [assignmentId]);

  return banner;
}
