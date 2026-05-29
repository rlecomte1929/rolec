import { useCaseOverviewQuery } from '../../hooks/useCaseDetailQuery';
import { SectionShell } from './SectionShell';
import type { FamilyMember } from './types';

interface OverviewSectionProps {
  caseId: string;
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function relationshipLabel(relation: FamilyMember['relationship']): string {
  const map: Record<string, string> = {
    spouse: 'Spouse',
    partner: 'Partner',
    child: 'Child',
    parent: 'Parent',
    other: 'Other',
  };
  return map[relation] ?? relation;
}

export function OverviewSection({ caseId }: OverviewSectionProps): JSX.Element {
  const query = useCaseOverviewQuery(caseId);
  const data = query.data;

  return (
    <SectionShell
      title="Overview"
      subtitle="Employee, family, status, and target dates."
      isLoading={query.isLoading}
      isError={query.isError}
      error={query.error}
      onRetry={() => void query.refetch()}
    >
      {data ? (
        <div className="flex flex-col gap-6">
          <dl className="grid grid-cols-1 gap-4 rounded-lg border border-border bg-card p-4 shadow-sm md:grid-cols-2">
            <Definition term="Employee" value={data.employee.display_name} />
            <Definition term="Email" value={data.employee.primary_email ?? '—'} />
            <Definition term="Nationality" value={data.employee.nationality ?? '—'} />
            <Definition
              term="Corridor"
              value={data.corridor ?? `${data.origin_country_code ?? '—'} → ${data.dest_country_code ?? '—'}`}
            />
            <Definition term="Status" value={data.status} />
            <Definition term="Stage" value={data.stage ?? '—'} />
            <Definition term="Target start" value={formatDate(data.target_start_date)} />
            <Definition term="Actual start" value={formatDate(data.actual_start_date)} />
            <Definition term="Target close" value={formatDate(data.target_close_date)} />
          </dl>

          <FamilyTable members={data.family_members} />
        </div>
      ) : null}
    </SectionShell>
  );
}

function Definition({ term, value }: { term: string; value: string }): JSX.Element {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{term}</dt>
      <dd className="text-sm text-foreground">{value}</dd>
    </div>
  );
}

function FamilyTable({ members }: { members: FamilyMember[] }): JSX.Element {
  if (members.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">
        <h3 className="text-sm font-semibold text-foreground">Family</h3>
        <p className="mt-2">No family members registered for this case.</p>
      </div>
    );
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-card shadow-sm">
      <h3 className="px-4 pb-2 pt-4 text-sm font-semibold text-foreground">
        Family ({members.length})
      </h3>
      <table className="w-full text-sm">
        <thead className="text-xs uppercase tracking-wide text-muted-foreground">
          <tr className="border-b border-border">
            <th scope="col" className="px-4 py-2 text-left font-medium">Relationship</th>
            <th scope="col" className="px-4 py-2 text-left font-medium">Name</th>
            <th scope="col" className="px-4 py-2 text-left font-medium">Date of birth</th>
            <th scope="col" className="px-4 py-2 text-left font-medium">Dependent</th>
          </tr>
        </thead>
        <tbody>
          {members.map((m) => (
            <tr key={m.family_member_id} className="border-b border-border last:border-b-0">
              <td className="px-4 py-2">{relationshipLabel(m.relationship)}</td>
              <td className="px-4 py-2 font-medium text-foreground">{m.display_name}</td>
              <td className="px-4 py-2 text-muted-foreground">{formatDate(m.date_of_birth)}</td>
              <td className="px-4 py-2 text-muted-foreground">
                {m.is_dependent === true ? 'Yes' : m.is_dependent === false ? 'No' : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
