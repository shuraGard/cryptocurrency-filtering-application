// The only place the frontend talks to the network. Everything goes through our
// backend; the browser never calls CoinGecko directly.

const API_BASE = import.meta.env.VITE_API_BASE || '';

export async function fetchProjects({ previewListing = 'true', signal } = {}) {
  const params = new URLSearchParams({ preview_listing: previewListing });
  const response = await fetch(`${API_BASE}/api/projects?${params}`, { signal });

  if (!response.ok) {
    let message = `Backend returned HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (body?.detail) message = body.detail;
    } catch {
      // body was not JSON; keep the generic message
    }
    throw new Error(message);
  }
  return response.json();
}
