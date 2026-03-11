import { useEffect, useRef, useState } from 'react';
import { BrowserRouter, NavLink, Navigate, Route, Routes, useNavigate, useParams } from 'react-router-dom';
import './App.css';
import { searchByImage } from './api';
import type { MediaType, SearchResponse } from './types';
import { AuthProvider, useAuth } from './AuthContext';
import ImageUpload from './components/ImageUpload';
import LoginPage from './components/LoginPage';
import MediaTypeSelector from './components/MediaTypeSelector';
import ResultsList from './components/ResultsList';
import BatchView from './components/BatchView';
import ReviewView from './components/ReviewView';
import IssuesView from './components/IssuesView';
import CollectionView from './components/CollectionView';
import ProfilePage from './components/ProfilePage';
import vinylIcon from './assets/vinyl.svg';
import cdIcon from './assets/cd.svg';
import logoImg from './assets/logo.svg';
import logoIcon from './assets/icon.svg';

function SingleSearchPage() {
  const [mediaType, setMediaType] = useState<MediaType | null>(null);
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => { abortRef.current?.abort(); }, []);

  const handleFileSelected = async (file: File) => {
    if (!mediaType) return;
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

  const handleChangeType = () => {
    abortRef.current?.abort();
    setMediaType(null);
    setResponse(null);
    setError(null);
    setIsLoading(false);
  };

  if (!mediaType) {
    return (
      <div>
        <p className="batch-instructions">
          Upload a photo of your record label to identify it.
        </p>
        <MediaTypeSelector onSelect={setMediaType} />
      </div>
    );
  }

  return (
    <>
      <div className="media-selected-bar">
        <div className="media-selected-info">
          <img src={mediaType === 'cd' ? cdIcon : vinylIcon} alt="" className="media-selected-icon" />
          <span>{mediaType === 'cd' ? 'CD' : 'Vinyl'}</span>
        </div>
        <button className="btn-change-media" onClick={handleChangeType}>Change</button>
      </div>

      <ImageUpload
        onFileSelected={handleFileSelected}
        onClear={handleClear}
        isLoading={isLoading}
        mediaType={mediaType}
      />

      {isLoading && (
        <div className="loading">
          <div className="spinner" />
          <p>Analyzing image and searching Discogs...</p>
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

function PublicCollectionPage() {
  const { username } = useParams<{ username: string }>();
  if (!username) return <p className="error">We need a username to show this collection.</p>;
  return (
    <div className="app public-collection-page">
      <header className="app-header">
        <div className="app-logo-row">
          <img src={logoIcon} alt="" className="app-icon" />
          <img src={logoImg} alt="groove log" className="app-logo" />
        </div>
      </header>
      <CollectionView readOnly username={username} />
    </div>
  );
}

function AppInner() {
  const navigate = useNavigate();
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="app">
        <div className="loading"><div className="spinner" /></div>
      </div>
    );
  }

  if (!user) {
    return <LoginPage />;
  }

  return (
    <div className="app">
      <nav className="app-navbar">
        <NavLink to="/" className="navbar-logo">
          <img src={logoIcon} alt="" className="navbar-icon" />
          <img src={logoImg} alt="groove log" className="navbar-wordmark" />
        </NavLink>

        <div className="navbar-links">
          <NavLink to="/identify" className="nav-link">
            Identify
          </NavLink>
          <NavLink to="/collection" className="nav-link">
            Collection
          </NavLink>
          <NavLink to="/review" className="nav-link">
            Review
          </NavLink>
          <NavLink to="/issues" className="nav-link">
            Issues
          </NavLink>
        </div>

        <div className="navbar-spacer" />

        <div className="navbar-actions">
          <NavLink to="/profile" className="nav-avatar-btn" title="Profile">
            <span className="nav-avatar-fallback">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                <circle cx="12" cy="7" r="4"/>
              </svg>
            </span>
          </NavLink>
        </div>
      </nav>

      <div className="route-content">
        <Routes>
          <Route path="/" element={<Navigate to="/collection" replace />} />
          <Route path="/identify" element={<SingleSearchPage />} />
          <Route path="/batch" element={<BatchView onGoToReview={() => navigate('/review')} />} />
          <Route path="/review" element={<ReviewView />} />
          <Route path="/issues" element={<IssuesView />} />
          <Route path="/collection" element={<CollectionView />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/login" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/collection/:username" element={<PublicCollectionPage />} />
          <Route path="/*" element={<AppInner />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
