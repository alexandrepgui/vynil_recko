import { useCallback, useEffect, useState } from 'react';
import { getAuthStatus, logout, startOAuthLogin } from '../api';
import type { AuthStatus } from '../types';

export default function DiscogsAuth() {
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      const s = await getAuthStatus();
      setStatus(s);
      return s;
    } catch {
      // Auth endpoint unavailable — likely no OAuth configured
      return null;
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  if (!status || !status.oauth_configured) return null;

  const handleLogin = async () => {
    setLoading(true);
    setError(null);
    try {
      const authorizeUrl = await startOAuthLogin();
      window.location.href = authorizeUrl;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start login');
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      await logout();
      setStatus({ ...status, authenticated: false, username: null });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to logout');
    }
  };

  if (status.authenticated) {
    return (
      <div className="discogs-auth">
        <span className="auth-user">Connected as <strong>{status.username ?? 'Discogs user'}</strong></span>
        <button className="btn btn-auth-logout" onClick={handleLogout}>Disconnect</button>
      </div>
    );
  }

  return (
    <div className="discogs-auth">
      <button className="btn btn-auth-login" onClick={handleLogin} disabled={loading}>
        {loading ? 'Connecting...' : 'Connect to Discogs'}
      </button>
      {error && <span className="auth-error">{error}</span>}
    </div>
  );
}
