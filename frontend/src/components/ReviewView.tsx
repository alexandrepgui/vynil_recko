import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getAllReviewItems } from '../api';
import type { BatchItem } from '../types';
import BatchReview from './BatchReview';

interface ReviewViewProps {
  onCountChange?: () => void;
}

export default function ReviewView({ onCountChange }: ReviewViewProps) {
  const [items, setItems] = useState<BatchItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchParams] = useSearchParams();

  const loadItems = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const unreviewed = await getAllReviewItems('unreviewed');
      setItems(unreviewed);
      onCountChange?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Couldn\'t load the review queue. Try refreshing?');
    } finally {
      setLoading(false);
    }
  }, [onCountChange]);

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
        <h3>All caught up</h3>
        <p>All caught up. Upload photos to identify more records.</p>
      </div>
    );
  }

  const focusId = searchParams.get('item');
  const initialIndex = focusId
    ? Math.max(0, items.findIndex((i) => i.item_id === focusId))
    : 0;

  return <BatchReview items={items} onDone={loadItems} initialIndex={initialIndex} />;
}
