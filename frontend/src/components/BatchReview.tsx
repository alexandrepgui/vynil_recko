import { useState } from 'react';
import { addToCollection, reviewItemGlobal, undoReviewItem } from '../api';
import type { BatchItem } from '../types';
import { parseDiscogsTitle } from '../utils';
import ResultCard from './ResultCard';

interface Props {
  items: BatchItem[];
  onDone: () => void;
}

export default function BatchReview({ items, onDone }: Props) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  // Track items acted on in this session: item_id -> action
  const [acted, setActed] = useState<Map<string, 'accepted' | 'skipped'>>(new Map());

  const completedItems = items.filter((i) => i.status === 'completed' && i.review_status === 'unreviewed');
  const reviewable = completedItems.filter((i) => !acted.has(i.item_id));

  if (reviewable.length === 0 && acted.size === 0) {
    const accepted = items.filter((i) => i.review_status === 'accepted').length;
    const skipped = items.filter((i) => i.review_status === 'skipped').length;
    const errored = items.filter((i) => i.status === 'error').length;

    return (
      <div className="batch-summary">
        <h3>Review complete</h3>
        <p>{accepted} accepted, {skipped} dismissed, {errored} errored</p>
        <button className="btn btn-show-more" onClick={onDone}>Done</button>
      </div>
    );
  }

  const safeIndex = currentIndex >= completedItems.length ? 0 : currentIndex;
  const item = completedItems[safeIndex];
  const itemAction = acted.get(item?.item_id);
  const topResult = item?.results?.[0] ?? null;

  const handleAction = async (
    action: 'accepted' | 'skipped',
    releaseId?: number,
  ) => {
    setActionLoading(true);
    try {
      await reviewItemGlobal(item.item_id, action, releaseId);
      if (action === 'accepted' && releaseId) {
        try {
          await addToCollection(releaseId);
        } catch {
          // Collection add is best-effort; review still counts
        }
      }
      setActed((prev) => new Map(prev).set(item.item_id, action));
      setExpanded(false);
    } finally {
      setActionLoading(false);
    }
  };

  const handleUndo = async () => {
    setActionLoading(true);
    try {
      await undoReviewItem(item.item_id);
      setActed((prev) => {
        const next = new Map(prev);
        next.delete(item.item_id);
        return next;
      });
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="batch-review">
      <div className="batch-review-counter">
        {safeIndex + 1} of {completedItems.length} &middot; {reviewable.length} remaining
      </div>

      <div className="batch-review-label-info">
        <span className="batch-review-filename">{item.image_filename}</span>
        {item.label_data && (
          <span className="batch-review-extracted">
            {item.label_data.artists.join(', ')} — {item.label_data.albums.join(', ')}
          </span>
        )}
      </div>

      {topResult ? (
        <ResultCard
          result={topResult}
          className="batch-review-featured"
          renderActions={(r) => (
            <>
              {r.discogs_url && (
                <a href={r.discogs_url} target="_blank" rel="noopener noreferrer" className="btn btn-discogs">
                  See in Discogs
                </a>
              )}
            </>
          )}
        />
      ) : (
        <p className="batch-review-no-results">No results found for this image.</p>
      )}

      <div className="batch-review-actions">
        {itemAction ? (
          <>
            <span className="batch-review-acted">
              {itemAction === 'accepted' ? 'Added' : 'Dismissed'}
            </span>
            <button
              className="btn btn-undo"
              disabled={actionLoading}
              onClick={handleUndo}
            >
              Undo
            </button>
          </>
        ) : (
          <>
            <button
              className="btn btn-dismiss"
              disabled={actionLoading}
              onClick={() => handleAction('skipped')}
            >
              Dismiss
            </button>
            {(item.results?.length ?? 0) > 1 && (
              <button
                className="btn btn-show-more"
                onClick={() => setExpanded(!expanded)}
              >
                {expanded ? 'Hide' : 'See all'} ({item.results!.length})
              </button>
            )}
            {topResult?.discogs_id && (
              <button
                className="btn btn-collection"
                disabled={actionLoading}
                onClick={() => handleAction('accepted', topResult.discogs_id!)}
              >
                {actionLoading ? 'Adding...' : 'Accept + Add'}
              </button>
            )}
          </>
        )}
      </div>

      {!itemAction && expanded && item.results && (
        <div className="batch-expanded-results">
          {item.results.slice(1).map((r, i) => (
            <ResultCard
              key={`${r.discogs_id}-${i}`}
              result={r}
              renderActions={(r) => (
                <>
                  {r.discogs_url && (
                    <a href={r.discogs_url} target="_blank" rel="noopener noreferrer" className="btn btn-discogs">
                      See in Discogs
                    </a>
                  )}
                  {r.discogs_id && (
                    <button
                      className="btn btn-collection"
                      disabled={actionLoading}
                      onClick={() => handleAction('accepted', r.discogs_id!)}
                    >
                      Pick this
                    </button>
                  )}
                </>
              )}
            />
          ))}
        </div>
      )}

      <div className="batch-review-nav">
        <button
          className="btn"
          disabled={safeIndex === 0}
          onClick={() => { setCurrentIndex((i) => i - 1); setExpanded(false); }}
        >
          Prev
        </button>
        <button
          className="btn"
          disabled={safeIndex >= completedItems.length - 1}
          onClick={() => { setCurrentIndex((i) => i + 1); setExpanded(false); }}
        >
          Next
        </button>
      </div>

      {reviewable.length === 0 && acted.size > 0 && (
        <div className="batch-review-done-hint">
          <button className="btn btn-show-more" onClick={onDone}>
            All reviewed — Done
          </button>
        </div>
      )}
    </div>
  );
}
