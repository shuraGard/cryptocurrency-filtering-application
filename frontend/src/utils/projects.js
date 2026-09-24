// Client-side refinement of the backend list: search, extra FDV cap, sorting.
// Kept as a pure function so it is easy to reason about and test.

export const SORT_FIELDS = [
  { value: 'market_cap', label: 'Market cap' },
  { value: 'total_volume', label: '24h volume' },
];

export function applyViewOptions(items, { query, maxFdv, sortBy, sortDir }) {
  const needle = query.trim().toLowerCase();
  let result = items;

  if (needle) {
    result = result.filter(
      (p) => p.name.toLowerCase().includes(needle) || p.symbol.toLowerCase().includes(needle),
    );
  }

  if (Number.isFinite(maxFdv)) {
    result = result.filter((p) => p.fully_diluted_valuation != null && p.fully_diluted_valuation < maxFdv);
  }

  const direction = sortDir === 'asc' ? 1 : -1;
  return [...result].sort((a, b) => ((a[sortBy] ?? -Infinity) - (b[sortBy] ?? -Infinity)) * direction);
}
