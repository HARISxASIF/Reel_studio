'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { Download, Sliders, Play, Sparkles, Loader2, CheckCircle2, AlertCircle, Trash2 } from 'lucide-react';
import { Reel } from '@/lib/types';
import { api } from '@/lib/api';

interface ReelCardProps {
  reel: Reel;
  projectId: string;
  onDelete?: (reelId: string) => void;
}

export const ReelCard: React.FC<ReelCardProps> = ({ reel, projectId, onDelete }) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const handleDelete = async () => {
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await api.deleteReel(reel.id);
      onDelete?.(reel.id);
    } catch (err: any) {
      setDeleteError(err?.message || 'Failed to delete reel');
      setIsDeleting(false);
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'from-emerald-500 to-teal-600 text-white';
    if (score >= 70) return 'from-indigo-500 to-violet-600 text-white';
    return 'from-amber-500 to-orange-600 text-white';
  };

  const isReady = reel.render_status === 'completed' && reel.video_url;

  return (
    <div className="group relative flex flex-col rounded-2xl border border-slate-800 bg-slate-900/80 overflow-hidden shadow-xl transition-all duration-300 hover:border-slate-700 hover:shadow-2xl">
      {/* 9:16 Vertical Preview Container */}
      <div className="relative aspect-[9/16] w-full bg-slate-950 overflow-hidden">
        {isReady && isPlaying ? (
          <video
            src={reel.video_url}
            controls
            autoPlay
            playsInline
            className="h-full w-full object-cover"
            onEnded={() => setIsPlaying(false)}
          />
        ) : (
          <div className="relative h-full w-full">
            {reel.thumbnail_url ? (
              <img
                src={reel.thumbnail_url}
                alt={reel.title}
                className="h-full w-full object-cover transition duration-300 group-hover:scale-105"
              />
            ) : (
              <div className="flex h-full w-full flex-col items-center justify-center p-4 text-center bg-slate-950">
                <div className="rounded-xl bg-slate-800/80 p-3 text-indigo-400 mb-2">
                  <Play className="h-6 w-6" />
                </div>
                <span className="text-xs font-semibold text-slate-400">
                  {reel.render_status === 'rendering' ? `Rendering (${Math.round(reel.render_progress)}%)...` : 'Preview Pending'}
                </span>
              </div>
            )}

            {/* Burned top caption preview overlay */}
            <div className="absolute top-4 left-3 right-3 z-10 text-center">
              <span className="inline-block rounded-lg bg-black/80 px-2.5 py-1 text-[11px] font-black tracking-wide text-white shadow-md border border-white/10 uppercase line-clamp-2">
                {reel.top_caption}
              </span>
            </div>

            {/* Play Button Overlay */}
            {isReady && (
              <button
                onClick={() => setIsPlaying(true)}
                className="absolute inset-0 m-auto flex h-14 w-14 items-center justify-center rounded-full bg-indigo-600/90 text-white shadow-xl backdrop-blur-sm transition duration-300 group-hover:scale-110 hover:bg-indigo-500"
              >
                <Play className="h-6 w-6 fill-current ml-0.5" />
              </button>
            )}

            {/* Status overlay when rendering */}
            {reel.render_status === 'rendering' && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/70 p-4 text-center">
                <Loader2 className="h-8 w-8 animate-spin text-indigo-400 mb-2" />
                <span className="text-xs font-medium text-white">Rendering MP4 Reel</span>
                <span className="text-[10px] text-slate-400 mt-1">{Math.round(reel.render_progress)}% complete</span>
              </div>
            )}

            {/* Duration Pill */}
            <div className="absolute bottom-3 right-3 rounded-md bg-black/70 px-2 py-0.5 text-[10px] font-bold text-white font-mono backdrop-blur-sm">
              {Math.round(reel.clip_duration)}s
            </div>

            {/* Source range pill */}
            <div className="absolute bottom-3 left-3 rounded-md bg-black/70 px-2 py-0.5 text-[10px] font-medium text-slate-300 font-mono backdrop-blur-sm">
              {formatTime(reel.source_start)} - {formatTime(reel.source_end)}
            </div>
          </div>
        )}

        {/* Floating Viral Score Badge */}
        <div className="absolute top-3 right-3 z-20">
          <div className={`flex items-center gap-1 rounded-full bg-gradient-to-r ${getScoreColor(reel.score)} px-2.5 py-1 text-xs font-black shadow-lg`}>
            <Sparkles className="h-3 w-3" />
            <span>{Math.round(reel.score)}</span>
          </div>
        </div>

        {/* Category Pill */}
        <div className="absolute top-3 left-3 z-20">
          <span className="rounded-full bg-slate-900/90 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-indigo-400 border border-slate-700/60 backdrop-blur-sm">
            {reel.category}
          </span>
        </div>
      </div>

      {/* Reel Card Body */}
      <div className="flex flex-1 flex-col p-4 space-y-3">
        <div>
          <h3 className="text-sm font-bold text-white line-clamp-2 leading-snug">
            {reel.title}
          </h3>
          <p className="mt-1 text-xs text-slate-400 line-clamp-2 italic">
            "{reel.reason}"
          </p>
        </div>

        {/* Score Breakdown Pills */}
        <div className="grid grid-cols-4 gap-1 pt-1 text-center">
          <div className="rounded bg-slate-950/60 py-1 border border-slate-800">
            <span className="block text-[9px] uppercase tracking-wider text-slate-500 font-semibold">Hook</span>
            <span className="text-xs font-bold text-slate-300">{Math.round(reel.score_hook)}</span>
          </div>
          <div className="rounded bg-slate-950/60 py-1 border border-slate-800">
            <span className="block text-[9px] uppercase tracking-wider text-slate-500 font-semibold">Payoff</span>
            <span className="text-xs font-bold text-slate-300">{Math.round(reel.score_payoff)}</span>
          </div>
          <div className="rounded bg-slate-950/60 py-1 border border-slate-800">
            <span className="block text-[9px] uppercase tracking-wider text-slate-500 font-semibold">Clarity</span>
            <span className="text-xs font-bold text-slate-300">{Math.round(reel.score_clarity)}</span>
          </div>
          <div className="rounded bg-slate-950/60 py-1 border border-slate-800">
            <span className="block text-[9px] uppercase tracking-wider text-slate-500 font-semibold">Fun</span>
            <span className="text-xs font-bold text-slate-300">{Math.round(reel.score_entertainment)}</span>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="mt-auto flex items-center gap-2 pt-2 border-t border-slate-800">
          <Link
            href={`/projects/${projectId}/reels/${reel.id}`}
            className="flex-1 flex items-center justify-center gap-1.5 rounded-xl bg-slate-800 px-3 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-700 hover:text-white transition"
          >
            <Sliders className="h-3.5 w-3.5 text-indigo-400" />
            Edit Reel
          </Link>

          {isReady ? (
            <a
              href={`http://localhost:8000/api/reels/${reel.id}/download`}
              download
              className="flex items-center justify-center gap-1.5 rounded-xl bg-indigo-600 px-3 py-2 text-xs font-semibold text-white hover:bg-indigo-500 transition shadow-lg shadow-indigo-600/30"
              title="Download 1080x1920 MP4"
            >
              <Download className="h-3.5 w-3.5" />
              Download
            </a>
          ) : (
            <button
              disabled
              className="flex items-center justify-center gap-1.5 rounded-xl bg-slate-800 px-3 py-2 text-xs font-medium text-slate-500 cursor-not-allowed"
            >
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Rendering
            </button>
          )}

          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="flex items-center justify-center p-2 rounded-xl bg-slate-800/80 text-slate-400 hover:bg-rose-500/20 hover:text-rose-400 hover:border-rose-500/30 border border-transparent transition"
            title="Delete this reel"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Delete Confirmation Overlay */}
      {showDeleteConfirm && (
        <div className="absolute inset-0 z-40 flex flex-col items-center justify-center bg-slate-950/95 p-6 text-center backdrop-blur-md animate-in fade-in duration-150">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-rose-500/10 text-rose-400 mb-3 border border-rose-500/20 shadow-lg shadow-rose-500/10">
            <Trash2 className="h-6 w-6" />
          </div>
          <h4 className="text-sm font-bold text-white mb-1">Delete Reel?</h4>
          <p className="text-xs text-slate-400 mb-4 line-clamp-2">
            Are you sure you want to permanently delete "{reel.title}"?
          </p>
          {deleteError && (
            <p className="text-[11px] text-rose-400 mb-3 font-medium bg-rose-950/30 p-2 rounded border border-rose-900/40">
              {deleteError}
            </p>
          )}
          <div className="flex items-center gap-2 w-full">
            <button
              onClick={() => {
                setShowDeleteConfirm(false);
                setDeleteError(null);
              }}
              disabled={isDeleting}
              className="flex-1 rounded-xl bg-slate-800 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-700 hover:text-white transition disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              onClick={handleDelete}
              disabled={isDeleting}
              className="flex-1 flex items-center justify-center gap-1.5 rounded-xl bg-rose-600 py-2 text-xs font-semibold text-white hover:bg-rose-500 transition shadow-lg shadow-rose-600/30 disabled:opacity-50"
            >
              {isDeleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
              Delete
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
