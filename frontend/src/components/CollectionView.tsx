import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { deleteCollectionItems, getCollection, getCollectionSyncStatus, getDiscogsMarketplaceUrl, getDiscogsReleaseUrl, getProfile, getPublicCollection, getSettings, previewMasterCover, resetCover, setCustomCover, triggerCollectionSync, useMasterCover } from '../api';
import { supabase } from '../supabaseClient';
import { useAuth } from '../AuthContext';
import type { CollectionItem, SyncStatus } from '../types';
import { useToast } from './Toast';
import { createPortal } from 'react-dom';

const PAGE_SIZE_OPTIONS = [25, 50, 100, 150, 200, 250];
const PAGE_SIZE_KEY = 'groove-log-page-size';
const GROUP_KEY = 'groove-log-group';

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

function loadGroup(): string {
  try {
    const stored = localStorage.getItem(GROUP_KEY);
    if (stored && ['artist', 'format', 'none'].includes(stored)) {
      return stored;
    }
  } catch { /* ignore */ }
  return 'none';
}

const GROUP_OPTIONS = [
  { value: 'none', label: 'No Grouping' },
  { value: 'artist', label: 'Artist' },
  { value: 'format', label: 'Media Type' },
];

interface CollectionGroup {
  name: string;
  count: number;
  items: CollectionItem[];
}

const SORT_OPTIONS = [
  { value: 'artist', label: 'Artist' },
  { value: 'title', label: 'Title' },
  { value: 'year', label: 'Year' },
  { value: 'added', label: 'Date Added' },
  { value: 'format', label: 'Format' },
];

function getDisplayCover(item: CollectionItem): string | null {
  return item.custom_cover_image || item.cover_image;
}

interface CollectionViewProps {
  username: string;
}

export default function CollectionView({ username }: CollectionViewProps) {
  const { user } = useAuth();
  const [isOwner, setIsOwner] = useState(false);
  const [allItems, setAllItems] = useState<CollectionItem[]>([]);
  const [items, setItems] = useState<CollectionItem[]>([]);
  // Store current page's groups for rendering (avoids re-grouping on each render)
  const [currentGroups, setCurrentGroups] = useState<CollectionGroup[]>([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [sort, setSort] = useState('artist');
  const [sortOrder, setSortOrder] = useState('asc');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [skeletonPhase, setSkeletonPhase] = useState<'hidden' | 'visible' | 'fading'>('hidden');
  const [error, setError] = useState<string | null>(null);
  const [pageSize, setPageSize] = useState(loadPageSize);
  const [group, setGroup] = useState(loadGroup);

  // Skeleton fade-out: show skeleton while loading, then fade it out
  useEffect(() => {
    if (loading) {
      setSkeletonPhase('visible');
    } else if (skeletonPhase === 'visible') {
      setSkeletonPhase('fading');
    }
  }, [loading, skeletonPhase]);

  useEffect(() => {
    if (skeletonPhase === 'fading') {
      const timer = setTimeout(() => setSkeletonPhase('hidden'), 300);
      return () => clearTimeout(timer);
    }
  }, [skeletonPhase]);

  // Public collection owner info
  const [ownerName, setOwnerName] = useState<string | null>(null);
  const [ownerAvatar, setOwnerAvatar] = useState<string | null>(null);

  // Selection state (only used when isOwner)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Context menu state
  const [showContextMenu, setShowContextMenu] = useState(false);
  const [contextItem, setContextItem] = useState<CollectionItem | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Dialog view state: detail view or change cover view
  const [dialogView, setDialogView] = useState<'detail' | 'changeCover'>('detail');
  const [coverLoading, setCoverLoading] = useState(false);
  const [coverUploading, setCoverUploading] = useState(false);
  const [masterCoverPreview, setMasterCoverPreview] = useState<string | null>(null);
  const coverFileRef = useRef<HTMLInputElement>(null);

  // Copy link state (only used in authenticated view)
  const [collectionPublic, setCollectionPublic] = useState(false);
  const [discogsUsername, setDiscogsUsername] = useState<string | null>(null);

  const { showToast } = useToast();

  // Sync state
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [initialCheckDone, setInitialCheckDone] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval>>();
  const searchTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const groupTimerRef = useRef<ReturnType<typeof setTimeout>>();

  // Debounced search value actually sent to the API
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Check sync status on mount to decide what to show
  useEffect(() => {
    if (!user) {
      // Not authenticated: public view, skip sync check
      setIsOwner(false);
      setInitialCheckDone(true);
      return;
    }
    // Authenticated: fetch profile to determine ownership
    Promise.all([
      getCollectionSyncStatus().catch(() => ({ status: 'idle' }) as SyncStatus),
      getSettings().catch(() => ({ collection_public: false })),
      getProfile().catch(() => null),
    ]).then(([s, settings, profile]) => {
      const ownerUsername = profile?.discogs.username ?? null;
      setDiscogsUsername(ownerUsername);
      setIsOwner(ownerUsername != null && ownerUsername === username);
      setSyncStatus(s);
      if (s.status === 'syncing') startPolling();
      setCollectionPublic(settings.collection_public);
    }).catch((err) => {
      console.warn('Initial collection load failed:', err);
    }).finally(() => {
      setInitialCheckDone(true);
    });

    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, username]);

  const hasSynced = !isOwner ? true : syncStatus?.completed_at != null;
  const isSyncing = !isOwner ? false : syncStatus?.status === 'syncing';

  // Grouping: sort items into groups by the specified field
  const getGroupKey = useCallback((item: CollectionItem, groupBy: string): string => {
    switch (groupBy) {
      case 'artist':
        return item.artist || 'Unknown Artist';
      case 'format':
        return item.format || 'Unknown Format';
      default:
        return 'none';
    }
  }, []);

  const groupItems = useCallback((itemsToGroup: CollectionItem[], groupBy: string): CollectionGroup[] => {
    if (groupBy === 'none') return [];

    const groups = new Map<string, CollectionItem[]>();
    for (const item of itemsToGroup) {
      const key = getGroupKey(item, groupBy);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(item);
    }

    return Array.from(groups.entries())
      .map(([name, items]) => ({ name, count: items.length, items }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [getGroupKey]);

  // Get paginated groups respecting group boundaries
  const getPaginatedGroups = useCallback((groups: CollectionGroup[], pageNum: number, itemsPerPage: number): CollectionGroup[] => {
    if (groups.length === 0) return [];

    let currentPage = 1;
    let currentCount = 0;
    const pageGroups: CollectionGroup[] = [];

    for (const group of groups) {
      // Add the entire group to current page
      pageGroups.push(group);
      currentCount += group.count;

      // Check if we've reached or exceeded the page size
      // When that happens, if this is NOT the target page, clear and move on
      if (currentCount >= itemsPerPage && currentPage < pageNum) {
        pageGroups.length = 0;
        currentCount = 0;
        currentPage++;
      }

      // If we've reached the target page, stop here
      if (currentPage === pageNum && currentCount >= itemsPerPage) {
        break;
      }
    }

    return pageGroups;
  }, []);

  // Calculate total pages for grouped view
  const calculateTotalPages = useCallback((groups: CollectionGroup[], itemsPerPage: number): number => {
    if (groups.length === 0) return 1;
    let currentPage = 1;
    let currentCount = 0;

    for (const group of groups) {
      currentCount += group.count;
      if (currentCount >= itemsPerPage) {
        currentPage++;
        currentCount = 0;
      }
    }

    return currentPage;
  }, []);

  // Fetch from local DB
  const fetchCollection = useCallback(
    async (p: number, ps: number, s: string, so: string, q: string, groupBy: string) => {
      setLoading(true);
      setError(null);
      try {
        // When grouping is enabled, fetch all items (up to max limit)
        // Note: For collections larger than 250 items, server-side grouping would be needed
        const fetchPage = groupBy !== 'none' ? 1 : p;
        const fetchPerPage = groupBy !== 'none' ? 250 : ps;

        const data = !isOwner
          ? await getPublicCollection(username, fetchPage, fetchPerPage, s, so, q)
          : await getCollection(fetchPage, fetchPerPage, s, so, q);

        setAllItems(data.items);
        setPage(fetchPage);

        if (groupBy !== 'none') {
          // Compute groups and page groups client-side
          const groups = groupItems(data.items, groupBy);
          const pageGroups = getPaginatedGroups(groups, 1, ps);
          setCurrentGroups(pageGroups);
          // Calculate total pages based on grouping
          const totalPages = calculateTotalPages(groups, ps);
          setPages(totalPages);
          setTotalItems(data.total_items);
        } else {
          setCurrentGroups([]);
          setItems(data.items);
          setPage(data.page);
          setPages(data.pages);
          setTotalItems(data.total_items);
        }
        if ('owner' in data) {
          setOwnerName(data.owner.username);
          setOwnerAvatar(data.owner.avatar_url ?? null);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Couldn\'t load the collection. Try refreshing?');
      } finally {
        setLoading(false);
      }
    },
    [isOwner, username, groupItems, getPaginatedGroups, calculateTotalPages],
  );

  // Load collection when ready and when params change
  useEffect(() => {
    if (!hasSynced || isSyncing) return;
    fetchCollection(page, pageSize, sort, sortOrder, debouncedSearch, group);
  }, [hasSynced, isSyncing, page, pageSize, sort, sortOrder, debouncedSearch, group, fetchCollection]);

  // Update page groups when page or pageSize changes in grouped mode
  useEffect(() => {
    if (group !== 'none' && allItems.length > 0) {
      const groups = groupItems(allItems, group);
      const pageGroups = getPaginatedGroups(groups, page, pageSize);
      setCurrentGroups(pageGroups);
      // Calculate total pages based on grouping
      const totalPages = calculateTotalPages(groups, pageSize);
      setPages(totalPages);
    } else if (group === 'none') {
      setCurrentGroups([]);
      // Items are already set by fetchCollection
    }
  }, [page, pageSize, group, allItems, groupItems, getPaginatedGroups, calculateTotalPages]);


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
      setError(e instanceof Error ? e.message : 'Couldn\'t start the sync. Try again?');
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

  const handleGroupChange = (newGroup: string) => {
    // Debounce group changes to avoid rapid re-fetches
    if (groupTimerRef.current) clearTimeout(groupTimerRef.current);
    groupTimerRef.current = setTimeout(() => {
      setGroup(newGroup);
      setPage(1);
      try { localStorage.setItem(GROUP_KEY, newGroup); } catch { /* ignore */ }
    }, 150);
  };

  // Clear selection when page/search/sort/group changes
  useEffect(() => {
    setSelectedIds(new Set());
  }, [page, pageSize, sort, sortOrder, debouncedSearch, group]);

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
    try {
      const result = await deleteCollectionItems(Array.from(selectedIds));
      if (result.deleted > 0) {
        showToast(`Deleted ${result.deleted} record${result.deleted !== 1 ? 's' : ''}`);
      }
      if (result.errors.length > 0) {
        showToast(`${result.errors.length} failed to delete`, 'error');
      }
      setSelectedIds(new Set());
      setShowDeleteModal(false);
      // Refresh the current page
      fetchCollection(page, pageSize, sort, sortOrder, debouncedSearch, group);
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Delete failed.', 'error');
      setShowDeleteModal(false);
    } finally {
      setDeleting(false);
    }
  };

  // Close context menu on Escape
  useEffect(() => {
    if (!showContextMenu) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setShowContextMenu(false);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [showContextMenu]);

  // Helper: update a single item's cover in local state
  const updateItemCover = (instanceId: number, customCover: string | null) => {
    const patch = (list: CollectionItem[]) =>
      list.map((it) => it.instance_id === instanceId ? { ...it, custom_cover_image: customCover } : it);
    setItems(patch);
    setAllItems(patch);
    setContextItem((prev) => prev && prev.instance_id === instanceId ? { ...prev, custom_cover_image: customCover } : prev);
  };

  // Context menu handlers
  const handleCardClick = (item: CollectionItem) => {
    setContextItem(item);
    setDialogView('detail');
    setMasterCoverPreview(null);
    setShowContextMenu(true);
  };

  const handleViewOnDiscogs = () => {
    if (contextItem) {
      window.open(getDiscogsReleaseUrl(contextItem.release_id), '_blank');
    }
    setShowContextMenu(false);
  };

  const handleViewPricing = () => {
    if (contextItem) {
      window.open(getDiscogsMarketplaceUrl(contextItem.release_id), '_blank');
    }
    setShowContextMenu(false);
  };

  const handleDeleteFromCollection = () => {
    setShowContextMenu(false);
    setShowDeleteConfirm(true);
  };

  const handleDeleteConfirm = async () => {
    if (!contextItem) return;
    setDeleting(true);
    try {
      const result = await deleteCollectionItems([contextItem.instance_id]);
      if (result.deleted > 0) {
        showToast(`Deleted "${contextItem.title}"`);
      }
      setShowDeleteConfirm(false);
      // Refresh the current page
      fetchCollection(page, pageSize, sort, sortOrder, debouncedSearch, group);
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Delete failed.', 'error');
    } finally {
      setDeleting(false);
    }
  };

  const handleFetchMasterCover = async () => {
    if (!contextItem) return;
    setCoverLoading(true);
    try {
      const { cover_url } = await previewMasterCover(contextItem.instance_id);
      setMasterCoverPreview(cover_url);
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Failed to fetch master cover.', 'error');
    } finally {
      setCoverLoading(false);
    }
  };

  const handleConfirmMasterCover = async () => {
    if (!contextItem) return;
    setCoverLoading(true);
    try {
      const { custom_cover_image } = await useMasterCover(contextItem.instance_id);
      updateItemCover(contextItem.instance_id, custom_cover_image);
      setMasterCoverPreview(null);
      showToast('Cover updated');
      setDialogView('detail');
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Failed to set master cover.', 'error');
    } finally {
      setCoverLoading(false);
    }
  };

  const handleCoverUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !contextItem || !user) return;

    if (file.size > 5 * 1024 * 1024) {
      showToast('File must be under 5 MB.', 'error');
      return;
    }

    setCoverUploading(true);
    try {
      const path = `${user.id}/${contextItem.instance_id}.jpg`;
      const { error: uploadError } = await supabase.storage
        .from('covers')
        .upload(path, file, { upsert: true, contentType: file.type });
      if (uploadError) throw uploadError;

      const { data: { publicUrl } } = supabase.storage
        .from('covers')
        .getPublicUrl(path);

      const coverUrl = `${publicUrl}?t=${Date.now()}`;
      await setCustomCover(contextItem.instance_id, coverUrl);
      updateItemCover(contextItem.instance_id, coverUrl);
      showToast('Cover updated');
      setDialogView('detail');
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Upload failed.', 'error');
    } finally {
      setCoverUploading(false);
      if (coverFileRef.current) coverFileRef.current.value = '';
    }
  };

  const handleResetCover = async () => {
    if (!contextItem) return;
    setCoverLoading(true);
    try {
      await resetCover(contextItem.instance_id);
      updateItemCover(contextItem.instance_id, null);
      showToast('Cover reset to default');
      setDialogView('detail');
    } catch (e) {
      showToast(e instanceof Error ? e.message : 'Failed to reset cover.', 'error');
    } finally {
      setCoverLoading(false);
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
    navigator.clipboard.writeText(url).then(
      () => showToast('Link copied'),
      () => showToast("Couldn't copy link", 'error'),
    );
  };

  // Landing: never synced and not currently syncing (only for owner view)
  if (isOwner && !hasSynced && !isSyncing) {
    return (
      <div className="collection-view">
        <div className="collection-landing">
          <p>Browse your Discogs vinyl collection.</p>
          <button className="btn btn-primary" onClick={handleSync}>
            Fetch my collection
          </button>
          {syncStatus?.status === 'error' && (
            <p className="error">{syncStatus.error || 'Sync didn\'t work. Want to try again?'}</p>
          )}
          {error && (
            <p className="error">
              {error.toLowerCase().includes('not connected')
                ? <>Discogs account not connected. <Link to="/profile">Connect it in your profile</Link>.</>
                : error}
            </p>
          )}
        </div>
      </div>
    );
  }

  // Syncing progress (only for owner view)
  if (isOwner && isSyncing) {
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
      {!isOwner && ownerName && (
        <div className="public-collection-header">
          {ownerAvatar && (
            <img src={ownerAvatar} alt="" className="public-collection-avatar" />
          )}
          <h2 className="public-collection-owner"><span className="public-collection-username">{ownerName}</span>'s collection</h2>
        </div>
      )}

      <div className="collection-controls">
        <div className="collection-search-row">
          <input
            type="text"
            className="collection-search"
            placeholder="Search by title or artist..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="collection-filters-row">
          <span className="filter-label">Sort:</span>
          <div className="collection-sort">
            <select
              value={sort}
              onChange={(e) => handleSortChange(e.target.value)}
              className="collection-sort-select"
              disabled={group !== 'none'}
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <button
              className="btn collection-sort-order"
              onClick={toggleSortOrder}
              disabled={group !== 'none'}
              title={group !== 'none' ? 'Sorting disabled when grouped' : 'Toggle sort order'}
            >
              {sortOrder === 'asc' ? '\u2191' : '\u2193'}
            </button>
          </div>
          <span className="filter-separator">&middot;</span>
          <span className="filter-label">Group:</span>
          <select
            className="collection-group-select"
            value={group}
            onChange={(e) => handleGroupChange(e.target.value)}
            title="Group records by"
          >
            {GROUP_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <span className="filter-separator">&middot;</span>
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
          {isOwner && (
            <>
              <span className="filter-separator">&middot;</span>
              <button
                className="btn collection-resync"
                onClick={handleSync}
                disabled={isSyncing}
                title="Re-sync from Discogs"
              >
                Re-sync
              </button>
            </>
          )}
          {isOwner && collectionPublic && discogsUsername && (
            <>
              <span className="filter-separator">&middot;</span>
              <button
                className="btn btn-copy-link"
                onClick={handleCopyLink}
                title="Copy public collection link"
              >
                Copy link
              </button>
            </>
          )}
        </div>
      </div>

      {error && <p className="error">{error}</p>}

      {isOwner && selectedIds.size > 0 && (
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

      {skeletonPhase !== 'hidden' && (
        <div className={`collection-grid${skeletonPhase === 'fading' ? ' skeleton-fading-out' : ''}`} aria-hidden="true">
          {Array.from({ length: Math.min(pageSize, 25) }, (_, i) => (
            <div key={i} className="collection-card skeleton-card">
              <div className="skeleton-cover skeleton-shimmer" />
              <div className="skeleton-info">
                <div className="skeleton-bar skeleton-bar-long skeleton-shimmer" />
                <div className="skeleton-bar skeleton-bar-medium skeleton-shimmer" />
                <div className="skeleton-bar skeleton-bar-short skeleton-shimmer" />
              </div>
            </div>
          ))}
        </div>
      )}

      {!loading && !error && items.length === 0 && allItems.length === 0 && (
        <p className="no-results">
          {search ? 'No items match your search.' : 'No records yet. Sync from Discogs to get started.'}
        </p>
      )}

      {!loading && (items.length > 0 || allItems.length > 0) && (
        <>
          <div className="collection-info">
            {totalItems} item{totalItems !== 1 ? 's' : ''} in collection
            {group !== 'none' && allItems.length >= 250 && (
              <span className="collection-limit-notice"> (showing first 250 items when grouped)</span>
            )}
          </div>
          {group !== 'none' ? (
            // Grouped display
            <>
              {currentGroups.map((grp) => (
                <div key={grp.name} className="collection-group">
                  <div className="collection-group-header">
                    <h3 className="collection-group-name">{grp.name}</h3>
                    <span className="collection-group-count">{grp.count} record{grp.count !== 1 ? 's' : ''}</span>
                  </div>
                  <div className="collection-grid">
                    {grp.items.map((item, i) => (
                      <div
                        key={`${item.release_id}-${item.instance_id}`}
                        className={`collection-card${isOwner && selectedIds.has(item.instance_id) ? ' collection-card-selected' : ''}`}
                        style={{ animationDelay: `${Math.min(i * 40, 600)}ms` }}
                        onClick={() => handleCardClick(item)}
                      >
                        {isOwner && (
                          <label className="collection-card-checkbox" onClickCapture={(e) => e.stopPropagation()}>
                            <input
                              type="checkbox"
                              checked={selectedIds.has(item.instance_id)}
                              onChange={() => toggleSelect(item.instance_id)}
                            />
                          </label>
                        )}
                        {getDisplayCover(item) ? (
                          <div className="collection-cover-wrapper">
                            <img
                              src={getDisplayCover(item)!}
                              alt={item.title}
                              className="collection-cover"
                              loading="lazy"
                            />
                          </div>
                        ) : (
                          <div className="collection-cover collection-cover-placeholder" role="img" aria-label="No cover available">
                            <div className="collection-cover-placeholder-icon" aria-hidden="true" />
                          </div>
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
                </div>
              ))}
            </>
          ) : (
            // Standard grid display
            <div className="collection-grid">
              {items.map((item, i) => (
                <div
                  key={`${item.release_id}-${item.instance_id}`}
                  className={`collection-card${isOwner && selectedIds.has(item.instance_id) ? ' collection-card-selected' : ''}`}
                  style={{ animationDelay: `${Math.min(i * 40, 600)}ms` }}
                  onClick={() => handleCardClick(item)}
                >
                  {isOwner && (
                    <label className="collection-card-checkbox" onClickCapture={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={selectedIds.has(item.instance_id)}
                        onChange={() => toggleSelect(item.instance_id)}
                      />
                    </label>
                  )}
                  {getDisplayCover(item) ? (
                    <div className="collection-cover-wrapper">
                      <img
                        src={getDisplayCover(item)!}
                        alt={item.title}
                        className="collection-cover"
                        loading="lazy"
                      />
                    </div>
                  ) : (
                    <div className="collection-cover collection-cover-placeholder" role="img" aria-label="No cover available">
                      <div className="collection-cover-placeholder-icon" aria-hidden="true" />
                    </div>
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
          )}

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

      {isOwner && showDeleteModal && (
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

      {/* Record detail dialog — zoomed cover + actions / change cover */}
      {showContextMenu && contextItem && createPortal(
        <div className="context-menu-overlay" onClick={() => setShowContextMenu(false)}>
          <div className="context-menu context-menu-with-cover" onClick={(e) => e.stopPropagation()}>
            {dialogView === 'detail' ? (
              <>
                {getDisplayCover(contextItem) && (
                  <img
                    src={getDisplayCover(contextItem)!}
                    alt={contextItem.title}
                    className="context-menu-cover"
                  />
                )}
                <div className="context-menu-body">
                  <h3 className="context-menu-title">{contextItem.title}</h3>
                  <p className="context-menu-subtitle">{contextItem.artist}</p>
                  <div className="context-menu-meta">
                    {contextItem.year > 0 && <span>{contextItem.year}</span>}
                    {contextItem.format && <span>{contextItem.format}</span>}
                    {contextItem.genres.slice(0, 2).map((g) => (
                      <span key={g}>{g}</span>
                    ))}
                    {contextItem.styles.slice(0, 2).map((s) => (
                      <span key={s}>{s}</span>
                    ))}
                  </div>
                  <div className="context-menu-actions">
                    <button className="context-menu-item" onClick={handleViewOnDiscogs}>
                      View on Discogs
                    </button>
                    <button className="context-menu-item" onClick={handleViewPricing}>
                      View Pricing
                    </button>
                    {isOwner && (
                      <button className="context-menu-item" onClick={() => setDialogView('changeCover')}>
                        Change Cover
                      </button>
                    )}
                    {isOwner && (
                      <button
                        className="context-menu-item context-menu-item-danger"
                        onClick={handleDeleteFromCollection}
                      >
                        Delete from Collection
                      </button>
                    )}
                  </div>
                </div>
              </>
            ) : (
              <div className="change-cover-view">
                <div className="change-cover-header">
                  <button className="change-cover-back" onClick={() => { setMasterCoverPreview(null); setDialogView('detail'); }} title="Back">
                    <svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M12.5 15L7.5 10L12.5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                  </button>
                  <h3 className="change-cover-title">Change Cover</h3>
                </div>
                {masterCoverPreview ? (
                  <div className="change-cover-preview-section">
                    <img
                      src={masterCoverPreview}
                      alt={contextItem.title}
                      className="change-cover-preview"
                    />
                    <p className="change-cover-caption">Master release artwork</p>
                    <div className="change-cover-confirm-actions">
                      <button
                        className="btn btn-primary"
                        onClick={handleConfirmMasterCover}
                        disabled={coverLoading}
                      >
                        {coverLoading ? 'Applying...' : 'Use This Cover'}
                      </button>
                      <button
                        className="btn btn-nav"
                        onClick={() => setMasterCoverPreview(null)}
                        disabled={coverLoading}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="change-cover-options">
                    <button
                      className="change-cover-option"
                      onClick={handleFetchMasterCover}
                      disabled={!contextItem.master_id || coverLoading}
                      title={contextItem.master_id ? 'Fetch cover from master release' : 'No master release available'}
                    >
                      <svg className="change-cover-option-icon" width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="1.5"/><circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.5"/><line x1="12" y1="2" x2="12" y2="5" stroke="currentColor" strokeWidth="1" opacity="0.4"/><line x1="12" y1="19" x2="12" y2="22" stroke="currentColor" strokeWidth="1" opacity="0.4"/><line x1="2" y1="12" x2="5" y2="12" stroke="currentColor" strokeWidth="1" opacity="0.4"/><line x1="19" y1="12" x2="22" y2="12" stroke="currentColor" strokeWidth="1" opacity="0.4"/></svg>
                      <div className="change-cover-option-text">
                        <span className="change-cover-option-label">
                          {coverLoading ? 'Fetching...' : 'Use Master Cover'}
                        </span>
                        <span className="change-cover-option-desc">Canonical artwork from Discogs</span>
                      </div>
                    </button>
                    <button
                      className="change-cover-option"
                      onClick={() => coverFileRef.current?.click()}
                      disabled={coverUploading}
                    >
                      <svg className="change-cover-option-icon" width="22" height="22" viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="18" height="18" rx="3" stroke="currentColor" strokeWidth="1.5"/><path d="M3 16L8.29 11.71a1 1 0 011.42 0L15 17" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/><path d="M14 14l2.29-2.29a1 1 0 011.42 0L21 15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/><circle cx="8.5" cy="8.5" r="1.5" stroke="currentColor" strokeWidth="1.5"/></svg>
                      <div className="change-cover-option-text">
                        <span className="change-cover-option-label">
                          {coverUploading ? 'Uploading...' : 'Upload Image'}
                        </span>
                        <span className="change-cover-option-desc">JPEG or PNG, up to 5 MB</span>
                      </div>
                    </button>
                    <input
                      ref={coverFileRef}
                      type="file"
                      accept="image/png,image/jpeg"
                      style={{ display: 'none' }}
                      onChange={handleCoverUpload}
                    />
                    {contextItem.custom_cover_image && (
                      <button
                        className="change-cover-option change-cover-option-reset"
                        onClick={handleResetCover}
                        disabled={coverLoading}
                      >
                        <svg className="change-cover-option-icon" width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M3 12a9 9 0 1115.36-6.36" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/><path d="M18 2v5h-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                        <div className="change-cover-option-text">
                          <span className="change-cover-option-label">Reset to Default</span>
                          <span className="change-cover-option-desc">Revert to original release cover</span>
                        </div>
                      </button>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>,
        document.body,
      )}

      {/* Delete confirmation for single item */}
      {isOwner && showDeleteConfirm && contextItem && (
        <div className="delete-modal-overlay" onClick={() => !deleting && setShowDeleteConfirm(false)}>
          <div className="delete-modal" onClick={(e) => e.stopPropagation()}>
            <p className="delete-modal-warning">
              Are you sure you want to delete <strong>"{contextItem.title}"</strong> by {contextItem.artist}
              from your collection? This will also remove it from your Discogs account.
              This action cannot be undone.
            </p>
            <div className="delete-modal-actions">
              <button
                className="btn btn-nav"
                onClick={() => setShowDeleteConfirm(false)}
                disabled={deleting}
              >
                Cancel
              </button>
              <button
                className="btn btn-delete-confirm"
                onClick={handleDeleteConfirm}
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
