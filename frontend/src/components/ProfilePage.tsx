import { useCallback, useEffect, useRef, useState } from 'react';
import { discogsLogout, getProfile, getSettings, startDiscogsLogin, updateSettings } from '../api';
import { useAuth } from '../AuthContext';
import { supabase } from '../supabaseClient';
import type { UserProfile, UserSettings } from '../types';

const AVATAR_SIZE = 256;
const AVATAR_QUALITY = 0.85;

function resizeImage(file: File): Promise<Blob> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const objectUrl = URL.createObjectURL(file);
    const cleanup = () => URL.revokeObjectURL(objectUrl);
    img.onload = () => {
      cleanup();
      const canvas = document.createElement('canvas');
      canvas.width = AVATAR_SIZE;
      canvas.height = AVATAR_SIZE;

      const ctx = canvas.getContext('2d')!;
      // Crop to center square, then scale down
      const side = Math.min(img.width, img.height);
      const sx = (img.width - side) / 2;
      const sy = (img.height - side) / 2;
      ctx.drawImage(img, sx, sy, side, side, 0, 0, AVATAR_SIZE, AVATAR_SIZE);

      canvas.toBlob(
        (blob) => (blob ? resolve(blob) : reject(new Error('Failed to compress image'))),
        'image/jpeg',
        AVATAR_QUALITY,
      );
    };
    img.onerror = () => { cleanup(); reject(new Error('Failed to load image')); };
    img.src = objectUrl;
  });
}

export default function ProfilePage() {
  const { user, signOut } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [discogsLoading, setDiscogsLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchProfile = useCallback(async () => {
    try {
      setProfile(await getProfile());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load profile');
    }
  }, []);

  const fetchSettings = useCallback(async () => {
    try {
      setSettings(await getSettings());
    } catch {
      // Settings not available, use defaults
      setSettings({ collection_public: false });
    }
  }, []);

  useEffect(() => {
    fetchProfile();
    fetchSettings();
  }, [fetchProfile, fetchSettings]);

  if (!profile && !error) {
    return (
      <div className="loading">
        <div className="spinner" />
      </div>
    );
  }

  if (error && !profile) {
    return <p className="error">{error}</p>;
  }

  const handleAvatarUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !user) return;

    setUploading(true);
    setError(null);
    try {
      const resized = await resizeImage(file);
      const path = `${user.id}/avatar.jpg`;

      const { error: uploadError } = await supabase.storage
        .from('avatars')
        .upload(path, resized, { upsert: true, contentType: 'image/jpeg' });
      if (uploadError) throw uploadError;

      const { data: { publicUrl } } = supabase.storage
        .from('avatars')
        .getPublicUrl(path);

      // Bust browser cache by appending timestamp
      const avatarUrl = `${publicUrl}?t=${Date.now()}`;

      const { error: updateError } = await supabase.auth.updateUser({
        data: { avatar_url: avatarUrl },
      });
      if (updateError) throw updateError;

      // Refresh session so the new JWT includes the updated avatar_url
      await supabase.auth.refreshSession();

      setProfile((p) => p ? { ...p, avatar_url: avatarUrl } : p);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to upload avatar');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDisconnect = async () => {
    setDiscogsLoading(true);
    try {
      await discogsLogout();
      setProfile((p) =>
        p ? { ...p, discogs: { ...p.discogs, connected: false, username: null } } : p,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to disconnect');
    } finally {
      setDiscogsLoading(false);
    }
  };

  const handleConnect = async () => {
    setDiscogsLoading(true);
    setError(null);
    try {
      const authorizeUrl = await startDiscogsLogin();
      window.location.href = authorizeUrl;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start Discogs login');
      setDiscogsLoading(false);
    }
  };

  const handleToggleVisibility = async () => {
    if (!settings) return;
    setSettingsLoading(true);
    setError(null);
    try {
      const updated = await updateSettings({ collection_public: !settings.collection_public });
      setSettings(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update settings');
    } finally {
      setSettingsLoading(false);
    }
  };

  const p = profile!;
  const avatarUrl = p.avatar_url;

  return (
    <div className="profile-page">
      <div className="profile-card">
        <div className="profile-avatar-wrapper">
          {avatarUrl ? (
            <img src={avatarUrl} alt="" className="profile-avatar-large" referrerPolicy="no-referrer" />
          ) : (
            <div className="profile-avatar-large avatar-fallback avatar-fallback-lg" />
          )}
          <button
            className="btn btn-upload-avatar"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
          >
            {uploading ? 'Uploading...' : 'Change photo'}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            onChange={handleAvatarUpload}
            hidden
          />
        </div>

        <div className="profile-info">
          {p.name && <h2 className="profile-name">{p.name}</h2>}
          {p.email && <p className="profile-email">{p.email}</p>}
        </div>
      </div>

      {p.discogs.oauth_configured && (
        <div className="profile-section">
          <h3 className="profile-section-title">Discogs</h3>
          {p.discogs.connected ? (
            <div className="profile-discogs-status">
              <span>
                Connected as <strong>{p.discogs.username ?? 'Discogs user'}</strong>
              </span>
              <button
                className="btn btn-disconnect"
                onClick={handleDisconnect}
                disabled={discogsLoading}
              >
                {discogsLoading ? 'Disconnecting...' : 'Disconnect'}
              </button>
            </div>
          ) : (
            <div className="profile-discogs-status">
              <span className="profile-discogs-hint">
                Connect your Discogs account to manage your collection and identify records.
              </span>
              <button
                className="btn btn-auth-login"
                onClick={handleConnect}
                disabled={discogsLoading}
              >
                {discogsLoading ? 'Connecting...' : 'Connect to Discogs'}
              </button>
            </div>
          )}
        </div>
      )}

      <div className="profile-section">
        <h3 className="profile-section-title">Collection</h3>
        <div className="profile-visibility-row">
          <div className="profile-visibility-info">
            <span className="profile-visibility-label">Collection visibility</span>
            <span className="profile-visibility-hint">
              When public, anyone can view your collection at /collection/{p.discogs?.username || 'your-username'}
            </span>
          </div>
          <button
            className={`toggle-switch${settings?.collection_public ? ' toggle-on' : ''}`}
            onClick={handleToggleVisibility}
            disabled={settingsLoading}
            aria-label="Toggle collection visibility"
          >
            <span className="toggle-knob" />
          </button>
        </div>
        <span className="profile-visibility-status">
          {settings?.collection_public ? 'Public' : 'Private'}
        </span>
      </div>

      {error && <p className="error">{error}</p>}

      <div className="profile-section">
        <button className="btn btn-sign-out-large" onClick={signOut}>
          Sign Out
        </button>
      </div>
    </div>
  );
}
