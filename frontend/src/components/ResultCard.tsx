import { type ReactNode, useEffect, useState } from 'react';
import { addToCollection, getPrice, reviewItemGlobal, undoReviewItem } from '../api';
import type { DiscogsResult } from '../types';
import { parseDiscogsTitle } from '../utils';

interface Props {
  result: DiscogsResult;
  itemId?: string | null;
  /** Override default action buttons. When provided, replaces the entire actions section. */
  renderActions?: (result: DiscogsResult) => ReactNode;
  /** Optional extra CSS class */
  className?: string;
}

export default function ResultCard({ result, itemId, renderActions, className }: Props) {
  const [status, setStatus] = useState<'idle' | 'loading' | 'added' | 'error' | 'dismissed'>('idle');
  const [price, setPrice] = useState<{ lowest_price: number | null; num_for_sale: number } | null>(null);

  const { artist, album: albumTitle } = parseDiscogsTitle(result.title);

  useEffect(() => {
    if (!result.discogs_id) return;
    getPrice(result.discogs_id).then(setPrice).catch(() => {});
  }, [result.discogs_id]);

  const handleAddToCollection = async () => {
    if (!result.discogs_id || status === 'loading') return;
    setStatus('loading');
    try {
      await addToCollection(result.discogs_id);
      if (itemId) {
        await reviewItemGlobal(itemId, 'accepted', result.discogs_id).catch(() => {});
      }
      setStatus('added');
    } catch {
      setStatus('error');
    }
  };

  const handleDismiss = async () => {
    if (status === 'loading') return;
    setStatus('loading');
    try {
      if (itemId) {
        await reviewItemGlobal(itemId, 'skipped');
      }
      setStatus('dismissed');
    } catch {
      setStatus('error');
    }
  };

  const handleUndo = async () => {
    if (!itemId) return;
    setStatus('loading');
    try {
      await undoReviewItem(itemId);
      setStatus('idle');
    } catch {
      setStatus('error');
    }
  };

  const acted = status === 'added' || status === 'dismissed';

  return (
    <div className={`result-card ${acted ? 'result-card-acted' : ''} ${className ?? ''}`}>
      {result.cover_image && (
        <img
          className="result-cover"
          src={result.cover_image}
          alt={result.title ?? 'Cover'}
          loading="lazy"
        />
      )}

      <div className="result-info">
        <h3 className="result-title">{albumTitle}</h3>
        <p className="result-artist">{artist}</p>

        <div className="result-meta">
          {result.year && <span>{result.year}</span>}
          {result.country && <span>{result.country}</span>}
          {result.format && <span>{result.format}</span>}
          {result.label && <span>{result.label}</span>}
          {result.catno && <span>Cat# {result.catno}</span>}
          {price?.lowest_price != null && (
            <span className="result-price">From ${price.lowest_price.toFixed(2)} ({price.num_for_sale} for sale)</span>
          )}
        </div>

        {renderActions ? (
          <div className="result-actions">{renderActions(result)}</div>
        ) : (
          <div className="result-actions">
            {acted ? (
              <>
                <span className="result-acted-label">
                  {status === 'added' ? 'Added' : 'Dismissed'}
                </span>
                {itemId && (
                  <button className="btn btn-undo" onClick={handleUndo}>
                    Undo
                  </button>
                )}
              </>
            ) : (
              <>
                {result.discogs_url && (
                  <a
                    href={result.discogs_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-discogs"
                  >
                    See in Discogs
                  </a>
                )}
                {result.discogs_id && (
                  <button
                    className={`btn btn-collection ${status}`}
                    disabled={status === 'loading'}
                    onClick={handleAddToCollection}
                  >
                    {status === 'loading' ? 'Adding...' :
                     status === 'error' ? 'Failed — Retry?' :
                     'Add to collection'}
                  </button>
                )}
                <button
                  className="btn btn-dismiss"
                  disabled={status === 'loading'}
                  onClick={handleDismiss}
                >
                  Dismiss
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
