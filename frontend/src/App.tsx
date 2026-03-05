import { useState } from 'react';
import './App.css';
import { searchByImage } from './api';
import type { SearchResponse } from './types';
import ImageUpload from './components/ImageUpload';
import ResultsList from './components/ResultsList';
import BatchView from './components/BatchView';
import ReviewView from './components/ReviewView';

type Mode = 'single' | 'batch' | 'review';

export default function App() {
  const [mode, setMode] = useState<Mode>('single');
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileSelected = async (file: File) => {
    setIsLoading(true);
    setError(null);
    setResponse(null);

    try {
      const data = await searchByImage(file);
      setResponse(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>Vinyl Recko</h1>
        <p>Drop a record label photo to identify your vinyl</p>
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
      </div>

      {mode === 'single' && (
        <>
          <ImageUpload onFileSelected={handleFileSelected} isLoading={isLoading} />

          {isLoading && (
            <div className="loading">
              <div className="spinner" />
              <p>Analyzing image and searching Discogs... This may take up to 30 seconds.</p>
            </div>
          )}

          {error && <p className="error">{error}</p>}

          {response && (
            <>
              <div className="search-info">
                <span>{response.total} release{response.total !== 1 ? 's' : ''} found</span>
                <span className="strategy">Strategy: {response.strategy}</span>
              </div>
              <ResultsList results={response.results} itemId={response.item_id} />
            </>
          )}
        </>
      )}

      {mode === 'batch' && <BatchView onGoToReview={() => setMode('review')} />}

      {mode === 'review' && <ReviewView />}
    </div>
  );
}
