import { useEffect, useRef, useState } from 'react';
import { BrowserRouter, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
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

const ROUTES_WITHOUT_MEDIA_TOGGLE = ['review', 'issues', 'collection'];

function SingleSearchPage({ mediaType }: { mediaType: MediaType }) {
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => { abortRef.current?.abort(); }, []);

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
  );
}

function AppInner() {
  const [mediaType, setMediaType] = useState<MediaType>('vinyl');
  const location = useLocation();
  const navigate = useNavigate();
  const showMediaToggle = !ROUTES_WITHOUT_MEDIA_TOGGLE.some(
    (p) => location.pathname.startsWith(`/${p}`)
  );

  return (
    <div className="app">
      <nav className="mode-tabs">
        <NavLink to="/" end className={({ isActive }) => `mode-tab${isActive ? ' active' : ''}`}>
          Single Search
        </NavLink>
        <NavLink to="/batch" className={({ isActive }) => `mode-tab${isActive ? ' active' : ''}`}>
          Batch
        </NavLink>
        <NavLink to="/review" className={({ isActive }) => `mode-tab${isActive ? ' active' : ''}`}>
          Review
        </NavLink>
        <NavLink to="/issues" className={({ isActive }) => `mode-tab${isActive ? ' active' : ''}`}>
          Issues
        </NavLink>
        <NavLink to="/collection" className={({ isActive }) => `mode-tab${isActive ? ' active' : ''}`}>
          Collection
        </NavLink>
      </nav>

      <header className="app-header">
        <h1>Groove Log</h1>
        <p>Drop a {mediaType === 'cd' ? 'CD' : 'record label'} photo to identify your {mediaType === 'cd' ? 'CD' : 'vinyl'}</p>
        <DiscogsAuth />
      </header>

      {showMediaToggle && (
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

      <Routes>
        <Route path="/" element={<SingleSearchPage mediaType={mediaType} />} />
        <Route path="/batch" element={<BatchView onGoToReview={() => navigate('/review')} mediaType={mediaType} />} />
        <Route path="/review" element={<ReviewView />} />
        <Route path="/issues" element={<IssuesView />} />
        <Route path="/collection" element={<CollectionView />} />
      </Routes>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppInner />
    </BrowserRouter>
  );
}
