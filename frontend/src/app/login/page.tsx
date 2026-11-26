'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Film, Lock, Mail, ArrowRight, AlertCircle, Loader2 } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { ThemeToggle } from '@/components/ThemeToggle';

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      router.push('/');
    } catch (err: any) {
      setError(err?.message || 'Invalid email or password. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleDemoLogin = async () => {
    setEmail('test@reelstudio.local');
    setPassword('password123');
    setError(null);
    setLoading(true);
    try {
      await login('test@reelstudio.local', 'password123');
      router.push('/');
    } catch (err: any) {
      setError(err?.message || 'Demo login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Card */}
        <div className="relative rounded-3xl border border-divider bg-surface p-8 sm:p-10 shadow-2xl backdrop-blur-xl">
          {/* Header */}
          <div className="text-center mb-8">
            <div className="mx-auto flex h-16 w-16 items-center justify-center overflow-hidden mb-4">
              <img src="/logo.png" alt="Reel Studio Logo" className="h-full w-full object-contain drop-shadow" />
            </div>
            <h1 className="font-heading text-3xl sm:text-4xl font-bold tracking-tight text-text-primary">
              Welcome to Reel Studio
            </h1>
            <p className="font-body text-sm text-text-secondary mt-1.5 font-medium">
              Sign in to access your projects and video workspace
            </p>
          </div>

          {error && (
            <div className="mb-6 flex items-start gap-3 rounded-xl border border-status-error/30 bg-status-error/10 p-4 text-sm text-status-error animate-in fade-in duration-200">
              <AlertCircle className="h-5 w-5 shrink-0 mt-0.5 text-status-error" />
              <span className="font-body font-medium">{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4 font-body">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-text-secondary mb-1.5">
                Email Address
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-text-secondary">
                  <Mail className="h-4 w-4" />
                </div>
                <input
                  type="email"
                  required
                  autoFocus
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@example.com"
                  className="w-full rounded-xl border border-outline bg-surface-raised pl-10 pr-4 py-2.5 text-base text-text-primary placeholder:text-text-secondary/60 transition focus:border-accent focus:outline-none focus:ring-2 focus:ring-focus/30 font-medium"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-text-secondary mb-1.5">
                Password
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-text-secondary">
                  <Lock className="h-4 w-4" />
                </div>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full rounded-xl border border-outline bg-surface-raised pl-10 pr-4 py-2.5 text-base text-text-primary placeholder:text-text-secondary/60 transition focus:border-accent focus:outline-none focus:ring-2 focus:ring-focus/30 font-medium"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary-action w-full mt-2 flex items-center justify-center gap-2 rounded-xl py-3 text-base font-bold shadow-lg shadow-purple-600/30 transition hover:brightness-110 active:scale-[0.99] disabled:opacity-50 cursor-pointer"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Signing in...</span>
                </>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </form>

          {/* Quick Demo Login Option */}
          <div className="mt-6 pt-6 border-t border-divider text-center">
            <button
              type="button"
              onClick={handleDemoLogin}
              disabled={loading}
              className="text-xs text-accent hover:underline font-semibold underline-offset-4 cursor-pointer font-body"
            >
              Quick demo sign in (test@reelstudio.local)
            </button>
          </div>

          {/* Footer switch to Signup */}
          <div className="mt-4 text-center font-body">
            <p className="text-xs text-text-secondary font-medium">
              Don&apos;t have an account yet?{' '}
              <Link href="/signup" className="font-bold text-accent hover:underline">
                Sign up free
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
