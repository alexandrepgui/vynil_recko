import { useCallback, useEffect, useMemo, useState } from 'react';
import { getCollection } from '../api';
import type { CollectionItem } from '../types';

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

  const fetchCollection = useCallback(async (p: number, s: string, so: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getCollection(p, PAGE_SIZE, s, so);
      setItems(data.items);
      setPage(data.page);
      setPages(data.pages);
      setTotalItems(data.total_items);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load collection.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCollection(page, sort, sortOrder);
  }, [page, sort, sortOrder, fetchCollection]);

  const filtered = useMemo(() => {
    if (!search.trim()) return items;
    const q = search.toLowerCase();
    return items.filter(
      (item) =>
        item.title.toLowerCase().includes(q) ||
        item.artist.toLowerCase().includes(q) ||
        item.genres.some((g) => g.toLowerCase().includes(q)) ||
        item.styles.some((s) => s.toLowerCase().includes(q)),
    );
  }, [items, search]);

  const handleSortChange = (newSort: string) => {
    setSort(newSort);
    setPage(1);
  };

  const toggleSortOrder = () => {
    setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    setPage(1);
  };

  return (
    <div className="collection-view">
      <div className="collection-controls">
        <input
          type="text"
          className="collection-search"
          placeholder="Filter by title, artist, genre..."
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
      </div>

      {error && <p className="error">{error}</p>}

      {loading && (
        <div className="loading">
          <div className="spinner" />
          <p>Loading collection...</p>
        </div>
      )}

      {!loading && !error && filtered.length === 0 && (
        <p className="no-results">
          {search ? 'No items match your filter.' : 'Your collection is empty.'}
        </p>
      )}

      {!loading && filtered.length > 0 && (
        <>
          <div className="collection-info">
            {totalItems} item{totalItems !== 1 ? 's' : ''} in collection
            {search && ` (${filtered.length} shown)`}
          </div>
          <div className="collection-grid">
            {filtered.map((item) => (
              <div key={`${item.id}-${item.instance_id}`} className="collection-card">
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
