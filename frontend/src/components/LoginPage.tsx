import { useState } from 'react';
import hideIcon from '../assets/hide.svg';
import viewIcon from '../assets/view.svg';
import logoIcon from '../assets/icon.svg';
import logoImg from '../assets/logo.svg';
import { supabase } from '../supabaseClient';

type Mode = 'login' | 'signup';

export default function LoginPage() {
  const [mode, setMode] = useState<Mode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [signupSuccess, setSignupSuccess] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (mode === 'login') {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
      } else {
        const { error } = await supabase.auth.signUp({ email, password });
        if (error) throw error;
        setSignupSuccess(true);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    setError(null);
    const { error } = await supabase.auth.signInWithOAuth({ provider: 'google' });
    if (error) setError(error.message);
  };

  if (signupSuccess) {
    return (
      <div className="login-page">
        <div className="login-card">
          <div className="login-logo">
            <img src={logoIcon} alt="" className="login-icon" />
            <img src={logoImg} alt="groove log" className="login-wordmark" />
          </div>
          <p className="login-success">Check your email to confirm your account, then log in.</p>
          <button className="btn btn-primary" onClick={() => { setSignupSuccess(false); setMode('login'); }}>
            Back to Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">
          <img src={logoIcon} alt="" className="login-icon" />
          <img src={logoImg} alt="groove log" className="login-wordmark" />
        </div>
        <p className="login-subtitle">Identify your vinyl and CDs from label photos</p>

        <form onSubmit={handleSubmit} className="login-form">
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
          <div className="password-field">
            <input
              type={showPassword ? 'text' : 'password'}
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              minLength={6}
            />
            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowPassword((v) => !v)}
              aria-label={showPassword ? 'Hide password' : 'Show password'}
            >
              <img src={showPassword ? hideIcon : viewIcon} alt="" width={20} height={20} />
            </button>
          </div>
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? 'Please wait...' : mode === 'login' ? 'Log In' : 'Sign Up'}
          </button>
        </form>

        <div className="login-divider"><span>or</span></div>

        <button className="btn btn-google" onClick={handleGoogleLogin}>
          <svg className="google-logo" viewBox="-0.5 0 48 48" width="18" height="18">
            <path d="M9.827,24c0-1.524.253-3.086.705-4.356L2.623,13.604C1.082,16.734.214,20.26.214,24c0,3.737.867,7.261,2.406,10.388l7.905-6.051c-.453-1.364-.698-2.82-.698-4.337" fill="#FBBC05"/>
            <path d="M23.714,10.133c3.311,0,6.302,1.173,8.652,3.093l6.837-6.826C35.036,2.773,29.695.533,23.714.533,14.427.533,6.445,5.844,2.623,13.604l7.909,6.04c1.822-5.532,7.017-9.511,13.182-9.511" fill="#EB4335"/>
            <path d="M23.714,37.867c-6.165,0-11.359-3.979-13.182-9.511l-7.909,6.038c3.822,7.761,11.804,13.072,21.091,13.072,5.732,0,11.204-2.036,15.311-5.849l-7.507-5.804c-2.118,1.335-4.786,2.054-7.804,2.054" fill="#34A853"/>
            <path d="M46.145,24c0-1.387-.213-2.88-.534-4.267H23.714V28.8h12.604c-.63,3.091-2.346,5.468-4.8,7.014l7.507,5.804c4.315-4.004,7.12-9.969,7.12-17.618" fill="#4285F4"/>
          </svg>
          Sign in with Google
        </button>

        {error && <p className="login-error">{error}</p>}

        <p className="login-toggle">
          {mode === 'login' ? (
            <>Don&apos;t have an account? <button className="link-btn" onClick={() => { setMode('signup'); setError(null); }}>Sign up</button></>
          ) : (
            <>Already have an account? <button className="link-btn" onClick={() => { setMode('login'); setError(null); }}>Log in</button></>
          )}
        </p>
      </div>
    </div>
  );
}
