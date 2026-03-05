import type { Batch, BatchItem, SearchResponse } from './types';

export async function searchByImage(file: File): Promise<SearchResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const resp = await fetch('/api/search', {
    method: 'POST',
    body: formData,
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
): Promise<{ batch_id: string; total_images: number }> {
  const formData = new FormData();
  formData.append('file', file);

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
