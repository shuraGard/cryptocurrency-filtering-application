import { useMemo, useState } from 'react';
import Controls from './components/Controls.jsx';
import ProjectTable from './components/ProjectTable.jsx';
import { useProjects } from './hooks/useProjects.js';
import { formatTime } from './utils/format.js';
import { applyViewOptions } from './utils/projects.js';

const DEFAULT_VIEW = { query: '', maxFdvInput: '', sortBy: 'market_cap', sortDir: 'desc' };

export default function App() {
  const [previewListing, setPreviewListing] = useState('true');
  const [view, setView] = useState(DEFAULT_VIEW);
  const { status, data, error, reload } = useProjects(previewListing);

  const allItems = data?.items ?? [];
  const visible = useMemo(
    () => applyViewOptions(allItems, { ...view, maxFdv: view.maxFdvInput === '' ? null : Number(view.maxFdvInput) }),
    [allItems, view],
  );

  return (
    <main className="page">
      <header className="page-header">
        <h1>Crypto project screener</h1>
        <p>
          Projects from CoinGecko with market cap above 0, FDV under $100M, 24h volume over $50k, TVL over $50k
          and max supply equal to total supply. Narrow the list further below.
        </p>
      </header>

      <Controls
        options={view}
        onChange={setView}
        previewListing={previewListing}
        onPreviewChange={setPreviewListing}
        onRefresh={reload}
        loading={status === 'loading'}
      />

      {status === 'loading' && (
        <p className="status">
          Loading projects. The first load after the backend starts can take a minute or two, because CoinGecko
          limits how fast we can look coins up.
        </p>
      )}

      {status === 'error' && (
        <div className="status status--error" role="alert">
          <p>Could not load projects: {error}</p>
          <button type="button" className="button" onClick={reload}>
            Try again
          </button>
        </div>
      )}

      {status === 'ready' && (
        <>
          <p className="status">
            Showing {visible.length} of {allItems.length} projects. Data from {formatTime(data.meta.fetched_at)},{' '}
            {data.meta.scanned_coins} coins scanned, {data.meta.candidates} looked up in detail.
            {data.meta.candidates_truncated &&
              ' The candidate list hit the backend cap, so some smaller projects were not checked.'}
            {data.meta.detail_failures > 0 && ` ${data.meta.detail_failures} lookups failed and were skipped.`}
          </p>

          <ProjectTable
            projects={visible}
            sortBy={view.sortBy}
            emptyMessage={
              allItems.length === 0 ? (
                <EmptyBackendResult previewListing={previewListing} onShowAll={() => setPreviewListing('any')} />
              ) : (
                'No projects match your search or FDV filter.'
              )
            }
          />
        </>
      )}
    </main>
  );
}

function EmptyBackendResult({ previewListing, onShowAll }) {
  if (previewListing !== 'true') return 'No projects match the backend criteria right now.';
  return (
    <span>
      No projects match all criteria with preview listing required. CoinGecko preview listings usually have no
      market data yet, so this combination is often empty.{' '}
      <button type="button" className="link-button" onClick={onShowAll}>
        Show projects regardless of preview status
      </button>
    </span>
  );
}
