'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Sparkles,
  Youtube,
  Key,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  ExternalLink,
  Copy,
  Check,
  Trash2,
  RefreshCw,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  HardDrive,
  Cpu,
  User,
  ArrowLeft,
  Loader2,
  Lock,
  Eye,
  EyeOff,
  Video,
} from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { api, API_BASE } from '@/lib/api';
import { IntegrationsSettings, SocialAccount } from '@/lib/types';

export default function SettingsPage() {
  const router = useRouter();
  const { user, isLoading: authLoading } = useAuth();

  const [settingsData, setSettingsData] = useState<IntegrationsSettings | null>(null);
  const [socialAccounts, setSocialAccounts] = useState<SocialAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'integrations' | 'workspace'>('integrations');

  // Gemini state
  const [geminiKeyInput, setGeminiKeyInput] = useState('');
  const [showGeminiKey, setShowGeminiKey] = useState(false);
  const [isReplacingGemini, setIsReplacingGemini] = useState(false);
  const [geminiActionLoading, setGeminiActionLoading] = useState(false);
  const [geminiFeedback, setGeminiFeedback] = useState<{ type: 'success' | 'error' | 'warning'; message: string } | null>(null);
  const [showGeminiGuide, setShowGeminiGuide] = useState(false);

  // YouTube OAuth state
  const [youtubeClientIdInput, setYoutubeClientIdInput] = useState('');
  const [youtubeClientSecretInput, setYoutubeClientSecretInput] = useState('');
  const [showYoutubeSecret, setShowYoutubeSecret] = useState(false);
  const [isReplacingYoutube, setIsReplacingYoutube] = useState(false);
  const [youtubeActionLoading, setYoutubeActionLoading] = useState(false);
  const [youtubeFeedback, setYoutubeFeedback] = useState<{ type: 'success' | 'error' | 'warning'; message: string } | null>(null);
  const [copiedRedirect, setCopiedRedirect] = useState(false);
  const [showYoutubeGuide, setShowYoutubeGuide] = useState(false);
  const [showYoutubeTroubleshooting, setShowYoutubeTroubleshooting] = useState(false);

  // Disconnect loading
  const [disconnectingId, setDisconnectingId] = useState<string | null>(null);

  const fetchSettings = async () => {
    try {
      const [intSettings, accounts] = await Promise.all([
        api.getIntegrationsSettings(),
        api.getSocialAccounts(),
      ]);
      setSettingsData(intSettings);
      setSocialAccounts(accounts.filter((a) => a.platform === 'youtube'));
      if (intSettings.youtube_client_id) {
        setYoutubeClientIdInput(intSettings.youtube_client_id);
      }
    } catch (err: any) {
      console.error('Failed to load settings:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!authLoading && !user) {
      router.push('/login');
      return;
    }
    if (user) {
      fetchSettings();
    }
  }, [user, authLoading, router]);

  // Copy Authorized Redirect URI
  const handleCopyRedirect = () => {
    if (!settingsData?.youtube_redirect_uri) return;
    navigator.clipboard.writeText(settingsData.youtube_redirect_uri);
    setCopiedRedirect(true);
    setTimeout(() => setCopiedRedirect(false), 2500);
  };

  // Gemini Actions
  const handleSaveGemini = async () => {
    if (!geminiKeyInput.trim()) return;
    setGeminiActionLoading(true);
    setGeminiFeedback(null);
    try {
      const res = await api.updateGeminiSettings({
        action: 'save',
        api_key: geminiKeyInput.trim(),
      });
      setGeminiFeedback({
        type: res.connection_status === 'connected' ? 'success' : 'warning',
        message: res.message || 'Gemini API key saved successfully.',
      });
      setGeminiKeyInput('');
      setIsReplacingGemini(false);
      await fetchSettings();
    } catch (err: any) {
      setGeminiFeedback({ type: 'error', message: err?.message || 'Failed to save Gemini key.' });
    } finally {
      setGeminiActionLoading(false);
    }
  };

  const handleTestGemini = async () => {
    setGeminiActionLoading(true);
    setGeminiFeedback(null);
    try {
      const res = await api.updateGeminiSettings({
        action: 'test',
        api_key: geminiKeyInput.trim() || undefined,
      });
      if (res.status === 'connected') {
        setGeminiFeedback({ type: 'success', message: res.message });
      } else if (res.status === 'quota_exhausted') {
        setGeminiFeedback({ type: 'warning', message: res.message });
      } else {
        setGeminiFeedback({ type: 'error', message: res.message });
      }
      await fetchSettings();
    } catch (err: any) {
      setGeminiFeedback({ type: 'error', message: err?.message || 'Connection test failed.' });
    } finally {
      setGeminiActionLoading(false);
    }
  };

  const handleRemoveGemini = async () => {
    if (!confirm('Are you sure you want to remove your Gemini API key? Reel Studio will revert to high-precision heuristic candidate extraction.')) return;
    setGeminiActionLoading(true);
    setGeminiFeedback(null);
    try {
      await api.updateGeminiSettings({ action: 'remove' });
      setGeminiFeedback({ type: 'success', message: 'Gemini API key removed. Using heuristic fallback.' });
      setIsReplacingGemini(false);
      setGeminiKeyInput('');
      await fetchSettings();
    } catch (err: any) {
      setGeminiFeedback({ type: 'error', message: err?.message || 'Failed to remove Gemini key.' });
    } finally {
      setGeminiActionLoading(false);
    }
  };

  // YouTube OAuth Actions
  const handleSaveYouTube = async () => {
    if (!youtubeClientIdInput.trim() || !youtubeClientSecretInput.trim()) {
      setYoutubeFeedback({ type: 'error', message: 'Both Client ID and Client Secret are required.' });
      return;
    }
    setYoutubeActionLoading(true);
    setYoutubeFeedback(null);
    try {
      const res = await api.updateYouTubeSettings({
        action: 'save',
        client_id: youtubeClientIdInput.trim(),
        client_secret: youtubeClientSecretInput.trim(),
      });
      setYoutubeFeedback({ type: 'success', message: res.message || 'YouTube OAuth credentials saved.' });
      setYoutubeClientSecretInput('');
      setIsReplacingYoutube(false);
      await fetchSettings();
    } catch (err: any) {
      setYoutubeFeedback({ type: 'error', message: err?.message || 'Failed to save YouTube credentials.' });
    } finally {
      setYoutubeActionLoading(false);
    }
  };

  const handleRemoveYouTube = async () => {
    if (!confirm('Remove your YouTube OAuth credentials? Connected YouTube channels will require reconnection.')) return;
    setYoutubeActionLoading(true);
    setYoutubeFeedback(null);
    try {
      await api.updateYouTubeSettings({ action: 'remove' });
      setYoutubeFeedback({ type: 'success', message: 'YouTube OAuth credentials removed.' });
      setYoutubeClientSecretInput('');
      setIsReplacingYoutube(false);
      await fetchSettings();
    } catch (err: any) {
      setYoutubeFeedback({ type: 'error', message: err?.message || 'Failed to remove credentials.' });
    } finally {
      setYoutubeActionLoading(false);
    }
  };

  const handleConnectYouTube = async () => {
    try {
      const res = await api.getOAuthAuthorizeUrl('youtube');
      if (res.authorize_url) {
        window.location.href = res.authorize_url;
      }
    } catch (err: any) {
      setYoutubeFeedback({ type: 'error', message: err?.message || 'Failed to initiate Google authorization.' });
    }
  };

  const handleDisconnectAccount = async (accountId: string) => {
    if (!confirm('Disconnect this YouTube channel?')) return;
    setDisconnectingId(accountId);
    try {
      await api.disconnectSocialAccount(accountId);
      await fetchSettings();
    } catch (err: any) {
      alert(`Disconnect failed: ${err?.message}`);
    } finally {
      setDisconnectingId(null);
    }
  };

  if (authLoading || loading) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
      </div>
    );
  }

  const storageUsedPercent = Math.min(
    100,
    Math.round(((settingsData?.storage_used_mb || 0) / (settingsData?.storage_limit_mb || 10240)) * 100)
  );

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8 font-body">
      {/* Top Breadcrumb & Heading */}
      <div className="mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-text-secondary hover:text-text-primary transition mb-2"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Back to Dashboard
          </Link>
          <h1 className="font-heading text-3xl sm:text-4xl font-bold tracking-tight text-text-primary">Settings &amp; Integrations</h1>
          <p className="font-body text-sm text-text-secondary mt-0.5 font-medium">
            Manage your AI quota, Google Cloud OAuth credentials, and private workspace limits
          </p>
        </div>

        {/* Tab Navigation */}
        <div className="flex flex-wrap rounded-xl bg-surface-raised border border-divider p-1">
          <button
            onClick={() => setActiveTab('integrations')}
            className={`flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-xs font-bold transition cursor-pointer whitespace-nowrap shrink-0 ${
              activeTab === 'integrations'
                ? 'bg-selected text-accent border border-accent/40 shadow-sm'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            <Sparkles className="h-3.5 w-3.5 shrink-0" />
            <span className="whitespace-nowrap">Integrations</span>
          </button>
          <button
            onClick={() => setActiveTab('workspace')}
            className={`flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-xs font-bold transition cursor-pointer whitespace-nowrap shrink-0 ${
              activeTab === 'workspace'
                ? 'bg-selected text-accent border border-accent/40 shadow-sm'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            <HardDrive className="h-3.5 w-3.5 shrink-0" />
            <span className="whitespace-nowrap">Workspace &amp; Quotas</span>
          </button>
        </div>
      </div>

      {activeTab === 'integrations' && (
        <div className="space-y-8">
          {/* ========================================================================= */}
          {/* SECTION 1: GOOGLE AI STUDIO (GEMINI)                                      */}
          {/* ========================================================================= */}
          <div className="rounded-2xl border border-divider bg-surface p-6 shadow-xl backdrop-blur-md">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-6 border-b border-divider">
              <div className="flex items-start gap-3.5">
                <div className="rounded-xl bg-primary p-2.5 text-white shadow-md shadow-primary/20 shrink-0">
                  <Sparkles className="h-5 w-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2.5">
                    <h2 className="font-heading text-xl font-bold text-text-primary">Google AI Studio (Gemini)</h2>
                    {settingsData?.gemini_status === 'connected' && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-status-success/10 px-2.5 py-0.5 text-xs font-semibold text-status-success border border-status-success/20">
                        <CheckCircle2 className="h-3 w-3" /> Connected
                      </span>
                    )}
                    {settingsData?.gemini_status === 'quota_exhausted' && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-status-warning/10 px-2.5 py-0.5 text-xs font-semibold text-status-warning border border-status-warning/20">
                        <AlertTriangle className="h-3 w-3" /> Quota Exhausted
                      </span>
                    )}
                    {settingsData?.gemini_status === 'invalid' && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-status-error/10 px-2.5 py-0.5 text-xs font-semibold text-status-error border border-status-error/20">
                        <AlertCircle className="h-3 w-3" /> Invalid Key
                      </span>
                    )}
                    {(!settingsData?.gemini_configured || settingsData?.gemini_status === 'not_configured') && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-surface-raised px-2.5 py-0.5 text-xs font-medium text-text-secondary border border-divider">
                        Not Configured (Heuristic Mode Active)
                      </span>
                    )}
                  </div>
                  <p className="font-body text-xs text-text-secondary mt-1">
                    Extract viral hooks, rate punchlines, transliterate to Roman Urdu/Hinglish, and generate hashtag SEO using your own Google quota.
                  </p>
                </div>
              </div>

              {/* Guide Accordion Toggle */}
              <button
                onClick={() => setShowGeminiGuide(!showGeminiGuide)}
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-accent hover:text-focus transition whitespace-nowrap shrink-0 self-start lg:self-auto"
              >
                <HelpCircle className="h-4 w-4 shrink-0" />
                <span className="whitespace-nowrap">How to get your Gemini API key</span>
                {showGeminiGuide ? <ChevronUp className="h-3.5 w-3.5 shrink-0" /> : <ChevronDown className="h-3.5 w-3.5 shrink-0" />}
              </button>
            </div>

            {/* Expandable Step-by-Step Guide */}
            {showGeminiGuide && (
              <div className="my-5 rounded-xl border border-accent/20 bg-selected/30 p-5 text-sm text-text-primary animate-in fade-in duration-200">
                <h4 className="font-semibold text-text-primary mb-3 flex items-center gap-2">
                  <Key className="h-4 w-4 text-accent" /> Step-by-Step: Obtaining your Free Gemini API Key
                </h4>
                <ol className="space-y-2.5 text-xs text-text-secondary list-decimal list-inside pl-1 font-body">
                  <li>
                    Open{' '}
                    <a
                      href="https://aistudio.google.com/apikey"
                      target="_blank"
                      rel="noreferrer"
                      className="font-medium text-accent hover:text-focus underline inline-flex items-center gap-0.5"
                    >
                      https://aistudio.google.com/apikey <ExternalLink className="h-3 w-3" />
                    </a>{' '}
                    in your web browser.
                  </li>
                  <li>Sign in with your standard Google Account.</li>
                  <li>Click the blue <strong>"Create API key"</strong> button. If prompted, select or import your Google Cloud project (or choose "Create API key in new project").</li>
                  <li>Copy the newly generated API key string (starts with <code>AIzaSy...</code>).</li>
                  <li>Paste the key into the input field below, click <strong>"Save Key"</strong>, and then click <strong>"Test Connection"</strong>.</li>
                </ol>

                <div className="mt-4 pt-3 border-t border-accent/20 text-xs text-text-secondary font-body">
                  <strong className="text-text-primary">Which Reel Studio actions use your Google quota?</strong>
                  <ul className="mt-1 list-disc list-inside space-y-0.5 text-text-secondary">
                    <li>Highlight Discovery & Multi-Candidate Extraction (~1,500 tokens per 5-minute video chunk)</li>
                    <li>Entertainment, Hook, and Payoff Scoring (0-100 evaluation)</li>
                    <li>Automatic Roman Urdu / Hinglish transliteration for karaoke subtitles</li>
                    <li>Contextual Gaming SEO Hashtag generation</li>
                  </ul>
                  <p className="mt-2 text-accent">
                    <em>Tip: Manual timeline clipping, framing adjustment, rendering, and MP4 downloads remain 100% free and work even without a Gemini key!</em>
                  </p>
                </div>
              </div>
            )}

            {/* Feedback Alert */}
            {geminiFeedback && (
              <div
                className={`my-4 flex items-start gap-3 rounded-xl p-3.5 text-xs font-body ${
                  geminiFeedback.type === 'success'
                    ? 'border border-status-success/30 bg-status-success/10 text-status-success'
                    : geminiFeedback.type === 'warning'
                    ? 'border border-status-warning/30 bg-status-warning/10 text-status-warning'
                    : 'border border-status-error/30 bg-status-error/10 text-status-error'
                }`}
              >
                {geminiFeedback.type === 'success' && <CheckCircle2 className="h-4 w-4 shrink-0 text-status-success mt-0.5" />}
                {geminiFeedback.type === 'warning' && <AlertTriangle className="h-4 w-4 shrink-0 text-status-warning mt-0.5" />}
                {geminiFeedback.type === 'error' && <AlertCircle className="h-4 w-4 shrink-0 text-status-error mt-0.5" />}
                <div>{geminiFeedback.message}</div>
              </div>
            )}

            {/* Saved Key State Display */}
            {settingsData?.gemini_configured && !isReplacingGemini ? (
              <div className="mt-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-xl border border-divider bg-surface-raised p-4 font-body">
                <div className="flex items-center gap-3">
                  <div className="rounded-lg bg-selected p-2 text-accent border border-accent/20">
                    <Lock className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="text-xs font-semibold text-text-secondary uppercase tracking-wider">Configured Gemini API Key</div>
                    <div className="font-mono text-sm font-semibold text-text-primary mt-0.5">
                      {settingsData.gemini_key_masked}
                    </div>
                    {settingsData.gemini_last_tested_at && (
                      <div className="text-[11px] text-text-secondary mt-0.5">
                        Last tested: {new Date(settingsData.gemini_last_tested_at).toLocaleString()}
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <button
                    onClick={handleTestGemini}
                    disabled={geminiActionLoading}
                    className="flex items-center gap-1.5 rounded-lg border border-divider bg-surface px-3 py-1.5 text-xs font-semibold text-text-primary hover:bg-surface-raised transition disabled:opacity-50 cursor-pointer whitespace-nowrap shrink-0"
                  >
                    {geminiActionLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin shrink-0" /> : <RefreshCw className="h-3.5 w-3.5 shrink-0" />}
                    <span className="whitespace-nowrap">Test Connection</span>
                  </button>
                  <button
                    onClick={() => setIsReplacingGemini(true)}
                    className="rounded-lg border border-divider bg-surface px-3 py-1.5 text-xs font-semibold text-text-secondary hover:text-text-primary hover:bg-surface-raised transition cursor-pointer whitespace-nowrap shrink-0"
                  >
                    Replace Key
                  </button>
                  <button
                    onClick={handleRemoveGemini}
                    disabled={geminiActionLoading}
                    className="flex items-center gap-1 rounded-lg border border-status-error/20 bg-status-error/10 px-3 py-1.5 text-xs font-semibold text-status-error hover:bg-status-error/20 transition cursor-pointer whitespace-nowrap shrink-0"
                  >
                    <Trash2 className="h-3.5 w-3.5 shrink-0" /> <span className="whitespace-nowrap">Remove</span>
                  </button>
                </div>
              </div>
            ) : (
              /* Input Form for adding or replacing key */
              <div className="mt-6 space-y-4 font-body">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-text-secondary mb-1.5">
                    {isReplacingGemini ? 'Enter New Gemini API Key' : 'Enter Gemini API Key'}
                  </label>
                  <div className="relative">
                    <input
                      type={showGeminiKey ? 'text' : 'password'}
                      value={geminiKeyInput}
                      onChange={(e) => setGeminiKeyInput(e.target.value)}
                      placeholder="AIzaSy..."
                      className="w-full rounded-xl border border-outline bg-surface-raised px-4 py-2.5 pr-10 text-sm font-mono text-text-primary placeholder:text-text-secondary/50 transition focus:border-focus focus:outline-none focus:ring-1 focus:ring-focus"
                    />
                    <button
                      type="button"
                      onClick={() => setShowGeminiKey(!showGeminiKey)}
                      className="absolute inset-y-0 right-0 flex items-center pr-3 text-text-secondary hover:text-text-primary"
                    >
                      {showGeminiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <button
                    onClick={handleSaveGemini}
                    disabled={geminiActionLoading || !geminiKeyInput.trim()}
                    className="btn-primary-action flex items-center gap-1.5 cursor-pointer disabled:opacity-50 whitespace-nowrap shrink-0"
                  >
                    {geminiActionLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin shrink-0" /> : <Check className="h-3.5 w-3.5 shrink-0" />}
                    <span className="whitespace-nowrap">Save &amp; Test Key</span>
                  </button>
                  {isReplacingGemini && (
                    <button
                      onClick={() => {
                        setIsReplacingGemini(false);
                        setGeminiKeyInput('');
                      }}
                      className="rounded-xl border border-divider px-4 py-2 text-xs font-semibold text-text-secondary hover:text-text-primary transition cursor-pointer whitespace-nowrap shrink-0"
                    >
                      Cancel
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* ========================================================================= */}
          {/* SECTION 2: YOUTUBE (GOOGLE CLOUD OAUTH)                                   */}
          {/* ========================================================================= */}
          <div className="rounded-2xl border border-divider bg-surface p-6 shadow-xl backdrop-blur-md">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-6 border-b border-divider">
              <div className="flex items-start gap-3.5">
                <div className="rounded-xl bg-red-600 p-2.5 text-white shadow-md shadow-red-500/20 shrink-0">
                  <Youtube className="h-5 w-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2.5">
                    <h2 className="font-heading text-xl font-bold text-text-primary">YouTube (Google Cloud OAuth)</h2>
                    {settingsData?.youtube_configured ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-status-success/10 px-2.5 py-0.5 text-xs font-semibold text-status-success border border-status-success/20">
                        <CheckCircle2 className="h-3 w-3" /> Credentials Configured
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full bg-surface-raised px-2.5 py-0.5 text-xs font-medium text-text-secondary border border-divider">
                        Not Configured
                      </span>
                    )}
                  </div>
                  <p className="font-body text-xs text-text-secondary mt-1">
                    Connect your own YouTube channels and publish Shorts directly using your personal Google Cloud OAuth app.
                  </p>
                </div>
              </div>

              {/* Guide Accordion Toggle */}
              <button
                onClick={() => setShowYoutubeGuide(!showYoutubeGuide)}
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-accent hover:text-focus transition whitespace-nowrap shrink-0 self-start lg:self-auto"
              >
                <HelpCircle className="h-4 w-4 shrink-0" />
                <span className="whitespace-nowrap">Google Console Setup Guide</span>
                {showYoutubeGuide ? <ChevronUp className="h-3.5 w-3.5 shrink-0" /> : <ChevronDown className="h-3.5 w-3.5 shrink-0" />}
              </button>
            </div>

            {/* Numbered Setup Guide (Exact Prompt Instructions) */}
            {showYoutubeGuide && (
              <div className="my-5 rounded-xl border border-accent/20 bg-selected/30 p-5 text-sm text-text-primary animate-in fade-in duration-200">
                <h4 className="font-semibold text-text-primary mb-3 flex items-center gap-2 font-body">
                  <ShieldCheck className="h-4 w-4 text-accent" /> Step-by-Step: Setting Up Your Google Cloud OAuth Client
                </h4>
                <ol className="space-y-2.5 text-xs text-text-secondary list-decimal list-inside pl-1 font-body">
                  <li>
                    Open{' '}
                    <a
                      href="https://console.cloud.google.com"
                      target="_blank"
                      rel="noreferrer"
                      className="font-medium text-accent hover:text-focus underline inline-flex items-center gap-0.5"
                    >
                      Google Cloud Console <ExternalLink className="h-3 w-3" />
                    </a>{' '}
                    and create or select a project.
                  </li>
                  <li>Open <strong>APIs & Services → Library</strong> and enable <strong>YouTube Data API v3</strong>.</li>
                  <li>
                    Configure <strong>Google Auth Platform branding</strong>, audience, and the scopes required by Reel Studio (<code>https://www.googleapis.com/auth/youtube.upload</code> and <code>https://www.googleapis.com/auth/youtube.readonly</code>). If using <strong>External / Testing</strong>, add the Google account that owns the channel as a <strong>Test User</strong>.
                  </li>
                  <li>Go to <strong>Credentials → Create Credentials → OAuth client ID</strong> and choose the <strong>Web application</strong> type.</li>
                  <li>Copy the <strong>Authorized redirect URI</strong> displayed in Reel Studio below into <strong>Authorized redirect URIs</strong> in Google Cloud Console and save.</li>
                  <li>Paste your <strong>Client ID</strong> and <strong>Client Secret</strong> into Reel Studio below and save.</li>
                  <li>Click <strong>Connect YouTube Channel</strong>, complete Google consent, and confirm the channel name, handle, and avatar shown in Reel Studio.</li>
                </ol>
              </div>
            )}

            {/* Read-only Authorized Redirect URI */}
            <div className="my-5 rounded-xl border border-divider bg-surface-raised p-4 font-body">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <div className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
                    Authorized redirect URI (Read-only)
                  </div>
                  <p className="text-[11px] text-text-secondary mt-0.5">
                    Must match exactly in your Google Cloud Console Web Application settings:
                  </p>
                  <code className="mt-1 block font-mono text-xs text-accent break-all bg-surface px-2 py-1 rounded border border-divider">
                    {settingsData?.youtube_redirect_uri || `${API_BASE}/api/social/youtube/callback`}
                  </code>
                </div>
                <button
                  onClick={handleCopyRedirect}
                  className="flex items-center gap-1.5 self-start sm:self-center shrink-0 rounded-lg border border-divider bg-surface px-3.5 py-2 text-xs font-semibold text-text-primary hover:bg-surface-raised transition cursor-pointer"
                >
                  {copiedRedirect ? (
                    <>
                      <Check className="h-3.5 w-3.5 text-status-success" />
                      <span className="text-status-success">Copied!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="h-3.5 w-3.5" />
                      <span>Copy URI</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Feedback Alert */}
            {youtubeFeedback && (
              <div
                className={`my-4 flex items-start gap-3 rounded-xl p-3.5 text-xs font-body ${
                  youtubeFeedback.type === 'success'
                    ? 'border border-status-success/30 bg-status-success/10 text-status-success'
                    : youtubeFeedback.type === 'warning'
                    ? 'border border-status-warning/30 bg-status-warning/10 text-status-warning'
                    : 'border border-status-error/30 bg-status-error/10 text-status-error'
                }`}
              >
                {youtubeFeedback.type === 'success' && <CheckCircle2 className="h-4 w-4 shrink-0 text-status-success mt-0.5" />}
                {youtubeFeedback.type === 'warning' && <AlertTriangle className="h-4 w-4 shrink-0 text-status-warning mt-0.5" />}
                {youtubeFeedback.type === 'error' && <AlertCircle className="h-4 w-4 shrink-0 text-status-error mt-0.5" />}
                <div>{youtubeFeedback.message}</div>
              </div>
            )}

            {/* Saved Credentials Display */}
            {settingsData?.youtube_configured && !isReplacingYoutube ? (
              <div className="space-y-4 font-body">
                <div className="rounded-xl border border-divider bg-surface-raised p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="space-y-1">
                    <div className="text-xs font-semibold text-text-secondary uppercase tracking-wider">Configured Google OAuth Client</div>
                    <div className="text-xs font-mono text-text-primary break-all">
                      <span className="text-text-secondary">Client ID:</span> {settingsData.youtube_client_id}
                    </div>
                    <div className="text-xs font-mono text-text-secondary">
                      <span>Secret:</span> {settingsData.youtube_secret_masked}
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      onClick={() => setIsReplacingYoutube(true)}
                      className="rounded-lg border border-divider bg-surface px-3 py-1.5 text-xs font-semibold text-text-secondary hover:text-text-primary hover:bg-surface-raised transition cursor-pointer whitespace-nowrap shrink-0"
                    >
                      Replace Credentials
                    </button>
                    <button
                      onClick={handleRemoveYouTube}
                      disabled={youtubeActionLoading}
                      className="flex items-center gap-1 rounded-lg border border-status-error/20 bg-status-error/10 px-3 py-1.5 text-xs font-semibold text-status-error hover:bg-status-error/20 transition cursor-pointer whitespace-nowrap shrink-0"
                    >
                      <Trash2 className="h-3.5 w-3.5 shrink-0" /> <span className="whitespace-nowrap">Remove</span>
                    </button>
                  </div>
                </div>

                {/* Connect YouTube Channel Trigger */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-xl border border-divider bg-surface-raised">
                  <div>
                    <h4 className="text-sm font-bold text-text-primary font-body">Connect Channel via Google Consent</h4>
                    <p className="text-xs text-text-secondary mt-0.5">
                      Authorize Reel Studio to upload approved vertical Reels directly to your channel.
                    </p>
                  </div>
                  <button
                    onClick={handleConnectYouTube}
                    className="flex items-center gap-2 rounded-xl bg-red-600 px-4 py-2.5 text-xs font-bold text-white shadow-lg shadow-red-600/25 hover:bg-red-500 transition cursor-pointer whitespace-nowrap shrink-0"
                  >
                    <Youtube className="h-4 w-4 shrink-0" />
                    <span className="whitespace-nowrap">Connect YouTube Channel</span>
                  </button>
                </div>

                {/* Connected Channels List */}
                {socialAccounts.length > 0 && (
                  <div className="mt-4">
                    <h4 className="text-xs font-semibold uppercase tracking-wider text-text-secondary mb-2">
                      Connected Channels ({socialAccounts.length})
                    </h4>
                    <div className="space-y-2">
                      {socialAccounts.map((account) => (
                        <div
                          key={account.id}
                          className="flex items-center justify-between gap-4 rounded-xl border border-divider bg-surface-raised p-3"
                        >
                          <div className="flex items-center gap-3">
                            {account.profile_picture_url ? (
                              <img
                                src={account.profile_picture_url}
                                alt={account.account_name}
                                className="h-9 w-9 rounded-full object-cover border border-divider"
                              />
                            ) : (
                              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-red-600 text-white font-bold text-xs">
                                YT
                              </div>
                            )}
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-semibold text-text-primary">{account.account_name}</span>
                                {account.status === 'connected' ? (
                                  <span className="rounded-full bg-status-success/10 px-2 py-0.5 text-[10px] font-semibold text-status-success border border-status-success/20">
                                    Active
                                  </span>
                                ) : (
                                  <span className="rounded-full bg-status-warning/10 px-2 py-0.5 text-[10px] font-semibold text-status-warning border border-status-warning/20">
                                    Reconnect Required
                                  </span>
                                )}
                              </div>
                              <span className="text-xs text-text-secondary font-mono">
                                {account.account_username || account.platform_account_id}
                              </span>
                            </div>
                          </div>

                          <button
                            onClick={() => handleDisconnectAccount(account.id)}
                            disabled={disconnectingId === account.id}
                            className="text-xs font-medium text-text-secondary hover:text-status-error transition cursor-pointer"
                          >
                            {disconnectingId === account.id ? 'Disconnecting...' : 'Disconnect'}
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              /* Input Form for entering YouTube OAuth Client ID & Secret */
              <div className="space-y-4 font-body">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-text-secondary mb-1.5">
                    Google OAuth Client ID
                  </label>
                  <input
                    type="text"
                    value={youtubeClientIdInput}
                    onChange={(e) => setYoutubeClientIdInput(e.target.value)}
                    placeholder="xxxxxxxxxxxx-xxxxxxxxxxxxxxxx.apps.googleusercontent.com"
                    className="w-full rounded-xl border border-outline bg-surface-raised px-4 py-2.5 text-sm font-mono text-text-primary placeholder:text-text-secondary/50 transition focus:border-focus focus:outline-none focus:ring-1 focus:ring-focus"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-text-secondary mb-1.5">
                    Google OAuth Client Secret
                  </label>
                  <div className="relative">
                    <input
                      type={showYoutubeSecret ? 'text' : 'password'}
                      value={youtubeClientSecretInput}
                      onChange={(e) => setYoutubeClientSecretInput(e.target.value)}
                      placeholder="GOCSPX-••••••••••••••••"
                      className="w-full rounded-xl border border-outline bg-surface-raised px-4 py-2.5 pr-10 text-sm font-mono text-text-primary placeholder:text-text-secondary/50 transition focus:border-focus focus:outline-none focus:ring-1 focus:ring-focus"
                    />
                    <button
                      type="button"
                      onClick={() => setShowYoutubeSecret(!showYoutubeSecret)}
                      className="absolute inset-y-0 right-0 flex items-center pr-3 text-text-secondary hover:text-text-primary"
                    >
                      {showYoutubeSecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>

                <div className="flex items-center gap-3 pt-2">
                  <button
                    onClick={handleSaveYouTube}
                    disabled={youtubeActionLoading || !youtubeClientIdInput.trim() || !youtubeClientSecretInput.trim()}
                    className="btn-primary-action flex items-center gap-1.5 cursor-pointer disabled:opacity-50 whitespace-nowrap shrink-0"
                  >
                    {youtubeActionLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin shrink-0" /> : <Check className="h-3.5 w-3.5 shrink-0" />}
                    <span className="whitespace-nowrap">Save OAuth Credentials</span>
                  </button>
                  {isReplacingYoutube && (
                    <button
                      onClick={() => {
                        setIsReplacingYoutube(false);
                        setYoutubeClientSecretInput('');
                      }}
                      className="rounded-xl border border-divider px-4 py-2 text-xs font-semibold text-text-secondary hover:text-text-primary transition cursor-pointer whitespace-nowrap shrink-0"
                    >
                      Cancel
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* Troubleshooting Accordion */}
            <div className="mt-6 pt-4 border-t border-divider font-body">
              <button
                onClick={() => setShowYoutubeTroubleshooting(!showYoutubeTroubleshooting)}
                className="flex items-center gap-1.5 text-xs text-text-secondary hover:text-text-primary transition"
              >
                <HelpCircle className="h-3.5 w-3.5" />
                <span>Common YouTube OAuth Troubleshooting Messages</span>
                {showYoutubeTroubleshooting ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              </button>

              {showYoutubeTroubleshooting && (
                <div className="mt-3 space-y-2 text-xs text-text-secondary pl-4 border-l-2 border-divider">
                  <p>
                    <strong className="text-text-primary">Error: redirect_uri_mismatch (HTTP 400):</strong> The URL in Google Cloud Console under "Authorized redirect URIs" does not match the callback URL above character-for-character.
                  </p>
                  <p>
                    <strong className="text-text-primary">Error: Access Blocked / App has not completed verification:</strong> If your project publishing status is "Testing", you must add your Google account as a <strong>Test User</strong> under Google Auth Platform branding.
                  </p>
                  <p>
                    <strong className="text-text-primary">Video uploaded as "Private" or "Locked":</strong> Google restricts uploads from unverified developer projects to Private by default. You can change visibility directly in YouTube Studio or verify your Google Cloud project.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* ========================================================================= */}
          {/* SECTION 3: TIKTOK MANUAL PUBLISHING FLOW INFO                             */}
          {/* ========================================================================= */}
          <div className="rounded-2xl border border-divider bg-surface p-6 shadow-xl backdrop-blur-md">
            <div className="flex items-start gap-3.5">
              <div className="rounded-xl bg-surface-raised border border-divider p-2.5 text-text-primary">
                <Video className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-heading text-lg font-bold text-text-primary">TikTok Publishing</h3>
                <p className="font-body text-xs text-text-secondary mt-1">
                  TikTok publishing in Reel Studio uses our seamless <strong>Manual Preparation Flow</strong>: 1-click video MP4 download, 1-click formatted caption &amp; hashtag copy, and a direct link to the TikTok Web Upload studio. No OAuth client or developer approval required!
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: WORKSPACE & QUOTAS                                                 */}
      {/* ========================================================================= */}
      {activeTab === 'workspace' && (
        <div className="space-y-6 font-body">
          <div className="rounded-2xl border border-divider bg-surface p-6 shadow-xl backdrop-blur-md">
            <h2 className="font-heading text-xl font-bold text-text-primary mb-4 flex items-center gap-2">
              <User className="h-5 w-5 text-accent" /> Account &amp; Workspace Profile
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-body">
              <div className="rounded-xl border border-divider bg-surface-raised p-4">
                <span className="text-text-secondary block mb-1">Full Name</span>
                <span className="text-sm font-semibold text-text-primary">{user?.full_name || 'Creator'}</span>
              </div>
              <div className="rounded-xl border border-divider bg-surface-raised p-4">
                <span className="text-text-secondary block mb-1">Email Address</span>
                <span className="text-sm font-semibold text-text-primary">{user?.email}</span>
              </div>
              <div className="rounded-xl border border-divider bg-surface-raised p-4">
                <span className="text-text-secondary block mb-1">User Identifier</span>
                <span className="font-mono text-xs text-text-primary">{user?.id}</span>
              </div>
              <div className="rounded-xl border border-divider bg-surface-raised p-4">
                <span className="text-text-secondary block mb-1">Member Since</span>
                <span className="text-xs text-text-secondary">
                  {user?.created_at ? new Date(user.created_at).toLocaleDateString() : 'Active'}
                </span>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-divider bg-surface p-6 shadow-xl backdrop-blur-md">
            <h2 className="font-heading text-xl font-bold text-text-primary mb-4 flex items-center gap-2">
              <HardDrive className="h-5 w-5 text-accent" /> Storage &amp; Resource Limits
            </h2>

            <div className="space-y-4 font-body">
              <div>
                <div className="flex justify-between text-xs font-semibold mb-1.5">
                  <span className="text-text-secondary">Object Storage Quota</span>
                  <span className="text-accent font-mono timecode-digits">
                    {settingsData?.storage_used_mb || 0} MB / {settingsData?.storage_limit_mb || 10240} MB ({storageUsedPercent}%)
                  </span>
                </div>
                <div className="h-2.5 w-full rounded-full bg-surface-raised border border-divider overflow-hidden">
                  <div
                    className={`h-full transition-all duration-500 rounded-full ${
                      storageUsedPercent > 90 ? 'bg-status-error' : 'bg-primary'
                    }`}
                    style={{ width: `${storageUsedPercent}%` }}
                  />
                </div>
                <p className="text-[11px] text-text-secondary mt-1">
                  Private bucket storage dedicated to your uploaded master videos, analyzed chunks, and rendered vertical reels.
                </p>
              </div>

              <div className="pt-4 border-t border-divider grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-body">
                <div className="rounded-xl border border-divider bg-surface-raised p-4 flex items-center gap-3">
                  <div className="rounded-lg bg-selected p-2 text-accent border border-accent/20">
                    <Cpu className="h-4 w-4" />
                  </div>
                  <div>
                    <span className="text-text-secondary block">Max Concurrent Jobs</span>
                    <span className="text-sm font-semibold text-text-primary">
                      {settingsData?.max_concurrent_jobs || 2} pipelines
                    </span>
                  </div>
                </div>

                <div className="rounded-xl border border-divider bg-surface-raised p-4 flex items-center gap-3">
                  <div className="rounded-lg bg-status-success/10 p-2 text-status-success border border-status-success/20">
                    <RefreshCw className="h-4 w-4" />
                  </div>
                  <div>
                    <span className="text-text-secondary block">Active Jobs Now</span>
                    <span className="text-sm font-semibold text-text-primary">
                      {settingsData?.active_jobs_count || 0} running
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
