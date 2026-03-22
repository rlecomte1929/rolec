/**
 * Mobility context summary, missing items, and next actions (MVP: no motion).
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchMobilityContext, fetchMobilityNextActions, type MobilityNextAction } from '../../api/mobility';
import type { CaseDraftDTO } from '../../types';
import { MobilityCasePanelsView, type MobilityCasePanelsViewProps } from './MobilityCasePanelsView';

const COUNTRY_LABELS: Record<string, string> = {
  FR: 'France',
  NO: 'Norway',
  DE: 'Germany',
  SE: 'Sweden',
  US: 'United States',
  SG: 'Singapore',
  GB: 'United Kingdom',
};

function labelCountry(code: string | undefined | null): string {
  const c = (code || '').trim().toUpperCase();
  if (!c) return '-';
  return COUNTRY_LABELS[c] || c;
}

function formatCaseType(raw: string | undefined | null): string {
  const s = (raw || '').trim();
  if (!s) return '-';
  return s.replace(/_/g, ' ');
}

export type { MobilityCasePanelsViewProps };

function familyLineFromDraft(fm: CaseDraftDTO['familyMembers']): string {
  const spouse = fm?.spouse?.fullName?.trim();
  const nKids = fm?.children?.length ?? 0;
  if (spouse && nKids > 0) return `Spouse listed; ${nKids} child(ren) listed`;
  if (spouse) return 'Spouse or partner listed';
  if (nKids > 0) return `${nKids} child(ren) listed`;
  return 'Not provided yet';
}

export type MobilityCasePanelsProps = {
  mobilityCaseId: string | null | undefined;
  /** Fallback labels when mobility case is not loaded */
  relocationBasics: CaseDraftDTO['relocationBasics'];
  familyMembers: CaseDraftDTO['familyMembers'];
};

export function MobilityCasePanels({ mobilityCaseId, relocationBasics, familyMembers }: MobilityCasePanelsProps) {
  const [loadState, setLoadState] = useState<'skipped' | 'loading' | 'error' | 'loaded'>(() =>
    mobilityCaseId ? 'loading' : 'skipped'
  );
  const [errorMessage, setErrorMessage] = useState<string | undefined>();
  const [routeOrigin, setRouteOrigin] = useState<string>(() =>
    labelCountry(relocationBasics?.originCountry || undefined)
  );
  const [routeDestination, setRouteDestination] = useState<string>(() =>
    labelCountry(relocationBasics?.destCountry || undefined)
  );
  const [caseTypeLabel, setCaseTypeLabel] = useState<string>(() => formatCaseType(relocationBasics?.purpose || null));
  const [missingItems, setMissingItems] = useState<MobilityCasePanelsViewProps['missingItems']>([]);
  const [nextActions, setNextActions] = useState<MobilityCasePanelsViewProps['nextActions']>([]);
  const [familyLine, setFamilyLine] = useState(() => familyLineFromDraft(familyMembers));

  const draftFamilyLine = useMemo(() => familyLineFromDraft(familyMembers), [familyMembers]);

  const load = useCallback(async () => {
    const mid = (mobilityCaseId || '').trim();
    setFamilyLine(draftFamilyLine);
    if (!mid) {
      setLoadState('skipped');
      setMissingItems([]);
      setNextActions([]);
      setRouteOrigin(labelCountry(relocationBasics?.originCountry || undefined));
      setRouteDestination(labelCountry(relocationBasics?.destCountry || undefined));
      setCaseTypeLabel(formatCaseType(relocationBasics?.purpose || null));
      setErrorMessage(undefined);
      return;
    }
    setLoadState('loading');
    setErrorMessage(undefined);
    try {
      const [ctx, next] = await Promise.all([fetchMobilityContext(mid), fetchMobilityNextActions(mid)]);
      const c = ctx.case;
      if (c) {
        setRouteOrigin(labelCountry(c.origin_country));
        setRouteDestination(labelCountry(c.destination_country));
        setCaseTypeLabel(formatCaseType(c.case_type));
      } else {
        setRouteOrigin(labelCountry(relocationBasics?.originCountry || undefined));
        setRouteDestination(labelCountry(relocationBasics?.destCountry || undefined));
        setCaseTypeLabel(formatCaseType(relocationBasics?.purpose || null));
      }
      const meta = c?.metadata && typeof c.metadata === 'object' ? (c.metadata as Record<string, unknown>) : {};
      const householdSpouse = Boolean(meta.household_includes_spouse);
      const familyExtra =
        householdSpouse && !draftFamilyLine.toLowerCase().includes('spouse')
          ? 'Household may include spouse (confirm in wizard).'
          : null;
      setFamilyLine(familyExtra ? `${draftFamilyLine} · ${familyExtra}` : draftFamilyLine);
      const evs = (ctx.evaluations || []).filter((e) => {
        const st = (e.evaluation_status || '').toLowerCase();
        return st === 'missing' || st === 'needs_review';
      });
      setMissingItems(
        evs.map((e, idx) => ({
          id: String(e.id ?? `eval-${e.requirement_id ?? idx}-${idx}`),
          code: String(e.requirement_code || e.requirement_id || 'requirement'),
          status: String(e.evaluation_status || ''),
          detail: (e.reason_text || '').trim(),
        }))
      );

      const acts: MobilityNextAction[] = next.actions || [];
      setNextActions(
        acts.map((a) => ({
          id: a.id,
          title: a.action_title,
          description: a.action_description,
          priority: a.priority,
        }))
      );
      setLoadState('loaded');
    } catch (e: unknown) {
      const ax = e as { response?: { status?: number; data?: { detail?: unknown } } };
      const st = ax.response?.status;
      const detail = ax.response?.data?.detail;
      const msg =
        st === 404
          ? 'Mobility case not found. Check that this assignment is linked to a mobility case ID.'
          : typeof detail === 'string'
            ? detail
            : 'Could not load mobility data.';
      setErrorMessage(msg);
      setLoadState('error');
      setMissingItems([]);
      setNextActions([]);
      setRouteOrigin(labelCountry(relocationBasics?.originCountry || undefined));
      setRouteDestination(labelCountry(relocationBasics?.destCountry || undefined));
      setCaseTypeLabel(formatCaseType(relocationBasics?.purpose || null));
      setFamilyLine(draftFamilyLine);
    }
  }, [mobilityCaseId, relocationBasics, draftFamilyLine]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <MobilityCasePanelsView
      routeOrigin={routeOrigin}
      routeDestination={routeDestination}
      caseTypeLabel={caseTypeLabel}
      familyStatusLine={familyLine}
      missingItems={missingItems}
      nextActions={nextActions}
      loadState={loadState}
      errorMessage={errorMessage}
    />
  );
}
