import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import type { BatchItem, CollectionItem } from '../types';

interface Props {
  reviewItems: BatchItem[];
  issuesCount: number;
  recentItems: CollectionItem[];
  collectionTotal: number;
}

const STEPS = [
  {
    num: '1',
    title: 'Snap',
    desc: 'Take a photo of the record label above.',
  },
  {
    num: '2',
    title: 'Match',
    desc: 'We read the label and find the exact pressing on Discogs.',
  },
  {
    num: '3',
    title: 'Collect',
    desc: 'Review the match, approve it, and it lands in your collection.',
  },
];

function parseDiscogsTitle(raw: string | null): { artist: string; title: string } {
  if (!raw) return { artist: '', title: 'Unknown title' };
  const sep = raw.indexOf(' - ');
  if (sep === -1) return { artist: '', title: raw };
  return { artist: raw.slice(0, sep), title: raw.slice(sep + 3) };
}

function ReviewCard({ item }: { item: BatchItem }) {
  const match = item.results?.[0];
  const { artist, title } = parseDiscogsTitle(match?.title ?? null);

  return (
    <Link to={`/identify/review?item=${item.item_id}`} className="search-review-card">
      {match?.cover_image ? (
        <img src={match.cover_image} alt={match.title ?? ''} className="search-review-cover" loading="lazy" />
      ) : (
        <div className="search-review-cover search-review-cover--empty">
          <div className="collection-cover-placeholder-icon" aria-hidden="true" />
        </div>
      )}
      <div className="search-review-info">
        <div className="search-review-title">{title}</div>
        {artist && <div className="search-review-artist">{artist}</div>}
        <div className="search-review-meta">
          {match?.year && match.year > 0 && <span>{match.year}</span>}
          {match?.format && <span>{match.format}</span>}
          {match?.catno && <span>{match.catno}</span>}
        </div>
      </div>
    </Link>
  );
}

export default function SearchDashboard({ reviewItems, issuesCount, recentItems, collectionTotal }: Props) {
  const hasReview = reviewItems.length > 0;
  const hasCollection = recentItems.length > 0;
  const isNewUser = !hasReview && !hasCollection && issuesCount === 0;

  return (
    <motion.div
      className="search-dashboard"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 0.1 }}
    >
      {/* Issues nudge */}
      {issuesCount > 0 && (
        <Link to="/identify/issues" className="search-nudge search-nudge--issues">
          <span className="search-nudge-count">{issuesCount}</span>
          <span>issue{issuesCount !== 1 ? 's' : ''} need{issuesCount === 1 ? 's' : ''} attention</span>
        </Link>
      )}

      {/* Review items — primary content */}
      {hasReview && (
        <div className="search-section">
          <div className="search-section-header">
            <span className="search-section-label">Waiting for review</span>
            <Link to="/identify/review" className="search-section-link">Review all</Link>
          </div>
          <div className="search-review-grid">
            {reviewItems.map((item) => (
              <ReviewCard key={item.item_id} item={item} />
            ))}
          </div>
        </div>
      )}

      {/* Recently added — fallback when no review items */}
      {!hasReview && hasCollection && (
        <div className="search-section">
          <div className="search-section-header">
            <span className="search-section-label">Recently added</span>
            <Link to="/collection" className="search-section-link">View collection</Link>
          </div>
          <div className="search-review-grid">
            {recentItems.map((item) => (
              <div key={item.instance_id} className="search-review-card">
                {(item.custom_cover_image || item.cover_image) ? (
                  <img
                    src={item.custom_cover_image || item.cover_image!}
                    alt={`${item.artist} — ${item.title}`}
                    className="search-review-cover"
                    loading="lazy"
                  />
                ) : (
                  <div className="search-review-cover search-review-cover--empty">
                    <div className="collection-cover-placeholder-icon" aria-hidden="true" />
                  </div>
                )}
                <div className="search-review-info">
                  <div className="search-review-title">{item.title}</div>
                  <div className="search-review-artist">{item.artist}</div>
                  <div className="search-review-meta">
                    {item.year > 0 && <span>{item.year}</span>}
                    {item.format && <span>{item.format}</span>}
                    {item.genres.map((g) => <span key={g}>{g}</span>)}
                  </div>
                </div>
              </div>
            ))}
          </div>
          <p className="search-stat">
            {collectionTotal} record{collectionTotal !== 1 ? 's' : ''} in your collection
          </p>
        </div>
      )}

      {/* New user empty state */}
      {isNewUser && (
        <div className="search-onboarding">
          <div className="search-onboarding-steps">
            {STEPS.map((step, i) => (
              <motion.div
                key={i}
                className="search-onboarding-step"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: 0.15 + i * 0.1 }}
              >
                <span className="search-onboarding-num">{step.num}</span>
                <h3 className="search-onboarding-title">{step.title}</h3>
                <p className="search-onboarding-desc">{step.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}
