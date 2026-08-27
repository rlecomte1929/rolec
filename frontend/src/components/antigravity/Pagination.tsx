import React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

interface PaginationProps {
  /** 1-based current page. */
  page: number;
  /** Total number of pages (>= 1). */
  totalPages: number;
  onChange: (page: number) => void;
  /** Max numbered buttons to show (default 7); the rest collapse to ellipses. */
  maxButtons?: number;
  className?: string;
}

/** Build the visible page list with ellipses, e.g. [1,'…',4,5,6,'…',20]. */
function pageWindow(page: number, total: number, maxButtons: number): Array<number | 'ellipsis'> {
  if (total <= maxButtons) return Array.from({ length: total }, (_, i) => i + 1);
  const side = Math.max(1, Math.floor((maxButtons - 3) / 2));
  const start = Math.max(2, page - side);
  const end = Math.min(total - 1, page + side);
  const out: Array<number | 'ellipsis'> = [1];
  if (start > 2) out.push('ellipsis');
  for (let i = start; i <= end; i++) out.push(i);
  if (end < total - 1) out.push('ellipsis');
  out.push(total);
  return out;
}

/**
 * Antigravity Pagination — shared page navigation (previously only inside
 * DataTable). `<nav aria-label="Pagination">`; the current page carries
 * `aria-current="page"`. Prev/Next disable at the ends.
 */
export const Pagination: React.FC<PaginationProps> = ({
  page,
  totalPages,
  onChange,
  maxButtons = 7,
  className = '',
}) => {
  if (totalPages <= 1) return null;
  const items = pageWindow(page, totalPages, maxButtons);
  const btn = 'inline-flex h-8 min-w-8 items-center justify-center rounded-lg px-2 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-[#0b2b43]';

  return (
    <nav aria-label="Pagination" className={`flex items-center gap-1 ${className}`}>
      <button
        type="button"
        onClick={() => onChange(page - 1)}
        disabled={page <= 1}
        aria-label="Previous page"
        className={`${btn} text-[#475569] hover:bg-[#f1f5f9] disabled:cursor-not-allowed disabled:opacity-40`}
      >
        <ChevronLeft size={16} />
      </button>
      {items.map((it, i) =>
        it === 'ellipsis' ? (
          <span key={`e${i}`} aria-hidden="true" className="px-1 text-slate-500">…</span>
        ) : (
          <button
            key={it}
            type="button"
            onClick={() => onChange(it)}
            aria-current={it === page ? 'page' : undefined}
            aria-label={`Page ${it}`}
            className={`${btn} ${
              it === page ? 'bg-[#0b2b43] text-white' : 'text-[#475569] hover:bg-[#f1f5f9]'
            }`}
          >
            {it}
          </button>
        ),
      )}
      <button
        type="button"
        onClick={() => onChange(page + 1)}
        disabled={page >= totalPages}
        aria-label="Next page"
        className={`${btn} text-[#475569] hover:bg-[#f1f5f9] disabled:cursor-not-allowed disabled:opacity-40`}
      >
        <ChevronRight size={16} />
      </button>
    </nav>
  );
};
