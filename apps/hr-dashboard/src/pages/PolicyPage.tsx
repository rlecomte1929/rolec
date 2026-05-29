import { EmptyState } from '../components/EmptyState';

export function PolicyPage(): JSX.Element {
  return (
    <div className="flex flex-col gap-6">
      <header className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold text-foreground">Policy</h1>
        <p className="text-sm text-muted-foreground">Active HR policies and their version history.</p>
      </header>
      <EmptyState
        title="Policy editor lands in C1-15"
        description="The 11-clause HR policy editor copy is already written (C1-15C). The UI consumes it once the editor is built."
      />
    </div>
  );
}
