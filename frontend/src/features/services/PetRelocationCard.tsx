/**
 * PetRelocationCard (AIQ-1001)
 *
 * Collects pet relocation details (species / count / specific needs) in the
 * service-selection phase. PR #681 reduced intake to a single has_pets yes/no;
 * this card is the destination for the details. Gated on:
 *   - intake has_pets === true (read from the assignment's intake draft), AND
 *   - pet relocation being available for the employee's corridor.
 *
 * When has_pets !== true, nothing renders. When has_pets but the corridor has
 * no pet service, an honest "not available for this corridor" message shows.
 *
 * Details persist into the shared ServicesFlow answers map under a single
 * `pet_relocation` key (auto-saved to services-state with the rest of the
 * services flow) — i.e. scoped to the service, no new persistence path.
 */
import React, { useEffect, useState } from 'react';
import { Card, Input, Select } from '../../components/antigravity';
import { employeeAPI } from '../../api/client';
import { isPetRelocationAvailableForCorridor } from './petCorridorAvailability';

/** Shape stored at answers.pet_relocation. */
export interface PetRelocationDetails {
  species?: string;
  count?: number | '';
  specific_needs?: string;
}

export const PET_RELOCATION_ANSWER_KEY = 'pet_relocation';

const SPECIES_OPTIONS = [
  { value: 'dog', label: 'Dog' },
  { value: 'cat', label: 'Cat' },
  { value: 'bird', label: 'Bird' },
  { value: 'other', label: 'Other' },
];

interface Props {
  assignmentId: string | null;
  originCountry?: string;
  destCountry?: string;
  answers: Record<string, unknown>;
  onChange: (next: Record<string, unknown>) => void;
}

export const PetRelocationCard: React.FC<Props> = ({
  assignmentId,
  originCountry,
  destCountry,
  answers,
  onChange,
}) => {
  const [hasPets, setHasPets] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    if (!assignmentId) {
      setHasPets(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    employeeAPI
      .getIntake(assignmentId)
      .then((res) => {
        if (cancelled) return;
        const draft = res.intakeDraft || {};
        setHasPets(draft.has_pets === true);
      })
      .catch(() => {
        // Soft failure — if we can't read the draft, don't surface the card.
        if (!cancelled) setHasPets(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [assignmentId]);

  // Nothing to show until we know has_pets, or when the employee has no pets.
  if (loading || hasPets !== true) return null;

  const available = isPetRelocationAvailableForCorridor(originCountry, destCountry);

  if (!available) {
    return (
      <Card padding="lg" className="mb-6 border-[#fde68a] bg-[#fffbeb]">
        <div className="flex items-start gap-2">
          <span className="text-base">🐾</span>
          <div>
            <h3 className="text-sm font-semibold text-[#92400e]">Pet relocation</h3>
            <p className="text-sm text-[#92400e] mt-1">
              Pet relocation services are not available for this corridor. Contact your HR team if
              you need assistance.
            </p>
          </div>
        </div>
      </Card>
    );
  }

  const details = (answers[PET_RELOCATION_ANSWER_KEY] as PetRelocationDetails | undefined) || {};

  const setDetail = (patch: Partial<PetRelocationDetails>) => {
    onChange({
      ...answers,
      [PET_RELOCATION_ANSWER_KEY]: { ...details, ...patch },
    });
  };

  return (
    <Card padding="lg" className="mb-6">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-base">🐾</span>
        <h3 className="text-sm font-semibold text-[#0b2b43]">Pet relocation</h3>
      </div>
      <p className="text-sm text-[#6b7280] mb-4">
        You told us you’re relocating with pets. Share a few details so we can help plan travel
        documents, quarantine, and transport.
      </p>
      <div className="space-y-4">
        <Select
          label="Species"
          placeholder="Select…"
          value={details.species ?? ''}
          onChange={(v) => setDetail({ species: v })}
          options={SPECIES_OPTIONS}
          fullWidth
        />
        <Input
          label="Number of pets"
          type="number"
          min={1}
          value={details.count ?? ''}
          onChange={(v) => setDetail({ count: v === '' ? '' : Number(v) })}
          fullWidth
        />
        <div>
          <label
            className="block text-sm font-medium text-[#374151] mb-1"
            htmlFor="pet-specific-needs"
          >
            Specific needs
          </label>
          <textarea
            id="pet-specific-needs"
            rows={3}
            value={details.specific_needs ?? ''}
            onChange={(e) => setDetail({ specific_needs: e.target.value })}
            placeholder="e.g. breed, age, microchip status, special handling, vet contact"
            className="w-full rounded-lg border border-[#d1d5db] px-4 py-2 text-sm text-[#0b2b43] focus:outline-none focus:ring-2 focus:ring-[#0b2b43] transition-all bg-white"
          />
        </div>
      </div>
    </Card>
  );
};
