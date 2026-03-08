import { useCallback, useEffect, useRef, useState } from 'react';
import { getCollection, getCollectionSyncStatus, triggerCollectionSync } from '../api';
import type { CollectionItem, SyncStatus } from '../types';

const PAGE_SIZE = 50;

const SORT_OPTIONS = [
  { value: 'artist', label: 'Artist' },
  { value: 'title', label: 'Title' },
  { value: 'year', label: 'Year' },
  { value: 'added', label: 'Date Added' },
  { value: 'format', label: 'Format' },
];

export default function CollectionView() {
  const [items, setItems] = useState<CollectionItem[]>([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [sort, setSort] = useState('artist');
  const [sortOrder, setSortOrder] = useState('asc');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sync state
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [initialCheckDone, setInitialCheckDone] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval>>();
  const searchTimerRef = useRef<ReturnType<typeof setTimeout>>();

  // Debounced search value actually sent to the API
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Check sync status on mount to decide what to show
  useEffect(() => {
    getCollectionSyncStatus()
      .then((s) => {
        setSyncStatus(s);
        // If a sync is in progress, start polling
        if (s.status === 'syncing') startPolling();
      })
      .catch(() => setSyncStatus({ status: 'idle' }))
      .finally(() => setInitialCheckDone(true));
    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const hasSynced = syncStatus?.completed_at != null;
  const isSyncing = syncStatus?.status === 'syncing';

  // Fetch from local DB
  const fetchCollection = useCallback(
    async (p: number, s: string, so: string, q: string) => {
      setLoading(true);
      setError(null);
      try {
        const data = await getCollection(p, PAGE_SIZE, s, so, q);
        setItems(data.items);
        setPage(data.page);
        setPages(data.pages);
        setTotalItems(data.total_items);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load collection.');
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  // Load collection when ready and when params change
  useEffect(() => {
    if (!hasSynced || isSyncing) return;
    fetchCollection(page, sort, sortOrder, debouncedSearch);
  }, [hasSynced, isSyncing, page, sort, sortOrder, debouncedSearch, fetchCollection]);

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

  const handleSortChange = (newSort: string) => {
    setSort(newSort);
    setPage(1);
  };

  const toggleSortOrder = () => {
    setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    setPage(1);
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

  // Landing: never synced and not currently syncing
  if (!hasSynced && !isSyncing) {
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

  // Syncing progress
  if (isSyncing) {
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
        <button
          className="btn collection-resync"
          onClick={handleSync}
          disabled={isSyncing}
          title="Re-sync from Discogs"
        >
          Re-sync
        </button>
      </div>

      {error && <p className="error">{error}</p>}

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
          <div className="collection-grid">
            {items.map((item) => (
              <div key={`${item.release_id}-${item.instance_id}`} className="collection-card">
                {item.cover_image ? (
                  <img
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
    </div>
  );
}
