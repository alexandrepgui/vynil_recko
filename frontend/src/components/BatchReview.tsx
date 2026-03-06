import { useState } from 'react';
import { addToCollection, reviewItemGlobal, undoReviewItem } from '../api';
import type { BatchItem, DebugInfo } from '../types';
import ResultCard from './ResultCard';

interface Props {
  items: BatchItem[];
  onDone: () => void;
}

function DebugPanel({ debug }: { debug: DebugInfo }) {
  const [open, setOpen] = useState(true);

  return (
    <div className="debug-panel">
      <button className="debug-toggle" onClick={() => setOpen(!open)}>
        {open ? 'Hide' : 'Show'} debug
        {debug.cache_hit ? (
          <span className="debug-badge debug-badge-hit">cache hit</span>
        ) : (
          <span className="debug-badge debug-badge-miss">cache miss</span>
        )}
      </button>
      {open && (
        <div className="debug-content">
          <div className="debug-row">
            <strong>Timing:</strong>{' '}
            vision {debug.timing_ms.vision}ms
            {debug.timing_ms.search != null && <> | search {debug.timing_ms.search}ms</>}
            {debug.timing_ms.ranking != null && <> | ranking {debug.timing_ms.ranking}ms</>}
          </div>
          {debug.prefilter && (
            <div className="debug-row">
              <strong>Prefilter:</strong> {debug.prefilter.before} → {debug.prefilter.after} releases
            </div>
          )}
          {debug.ranking && (
            <div className="debug-row">
              <strong>Ranking:</strong> {debug.ranking.likeliness.length} ordered, {debug.ranking.discarded.length} discarded
            </div>
          )}
          {debug.strategies_tried.length > 0 && (
            <div className="debug-row">
              <strong>Strategies tried:</strong>
              <ul className="debug-strategies">
                {debug.strategies_tried.map((s, i) => <li key={i}>{s}</li>)}
              </ul>
            </div>
          )}
          <details className="debug-raw">
            <summary>Raw debug data</summary>
            <pre>{JSON.stringify(debug, null, 2)}</pre>
          </details>
        </div>
      )}
    </div>
  );
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
      // Auto-advance to next item
      if (safeIndex < completedItems.length - 1) {
        setCurrentIndex((i) => i + 1);
      }
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

  const handleDismissAll = async () => {
    if (!window.confirm(`Dismiss all ${reviewable.length} remaining items?`)) return;
    setActionLoading(true);
    try {
      await Promise.all(reviewable.map((ri) => reviewItemGlobal(ri.item_id, 'skipped')));
      setActed((prev) => {
        const next = new Map(prev);
        for (const ri of reviewable) next.set(ri.item_id, 'skipped');
        return next;
      });
      setExpanded(false);
    } finally {
      setActionLoading(false);
    }
  };

  const handleAddAll = async () => {
    const confirmed = window.confirm(
      `This will accept all ${reviewable.length} remaining items using their top result.\n\n` +
      'This is not recommended — the matching algorithm may have picked the wrong release. ' +
      'Reviewing each item individually helps avoid false positives in your collection.\n\n' +
      'Are you sure you want to add all?',
    );
    if (!confirmed) return;
    setActionLoading(true);
    try {
      await Promise.all(
        reviewable
          .filter((ri) => ri.results?.[0]?.discogs_id)
          .map(async (ri) => {
            const releaseId = ri.results![0].discogs_id!;
            await reviewItemGlobal(ri.item_id, 'accepted', releaseId);
            try { await addToCollection(releaseId); } catch { /* best-effort */ }
          }),
      );
      setActed((prev) => {
        const next = new Map(prev);
        for (const ri of reviewable) next.set(ri.item_id, 'accepted');
        return next;
      });
      setExpanded(false);
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="batch-review">
      <div className="batch-review-counter">
        {safeIndex + 1} of {completedItems.length} &middot; {reviewable.length} remaining
        {reviewable.length > 1 && (
          <>
            <button
              className="btn btn-dismiss btn-dismiss-all"
              disabled={actionLoading}
              onClick={handleDismissAll}
            >
              Dismiss all
            </button>
            <button
              className="btn btn-add-all"
              disabled={actionLoading}
              onClick={handleAddAll}
            >
              Add all (not recommended)
            </button>
          </>
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
        <div className="batch-review-actions-row">
          <button
            className="btn btn-nav"
            disabled={safeIndex === 0}
            onClick={() => { setCurrentIndex((i) => i - 1); setExpanded(false); }}
          >
            &lt;
          </button>
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
          <button
            className="btn btn-nav"
            disabled={safeIndex >= completedItems.length - 1}
            onClick={() => { setCurrentIndex((i) => i + 1); setExpanded(false); }}
          >
            &gt;
          </button>
        </div>
        {!itemAction && (item.results?.length ?? 0) > 1 && (
          <div className="batch-review-actions-row">
            <button
              className="btn btn-show-more"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? 'Hide' : 'See all'} ({item.results!.length})
            </button>
          </div>
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

      {item.debug && <DebugPanel debug={item.debug} />}

      {item.image_url && (
        <div className="batch-review-photo-wrapper">
          <img
            src={item.image_url}
            alt={item.image_filename}
            className="batch-review-photo"
          />
        </div>
      )}

      <div className="batch-review-label-info">
        <span className="batch-review-filename">{item.image_filename}</span>
        {item.label_data && (
          <span className="batch-review-extracted">
            {item.label_data.artists.join(', ')} — {item.label_data.albums.join(', ')}
          </span>
        )}
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
