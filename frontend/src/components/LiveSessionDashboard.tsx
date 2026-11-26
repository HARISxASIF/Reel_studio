'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  Radio,
  Clock,
  Scissors,
  StopCircle,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Sparkles,
  Layers,
  Cpu,
  ShieldCheck,
  Video,
} from 'lucide-react';
import { api } from '@/lib/api';
import { Project, LiveSession, Reel } from '@/lib/types';
import { ReelCard } from '@/components/ReelCard';

interface LiveSessionDashboardProps {
  project: Project;
  reels: Reel[];
  onRefresh: () => void;
}

export const LiveSessionDashboard: React.FC<LiveSessionDashboardProps> = ({
  project,
  reels,
  onRefresh,
}) => {
  const [session, setSession] = useState<LiveSession | null>(null);
  const [limiterStatus, setLimiterStatus] = useState<any>(null);
  const [isStopping, setIsStopping] = useState(false);
  const [isClippingManual, setIsClippingManual] = useState(false);
  const [manualClipSuccess, setManualClipSuccess] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchSessionData = async () => {
    try {
      const sess = await api.getLiveSession(project.id);
      setSession(sess);
    } catch (e: any) {
      console.error('Failed to fetch live session data:', e);
    }

    try {
      const lim = await api.getGeminiLimiter();
      setLimiterStatus(lim);
    } catch {}
  };

  useEffect(() => {
    fetchSessionData();
    const interval = setInterval(fetchSessionData, 2500);
    return () => clearInterval(interval);
  }, [project.id]);

  const handleStopCapture = async () => {
    if (!confirm('Are you sure you want to stop live clipping? This will stop new capture and drain pending analysis.')) {
      return;
    }
    setIsStopping(true);
    setErrorMsg(null);
    try {
      await api.stopLiveClipping(project.id);
      await fetchSessionData();
      onRefresh();
    } catch (e: any) {
      setErrorMsg(e.message || 'Failed to stop live capture.');
    } finally {
      setIsStopping(false);
    }
  };

  const handleManualClip = async () => {
    setIsClippingManual(true);
    setManualClipSuccess(null);
    setErrorMsg(null);
    try {
      const res = await api.clipLastSeconds(project.id, 60.0);
      setManualClipSuccess('Manual 60-second clip queued for rendering!');
      await fetchSessionData();
      onRefresh();
      setTimeout(() => setManualClipSuccess(null), 5000);
    } catch (e: any) {
      setErrorMsg(e.message || 'Failed to queue manual clip.');
    } finally {
      setIsClippingManual(false);
    }
  };

  const formatSecs = (sec?: number) => {
    if (!sec || sec < 0) return '0:00';
    const mins = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${mins}:${s.toString().padStart(2, '0')}`;
  };

  const isCapturing = session?.status === 'capturing';
  const isDraining = session?.status === 'draining';
  const isStopped = session?.status === 'stopped' || session?.status === 'ended';
  const continuousSecs = session?.continuous_buffer_seconds || 0;
  const canManualClip = continuousSecs >= 30.0;

  return (
    <div className="space-y-8">
      {/* 1. Live Session Control & Status Panel */}
      <div className="rounded-3xl border border-red-500/20 bg-gradient-to-br from-red-950/20 via-slate-900 to-slate-950 p-6 sm:p-8 shadow-2xl space-y-6">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 pb-6 border-b border-slate-800">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              {isCapturing ? (
                <div className="flex items-center gap-2 rounded-full bg-red-500/10 px-3 py-1 text-xs font-bold text-red-400 border border-red-500/30 shadow-lg shadow-red-500/10">
                  <span className="h-2.5 w-2.5 rounded-full bg-red-500 animate-ping" />
                  <span className="h-2.5 w-2.5 rounded-full bg-red-500 -ml-4" />
                  LIVE STREAM CLIPPING ACTIVE
                </div>
              ) : isDraining ? (
                <div className="flex items-center gap-2 rounded-full bg-amber-500/10 px-3 py-1 text-xs font-bold text-amber-400 border border-amber-500/30">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  DRAINING PENDING FOOTAGE
                </div>
              ) : (
                <div className="flex items-center gap-2 rounded-full bg-slate-800 px-3 py-1 text-xs font-bold text-slate-300 border border-slate-700">
                  <CheckCircle2 className="h-3.5 w-3.5 text-slate-400" />
                  LIVE SESSION {session?.status.toUpperCase() || 'STOPPED'}
                </div>
              )}

              <span className="rounded-md bg-slate-800 px-2 py-0.5 text-[11px] font-mono text-slate-400 uppercase">
                {session?.platform || 'DIRECT_HLS'}
              </span>
            </div>

            <h1 className="text-2xl font-black text-white tracking-tight">
              {project.title}
            </h1>
            <p className="text-xs text-slate-400 font-mono line-clamp-1">
              Feed: <span className="text-slate-300">{session?.feed_url}</span>
            </p>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center gap-3 shrink-0">
            {/* Clip Last 60s Button */}
            <div className="flex flex-col items-end">
              <button
                type="button"
                onClick={handleManualClip}
                disabled={!canManualClip || !isCapturing || isClippingManual}
                className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 px-5 py-3 text-xs font-bold text-white shadow-lg shadow-orange-500/20 hover:from-amber-400 hover:to-orange-500 transition disabled:opacity-50 disabled:pointer-events-none"
              >
                {isClippingManual ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Extracting Clip...
                  </>
                ) : (
                  <>
                    <Scissors className="h-4 w-4" />
                    Clip Last 60 Seconds
                  </>
                )}
              </button>
              <span className="text-[10px] text-slate-400 mt-1 font-mono">
                {canManualClip
                  ? `${continuousSecs.toFixed(0)}s buffer available`
                  : `Need 30s buffer (${continuousSecs.toFixed(0)}s/30s)`}
              </span>
            </div>

            {/* Stop Live Clipping Button */}
            {isCapturing && (
              <button
                type="button"
                onClick={handleStopCapture}
                disabled={isStopping}
                className="flex items-center gap-2 rounded-xl bg-rose-950/60 border border-rose-500/40 px-5 py-3 text-xs font-bold text-rose-300 shadow hover:bg-rose-900/60 transition disabled:opacity-50"
              >
                {isStopping ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Stopping...
                  </>
                ) : (
                  <>
                    <StopCircle className="h-4 w-4 text-rose-400" />
                    Stop Live Clipping
                  </>
                )}
              </button>
            )}
          </div>
        </div>

        {/* Feedback alerts */}
        {manualClipSuccess && (
          <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-3 text-xs text-emerald-300 flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
            <span>{manualClipSuccess}</span>
          </div>
        )}

        {errorMsg && (
          <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-300 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0 text-red-400" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Status Metrics Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-4">
          {/* Total Captured */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4 space-y-1">
            <span className="text-[11px] font-semibold uppercase text-slate-400 flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5 text-indigo-400" />
              Total Captured
            </span>
            <div className="text-xl font-black text-white font-mono">
              {formatSecs(session?.total_captured_seconds)}
            </div>
            <p className="text-[10px] text-slate-500">Continuous timeline</p>
          </div>

          {/* Rolling Buffer */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4 space-y-1">
            <span className="text-[11px] font-semibold uppercase text-slate-400 flex items-center gap-1.5">
              <Layers className="h-3.5 w-3.5 text-amber-400" />
              Rolling Buffer
            </span>
            <div className="text-xl font-black text-white font-mono">
              {formatSecs(session?.continuous_buffer_seconds)}
            </div>
            <p className="text-[10px] text-slate-500">Active memory cache</p>
          </div>

          {/* Latest Analyzed Mark */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4 space-y-1">
            <span className="text-[11px] font-semibold uppercase text-slate-400 flex items-center gap-1.5">
              <Sparkles className="h-3.5 w-3.5 text-purple-400" />
              AI Coverage Mark
            </span>
            <div className="text-xl font-black text-white font-mono">
              {formatSecs(session?.last_analyzed_timestamp)}
            </div>
            <p className="text-[10px] text-slate-500">Whisper + Gemini edge</p>
          </div>

          {/* Coverage Gaps */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4 space-y-1">
            <span className="text-[11px] font-semibold uppercase text-slate-400 flex items-center gap-1.5">
              <AlertTriangle className="h-3.5 w-3.5 text-rose-400" />
              Coverage Gaps
            </span>
            <div className={`text-xl font-black font-mono ${session?.coverage_gaps && session.coverage_gaps.length > 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
              {session?.coverage_gaps?.length || 0}
            </div>
            <p className="text-[10px] text-slate-500">
              {session?.coverage_gaps && session.coverage_gaps.length > 0 ? 'Discontinuities detected' : 'Perfect continuity'}
            </p>
          </div>

          {/* AI Status & Backlog */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4 space-y-1">
            <span className="text-[11px] font-semibold uppercase text-slate-400 flex items-center gap-1.5">
              <Cpu className="h-3.5 w-3.5 text-cyan-400" />
              AI Backlog
            </span>
            <div className="text-xl font-black text-white font-mono flex items-center gap-2">
              <span>{session?.ai_backlog_count || 0}</span>
              {session?.ai_status === 'analyzing' && (
                <span className="h-2 w-2 rounded-full bg-cyan-400 animate-ping" />
              )}
            </div>
            <p className="text-[10px] text-slate-500 capitalize">{session?.ai_status || 'idle'}</p>
          </div>

          {/* Gemini Rate Limiter */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-4 space-y-1">
            <span className="text-[11px] font-semibold uppercase text-slate-400 flex items-center gap-1.5">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
              Gemini Limiter
            </span>
            <div className="text-xs font-mono font-bold text-white pt-1">
              {limiterStatus
                ? `${limiterStatus.rpm_used}/${limiterStatus.rpm_limit} RPM`
                : '15 RPM Limit'}
            </div>
            <p className="text-[10px] text-slate-500">
              {limiterStatus?.is_rate_limited
                ? `Cooldown (${limiterStatus.cooldown_remaining_seconds}s)`
                : 'Capacity Normal'}
            </p>
          </div>
        </div>

        {/* Coverage Gap Details (if any gaps occurred) */}
        {session?.coverage_gaps && session.coverage_gaps.length > 0 && (
          <div className="rounded-2xl border border-amber-500/20 bg-amber-950/20 p-4 text-xs space-y-2">
            <div className="font-bold text-amber-300 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              Stream Interruption & Discontinuity Log
            </div>
            <div className="space-y-1 text-slate-300 font-mono text-[11px]">
              {session.coverage_gaps.map((gap, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="text-amber-400">• [{gap.start}s - {gap.end}s]</span>
                  <span>Missing {gap.duration}s: {gap.reason}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 2. Real-Time Generated Reels Gallery */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-indigo-400" />
            <h2 className="text-lg font-bold text-white">
              Generated Live Reels
            </h2>
            <span className="rounded-full bg-indigo-500/10 px-2.5 py-0.5 text-xs font-bold text-indigo-400 border border-indigo-500/20">
              {reels.length}
            </span>
          </div>

          <p className="text-xs text-slate-400">
            Reels appear here in real-time as they finish rendering.
          </p>
        </div>

        {reels.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-800 p-12 text-center space-y-3">
            <Loader2 className="mx-auto h-8 w-8 animate-spin text-indigo-500" />
            <h3 className="text-sm font-semibold text-white">Monitoring Live Stream...</h3>
            <p className="text-xs text-slate-400 max-w-md mx-auto">
              Faster-Whisper is transcribing and Gemini is evaluating viral moments across 60-second
              windows. Standalone 30–150 second reels will appear automatically.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {reels.map((reel) => (
              <ReelCard key={reel.id} reel={reel} projectId={project.id} onDelete={() => onRefresh?.()} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
