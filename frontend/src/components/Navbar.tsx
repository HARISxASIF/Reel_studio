'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { Film, Sparkles, CheckCircle2, AlertCircle } from 'lucide-react';
import { api } from '@/lib/api';

export const Navbar: React.FC = () => {
  const [geminiActive, setGeminiActive] = useState<boolean | null>(null);

  useEffect(() => {
    api.getAiStatus()
      .then((res) => setGeminiActive(res.is_configured))
      .catch(() => setGeminiActive(false));
  }, []);

  return (
    <header className="sticky top-0 z-50 border-b border-slate-800 bg-slate-900/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link href="/" className="flex items-center gap-3 group">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-violet-500 text-white shadow-lg shadow-indigo-500/25 transition group-hover:scale-105">
            <Film className="h-5 w-5" />
          </div>
          <div className="flex flex-col">
            <span className="text-lg font-black tracking-tight text-white flex items-center gap-1.5">
              REEL STUDIO
              <span className="rounded bg-indigo-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-400 border border-indigo-500/20">PRO</span>
            </span>
            <span className="text-xs text-slate-400">AI Vertical Reel Generator</span>
          </div>
        </Link>

        <div className="flex items-center gap-4">
          {/* Gemini AI Status indicator */}
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-800/80 border border-slate-700 text-xs">
            <Sparkles className="w-3.5 h-3.5 text-indigo-400 animate-pulse" />
            <span className="text-slate-300">Gemini AI:</span>
            {geminiActive === null ? (
              <span className="text-slate-400">Checking...</span>
            ) : geminiActive ? (
              <span className="flex items-center gap-1 text-emerald-400 font-medium">
                <CheckCircle2 className="w-3 h-3" /> Enabled
              </span>
            ) : (
              <span className="flex items-center gap-1 text-amber-400 font-medium" title="Using heuristic detection until key is added">
                <AlertCircle className="w-3 h-3" /> Heuristic Mode
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-ping"></span>
            <span className="text-xs text-slate-300 font-medium">Workers Ready</span>
          </div>
        </div>
      </div>
    </header>
  );
};
