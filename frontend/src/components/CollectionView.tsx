import { useCallback, useEffect, useRef, useState } from 'react';
import { deleteCollectionItems, getCollection, getCollectionSyncStatus, getProfile, getPublicCollection, getSettings, triggerCollectionSync } from '../api';
import type { CollectionItem, SyncStatus } from '../types';
import ZoomableImage from './ZoomableImage';

const PAGE_SIZE_OPTIONS = [25, 50, 100, 150, 200, 250];
const PAGE_SIZE_KEY = 'groove-log-page-size';

function loadPageSize(): number {
  try {
    const stored = localStorage.getItem(PAGE_SIZE_KEY);
    if (stored) {
      const n = Number(stored);
      if (PAGE_SIZE_OPTIONS.includes(n)) return n;
    }
  } catch { /* ignore */ }
  return 50;
}

/**
 * Given `itemCount` items and a maximum number of columns that fit,
 * return the column count (>= 1) that minimises empty cells in the last row.
 * Prefer fewer empty cells; on ties, prefer more columns.
 */
function computeOptimalColumns(itemCount: number, maxCols: number): number {
  if (itemCount <= 0 || maxCols <= 0) return maxCols || 1;
  let best = maxCols;
  let bestEmpty = maxCols; // worst case
  for (let cols = maxCols; cols >= 1; cols--) {
    const remainder = itemCount % cols;
    const empty = remainder === 0 ? 0 : cols - remainder;
    if (empty < bestEmpty) {
      bestEmpty = empty;
      best = cols;
    }
    if (bestEmpty === 0) break;
  }
  return best;
}

const SORT_OPTIONS = [
  { value: 'artist', label: 'Artist' },
  { value: 'title', label: 'Title' },
  { value: 'year', label: 'Year' },
  { value: 'added', label: 'Date Added' },
  { value: 'format', label: 'Format' },
];

interface CollectionViewProps {
  readOnly?: boolean;
  username?: string;
}

export default function CollectionView({ readOnly = false, username }: CollectionViewProps) {
  const [items, setItems] = useState<CollectionItem[]>([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [sort, setSort] = useState('artist');
  const [sortOrder, setSortOrder] = useState('asc');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pageSize, setPageSize] = useState(loadPageSize);
  const [gridColumns, setGridColumns] = useState<number | null>(null);

  // Public collection owner info
  const [ownerName, setOwnerName] = useState<string | null>(null);

  // Selection state (only used when not readOnly)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteMessage, setDeleteMessage] = useState<string | null>(null);

  // Copy link state (only used in authenticated view)
  const [collectionPublic, setCollectionPublic] = useState(false);
  const [copySuccess, setCopySuccess] = useState(false);
  const [discogsUsername, setDiscogsUsername] = useState<string | null>(null);

  // Sync state
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [initialCheckDone, setInitialCheckDone] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval>>();
  const searchTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const gridRef = useRef<HTMLDivElement>(null);
  const resizeTimerRef = useRef<ReturnType<typeof setTimeout>>();

  // Debounced search value actually sent to the API
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Check sync status on mount to decide what to show
  useEffect(() => {
    if (readOnly && username) {
      // Public view: skip sync check, load directly
      setInitialCheckDone(true);
      return;
    }
    Promise.all([
      getCollectionSyncStatus().catch(() => ({ status: 'idle' }) as SyncStatus),
      getSettings().catch(() => ({ collection_public: false })),
      getProfile().catch(() => null),
    ]).then(([s, settings, profile]) => {
      setSyncStatus(s);
      if (s.status === 'syncing') startPolling();
      setCollectionPublic(settings.collection_public);
      if (profile) setDiscogsUsername(profile.discogs.username ?? null);
      setInitialCheckDone(true);
    });

    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [readOnly, username]);

  const hasSynced = readOnly ? true : syncStatus?.completed_at != null;
  const isSyncing = readOnly ? false : syncStatus?.status === 'syncing';

  // Fetch from local DB
  const fetchCollection = useCallback(
    async (p: number, ps: number, s: string, so: string, q: string) => {
      setLoading(true);
      setError(null);
      try {
        const data = readOnly && username
          ? await getPublicCollection(username, p, ps, s, so, q)
          : await getCollection(p, ps, s, so, q);
        setItems(data.items);
        setPage(data.page);
        setPages(data.pages);
        setTotalItems(data.total_items);
        if ('owner' in data) setOwnerName(data.owner.username);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load collection.');
      } finally {
        setLoading(false);
      }
    },
    [readOnly, username],
  );

  // Load collection when ready and when params change
  useEffect(() => {
    if (!hasSynced || isSyncing) return;
    fetchCollection(page, pageSize, sort, sortOrder, debouncedSearch);
  }, [hasSynced, isSyncing, page, pageSize, sort, sortOrder, debouncedSearch, fetchCollection]);

  // Adaptive grid: compute optimal columns based on container width and item count
  const itemCountRef = useRef(items.length);
  itemCountRef.current = items.length;

  const recalcColumns = useCallback(() => {
    const container = gridRef.current;
    if (!container || itemCountRef.current === 0) {
      setGridColumns(null);
      return;
    }
    const containerWidth = container.clientWidth;
    const gap = 16; // 1rem gap
    const preferredCardWidth = 180; // px
    const maxCols = Math.max(1, Math.floor((containerWidth + gap) / (preferredCardWidth + gap)));
    const optimal = computeOptimalColumns(itemCountRef.current, maxCols);
    setGridColumns(optimal);
  }, []);

  useEffect(() => {
    recalcColumns();
    const handleResize = () => {
      if (resizeTimerRef.current) clearTimeout(resizeTimerRef.current);
      resizeTimerRef.current = setTimeout(recalcColumns, 150);
    };
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      if (resizeTimerRef.current) clearTimeout(resizeTimerRef.current);
    };
  }, [recalcColumns]);

  // Recalculate columns when item count changes
  useEffect(() => {
    recalcColumns();
  }, [items.length, recalcColumns]);

  // Debounce search input
  useEffect(() => {
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    searchTimerRef.current = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => {
      if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    };
  }, [search]);

  // Polling helpers
  const startPolling = useCallback(() => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const s = await getCollectionSyncStatus();
        setSyncStatus(s);
        if (s.status !== 'syncing') stopPolling();
      } catch {
        // ignore transient errors
      }
    }, 2000);
  }, []);

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = undefined;
    }
  }

  const handleSync = async () => {
    setError(null);
    try {
      await triggerCollectionSync();
      setSyncStatus((prev) => ({ ...prev, status: 'syncing', items_synced: 0 } as SyncStatus));
      startPolling();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start sync.');
    }
  };

  const handlePageSizeChange = (newSize: number) => {
    setPageSize(newSize);
    setPage(1);
    try { localStorage.setItem(PAGE_SIZE_KEY, String(newSize)); } catch { /* ignore */ }
  };

  const handleSortChange = (newSort: string) => {
    setSort(newSort);
    setPage(1);
  };

  const toggleSortOrder = () => {
    setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    setPage(1);
  };

  // Clear selection when page/search/sort changes
  useEffect(() => {
    setSelectedIds(new Set());
  }, [page, pageSize, sort, sortOrder, debouncedSearch]);

  const toggleSelect = (instanceId: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(instanceId)) {
        next.delete(instanceId);
      } else {
        next.add(instanceId);
      }
      return next;
    });
  };

  const selectAllPage = () => {
    setSelectedIds(new Set(items.map((item) => item.instance_id)));
  };

  const deselectAll = () => {
    setSelectedIds(new Set());
  };

  const handleDeleteSelected = async () => {
    setDeleting(true);
    setDeleteMessage(null);
    try {
      const result = await deleteCollectionItems(Array.from(selectedIds));
      const msgs: string[] = [];
      if (result.deleted > 0) {
        msgs.push(`${result.deleted} record${result.deleted !== 1 ? 's' : ''} deleted.`);
      }
      if (result.errors.length > 0) {
        msgs.push(`${result.errors.length} failed.`);
      }
      setDeleteMessage(msgs.join(' '));
      setSelectedIds(new Set());
      setShowDeleteModal(false);
      // Refresh the current page
      fetchCollection(page, pageSize, sort, sortOrder, debouncedSearch);
    } catch (e) {
      setDeleteMessage(e instanceof Error ? e.message : 'Delete failed.');
      setShowDeleteModal(false);
    } finally {
      setDeleting(false);
    }
  };

  if (!initialCheckDone) {
    return (
      <div className="collection-view">
        <div className="loading">
          <div className="spinner" />
        </div>
      </div>
    );
  }

  const handleCopyLink = () => {
    if (!discogsUsername) return;
    const url = `${window.location.origin}/collection/${discogsUsername}`;
    navigator.clipboard.writeText(url).then(() => {
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2000);
    });
  };

  // Landing: never synced and not currently syncing (only for authenticated view)
  if (!readOnly && !hasSynced && !isSyncing) {
    return (
      <div className="collection-view">
        <div className="collection-landing">
          <p>Browse your Discogs vinyl collection.</p>
          <button className="btn btn-primary" onClick={handleSync}>
            Fetch my collection
          </button>
          {syncStatus?.status === 'error' && (
            <p className="error">{syncStatus.error || 'Sync failed. Please try again.'}</p>
          )}
          {error && <p className="error">{error}</p>}
        </div>
      </div>
    );
  }

  // Syncing progress (only for authenticated view)
  if (!readOnly && isSyncing) {
    const synced = syncStatus?.items_synced ?? 0;
    const total = syncStatus?.total_items ?? 0;
    return (
      <div className="collection-view">
        <div className="collection-syncing">
          <div className="spinner" />
          <p>
            Syncing collection...{' '}
            {total > 0 ? `${synced} / ${total} items` : `${synced} items`}
          </p>
          {total > 0 && (
            <div className="sync-progress-bar">
              <div
                className="sync-progress-fill"
                style={{ width: `${Math.round((synced / total) * 100)}%` }}
              />
            </div>
          )}
        </div>
      </div>
    );
  }

  // Collection view (data loaded from MongoDB)
  return (
    <div className="collection-view">
      {readOnly && ownerName && (
        <h2 className="public-collection-owner">{ownerName}'s Collection</h2>
      )}

      <div className="collection-controls">
        <input
          type="text"
          className="collection-search"
          placeholder="Search by title or artist..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="collection-sort">
          <select
            value={sort}
            onChange={(e) => handleSortChange(e.target.value)}
            className="collection-sort-select"
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <button className="btn collection-sort-order" onClick={toggleSortOrder}>
            {sortOrder === 'asc' ? '\u2191' : '\u2193'}
          </button>
        </div>
        <select
          className="collection-page-size-select"
          value={pageSize}
          onChange={(e) => handlePageSizeChange(Number(e.target.value))}
          title="Items per page"
        >
          {PAGE_SIZE_OPTIONS.map((n) => (
            <option key={n} value={n}>
              {n} / page
            </option>
          ))}
        </select>
        {!readOnly && (
          <button
            className="btn collection-resync"
            onClick={handleSync}
            disabled={isSyncing}
            title="Re-sync from Discogs"
          >
            Re-sync
          </button>
        )}
        {!readOnly && collectionPublic && discogsUsername && (
          <button
            className="btn btn-copy-link"
            onClick={handleCopyLink}
            title="Copy public collection link"
          >
            {copySuccess ? 'Copied!' : 'Copy link'}
          </button>
        )}
      </div>

      {error && <p className="error">{error}</p>}

      {!readOnly && deleteMessage && (
        <p className="collection-delete-message">{deleteMessage}</p>
      )}

      {!readOnly && selectedIds.size > 0 && (
        <div className="collection-selection-toolbar">
          <span className="collection-selection-count">
            {selectedIds.size} selected
          </span>
          <button className="btn btn-nav" onClick={selectAllPage}>
            Select All (page)
          </button>
          <button className="btn btn-nav" onClick={deselectAll}>
            Deselect All
          </button>
          <button
            className="btn btn-delete-selected"
            onClick={() => setShowDeleteModal(true)}
          >
            Delete Selected
          </button>
        </div>
      )}

      {loading && (
        <div className="loading">
          <div className="spinner" />
          <p>Loading collection...</p>
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <p className="no-results">
          {search ? 'No items match your search.' : 'Your collection is empty.'}
        </p>
      )}

      {!loading && items.length > 0 && (
        <>
          <div className="collection-info">
            {totalItems} item{totalItems !== 1 ? 's' : ''} in collection
          </div>
          <div
            className="collection-grid"
            ref={gridRef}
            style={gridColumns ? { gridTemplateColumns: `repeat(${gridColumns}, 1fr)` } : undefined}
          >
            {items.map((item) => (
              <div
                key={`${item.release_id}-${item.instance_id}`}
                className={`collection-card${!readOnly && selectedIds.has(item.instance_id) ? ' collection-card-selected' : ''}`}
              >
                {!readOnly && (
                  <label className="collection-card-checkbox">
                    <input
                      type="checkbox"
                      checked={selectedIds.has(item.instance_id)}
                      onChange={() => toggleSelect(item.instance_id)}
                    />
                  </label>
                )}
                {item.cover_image ? (
                  <ZoomableImage
                    src={item.cover_image}
                    alt={item.title}
                    className="collection-cover"
                    loading="lazy"
                  />
                ) : (
                  <div className="collection-cover collection-cover-placeholder" />
                )}
                <div className="collection-card-info">
                  <div className="collection-card-title">{item.title}</div>
                  <div className="collection-card-artist">{item.artist}</div>
                  <div className="collection-card-meta">
                    {item.year > 0 && <span>{item.year}</span>}
                    {item.format && <span>{item.format}</span>}
                    {item.genres.slice(0, 2).map((g) => (
                      <span key={g}>{g}</span>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {pages > 1 && (
            <div className="collection-pagination">
              <button
                className="btn btn-nav"
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                &lt; Prev
              </button>
              <span className="collection-page-info">
                Page {page} of {pages}
              </span>
              <button
                className="btn btn-nav"
                disabled={page >= pages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next &gt;
              </button>
            </div>
          )}
        </>
      )}

      {!readOnly && showDeleteModal && (
        <div className="delete-modal-overlay" onClick={() => !deleting && setShowDeleteModal(false)}>
          <div className="delete-modal" onClick={(e) => e.stopPropagation()}>
            <p className="delete-modal-warning">
              You are about to remove {selectedIds.size} record{selectedIds.size !== 1 ? 's' : ''} from
              your collection. This will also delete them from your Discogs account.
              This action cannot be undone.
            </p>
            <div className="delete-modal-actions">
              <button
                className="btn btn-nav"
                onClick={() => setShowDeleteModal(false)}
                disabled={deleting}
              >
                Cancel
              </button>
              <button
                className="btn btn-delete-confirm"
                onClick={handleDeleteSelected}
                disabled={deleting}
              >
                {deleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
