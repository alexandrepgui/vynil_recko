import { useCallback, useEffect, useState } from 'react';
import { getAllReviewItems, reviewItemGlobal, retryItem } from '../api';
import type { BatchItem } from '../types';
import ZoomableImage from './ZoomableImage';

export default function IssuesView() {
  const [wrongItems, setWrongItems] = useState<BatchItem[]>([]);
  const [errorItems, setErrorItems] = useState<BatchItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const loadItems = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [wrong, errored] = await Promise.all([
        getAllReviewItems('wrong'),
        getAllReviewItems('unreviewed', 'error'),
      ]);
      setWrongItems(wrong);
      setErrorItems(errored);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Couldn\'t load issues. Try refreshing?');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  const removeItem = (itemId: string) => {
    setWrongItems((prev) => prev.filter((i) => i.item_id !== itemId));
    setErrorItems((prev) => prev.filter((i) => i.item_id !== itemId));
  };

  const handleDismiss = async (itemId: string) => {
    setActionLoading(itemId);
    try {
      await reviewItemGlobal(itemId, 'skipped');
      removeItem(itemId);
    } finally {
      setActionLoading(null);
    }
  };

  const handleRetry = async (itemId: string) => {
    setActionLoading(itemId);
    try {
      await retryItem(itemId);
      removeItem(itemId);
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner" />
        <p>Loading issues...</p>
      </div>
    );
  }

  if (error) {
    return <p className="error">{error}</p>;
  }

  if (wrongItems.length === 0 && errorItems.length === 0) {
    return (
      <div className="batch-summary">
        <h3>No issues</h3>
        <p>No wrong matches or errors to show.</p>
      </div>
    );
  }

  return (
    <div className="issues-view">
      {wrongItems.length > 0 && (
        <section className="issues-section">
          <h3 className="issues-section-title">Wrong matches ({wrongItems.length})</h3>
          <div className="issues-list">
            {wrongItems.map((item) => (
              <div key={item.item_id} className="issues-card">
                {item.image_url && (
                  <ZoomableImage
                    src={item.image_url}
                    alt={item.image_filename}
                    className="issues-card-image"
                  />
                )}
                <div className="issues-card-info">
                  <span className="issues-card-filename">{item.image_filename}</span>
                  {item.label_data && (
                    <span className="issues-card-label">
                      {item.label_data.artists.join(', ')} — {item.label_data.albums.join(', ')}
                    </span>
                  )}
                  {item.results?.[0]?.title && (
                    <span className="issues-card-match">
                      Top match: {item.results[0].title}
                    </span>
                  )}
                </div>
                <div className="issues-card-actions">
                  <button
                    className="btn btn-show-more"
                    disabled={actionLoading === item.item_id}
                    onClick={() => handleRetry(item.item_id)}
                  >
                    Retry
                  </button>
                  <button
                    className="btn btn-dismiss"
                    disabled={actionLoading === item.item_id}
                    onClick={() => handleDismiss(item.item_id)}
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {errorItems.length > 0 && (
        <section className="issues-section">
          <h3 className="issues-section-title">Errors ({errorItems.length})</h3>
          <div className="issues-list">
            {errorItems.map((item) => (
              <div key={item.item_id} className="issues-card">
                {item.image_url && (
                  <ZoomableImage
                    src={item.image_url}
                    alt={item.image_filename}
                    className="issues-card-image"
                  />
                )}
                <div className="issues-card-info">
                  <span className="issues-card-filename">{item.image_filename}</span>
                  {item.error && (
                    <span className="issues-card-error">{item.error}</span>
                  )}
                </div>
                <div className="issues-card-actions">
                  <button
                    className="btn btn-show-more"
                    disabled={actionLoading === item.item_id}
                    onClick={() => handleRetry(item.item_id)}
                  >
                    Retry
                  </button>
                  <button
                    className="btn btn-dismiss"
                    disabled={actionLoading === item.item_id}
                    onClick={() => handleDismiss(item.item_id)}
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
