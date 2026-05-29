import { EmptyState } from '../components/EmptyState';

export function CasesPage(): JSX.Element {
  return (
    <div className="flex flex-col gap-6">
      <header className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold text-foreground">Cases</h1>
        <p className="text-sm text-muted-foreground">All immigration cases routed to your team.</p>
      </header>
      <EmptyState
        title="Case list lands in C1-11b"
        description="The real list view (filters, status chips, owner column) is built in the next subtask. This route already routes, authenticates, and pulls design tokens."
      />
    </div>
  );
}
