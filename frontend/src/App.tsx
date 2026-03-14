import { useCallback, useEffect, useRef, useState } from 'react';
import { BrowserRouter, Link, NavLink, Navigate, Route, Routes, useLocation, useNavigate, useParams } from 'react-router-dom';
import './App.css';
import { getAllReviewItems, getCollectionSyncStatus, getProfile, searchByImage } from './api';
import type { MediaType, SearchResponse } from './types';
import { AuthProvider, useAuth } from './AuthContext';
import { ThemeProvider } from './ThemeContext';
import { ToastProvider } from './components/Toast';
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
import { SingleSearchIcon, BatchIcon, ReviewIcon, IssuesIcon } from './components/Icons';
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
          <img src={mediaType === 'cd' ? cdIcon : vinylIcon} alt="" className="media-selected-icon dark-mode-invert" />
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

      {error && (
        <p className="error">
          {error.toLowerCase().includes('not connected')
            ? <>Discogs account not connected. <Link to="/profile">Connect it in your profile</Link>.</>
            : error}
        </p>
      )}

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

const subtabClass = ({ isActive }: { isActive: boolean }) =>
  `identify-subtab${isActive ? ' active' : ''}`;

function IdentifyPage() {
  const navigate = useNavigate();
  const [reviewCount, setReviewCount] = useState(0);
  const [issuesCount, setIssuesCount] = useState(0);

  const fetchCounts = useCallback(async () => {
    try {
      const [reviewItems, wrongItems, errorItems] = await Promise.all([
        getAllReviewItems('unreviewed'),
        getAllReviewItems('wrong'),
        getAllReviewItems('unreviewed', 'error'),
      ]);
      setReviewCount(reviewItems.length);
      setIssuesCount(wrongItems.length + errorItems.length);
    } catch {
      // Silently ignore count fetch failures
    }
  }, []);

  useEffect(() => {
    fetchCounts();
  }, [fetchCounts]);

  return (
    <div className="identify-page">
      <div className="identify-subtabs">
        <NavLink to="/identify" end className={subtabClass}>
          <SingleSearchIcon className="subtab-icon" aria-hidden="true" />
          Search
        </NavLink>
        <NavLink to="/identify/batch" className={subtabClass}>
          <BatchIcon className="subtab-icon" aria-hidden="true" />
          Batch
        </NavLink>
        <NavLink to="/identify/review" className={subtabClass}>
          <ReviewIcon className="subtab-icon" aria-hidden="true" />
          Review
          {reviewCount > 0 && <span className="subtab-badge">{reviewCount}</span>}
        </NavLink>
        <NavLink to="/identify/issues" className={subtabClass}>
          <IssuesIcon className="subtab-icon" aria-hidden="true" />
          Issues
          {issuesCount > 0 && <span className="subtab-badge">{issuesCount}</span>}
        </NavLink>
      </div>

      <Routes>
        <Route index element={<SingleSearchPage />} />
        <Route path="batch" element={<BatchView onGoToReview={() => navigate('/identify/review')} />} />
        <Route path="review" element={<ReviewView onCountChange={fetchCounts} />} />
        <Route path="issues" element={<IssuesView onCountChange={fetchCounts} />} />
        <Route path="*" element={<Navigate to="/identify" replace />} />
      </Routes>
    </div>
  );
}

function AppNavbar({ user }: { user?: { user_metadata?: { avatar_url?: string } } | null }) {
  const avatarUrl = user?.user_metadata?.avatar_url as string | undefined;

  return (
    <nav className="app-navbar">
      <NavLink to="/" className="navbar-logo">
        <img src={logoIcon} alt="" className="navbar-icon" />
        <span className="navbar-wordmark">groove log</span>
      </NavLink>

      {user && (
        <>
          <div className="navbar-links">
            <NavLink to="/identify" className="nav-link">
              Identify
            </NavLink>
            <NavLink to="/collection" className="nav-link">
              Collection
            </NavLink>
          </div>

          <div className="navbar-spacer" />

          <div className="navbar-actions">
            <NavLink to="/profile" className="nav-avatar-btn" title="Profile">
              {avatarUrl ? (
                <img src={avatarUrl} alt="" className="nav-avatar-img" />
              ) : (
                <span className="nav-avatar-fallback">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                    <circle cx="12" cy="7" r="4"/>
                  </svg>
                </span>
              )}
            </NavLink>
          </div>
        </>
      )}
    </nav>
  );
}

function CollectionRedirect() {
  const [target, setTarget] = useState<string | null>(null);

  useEffect(() => {
    getProfile()
      .then((profile) => {
        if (profile.discogs.username) {
          setTarget(`/collection/${profile.discogs.username}`);
        } else {
          setTarget('/profile');
        }
      })
      .catch(() => {
        setTarget('/profile');
      });
  }, []);

  if (!target) {
    return <div className="loading"><div className="spinner" /></div>;
  }

  return <Navigate to={target} replace />;
}

function CollectionPage() {
  const { username } = useParams<{ username: string }>();
  const { user, loading } = useAuth();

  if (!username) return <p className="error">We need a username to show this collection.</p>;

  if (loading) {
    return (
      <div className="app">
        <div className="loading"><div className="spinner" /></div>
      </div>
    );
  }

  return (
    <div className="app">
      <AppNavbar user={user} />
      <div className="route-content">
        <CollectionView username={username} />
      </div>
    </div>
  );
}

function SmartRedirect() {
  const [target, setTarget] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      getCollectionSyncStatus().catch(() => null),
      getProfile().catch(() => null),
    ]).then(([status, profile]) => {
      if (status?.completed_at && profile?.discogs.username) {
        setTarget(`/collection/${profile.discogs.username}`);
      } else {
        setTarget('/identify');
      }
    });
  }, []);

  if (!target) {
    return <div className="loading"><div className="spinner" /></div>;
  }

  return <Navigate to={target} replace />;
}

function AppInner() {
  const { user, loading } = useAuth();
  const location = useLocation();

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
      <AppNavbar user={user} />

      <div className="route-content" key={location.pathname.split('/')[1] || 'home'}>
        <Routes>
          <Route path="/" element={<SmartRedirect />} />
          <Route path="/identify/*" element={<IdentifyPage />} />
          <Route path="/collection" element={<CollectionRedirect />} />
          <Route path="/profile" element={<ProfilePage />} />
          {/* Redirects: old routes and login */}
          <Route path="/batch" element={<Navigate to="/identify/batch" replace />} />
          <Route path="/review" element={<Navigate to="/identify/review" replace />} />
          <Route path="/issues" element={<Navigate to="/identify/issues" replace />} />
          <Route path="/login" element={<Navigate to="/" replace />} />
          <Route path="*" element={<Navigate to="/identify" replace />} />
        </Routes>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <ToastProvider>
            <Routes>
              <Route path="/collection/:username" element={<CollectionPage />} />
              <Route path="/*" element={<AppInner />} />
            </Routes>
          </ToastProvider>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}
