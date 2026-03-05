import { useState } from 'react';
import type { DiscogsResult } from '../types';
import ResultCard from './ResultCard';

interface Props {
  results: DiscogsResult[];
  itemId?: string | null;
}

const PAGE_SIZE = 5;

export default function ResultsList({ results, itemId }: Props) {
  const [showCount, setShowCount] = useState(PAGE_SIZE);

  if (results.length === 0) {
    return <p className="no-results">No releases found.</p>;
  }

  const visible = results.slice(0, showCount);
  const hasMore = showCount < results.length;

  return (
    <div className="results-list">
      {visible.map((r, i) => (
        <ResultCard key={`${r.discogs_url}-${i}`} result={r} itemId={itemId} />
      ))}

      {hasMore && (
        <button
          className="btn btn-show-more"
          onClick={() => setShowCount((c) => c + PAGE_SIZE)}
        >
          Show more ({results.length - showCount} remaining)
        </button>
      )}
    </div>
  );
}
