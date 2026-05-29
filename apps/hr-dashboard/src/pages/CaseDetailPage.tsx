import { useParams, Link } from 'react-router-dom';
import { EmptyState } from '../components/EmptyState';

export function CaseDetailPage(): JSX.Element {
  const { id } = useParams<{ id: string }>();

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <Link to="/cases" className="text-sm font-medium text-primary hover:underline">
          ← Back to cases
        </Link>
        <h1 className="text-2xl font-semibold text-foreground">Case {id ?? '(unknown)'}</h1>
      </header>
      <EmptyState
        title="Case detail lands in C1-11c"
        description="Document panels, timeline and bbox PDF viewer are built in the following subtasks. The :id param is wired through so deep links keep working."
      />
    </div>
  );
}
