'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Film, Lock, Mail, User, ArrowRight, AlertCircle, Loader2, CheckCircle2 } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { ThemeToggle } from '@/components/ThemeToggle';

export default function SignupPage() {
  const router = useRouter();
  const { signup } = useAuth();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError('Passwords do not match. Please verify your password.');
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }

    setLoading(true);
    try {
      await signup({ email, password, full_name: fullName });
      router.push('/');
    } catch (err: any) {
      setError(err?.message || 'Registration failed. An account with this email may already exist.');
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
          <div className="text-center mb-6">
            <div className="mx-auto flex h-16 w-16 items-center justify-center overflow-hidden mb-4">
              <img src="/logo.png" alt="Reel Studio Logo" className="h-full w-full object-contain drop-shadow" />
            </div>
            <h1 className="font-heading text-3xl sm:text-4xl font-bold tracking-tight text-text-primary">
              Create Your Account
            </h1>
            <p className="font-body text-sm text-text-secondary mt-1.5 font-medium">
              Start creating viral reels in your private creator workspace
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
                Full Name
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-text-secondary">
                  <User className="h-4 w-4" />
                </div>
                <input
                  type="text"
                  required
                  autoFocus
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Alex Rivera"
                  className="w-full rounded-xl border border-outline bg-surface-raised pl-10 pr-4 py-2.5 text-base text-text-primary placeholder:text-text-secondary/60 transition focus:border-accent focus:outline-none focus:ring-2 focus:ring-focus/30 font-medium"
                />
              </div>
            </div>

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
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@example.com"
                  className="w-full rounded-xl border border-outline bg-surface-raised pl-10 pr-4 py-2.5 text-base text-text-primary placeholder:text-text-secondary/60 transition focus:border-accent focus:outline-none focus:ring-2 focus:ring-focus/30 font-medium"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-text-secondary mb-1.5">
                Password (min 8 chars)
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

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-text-secondary mb-1.5">
                Confirm Password
              </label>
              <div className="relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3.5 text-text-secondary">
                  <Lock className="h-4 w-4" />
                </div>
                <input
                  type="password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full rounded-xl border border-outline bg-surface-raised pl-10 pr-4 py-2.5 text-base text-text-primary placeholder:text-text-secondary/60 transition focus:border-accent focus:outline-none focus:ring-2 focus:ring-focus/30 font-medium"
                />
              </div>
            </div>

            {/* Privacy Promise */}
            <div className="rounded-xl border border-status-success/20 bg-status-success/10 p-3 flex items-start gap-2.5 text-xs text-status-success">
              <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5 text-status-success" />
              <span className="font-medium">Genuinely private workspace. Your projects, media, and credentials are completely isolated.</span>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary-action w-full mt-2 flex items-center justify-center gap-2 rounded-xl py-3 text-base font-bold shadow-lg shadow-purple-600/30 transition hover:brightness-110 active:scale-[0.99] disabled:opacity-50 cursor-pointer"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Creating Account...</span>
                </>
              ) : (
                <>
                  <span>Create Account</span>
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </form>

          {/* Footer switch to Login */}
          <div className="mt-6 text-center font-body">
            <p className="text-xs text-text-secondary font-medium">
              Already have an account?{' '}
              <Link href="/login" className="font-bold text-accent hover:underline">
                Sign in
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
