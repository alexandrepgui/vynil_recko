import { getAccessToken } from './AuthContext';
import type { Batch, BatchItem, CollectionResponse, DiscogsStatus, MediaType, SearchResponse, SyncStatus, UserProfile } from './types';

// ── Auth-aware fetch wrapper ────────────────────────────────────────────

function authFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers);
  const token = getAccessToken();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  return fetch(input, { ...init, headers });
}

// ── Search ──────────────────────────────────────────────────────────────

export async function searchByImage(file: File, mediaType: MediaType = 'vinyl', signal?: AbortSignal): Promise<SearchResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('media_type', mediaType);

  const resp = await authFetch('/api/search', {
    method: 'POST',
    body: formData,
    signal,
  });

  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new Error(body?.detail ?? `Search failed (${resp.status})`);
  }

  return resp.json();
}

export async function addToCollection(releaseId: number): Promise<void> {
  const resp = await authFetch('/api/collection', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ release_id: releaseId }),
  });

  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new Error(body?.detail ?? `Failed to add to collection (${resp.status})`);
  }
}

// ── Batch ─────────────────────────────────────────────────────────────────

export async function uploadBatch(
  file: File,
  mediaType: MediaType = 'vinyl',
): Promise<{ batch_id: string; total_images: number }> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('media_type', mediaType);

  const resp = await authFetch('/api/batch', { method: 'POST', body: formData });

  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new Error(body?.detail ?? `Batch upload failed (${resp.status})`);
  }

  return resp.json();
}

export async function getBatch(batchId: string): Promise<Batch> {
  const resp = await authFetch(`/api/batch/${batchId}`);
  if (!resp.ok) throw new Error(`Failed to fetch batch (${resp.status})`);
  return resp.json();
}

export async function getBatchItems(
  batchId: string,
  reviewStatus?: string,
): Promise<BatchItem[]> {
  const params = reviewStatus ? `?review_status=${reviewStatus}` : '';
  const resp = await authFetch(`/api/batch/${batchId}/items${params}`);
  if (!resp.ok) throw new Error(`Failed to fetch batch items (${resp.status})`);
  return resp.json();
}

export async function reviewItem(
  batchId: string,
  itemId: string,
  reviewStatus: 'accepted' | 'skipped' | 'wrong',
  acceptedReleaseId?: number,
): Promise<void> {
  const resp = await authFetch(`/api/batch/${batchId}/items/${itemId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      review_status: reviewStatus,
      accepted_release_id: acceptedReleaseId ?? null,
    }),
  });

  if (!resp.ok) throw new Error(`Failed to review item (${resp.status})`);
}

// ── Global review (across all batches + single searches) ─────────────────

export async function getAllReviewItems(
  reviewStatus?: string,
  status?: string,
): Promise<BatchItem[]> {
  const query = new URLSearchParams();
  if (reviewStatus) query.set('review_status', reviewStatus);
  if (status) query.set('status', status);
  const qs = query.toString();
  const resp = await authFetch(`/api/review/items${qs ? `?${qs}` : ''}`);
  if (!resp.ok) throw new Error(`Failed to fetch review items (${resp.status})`);
  return resp.json();
}

export async function reviewItemGlobal(
  itemId: string,
  reviewStatus: 'accepted' | 'skipped' | 'wrong',
  acceptedReleaseId?: number,
): Promise<void> {
  const resp = await authFetch(`/api/review/items/${itemId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      review_status: reviewStatus,
      accepted_release_id: acceptedReleaseId ?? null,
    }),
  });

  if (!resp.ok) throw new Error(`Failed to review item (${resp.status})`);
}

export async function undoReviewItem(itemId: string): Promise<void> {
  const resp = await authFetch(`/api/review/items/${itemId}/undo`, {
    method: 'POST',
  });

  if (!resp.ok) throw new Error(`Failed to undo review (${resp.status})`);
}

export async function retryItem(itemId: string): Promise<void> {
  const resp = await authFetch(`/api/review/items/${itemId}/retry`, {
    method: 'POST',
  });

  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new Error(body?.detail ?? `Failed to retry item (${resp.status})`);
  }
}

// ── Collection (browse) ──────────────────────────────────────────────────

export async function getCollection(
  page: number = 1,
  perPage: number = 50,
  sort: string = 'artist',
  sortOrder: string = 'asc',
  search: string = '',
): Promise<CollectionResponse> {
  const params = new URLSearchParams({
    page: String(page),
    per_page: String(perPage),
    sort,
    sort_order: sortOrder,
  });
  if (search.trim()) params.set('q', search.trim());
  const resp = await authFetch(`/api/collection?${params}`);
  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new Error(body?.detail ?? `Failed to fetch collection (${resp.status})`);
  }
  return resp.json();
}

export async function triggerCollectionSync(): Promise<{ message: string }> {
  const resp = await authFetch('/api/collection/sync', { method: 'POST' });
  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new Error(body?.detail ?? `Failed to trigger sync (${resp.status})`);
  }
  return resp.json();
}

export async function getCollectionSyncStatus(): Promise<SyncStatus> {
  const resp = await authFetch('/api/collection/sync');
  if (!resp.ok) throw new Error(`Failed to fetch sync status (${resp.status})`);
  return resp.json();
}

// ── Price ─────────────────────────────────────────────────────────────────

export async function getPrice(releaseId: number): Promise<{ lowest_price: number | null; num_for_sale: number; currency: string | null }> {
  const resp = await authFetch(`/api/price/${releaseId}`);
  if (!resp.ok) return { lowest_price: null, num_for_sale: 0, currency: null };
  return resp.json();
}

// ── Profile ──────────────────────────────────────────────────────────

export async function getProfile(): Promise<UserProfile> {
  const resp = await authFetch('/api/me');
  if (!resp.ok) throw new Error(`Failed to fetch profile (${resp.status})`);
  return resp.json();
}

// ── Discogs OAuth ────────────────────────────────────────────────────────

export async function getDiscogsStatus(): Promise<DiscogsStatus> {
  const resp = await authFetch('/api/discogs/status');
  if (!resp.ok) throw new Error(`Failed to fetch Discogs status (${resp.status})`);
  return resp.json();
}

export async function startDiscogsLogin(): Promise<string> {
  const resp = await authFetch('/api/discogs/login');
  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new Error(body?.detail ?? `Failed to start Discogs login (${resp.status})`);
  }
  const data = await resp.json();
  return data.authorize_url;
}

export async function discogsLogout(): Promise<void> {
  const resp = await authFetch('/api/discogs/logout', { method: 'POST' });
  if (!resp.ok) throw new Error(`Failed to disconnect Discogs (${resp.status})`);
}
