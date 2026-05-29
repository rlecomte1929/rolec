import { EmptyState } from '../components/EmptyState';

export function ResolutionPage(): JSX.Element {
  return (
    <div className="flex flex-col gap-6">
      <header className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold text-foreground">Resolution</h1>
        <p className="text-sm text-muted-foreground">Outstanding exceptions and decisions waiting on you.</p>
      </header>
      <EmptyState
        title="Resolution surface lands in C1-12"
        description="The resolution queue UI, copy and decisions log are scheduled for the C1-12 cohort. This scaffold reserves the route."
      />
    </div>
  );
}
