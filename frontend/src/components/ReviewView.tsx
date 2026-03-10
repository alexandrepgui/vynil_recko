import { useCallback, useEffect, useState } from 'react';
import { getAllReviewItems } from '../api';
import type { BatchItem } from '../types';
import BatchReview from './BatchReview';

export default function ReviewView() {
  const [items, setItems] = useState<BatchItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadItems = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const unreviewed = await getAllReviewItems('unreviewed');
      setItems(unreviewed);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Couldn\'t load the review queue. Try refreshing?');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner" />
        <p>Loading review queue...</p>
      </div>
    );
  }

  if (error) {
    return <p className="error">{error}</p>;
  }

  if (items.length === 0) {
    return (
      <div className="batch-summary">
        <h3>Nothing to review</h3>
        <p>Upload images via Single Search or Batch to get started.</p>
      </div>
    );
  }

  return <BatchReview items={items} onDone={loadItems} />;
}
