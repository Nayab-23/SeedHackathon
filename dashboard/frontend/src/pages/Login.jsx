import { useState } from 'react';
import { Shield } from 'lucide-react';
import { apiFetch, setToken } from '../api';

export default function Login({ onLogin }) {
  const [token, setTokenInput] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await apiFetch('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ token: token.trim() }),
        _skipAuth: true,
      });
      setToken(token.trim());
      onLogin();
    } catch (err) {
      setError('Invalid token. Check your config.yaml.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <div className="w-12 h-12 bg-emerald-500/20 rounded-xl flex items-center justify-center mb-4">
            <Shield className="w-6 h-6 text-emerald-400" />
          </div>
          <h1 className="text-2xl font-bold text-white">OpenClaw</h1>
          <p className="text-slate-400 text-sm mt-1">DNS Dashboard</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Admin Token
            </label>
            <input
              type="password"
              value={token}
              onChange={e => setTokenInput(e.target.value)}
              placeholder="Enter your admin token"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
              autoFocus
            />
          </div>

          {error && (
            <p className="text-red-400 text-sm">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading || !token.trim()}
            className="w-full bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-2 rounded-lg transition-colors"
          >
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        <p className="text-center text-slate-600 text-xs mt-4">
          Token is set in dns-server/config.yaml
        </p>
      </div>
    </div>
  );
}
