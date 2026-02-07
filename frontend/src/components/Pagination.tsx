interface PaginationProps {
  page: number;
  pages: number;
  onPageChange: (page: number) => void;
}

export default function Pagination({ page, pages, onPageChange }: PaginationProps) {
  if (pages <= 1) return null;

  const range = (start: number, end: number) =>
    Array.from({ length: end - start + 1 }, (_, i) => start + i);

  let visiblePages: (number | "...")[] = [];
  if (pages <= 7) {
    visiblePages = range(1, pages);
  } else {
    if (page <= 3) {
      visiblePages = [...range(1, 4), "...", pages];
    } else if (page >= pages - 2) {
      visiblePages = [1, "...", ...range(pages - 3, pages)];
    } else {
      visiblePages = [1, "...", page - 1, page, page + 1, "...", pages];
    }
  }

  return (
    <nav className="flex items-center justify-center gap-1 mt-6">
      <button
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1}
        className="btn-secondary px-3 py-1.5 text-xs disabled:opacity-40"
      >
        Prev
      </button>
      {visiblePages.map((p, i) =>
        p === "..." ? (
          <span key={`dots-${i}`} className="px-2 text-gray-400 text-sm">
            ...
          </span>
        ) : (
          <button
            key={p}
            onClick={() => onPageChange(p as number)}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
              p === page
                ? "bg-brand-600 text-white"
                : "bg-white text-gray-700 border border-gray-300 hover:bg-gray-50"
            }`}
          >
            {p}
          </button>
        )
      )}
      <button
        onClick={() => onPageChange(page + 1)}
        disabled={page >= pages}
        className="btn-secondary px-3 py-1.5 text-xs disabled:opacity-40"
      >
        Next
      </button>
    </nav>
  );
}
