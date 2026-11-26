'use client';

import React, { useEffect, useState } from 'react';
import { Sparkles, ExternalLink, X, Info } from 'lucide-react';
import { api } from '@/lib/api';

export const GeminiKeyBanner: React.FC = () => {
  const [isConfigured, setIsConfigured] = useState<boolean | null>(null);
  const [isDismissed, setIsDismissed] = useState(false);

  useEffect(() => {
    api.getAiStatus()
      .then((res) => setIsConfigured(res.is_configured))
      .catch(() => setIsConfigured(false));
  }, []);

  if (isConfigured === null || isConfigured === true || isDismissed) {
    return null;
  }

  return (
    <div className="relative border-b border-indigo-500/20 bg-gradient-to-r from-indigo-950/60 via-slate-900 to-slate-950 px-4 py-3 text-sm text-slate-300">
      <div className="mx-auto flex max-w-7xl items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 rounded-lg bg-indigo-500/10 p-1.5 text-indigo-400 border border-indigo-500/20">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <p className="font-medium text-white">
              Running in High-Precision Heuristic Mode
            </p>
            <p className="text-xs text-slate-400 mt-0.5">
              Reel Studio is currently generating candidate reels using audio peak and speech density heuristics. To enable LLM evaluation and Gemini titles, create an API key at{' '}
              <a
                href="https://aistudio.google.com/apikey"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 font-medium text-indigo-400 hover:text-indigo-300 underline"
              >
                Google AI Studio <ExternalLink className="h-3 w-3" />
              </a>{' '}
              and set <code className="rounded bg-slate-800 px-1 py-0.5 text-indigo-300 font-mono">GEMINI_API_KEY</code> in your <code className="rounded bg-slate-800 px-1 py-0.5 text-slate-300 font-mono">.env</code> file.
            </p>
          </div>
        </div>
        <button
          onClick={() => setIsDismissed(true)}
          className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};
