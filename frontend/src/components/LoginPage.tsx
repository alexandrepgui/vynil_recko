import { useState } from 'react';
import hideIcon from '../assets/hide.svg';
import viewIcon from '../assets/view.svg';
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
          <h1>groove log</h1>
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
        <h1>groove log</h1>
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
