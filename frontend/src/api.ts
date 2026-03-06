import type { AuthStatus, Batch, BatchItem, MediaType, SearchResponse } from './types';

export async function searchByImage(file: File, mediaType: MediaType = 'vinyl', signal?: AbortSignal): Promise<SearchResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('media_type', mediaType);

  const resp = await fetch('/api/search', {
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
  const resp = await fetch('/api/collection', {
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

  const resp = await fetch('/api/batch', { method: 'POST', body: formData });

  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new Error(body?.detail ?? `Batch upload failed (${resp.status})`);
  }

  return resp.json();
}

export async function getBatch(batchId: string): Promise<Batch> {
  const resp = await fetch(`/api/batch/${batchId}`);
  if (!resp.ok) throw new Error(`Failed to fetch batch (${resp.status})`);
  return resp.json();
}

export async function getBatchItems(
  batchId: string,
  reviewStatus?: string,
): Promise<BatchItem[]> {
  const params = reviewStatus ? `?review_status=${reviewStatus}` : '';
  const resp = await fetch(`/api/batch/${batchId}/items${params}`);
  if (!resp.ok) throw new Error(`Failed to fetch batch items (${resp.status})`);
  return resp.json();
}

export async function reviewItem(
  batchId: string,
  itemId: string,
  reviewStatus: 'accepted' | 'skipped',
  acceptedReleaseId?: number,
): Promise<void> {
  const resp = await fetch(`/api/batch/${batchId}/items/${itemId}`, {
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
): Promise<BatchItem[]> {
  const params = reviewStatus ? `?review_status=${reviewStatus}` : '';
  const resp = await fetch(`/api/review/items${params}`);
  if (!resp.ok) throw new Error(`Failed to fetch review items (${resp.status})`);
  return resp.json();
}

export async function reviewItemGlobal(
  itemId: string,
  reviewStatus: 'accepted' | 'skipped',
  acceptedReleaseId?: number,
): Promise<void> {
  const resp = await fetch(`/api/review/items/${itemId}`, {
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
  const resp = await fetch(`/api/review/items/${itemId}/undo`, {
    method: 'POST',
  });

  if (!resp.ok) throw new Error(`Failed to undo review (${resp.status})`);
}

// ── Price ─────────────────────────────────────────────────────────────────

export async function getPrice(releaseId: number): Promise<{ lowest_price: number | null; num_for_sale: number }> {
  const resp = await fetch(`/api/price/${releaseId}`);
  if (!resp.ok) return { lowest_price: null, num_for_sale: 0 };
  return resp.json();
}

// ── Auth ──────────────────────────────────────────────────────────────────

export async function getAuthStatus(): Promise<AuthStatus> {
  const resp = await fetch('/api/auth/status');
  if (!resp.ok) throw new Error(`Failed to fetch auth status (${resp.status})`);
  return resp.json();
}

export async function startOAuthLogin(): Promise<string> {
  const resp = await fetch('/api/auth/login');
  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    throw new Error(body?.detail ?? `Failed to start login (${resp.status})`);
  }
  const data = await resp.json();
  return data.authorize_url;
}

export async function logout(): Promise<void> {
  const resp = await fetch('/api/auth/logout', { method: 'POST' });
  if (!resp.ok) throw new Error(`Failed to logout (${resp.status})`);
}
