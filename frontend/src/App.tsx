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
import singleSearchIcon from './assets/single-search.svg';
import batchIcon from './assets/batch.svg';
import reviewIcon from './assets/review.svg';
import issuesIcon from './assets/issues.svg';
import collectionIcon from './assets/collection.svg';
import profileIcon from './assets/profile.svg';
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
          Upload a single photo of your disc (JPEG or PNG).
          First, select the media type:
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

function PublicCollectionPage() {
  const { username } = useParams<{ username: string }>();
  if (!username) return <p className="error">No username provided.</p>;
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
      <nav className="mode-tabs">
        <NavLink to="/" end className={({ isActive }) => `mode-tab${isActive ? ' active' : ''}`}>
          <img src={singleSearchIcon} alt="" className="tab-icon" />
          Single Search
        </NavLink>
        <NavLink to="/batch" className={({ isActive }) => `mode-tab${isActive ? ' active' : ''}`}>
          <img src={batchIcon} alt="" className="tab-icon" />
          Batch
        </NavLink>
        <NavLink to="/review" className={({ isActive }) => `mode-tab${isActive ? ' active' : ''}`}>
          <img src={reviewIcon} alt="" className="tab-icon" />
          Review
        </NavLink>
        <NavLink to="/issues" className={({ isActive }) => `mode-tab${isActive ? ' active' : ''}`}>
          <img src={issuesIcon} alt="" className="tab-icon" />
          Issues
        </NavLink>
        <NavLink to="/collection" className={({ isActive }) => `mode-tab${isActive ? ' active' : ''}`}>
          <img src={collectionIcon} alt="" className="tab-icon" />
          Collection
        </NavLink>
        <NavLink to="/profile" className={({ isActive }) => `mode-tab${isActive ? ' active' : ''}`}>
          <img src={profileIcon} alt="" className="tab-icon" />
          Profile
        </NavLink>
      </nav>

      <header className="app-header">
        <div className="app-logo-row">
          <img src={logoIcon} alt="" className="app-icon" />
          <img src={logoImg} alt="groove log" className="app-logo" />
        </div>
        <p>Identify your records by photo</p>
      </header>

      <Routes>
        <Route path="/" element={<SingleSearchPage />} />
        <Route path="/batch" element={<BatchView onGoToReview={() => navigate('/review')} />} />
        <Route path="/review" element={<ReviewView />} />
        <Route path="/issues" element={<IssuesView />} />
        <Route path="/collection" element={<CollectionView />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/login" element={<Navigate to="/" replace />} />
      </Routes>
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
