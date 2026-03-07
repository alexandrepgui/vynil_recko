import { useRef, useState } from 'react';
import './App.css';
import { searchByImage } from './api';
import type { MediaType, SearchResponse } from './types';
import DiscogsAuth from './components/DiscogsAuth';
import ImageUpload from './components/ImageUpload';
import ResultsList from './components/ResultsList';
import BatchView from './components/BatchView';
import ReviewView from './components/ReviewView';
import IssuesView from './components/IssuesView';
import CollectionView from './components/CollectionView';

type Mode = 'single' | 'batch' | 'review' | 'issues' | 'collection';

export default function App() {
  const [mode, setMode] = useState<Mode>('single');
  const [mediaType, setMediaType] = useState<MediaType>('vinyl');
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const handleFileSelected = async (file: File) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setIsLoading(true);
    setError(null);
    setResponse(null);

    try {
      const data = await searchByImage(file, mediaType, controller.signal);
      setResponse(data);
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') return;
      setError(e instanceof Error ? e.message : 'Something went wrong.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsLoading(false);
  };

  const handleClear = () => {
    setResponse(null);
    setError(null);
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>Vinyl Recko</h1>
        <p>Drop a {mediaType === 'cd' ? 'CD' : 'record label'} photo to identify your {mediaType === 'cd' ? 'CD' : 'vinyl'}</p>
        <DiscogsAuth />
      </header>

      <div className="mode-tabs">
        <button
          className={`mode-tab ${mode === 'single' ? 'active' : ''}`}
          onClick={() => setMode('single')}
        >
          Single Search
        </button>
        <button
          className={`mode-tab ${mode === 'batch' ? 'active' : ''}`}
          onClick={() => setMode('batch')}
        >
          Batch
        </button>
        <button
          className={`mode-tab ${mode === 'review' ? 'active' : ''}`}
          onClick={() => setMode('review')}
        >
          Review
        </button>
        <button
          className={`mode-tab ${mode === 'issues' ? 'active' : ''}`}
          onClick={() => setMode('issues')}
        >
          Issues
        </button>
        <button
          className={`mode-tab ${mode === 'collection' ? 'active' : ''}`}
          onClick={() => setMode('collection')}
        >
          Collection
        </button>
      </div>

      {mode !== 'review' && mode !== 'issues' && mode !== 'collection' && (
        <div className="media-type-toggle">
          <button
            className={`media-type-btn ${mediaType === 'vinyl' ? 'active' : ''}`}
            onClick={() => setMediaType('vinyl')}
          >
            Vinyl
          </button>
          <button
            className={`media-type-btn ${mediaType === 'cd' ? 'active' : ''}`}
            onClick={() => setMediaType('cd')}
          >
            CD
          </button>
        </div>
      )}

      {mode === 'single' && (
        <>
          <ImageUpload
            onFileSelected={handleFileSelected}
            onClear={handleClear}
            isLoading={isLoading}
            mediaType={mediaType}
          />

          {isLoading && (
            <div className="loading">
              <div className="spinner" />
              <p>Analyzing image and searching Discogs... This may take up to 30 seconds.</p>
              <button className="btn btn-cancel" onClick={handleCancel}>
                Cancel
              </button>
            </div>
          )}

          {error && <p className="error">{error}</p>}

          {response && (
            <>
              <div className="search-info">
                <span>{response.total} release{response.total !== 1 ? 's' : ''} found</span>

              </div>
              <ResultsList results={response.results} itemId={response.item_id} />
            </>
          )}
        </>
      )}

      {mode === 'batch' && <BatchView onGoToReview={() => setMode('review')} mediaType={mediaType} />}

      {mode === 'review' && <ReviewView />}

      {mode === 'issues' && <IssuesView />}

      {mode === 'collection' && <CollectionView />}
    </div>
  );
}
