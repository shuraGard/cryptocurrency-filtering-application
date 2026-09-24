import { useCallback, useEffect, useState } from 'react';
import { fetchProjects } from '../api.js';

// Loads the backend list for a given preview_listing mode. Re-fetches when the
// mode changes or reload() is called; in-flight requests are aborted on change.
export function useProjects(previewListing) {
  const [state, setState] = useState({ status: 'loading', data: null, error: null });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setState((prev) => ({ ...prev, status: 'loading', error: null }));

    fetchProjects({ previewListing, signal: controller.signal })
      .then((data) => setState({ status: 'ready', data, error: null }))
      .catch((error) => {
        if (error.name === 'AbortError') return;
        setState({ status: 'error', data: null, error: error.message });
      });

    return () => controller.abort();
  }, [previewListing, reloadKey]);

  const reload = useCallback(() => setReloadKey((key) => key + 1), []);
  return { ...state, reload };
}
