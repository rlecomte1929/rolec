/**
 * PetRequirementsSection — AIQ-160-E
 *
 * Surfaces pet import requirements on the HR case detail view.
 * Queries the pets table for the case and, per pet, looks up the
 * pet_import_rules table by destination country + species.
 *
 * Behaviour:
 *  - Hidden entirely when the case has no pets
 *  - One card per pet, showing: requirements list, quarantine badge,
 *    microchip/rabies/health cert flags, notes, and source link
 *  - Falls back to 'No data available' if no rule exists for the
 *    country/species combination
 *  - Does not throw on fetch failure — shows a subtle error state
 */

import React, { useCallback, useEffect, useState } from 'react';
import { supabase } from '../../api/supabase';
import { Card, Badge } from '../antigravity';
import { getCountryName } from '../../utils/countries';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Pet {
  id: string;
  name: string | null;
  species: string;
  breed: string | null;
}

interface PetImportRule {
  destination_country_code: string;
  species: string;
  requirements: string[];
  quarantine_days: number | null;
  microchip_required: boolean;
  rabies_cert_required: boolean;
  health_cert_required: boolean;
  notes: string | null;
  source_url: string | null;
  last_verified_at: string | null;
}

interface PetWithRule {
  pet: Pet;
  rule: PetImportRule | null;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function RequirementFlag({ label, required }: { label: string; required: boolean }) {
  return (
    <span className="inline-flex items-center gap-1 text-xs text-[#4b5563]">
      <span className={required ? 'text-[#22c55e]' : 'text-slate-500'}>
        {required ? '✓' : '–'}
      </span>
      {label}
    </span>
  );
}

function PetRuleCard({ petWithRule }: { petWithRule: PetWithRule }) {
  const { pet, rule } = petWithRule;
  const petLabel = pet.name
    ? `${pet.name} (${pet.species}${pet.breed ? ` · ${pet.breed}` : ''})`
    : `${pet.species}${pet.breed ? ` · ${pet.breed}` : ''}`;

  return (
    <div className="rounded-xl border border-[#e2e8f0] bg-[#f8fafc] p-4 space-y-3">
      {/* Pet header */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-[#0b2b43]">{petLabel}</span>
        {rule && (rule.quarantine_days ?? 0) > 0 && (
          <Badge variant="error" size="sm">
            ⚠ {rule.quarantine_days}-day quarantine
          </Badge>
        )}
        {rule && (rule.quarantine_days ?? 0) === 0 && rule !== null && (
          <Badge variant="success" size="sm">
            No quarantine
          </Badge>
        )}
      </div>

      {/* No data fallback */}
      {!rule && (
        <p className="text-sm text-slate-500 italic">
          No import data available for this country / species combination.
          Check official government sources before travel.
        </p>
      )}

      {/* Rule content */}
      {rule && (
        <>
          {/* Certificate / microchip flags */}
          <div className="flex flex-wrap gap-3">
            <RequirementFlag label="Microchip" required={rule.microchip_required} />
            <RequirementFlag label="Rabies cert" required={rule.rabies_cert_required} />
            <RequirementFlag label="Health cert" required={rule.health_cert_required} />
          </div>

          {/* Requirements list */}
          {rule.requirements.length > 0 && (
            <ul className="space-y-1">
              {rule.requirements.map((req, i) => (
                <li key={i} className="flex gap-2 text-sm text-[#374151]">
                  <span className="text-slate-500 shrink-0 mt-0.5">•</span>
                  <span>{req}</span>
                </li>
              ))}
            </ul>
          )}

          {/* Notes */}
          {rule.notes && (
            <p className="text-xs text-[#6b7280] bg-[#f1f5f9] rounded-lg px-3 py-2 leading-relaxed">
              {rule.notes}
            </p>
          )}

          {/* Footer: source link + last verified */}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-[#e2e8f0]">
            {rule.source_url ? (
              <a
                href={rule.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-[#1f8e8b] hover:underline font-medium"
              >
                Verify requirements ↗
              </a>
            ) : (
              <span className="text-xs text-slate-500">No source link available</span>
            )}
            {rule.last_verified_at && (
              <span className="text-xs text-slate-500">
                Last verified: {new Date(rule.last_verified_at).toLocaleDateString('en-GB', { month: 'short', year: 'numeric' })}
              </span>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  caseId: string;
  destCountry?: string | null;
}

export const PetRequirementsSection: React.FC<Props> = ({ caseId, destCountry }) => {
  const [petsWithRules, setPetsWithRules] = useState<PetWithRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setFailed(false);

    try {
      // 1. Fetch all pets for this case
      const { data: petsRaw, error: petsError } = await supabase
        .from('pets')
        .select('id, name, species, breed')
        .eq('case_id', caseId);

      // Pet data is optional. A failed or empty pets read almost always means the
      // case simply has no pets — treat it as a neutral empty state (the section
      // hides itself below) rather than alarming HR with a red connection error.
      // The error banner is reserved for a genuine failure once we KNOW pets exist
      // (the per-pet rules lookup below). AIQ-1344.
      const pets = (petsError ? [] : (petsRaw ?? [])) as Pet[];
      if (pets.length === 0) {
        setPetsWithRules([]);
        setLoading(false);
        return;
      }

      // 2. For each pet, fetch the import rule for this destination + species
      const results: PetWithRule[] = await Promise.all(
        pets.map(async (pet) => {
          if (!destCountry) return { pet, rule: null };

          const ruleResult = (await supabase
            .from('pet_import_rules')
            .select('*')
            .eq('destination_country_code', destCountry.toUpperCase())
            .eq('species', pet.species.toLowerCase())
            .maybeSingle()) as unknown as { data: PetImportRule | null };

          return { pet, rule: ruleResult.data ?? null };
        })
      );

      setPetsWithRules(results);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, [caseId, destCountry]);

  useEffect(() => {
    void load();
  }, [load]);

  // Hide entirely when no pets
  if (!loading && !failed && petsWithRules.length === 0) return null;

  return (
    <Card padding="lg" className="border border-[#e2e8f0]">
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-sm font-semibold text-[#0b2b43]">Pet import requirements</div>
          <p className="text-xs text-slate-500 mt-0.5">
            Import rules for {getCountryName(destCountry) || destCountry || 'the destination country'} — verify with source links before travel
          </p>
        </div>
        {destCountry && (
          <Badge variant="info" size="sm">{getCountryName(destCountry) || destCountry.toUpperCase()}</Badge>
        )}
      </div>

      {loading && (
        <div className="text-sm text-slate-500 py-4">Loading pet requirements…</div>
      )}

      {failed && (
        <div className="text-sm text-[#ef4444] py-2">
          Could not load pet import data. Please check your connection and try again.
        </div>
      )}

      {!loading && !failed && (
        <div className="space-y-4">
          {petsWithRules.map(({ pet, rule }) => (
            <PetRuleCard key={pet.id} petWithRule={{ pet, rule }} />
          ))}
        </div>
      )}
    </Card>
  );
};
