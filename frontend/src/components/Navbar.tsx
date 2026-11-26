'use client';

import React, { useEffect, useState, useRef } from 'react';
import Link from 'next/link';
import {
  Film,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  Settings,
  LogOut,
  User as UserIcon,
  ChevronDown,
  LogIn,
  UserPlus,
} from 'lucide-react';
import { api } from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import { ThemeToggle } from '@/components/ThemeToggle';

export const Navbar: React.FC = () => {
  const { user, isAuthenticated, logout, isLoading: authLoading } = useAuth();
  const [geminiActive, setGeminiActive] = useState<boolean | null>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isAuthenticated) {
      api.getIntegrationsSettings()
        .then((res) => setGeminiActive(res.gemini_configured))
        .catch(() => {
          api.getAiStatus()
            .then((res) => setGeminiActive(res.is_configured))
            .catch(() => setGeminiActive(false));
        });
    } else {
      api.getAiStatus()
        .then((res) => setGeminiActive(res.is_configured))
        .catch(() => setGeminiActive(false));
    }
  }, [isAuthenticated]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const getUserInitials = () => {
    if (user?.full_name) {
      const parts = user.full_name.trim().split(' ');
      if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
      return user.full_name.substring(0, 2).toUpperCase();
    }
    if (user?.email) {
      return user.email.substring(0, 2).toUpperCase();
    }
    return 'ME';
  };

  return (
    <header className="sticky top-0 z-50 h-[6.5rem] sm:h-[7rem] border-b border-divider bg-surface/85 backdrop-blur-md transition-colors duration-200">
      <div className="mx-auto flex h-full max-w-7xl items-center justify-between px-3 sm:px-6 lg:px-8">
        <Link href="/" className="flex items-center group py-1 shrink-0" aria-label="Reel Studio Home">
          <img
            src="/logo.png"
            alt="Reel Studio"
            width={150}
            height={150}
            className="w-[110px] h-[110px] sm:w-[150px] sm:h-[150px] object-contain transition-transform duration-200 group-hover:scale-105"
          />
        </Link>

        <div className="flex items-center gap-2 sm:gap-3.5 shrink-0">
          {/* Gemini AI Status indicator (Links to /settings) */}
          <Link
            href="/settings"
            className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface-raised border border-divider text-xs transition hover:border-outline hover:bg-surface font-body font-medium whitespace-nowrap"
            title="Configure AI & OAuth Credentials in Settings"
          >
            <Sparkles className="w-3.5 h-3.5 text-accent animate-pulse" />
            <span className="text-text-secondary">Gemini AI:</span>
            {geminiActive === null ? (
              <span className="text-text-secondary">Checking...</span>
            ) : geminiActive ? (
              <span className="flex items-center gap-1 text-status-success font-semibold whitespace-nowrap">
                <CheckCircle2 className="w-3 h-3" /> Enabled
              </span>
            ) : (
              <span className="flex items-center gap-1 text-status-warning font-semibold whitespace-nowrap">
                <AlertCircle className="w-3 h-3" /> Heuristic
              </span>
            )}
          </Link>

          {/* Workers Ready Badge */}
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface-raised border border-divider text-xs font-body font-medium whitespace-nowrap">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-ping"></span>
            <span className="text-text-secondary">Workers Ready</span>
          </div>

          {/* Settings Quick Link */}
          {isAuthenticated && (
            <Link
              href="/settings"
              className="flex items-center gap-1.5 rounded-xl border border-divider bg-surface-raised px-2.5 sm:px-3 py-1.5 text-xs font-semibold text-text-secondary hover:bg-surface hover:text-text-primary hover:border-outline transition font-body whitespace-nowrap shrink-0"
              title="Workspace Settings & Integrations"
            >
              <Settings className="h-3.5 w-3.5 text-text-secondary shrink-0" />
              <span className="hidden sm:inline">Settings</span>
            </Link>
          )}

          {/* User Auth Section */}
          {!authLoading && (
            <>
              {isAuthenticated && user ? (
                <div className="relative shrink-0" ref={dropdownRef}>
                  <button
                    onClick={() => setDropdownOpen(!dropdownOpen)}
                    className="flex items-center gap-1.5 sm:gap-2 rounded-xl border border-divider bg-surface-raised px-2 sm:px-2.5 py-1.5 text-xs text-text-primary hover:border-outline transition font-body font-medium whitespace-nowrap"
                  >
                    <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary text-xs font-bold text-primary-text shadow-sm font-body shrink-0">
                      {getUserInitials()}
                    </div>
                    <span className="hidden sm:block max-w-[120px] truncate text-text-primary font-semibold">
                      {user.full_name || user.email.split('@')[0]}
                    </span>
                    <ChevronDown className={`h-3.5 w-3.5 text-text-secondary transition-transform shrink-0 ${dropdownOpen ? 'rotate-180' : ''}`} />
                  </button>

                  {/* Dropdown Menu */}
                  {dropdownOpen && (
                    <div className="absolute right-0 mt-2 w-56 rounded-2xl border border-divider bg-surface p-2 shadow-2xl backdrop-blur-xl animate-in fade-in zoom-in-95 duration-150 z-50">
                      <div className="px-3 py-2 border-b border-divider mb-1">
                        <p className="text-xs font-bold text-text-primary truncate font-body">{user.full_name || 'Creator'}</p>
                        <p className="text-[11px] text-text-secondary truncate font-body">{user.email}</p>
                      </div>

                      <Link
                        href="/settings"
                        onClick={() => setDropdownOpen(false)}
                        className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-xs font-semibold text-text-secondary hover:bg-surface-raised hover:text-text-primary transition font-body"
                      >
                        <Settings className="h-4 w-4 text-accent" />
                        Settings & Integrations
                      </Link>

                      <button
                        onClick={() => {
                          setDropdownOpen(false);
                          logout();
                        }}
                        className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-xs font-semibold text-status-error hover:bg-status-error/10 transition mt-1 font-body"
                      >
                        <LogOut className="h-4 w-4" />
                        Sign Out
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <Link
                    href="/login"
                    className="flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-semibold text-text-secondary hover:text-text-primary hover:bg-surface-raised transition font-body"
                  >
                    <LogIn className="h-3.5 w-3.5" />
                    Sign In
                  </Link>
                  <Link
                    href="/signup"
                    className="flex items-center gap-1.5 rounded-xl bg-primary px-3.5 py-2 text-xs font-bold text-primary-text shadow-lg shadow-purple-600/30 hover:bg-primary-hover transition font-body"
                  >
                    <UserPlus className="h-3.5 w-3.5" />
                    Sign Up
                  </Link>
                </div>
              )}
            </>
          )}

          {/* Theme Toggle (Accessible on all screen sizes) */}
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
};
