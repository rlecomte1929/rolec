/**
 * Loading skeleton for the cases table — six rows of shimmer boxes that
 * match the live table's grid layout. Used while the first fetch is in
 * flight so the page doesn't flash an empty state.
 */
export function CasesSkeleton(): JSX.Element {
  return (
    <div className="rounded-lg border border-border bg-card shadow-sm">
      <div className="grid grid-cols-[1.6fr_1fr_0.9fr_0.9fr_0.9fr_0.6fr] border-b border-border bg-muted/40 px-4 py-3">
        {Array.from({ length: 6 }).map((_, idx) => (
          <div key={idx} className="h-3 w-20 rounded bg-muted" />
        ))}
      </div>
      {Array.from({ length: 6 }).map((_, rowIdx) => (
        <div
          key={rowIdx}
          className="grid grid-cols-[1.6fr_1fr_0.9fr_0.9fr_0.9fr_0.6fr] items-center gap-2 border-b border-border px-4 py-4"
        >
          {Array.from({ length: 6 }).map((__, cellIdx) => (
            <div
              key={cellIdx}
              className="h-3 rounded bg-muted"
              style={{ width: `${50 + ((rowIdx + cellIdx) % 5) * 10}%` }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}
