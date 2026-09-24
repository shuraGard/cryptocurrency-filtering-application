import { SORT_FIELDS } from '../utils/projects.js';

export default function Controls({ options, onChange, previewListing, onPreviewChange, onRefresh, loading }) {
  const set = (patch) => onChange({ ...options, ...patch });

  return (
    <div className="controls">
      <label className="control control--grow">
        <span>Search</span>
        <input
          type="search"
          placeholder="Name or symbol, e.g. eth"
          value={options.query}
          onChange={(e) => set({ query: e.target.value })}
        />
      </label>

      <label className="control">
        <span>Max FDV (USD)</span>
        <input
          type="number"
          min="0"
          step="1000000"
          placeholder="e.g. 25000000"
          value={options.maxFdvInput}
          onChange={(e) => set({ maxFdvInput: e.target.value })}
        />
      </label>

      <label className="control">
        <span>Sort by</span>
        <select value={options.sortBy} onChange={(e) => set({ sortBy: e.target.value })}>
          {SORT_FIELDS.map((field) => (
            <option key={field.value} value={field.value}>
              {field.label}
            </option>
          ))}
        </select>
      </label>

      <button
        type="button"
        className="button"
        onClick={() => set({ sortDir: options.sortDir === 'desc' ? 'asc' : 'desc' })}
        aria-label={`Sort direction: ${options.sortDir === 'desc' ? 'descending' : 'ascending'}`}
      >
        {options.sortDir === 'desc' ? 'High to low' : 'Low to high'}
      </button>

      <label className="control">
        <span>Preview listing</span>
        <select value={previewListing} onChange={(e) => onPreviewChange(e.target.value)}>
          <option value="true">Required (task spec)</option>
          <option value="false">Excluded</option>
          <option value="any">Any</option>
        </select>
      </label>

      <button type="button" className="button" onClick={onRefresh} disabled={loading}>
        {loading ? 'Loading…' : 'Refresh'}
      </button>
    </div>
  );
}
