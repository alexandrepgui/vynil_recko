import { getAccessToken } from './AuthContext';
import type { Batch, BatchItem, CollectionResponse, DiscogsStatus, MediaType, PublicCollectionResponse, SearchResponse, SyncStatus, UserProfile, UserSettings } from './types';

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
    throw new Error(body?.detail ?? 'Couldn\'t find any matches. Want to try again?');
  }

  return resp.json();
}

export class DuplicateError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'DuplicateError';
  }
}

export async function addToCollection(releaseId: number, force = false): Promise<void> {
  const resp = await authFetch('/api/collection', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ release_id: releaseId, force }),
  });

  if (resp.status === 409) {
    throw new DuplicateError('This release is already in your collection.');
  }

  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new Error(body?.detail ?? 'Couldn\'t add that to your collection. Try again?');
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
    throw new Error(body?.detail ?? 'Upload didn\'t work. Want to try again?');
  }

  return resp.json();
}

export async function getBatch(batchId: string): Promise<Batch> {
  const resp = await authFetch(`/api/batch/${batchId}`);
  if (!resp.ok) throw new Error('Couldn\'t load that batch. Try refreshing?');
  return resp.json();
}

export async function getBatchItems(
  batchId: string,
  reviewStatus?: string,
): Promise<BatchItem[]> {
  const params = reviewStatus ? `?review_status=${reviewStatus}` : '';
  const resp = await authFetch(`/api/batch/${batchId}/items${params}`);
  if (!resp.ok) throw new Error('Couldn\'t load the batch items. Try refreshing?');
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

  if (!resp.ok) throw new Error('Couldn\'t save that review. Try again?');
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
  if (!resp.ok) throw new Error('Couldn\'t load the review queue. Try refreshing?');
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

  if (!resp.ok) throw new Error('Couldn\'t save that review. Try again?');
}

export async function undoReviewItem(itemId: string): Promise<void> {
  const resp = await authFetch(`/api/review/items/${itemId}/undo`, {
    method: 'POST',
  });

  if (!resp.ok) throw new Error('Couldn\'t undo that review. Try again?');
}

export async function retryItem(itemId: string): Promise<void> {
  const resp = await authFetch(`/api/review/items/${itemId}/retry`, {
    method: 'POST',
  });

  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new Error(body?.detail ?? 'Couldn\'t retry that item. Try again in a moment?');
  }
}

// ── Collection (browse) ──────────────────────────────────────────────────

function buildCollectionParams(
  page: number, perPage: number, sort: string, sortOrder: string, search: string,
): URLSearchParams {
  const params = new URLSearchParams({
    page: String(page),
    per_page: String(perPage),
    sort,
    sort_order: sortOrder,
  });
  if (search.trim()) params.set('q', search.trim());
  return params;
}

export async function getCollection(
  page: number = 1,
  perPage: number = 50,
  sort: string = 'artist',
  sortOrder: string = 'asc',
  search: string = '',
): Promise<CollectionResponse> {
  const params = buildCollectionParams(page, perPage, sort, sortOrder, search);
  const resp = await authFetch(`/api/collection?${params}`);
  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new Error(body?.detail ?? 'Couldn\'t load your collection. Try refreshing?');
  }
  return resp.json();
}

export async function triggerCollectionSync(): Promise<{ message: string }> {
  const resp = await authFetch('/api/collection/sync', { method: 'POST' });
  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new Error(body?.detail ?? 'Couldn\'t start the sync. Try again in a moment?');
  }
  return resp.json();
}

export async function deleteCollectionItems(
  instanceIds: number[],
): Promise<{ deleted: number; errors: { instance_id: number; error: string }[] }> {
  const resp = await authFetch('/api/collection', {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ instance_ids: instanceIds }),
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new Error(body?.detail ?? 'Couldn\'t delete those items. Try again?');
  }
  return resp.json();
}

export async function previewMasterCover(instanceId: number): Promise<{ cover_url: string }> {
  const resp = await authFetch(`/api/collection/${instanceId}/cover/master`);
  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new Error(body?.detail ?? 'Couldn\'t fetch master cover. Try again?');
  }
  return resp.json();
}

export async function useMasterCover(instanceId: number): Promise<{ custom_cover_image: string }> {
  const resp = await authFetch(`/api/collection/${instanceId}/cover/master`, { method: 'POST' });
  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new Error(body?.detail ?? 'Couldn\'t fetch master cover. Try again?');
  }
  return resp.json();
}

export async function setCustomCover(instanceId: number, url: string): Promise<{ custom_cover_image: string }> {
  const resp = await authFetch(`/api/collection/${instanceId}/cover`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new Error(body?.detail ?? 'Couldn\'t set cover. Try again?');
  }
  return resp.json();
}

export async function resetCover(instanceId: number): Promise<void> {
  const resp = await authFetch(`/api/collection/${instanceId}/cover`, { method: 'DELETE' });
  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new Error(body?.detail ?? 'Couldn\'t reset cover. Try again?');
  }
}

export async function getCollectionSyncStatus(): Promise<SyncStatus> {
  const resp = await authFetch('/api/collection/sync');
  if (!resp.ok) throw new Error('Couldn\'t check the sync status. Try refreshing?');
  return resp.json();
}

// ── Export ───────────────────────────────────────────────────────────────

export type ExportFormat = 'csv' | 'xlsx' | 'pdf';

export async function exportCollection(
  format: ExportFormat,
  sort: string = 'artist',
  sortOrder: string = 'asc',
  search: string = '',
  signal?: AbortSignal,
): Promise<void> {
  const params = new URLSearchParams({ format, sort, sort_order: sortOrder });
  if (search.trim()) params.set('q', search.trim());

  const resp = await authFetch(`/api/collection/export?${params}`, { signal });
  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new Error(body?.detail ?? 'Export failed. Try again?');
  }

  const blob = await resp.blob();
  const disposition = resp.headers.get('Content-Disposition') ?? '';
  const filenameMatch = disposition.match(/filename="(.+)"/);
  const filename = filenameMatch?.[1] ?? `groove-log-collection.${format}`;

  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ── Public collection ────────────────────────────────────────────────────

export async function getPublicCollection(
  username: string,
  page: number = 1,
  perPage: number = 50,
  sort: string = 'artist',
  sortOrder: string = 'asc',
  search: string = '',
): Promise<PublicCollectionResponse> {
  const params = buildCollectionParams(page, perPage, sort, sortOrder, search);
  const resp = await fetch(`/api/collection/${encodeURIComponent(username)}?${params}`);
  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new Error(body?.detail ?? 'Couldn\'t load this collection. Try refreshing?');
  }
  return resp.json();
}

// ── Settings ─────────────────────────────────────────────────────────────

export async function getSettings(): Promise<UserSettings> {
  const resp = await authFetch('/api/me/settings');
  if (!resp.ok) throw new Error('Couldn\'t load your settings. Try refreshing?');
  return resp.json();
}

export async function updateSettings(settings: Partial<UserSettings>): Promise<UserSettings> {
  const resp = await authFetch('/api/me/settings', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  });
  if (!resp.ok) throw new Error('Couldn\'t save your settings. Try again?');
  return resp.json();
}

// ── Price ─────────────────────────────────────────────────────────────────

export async function getPrice(releaseId: number): Promise<{ lowest_price: number | null; num_for_sale: number; currency: string | null }> {
  const resp = await authFetch(`/api/price/${releaseId}`);
  if (!resp.ok) throw new Error('Price unavailable');
  return resp.json();
}

// ── Profile ──────────────────────────────────────────────────────────

export async function getProfile(): Promise<UserProfile> {
  const resp = await authFetch('/api/me');
  if (!resp.ok) throw new Error('Couldn\'t load your profile. Try refreshing?');
  return resp.json();
}

// ── Discogs OAuth ────────────────────────────────────────────────────────

export async function getDiscogsStatus(): Promise<DiscogsStatus> {
  const resp = await authFetch('/api/discogs/status');
  if (!resp.ok) throw new Error('Couldn\'t reach Discogs. Try again?');
  return resp.json();
}

export async function startDiscogsLogin(): Promise<string> {
  const resp = await authFetch('/api/discogs/login');
  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new Error(body?.detail ?? 'Couldn\'t connect to Discogs. Try again in a moment?');
  }
  const data = await resp.json();
  return data.authorize_url;
}

export async function discogsLogout(): Promise<void> {
  const resp = await authFetch('/api/discogs/logout', { method: 'POST' });
  if (!resp.ok) throw new Error('Couldn\'t disconnect from Discogs. Try again?');
}

// ── Discogs URL helpers ────────────────────────────────────────────────────

export function getDiscogsReleaseUrl(releaseId: number): string {
  return `https://www.discogs.com/release/${releaseId}`;
}

export function getDiscogsMarketplaceUrl(releaseId: number): string {
  return `https://www.discogs.com/sell/list?release_id=${releaseId}`;
}
