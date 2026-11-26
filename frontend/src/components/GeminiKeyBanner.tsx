'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { Sparkles, ArrowRight, X, KeyRound } from 'lucide-react';
import { api } from '@/lib/api';

export const GeminiKeyBanner: React.FC = () => {
  const [isConfigured, setIsConfigured] = useState<boolean | null>(null);
  const [isDismissed, setIsDismissed] = useState(false);

  useEffect(() => {
    // Try to get user-specific settings first, then fallback to global AI status
    api.getIntegrationsSettings()
      .then((settings) => setIsConfigured(settings.gemini_configured))
      .catch(() => {
        api.getAiStatus()
          .then((res) => setIsConfigured(res.is_configured))
          .catch(() => setIsConfigured(false));
      });
  }, []);

  if (isConfigured === null || isConfigured === true || isDismissed) {
    return null;
  }

  return (
    <div className="relative border-b border-indigo-500/20 bg-gradient-to-r from-indigo-950/70 via-slate-900 to-slate-950 px-4 py-2.5 sm:py-3 text-sm text-slate-300 overflow-hidden">
      <div className="mx-auto flex flex-col sm:flex-row sm:items-center justify-between gap-3 max-w-7xl">
        <div className="flex items-start sm:items-center gap-2.5 sm:gap-3 pr-8 sm:pr-0">
          <div className="rounded-xl bg-indigo-500/10 p-2 text-indigo-400 border border-indigo-500/20 shrink-0 mt-0.5 sm:mt-0">
            <Sparkles className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <div className="font-semibold text-white flex flex-wrap items-center gap-1.5 sm:gap-2 text-xs sm:text-sm">
              <span>Running in Heuristic Mode</span>
              <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-[9px] sm:text-[10px] font-bold uppercase text-amber-400 border border-amber-500/20 whitespace-nowrap">
                AI Inactive
              </span>
            </div>
            <p className="text-[11px] sm:text-xs text-slate-400 mt-0.5 line-clamp-2 sm:line-clamp-none">
              Candidate reels use audio & speech heuristics. Connect your personal Gemini key for AI narrative evaluation and viral titles.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-stretch sm:self-auto sm:shrink-0 justify-end">
          <Link
            href="/settings"
            className="flex-1 sm:flex-none flex items-center justify-center gap-1.5 rounded-xl bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white shadow-md shadow-indigo-600/25 hover:bg-indigo-500 transition whitespace-nowrap"
          >
            <KeyRound className="h-3.5 w-3.5" />
            <span>Configure in Settings</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
          <button
            onClick={() => setIsDismissed(true)}
            className="absolute top-2.5 right-2 sm:static sm:top-auto sm:right-auto rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white transition shrink-0"
            title="Dismiss banner"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
