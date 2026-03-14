import { type CSSProperties, type ReactNode, useEffect, useState } from 'react';
import { DuplicateError, addToCollection, getPrice, reviewItemGlobal, undoReviewItem } from '../api';
import type { DiscogsResult } from '../types';
import { parseDiscogsTitle } from '../utils';
import ZoomableImage from './ZoomableImage';

interface Props {
  result: DiscogsResult;
  itemId?: string | null;
  /** Override default action buttons. When provided, replaces the entire actions section. */
  renderActions?: (result: DiscogsResult) => ReactNode;
  /** Optional extra CSS class */
  className?: string;
  /** Optional inline styles (e.g. animation delay) */
  style?: CSSProperties;
}

export default function ResultCard({ result, itemId, renderActions, className, style }: Props) {
  const [status, setStatus] = useState<'idle' | 'loading' | 'added' | 'error' | 'dismissed'>('idle');
  const [showDuplicateConfirm, setShowDuplicateConfirm] = useState(false);
  const [price, setPrice] = useState<{ lowest_price: number | null; num_for_sale: number; currency: string | null } | null>(null);
  const [priceFailed, setPriceFailed] = useState(false);

  const { artist, album: albumTitle } = parseDiscogsTitle(result.title);

  useEffect(() => {
    if (!result.discogs_id) return;
    getPrice(result.discogs_id).then(setPrice).catch(() => setPriceFailed(true));
  }, [result.discogs_id]);

  const doAdd = async (force: boolean) => {
    if (!result.discogs_id) return;
    setStatus('loading');
    try {
      await addToCollection(result.discogs_id, force);
      if (itemId) {
        await reviewItemGlobal(itemId, 'accepted', result.discogs_id).catch(() => {});
      }
      setStatus('added');
    } catch (err) {
      if (err instanceof DuplicateError) {
        setStatus('idle');
        setShowDuplicateConfirm(true);
      } else {
        setStatus('error');
      }
    }
  };

  const handleAddToCollection = () => {
    if (!result.discogs_id || status === 'loading') return;
    doAdd(false);
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
    <div className={`result-card ${acted ? 'result-card-acted' : ''} ${status === 'added' ? 'result-card-added' : ''} ${className ?? ''}`} style={style}>
      {result.cover_image ? (
        <ZoomableImage
          className="result-cover"
          src={result.cover_image}
          alt={result.title ?? 'Cover'}
          loading="lazy"
        />
      ) : (
        <div className="result-cover result-cover-placeholder" role="img" aria-label="No cover available">
          <div className="result-cover-placeholder-icon" aria-hidden="true" />
        </div>
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
          {priceFailed ? (
            <span className="result-price result-price-unavailable">Price unavailable</span>
          ) : price?.lowest_price != null ? (
            <span className="result-price">From {price.lowest_price.toFixed(2)} {price.currency ?? ''} ({price.num_for_sale} for sale)</span>
          ) : null}
          {result.is_master_fallback && (
            <span className="result-master-badge">Master release — exact pressing not found</span>
          )}
        </div>

        {renderActions ? (
          <div className="result-actions">{renderActions(result)}</div>
        ) : (
          <div className="result-actions">
            {acted ? (
              <>
                <span className={`result-acted-label${status === 'added' ? ' result-acted-label-added' : ''}`}>
                  {status === 'added' ? (
                    <>
                      <svg className="check-icon" viewBox="0 0 16 16" aria-hidden="true">
                        <path d="M3 8.5 L6.5 12 L13 4" />
                      </svg>
                      Added
                    </>
                  ) : 'Dismissed'}
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
                {result.discogs_id && !result.is_master_fallback && (
                  <button
                    className={`btn btn-collection ${status}`}
                    disabled={status === 'loading'}
                    onClick={handleAddToCollection}
                  >
                    {status === 'loading' ? 'Adding...' :
                     status === 'error' ? 'Didn\'t work — try again?' :
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

      {showDuplicateConfirm && (
        <div className="delete-modal-overlay" onClick={() => setShowDuplicateConfirm(false)}>
          <div className="delete-modal" onClick={(e) => e.stopPropagation()}>
            <p className="delete-modal-warning">
              This release is already in your collection. Add it again?
            </p>
            <div className="delete-modal-actions">
              <button className="btn" onClick={() => setShowDuplicateConfirm(false)}>
                Cancel
              </button>
              <button
                className="btn btn-collection"
                onClick={() => { setShowDuplicateConfirm(false); doAdd(true); }}
              >
                Add anyway
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
