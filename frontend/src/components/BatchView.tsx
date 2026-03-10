import { useCallback, useEffect, useState } from 'react';
import { getBatch } from '../api';
import type { Batch, MediaType } from '../types';
import BatchUpload from './BatchUpload';
import BatchProgress from './BatchProgress';
import MediaTypeSelector from './MediaTypeSelector';
import vinylIcon from '../assets/vinyl.svg';
import cdIcon from '../assets/cd.svg';

type Phase = 'select' | 'upload' | 'processing' | 'done';

interface Props {
  onGoToReview?: () => void;
}

export default function BatchView({ onGoToReview }: Props) {
  const [mediaType, setMediaType] = useState<MediaType | null>(null);
  const [phase, setPhase] = useState<Phase>('select');
  const [batchId, setBatchId] = useState<string | null>(null);
  const [batch, setBatch] = useState<Batch | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSelect = useCallback((type: MediaType) => {
    setMediaType(type);
    setPhase('upload');
  }, []);

  const handleChangeType = useCallback(() => {
    setMediaType(null);
    setPhase('select');
  }, []);

  const handleBatchCreated = useCallback((id: string, _total: number) => {
    setBatchId(id);
    setPhase('processing');
    setError(null);
  }, []);

  // Poll batch status during processing
  useEffect(() => {
    if (phase !== 'processing' || !batchId) return;

    let cancelled = false;

    const poll = async () => {
      try {
        const b = await getBatch(batchId);
        if (cancelled) return;
        setBatch(b);
        if (b.status === 'completed' || b.status === 'failed') {
          setPhase('done');
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Polling failed.');
      }
    };

    poll();
    const interval = setInterval(poll, 3000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [phase, batchId]);

  const handleReset = useCallback(() => {
    setPhase('upload');
    setBatchId(null);
    setBatch(null);
  }, []);

  if (phase === 'select') {
    return (
      <div>
        <p className="batch-instructions">
          Upload a <strong>.zip</strong> file containing photos of your discs (JPEG or PNG).
          First, select the media type:
        </p>
        <MediaTypeSelector onSelect={handleSelect} />
      </div>
    );
  }

  return (
    <div>
      <div className="media-selected-bar">
        <div className="media-selected-info">
          <img src={mediaType === 'cd' ? cdIcon : vinylIcon} alt="" className="media-selected-icon" />
          <span>{mediaType === 'cd' ? 'CD' : 'Vinyl'}</span>
        </div>
        <button className="btn-change-media" onClick={handleChangeType}>Change</button>
      </div>

      {error && <p className="error">{error}</p>}

      {phase === 'upload' && (
        <BatchUpload onBatchCreated={handleBatchCreated} mediaType={mediaType!} />
      )}

      {phase === 'processing' && batch && (
        <BatchProgress batch={batch} />
      )}

      {phase === 'done' && batch && (
        <div className="batch-summary">
          <h3>Batch complete</h3>
          <p>
            {batch.processed} processed, {batch.failed} failed out of {batch.total_images} images.
          </p>
          <div className="batch-done-actions">
            {onGoToReview && (
              <button className="btn btn-collection" onClick={onGoToReview}>
                Go to Review
              </button>
            )}
            <button className="btn btn-show-more" onClick={handleReset}>
              Upload another batch
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
