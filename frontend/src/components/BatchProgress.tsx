import type { Batch } from '../types';

interface Props {
  batch: Batch;
}

export default function BatchProgress({ batch }: Props) {
  const pct = batch.total_images > 0
    ? Math.round(((batch.processed + batch.failed) / batch.total_images) * 100)
    : 0;

  return (
    <div className="batch-progress">
      <p className="batch-progress-text">
        Processing {batch.processed + batch.failed} of {batch.total_images} images...
        {batch.failed > 0 && <span className="batch-progress-failed"> ({batch.failed} couldn't be processed)</span>}
      </p>
      <div className="batch-progress-bar">
        <div className="batch-progress-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
