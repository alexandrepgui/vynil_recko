import { useCallback, useRef, useState } from 'react';
import { addToCollection, reviewItemGlobal, undoReviewItem } from '../api';
import type { BatchItem, DebugInfo, LabelData } from '../types';
import ResultCard from './ResultCard';
import ZoomableImage from './ZoomableImage';

interface Props {
  items: BatchItem[];
  onDone: () => void;
  initialIndex?: number;
}

function DebugPanel({ debug, strategy, labelData }: { debug: DebugInfo; strategy?: string | null; labelData?: LabelData | null }) {
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
          {strategy && (
            <div className="debug-row">
              <strong>Winning strategy:</strong> {strategy}
            </div>
          )}
          <div className="debug-row">
            <strong>Timing:</strong>{' '}
            vision {debug.timing_ms.vision}ms
            {debug.timing_ms.search != null && <> | search {debug.timing_ms.search}ms</>}
            {debug.timing_ms.ranking != null && <> | ranking {debug.timing_ms.ranking}ms</>}
          </div>
          {labelData && (
            <div className="debug-row">
              <strong>LLM extraction:</strong>{' '}
              {[
                labelData.artists?.length && `artists: ${labelData.artists.join(', ')}`,
                labelData.albums?.length && `albums: ${labelData.albums.join(', ')}`,
                labelData.tracks?.length && `${labelData.tracks.length} track(s)`,
                labelData.catno && `catno: ${labelData.catno}`,
                labelData.label && `label: ${labelData.label}`,
                labelData.year && `year: ${labelData.year}`,
                labelData.country && `country: ${labelData.country}`,
              ].filter(Boolean).join(' · ') || 'no data'}
            </div>
          )}
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

export default function BatchReview({ items, onDone, initialIndex = 0 }: Props) {
  const [currentIndex, setCurrentIndex] = useState(initialIndex);
  const [actionLoading, setActionLoading] = useState(false);
  // Track items acted on in this session: item_id -> action
  const [acted, setActed] = useState<Map<string, 'accepted' | 'skipped' | 'wrong'>>(new Map());
  const [cardHeight, setCardHeight] = useState<number | undefined>(undefined);
  const [transitioning, setTransitioning] = useState(false);
  const [slideDir, setSlideDir] = useState<'left' | 'right'>('left');
  const observerRef = useRef<ResizeObserver | null>(null);
  const cardRef = useCallback((node: HTMLDivElement | null) => {
    if (observerRef.current) observerRef.current.disconnect();
    if (node) {
      setCardHeight(node.offsetHeight);
      observerRef.current = new ResizeObserver(() => setCardHeight(node.offsetHeight));
      observerRef.current.observe(node);
    }
  }, []);

  const navigate = useCallback((nextIndex: number) => {
    const dir = nextIndex > currentIndex ? 'left' : 'right';
    setSlideDir(dir);
    setTransitioning(true);
    setTimeout(() => {
      setCurrentIndex(nextIndex);

      setTransitioning(false);
    }, 180);
  }, [currentIndex]);

  const completedItems = items.filter((i) => i.status === 'completed' && i.review_status === 'unreviewed');
  const reviewable = completedItems.filter((i) => !acted.has(i.item_id));

  if (reviewable.length === 0 && acted.size === 0) {
    const accepted = items.filter((i) => i.review_status === 'accepted').length;
    const skipped = items.filter((i) => i.review_status === 'skipped').length;
    const wrong = items.filter((i) => i.review_status === 'wrong').length;
    const errored = items.filter((i) => i.status === 'error').length;

    return (
      <div className="batch-summary">
        <h3>Review complete</h3>
        <p>{accepted} accepted, {skipped} dismissed, {wrong} wrong, {errored} errored</p>
        <button className="btn btn-show-more" onClick={onDone}>Done</button>
      </div>
    );
  }

  const safeIndex = currentIndex >= completedItems.length ? 0 : currentIndex;
  const item = completedItems[safeIndex];
  const itemAction = acted.get(item?.item_id);
  const topResult = item?.results?.[0] ?? null;

  const handleAction = async (
    action: 'accepted' | 'skipped' | 'wrong',
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

      // Auto-advance to next item with slide transition
      if (safeIndex < completedItems.length - 1) {
        navigate(safeIndex + 1);
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

      <div className={`batch-review-main ${transitioning ? (slideDir === 'left' ? 'batch-slide-out-left' : 'batch-slide-out-right') : 'batch-slide-in'}`}>
        {topResult ? (
          <div ref={cardRef} style={{ flex: 1, minWidth: 0 }}>
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
          </div>
        ) : (
          <p className="batch-review-no-results">No results found for this image.</p>
        )}
        {item.image_url && cardHeight && (
          <ZoomableImage
            src={item.image_url}
            alt={item.image_filename}
            className="batch-review-photo"
            style={{ height: cardHeight }}
          />
        )}
      </div>

      <div className="batch-review-actions">
        <div className="batch-review-actions-row">
          <button
            className="btn btn-nav"
            disabled={safeIndex === 0 || transitioning}
            onClick={() => navigate(safeIndex - 1)}
          >
            &lt;
          </button>
          {itemAction ? (
            <>
              <span className="batch-review-acted">
                {itemAction === 'accepted' ? 'Added' : itemAction === 'wrong' ? 'Wrong' : 'Dismissed'}
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
                className="btn btn-wrong"
                disabled={actionLoading || transitioning}
                onClick={() => handleAction('wrong')}
              >
                Wrong
              </button>
              <button
                className="btn btn-dismiss"
                disabled={actionLoading || transitioning}
                onClick={() => handleAction('skipped')}
              >
                Dismiss
              </button>
              {topResult?.discogs_id && (
                <button
                  className="btn btn-collection"
                  disabled={actionLoading || transitioning}
                  onClick={() => handleAction('accepted', topResult.discogs_id!)}
                >
                  {actionLoading ? 'Adding...' : 'Add to collection'}
                </button>
              )}
            </>
          )}
          <button
            className="btn btn-nav"
            disabled={safeIndex >= completedItems.length - 1 || transitioning}
            onClick={() => navigate(safeIndex + 1)}
          >
            &gt;
          </button>
        </div>
      </div>

      {!itemAction && item.results && item.results.length > 1 && (
        <div className="batch-expanded-results expanded-visible">
          <h4 className="batch-alt-heading">OTHER POSSIBLE MATCHES</h4>
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
                      Add to collection
                    </button>
                  )}
                </>
              )}
            />
          ))}
        </div>
      )}

      {item.debug && <DebugPanel debug={item.debug} strategy={item.strategy} labelData={item.label_data} />}



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
