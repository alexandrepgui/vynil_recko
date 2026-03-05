import { useCallback, useEffect, useState } from 'react';
import { getBatch } from '../api';
import type { Batch } from '../types';
import BatchUpload from './BatchUpload';
import BatchProgress from './BatchProgress';

type Phase = 'upload' | 'processing' | 'done';

interface Props {
  onGoToReview?: () => void;
}

export default function BatchView({ onGoToReview }: Props) {
  const [phase, setPhase] = useState<Phase>('upload');
  const [batchId, setBatchId] = useState<string | null>(null);
  const [batch, setBatch] = useState<Batch | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  return (
    <div>
      {error && <p className="error">{error}</p>}

      {phase === 'upload' && (
        <BatchUpload onBatchCreated={handleBatchCreated} />
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
