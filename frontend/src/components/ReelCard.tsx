'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { Download, Sliders, Play, Sparkles, Loader2, CheckCircle2, AlertCircle, Trash2, Maximize2, X } from 'lucide-react';
import { Reel } from '@/lib/types';
import { api } from '@/lib/api';

interface ReelCardProps {
  reel: Reel;
  projectId: string;
  onDelete?: (reelId: string) => void;
}

export const ReelCard: React.FC<ReelCardProps> = ({ reel, projectId, onDelete }) => {
  const [isPlaying, setIsPlaying] = useState(false);
  const [showFullPreviewModal, setShowFullPreviewModal] = useState(false);
  const [cachedVideoUrl, setCachedVideoUrl] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const handleStartPlay = () => {
    if (reel.video_url) setCachedVideoUrl(reel.video_url);
    setIsPlaying(true);
  };

  const handleOpenModal = () => {
    if (reel.video_url) setCachedVideoUrl(reel.video_url);
    setShowFullPreviewModal(true);
  };

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
  const isHeuristic = reel.reason?.toLowerCase().includes('heuristic') || (reel as any).source === 'heuristic';

  return (
    <div className="group relative flex flex-col rounded-2xl border border-divider bg-surface overflow-hidden shadow-lg transition-all duration-300 hover:border-outline hover:shadow-xl font-body">
      {/* 9:16 Vertical Preview Container — NEAR-BLACK (#0B0C10) in BOTH themes */}
      <div className="relative aspect-[9/16] w-full bg-video-surround overflow-hidden" data-video-surround="true">
        {isReady && isPlaying ? (
          <div className="relative h-full w-full">
            <video
              src={cachedVideoUrl || reel.video_url}
              controls
              autoPlay
              playsInline
              preload="auto"
              className="h-full w-full object-cover"
              onEnded={() => setIsPlaying(false)}
            />
            {/* Inline player overlay controls */}
            <div className="absolute top-2 right-2 z-30 flex items-center gap-1.5">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  handleOpenModal();
                }}
                className="rounded-full bg-black/75 p-1.5 text-white hover:bg-black transition shadow-lg cursor-pointer hover:scale-105"
                title="Open Fullscreen Preview"
              >
                <Maximize2 className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setIsPlaying(false);
                }}
                className="rounded-full bg-black/75 p-1.5 text-white hover:bg-black transition shadow-lg cursor-pointer hover:scale-105"
                title="Close Video"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        ) : (
          <div className="relative h-full w-full">
            {reel.thumbnail_url ? (
              <img
                src={reel.thumbnail_url}
                alt={reel.title}
                className="h-full w-full object-cover transition duration-300 group-hover:scale-105"
              />
            ) : (
              <div className="flex h-full w-full flex-col items-center justify-center p-4 text-center bg-video-surround">
                <div className="rounded-xl bg-surface-raised p-3 text-accent mb-2">
                  <Play className="h-6 w-6" />
                </div>
                <span className="text-xs font-semibold text-text-secondary">
                  {reel.render_status === 'rendering' ? `Rendering (${Math.round(reel.render_progress)}%)...` : 'Preview Pending'}
                </span>
              </div>
            )}

            {/* Burned top caption preview overlay */}
            <div className="absolute top-4 left-3 right-3 z-10 text-center pointer-events-none">
              <span className="inline-block rounded-lg bg-black/80 px-2.5 py-1 text-[11px] font-black tracking-wide text-white shadow-md border border-white/10 uppercase line-clamp-2">
                {reel.top_caption}
              </span>
            </div>

            {/* Play Button Overlay */}
            {isReady && (
              <button
                type="button"
                onClick={handleStartPlay}
                className="absolute inset-0 m-auto flex h-14 w-14 items-center justify-center rounded-full bg-primary text-primary-text shadow-xl backdrop-blur-sm transition duration-300 group-hover:scale-110 hover:bg-primary-hover cursor-pointer z-10"
                title="Play Video Clip"
              >
                <Play className="h-6 w-6 fill-current ml-0.5" />
              </button>
            )}

            {/* Status overlay when rendering */}
            {reel.render_status === 'rendering' && (
              <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/80 p-4 text-center">
                <Loader2 className="h-8 w-8 animate-spin text-accent mb-2" />
                <span className="text-xs font-bold text-white">Rendering MP4 Reel</span>
                <span className="text-[10px] text-slate-300 mt-1">{Math.round(reel.render_progress)}% complete</span>
              </div>
            )}

            {/* Duration Pill */}
            <div className="absolute bottom-3 right-3 rounded-md bg-black/80 px-2 py-0.5 text-[10px] font-bold text-white font-mono backdrop-blur-sm timecode-digits">
              {Math.round(reel.clip_duration)}s
            </div>

            {/* Source range pill */}
            <div className="absolute bottom-3 left-3 rounded-md bg-black/80 px-2 py-0.5 text-[10px] font-medium text-slate-200 font-mono backdrop-blur-sm timecode-digits">
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

        {/* Category Pill and Heuristic Fallback Pill */}
        <div className="absolute top-3 left-3 z-20 flex flex-col gap-1 items-start">
          <span className="rounded-full bg-black/75 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-accent border border-white/10 backdrop-blur-sm">
            {reel.category}
          </span>
          {isHeuristic && (
            <span className="rounded-full bg-status-warning/20 text-status-warning border border-status-warning/30 px-2 py-0.5 text-[9px] font-bold flex items-center gap-1 backdrop-blur-sm shadow">
              <AlertCircle className="w-2.5 h-2.5" /> Heuristic
            </span>
          )}
        </div>
      </div>

      {/* Reel Card Body */}
      <div className="flex flex-1 flex-col p-4 space-y-3">
        <div>
          <h3 className="font-heading text-base font-normal text-text-primary line-clamp-2 leading-snug">
            {reel.title}
          </h3>
          <p className="mt-1 text-xs text-text-secondary line-clamp-2 italic font-medium">
            &ldquo;{reel.reason}&rdquo;
          </p>
        </div>

        {/* Score Breakdown Pills */}
        <div className="grid grid-cols-4 gap-1 pt-1 text-center font-body">
          <div className="rounded-lg bg-surface-raised py-1 border border-divider">
            <span className="block text-[9px] uppercase tracking-wider text-text-secondary font-semibold">Hook</span>
            <span className="text-xs font-bold text-text-primary">{Math.round(reel.score_hook)}</span>
          </div>
          <div className="rounded-lg bg-surface-raised py-1 border border-divider">
            <span className="block text-[9px] uppercase tracking-wider text-text-secondary font-semibold">Payoff</span>
            <span className="text-xs font-bold text-text-primary">{Math.round(reel.score_payoff)}</span>
          </div>
          <div className="rounded-lg bg-surface-raised py-1 border border-divider">
            <span className="block text-[9px] uppercase tracking-wider text-text-secondary font-semibold">Clarity</span>
            <span className="text-xs font-bold text-text-primary">{Math.round(reel.score_clarity)}</span>
          </div>
          <div className="rounded-lg bg-surface-raised py-1 border border-divider">
            <span className="block text-[9px] uppercase tracking-wider text-text-secondary font-semibold">Fun</span>
            <span className="text-xs font-bold text-text-primary">{Math.round(reel.score_entertainment)}</span>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="mt-auto flex flex-wrap items-center gap-1.5 pt-2 border-t border-divider">
          {isReady && (
            <button
              type="button"
              onClick={handleOpenModal}
              className="flex items-center justify-center gap-1 rounded-xl border border-divider bg-surface-raised px-2.5 py-2 text-xs font-semibold text-text-primary hover:bg-surface hover:border-outline transition cursor-pointer whitespace-nowrap shrink-0"
              title="Preview Full Video in Modal"
            >
              <Maximize2 className="h-3.5 w-3.5 text-accent shrink-0" />
              <span>Preview</span>
            </button>
          )}

          <Link
            href={`/projects/${projectId}/reels/${reel.id}`}
            className="flex-1 min-w-[70px] flex items-center justify-center gap-1.5 rounded-xl border border-divider bg-surface-raised px-2.5 py-2 text-xs font-semibold text-text-primary hover:bg-surface hover:border-outline transition whitespace-nowrap shrink-0"
          >
            <Sliders className="h-3.5 w-3.5 text-accent shrink-0" />
            <span>Edit</span>
          </Link>

          {isReady ? (
            <a
              href={api.getDownloadUrl(reel.id)}
              download
              className="btn-primary-action flex items-center justify-center gap-1.5 rounded-xl px-2.5 py-2 text-xs font-bold shadow-lg shadow-purple-600/30 transition whitespace-nowrap shrink-0"
              title="Download 1080x1920 MP4"
            >
              <Download className="h-3.5 w-3.5 shrink-0" />
              <span>Download</span>
            </a>
          ) : (
            <button
              disabled
              className="flex items-center justify-center gap-1.5 rounded-xl bg-surface-raised px-2.5 py-2 text-xs font-medium text-text-secondary cursor-not-allowed border border-divider whitespace-nowrap shrink-0"
            >
              <Loader2 className="h-3.5 w-3.5 animate-spin shrink-0" />
              <span>Rendering</span>
            </button>
          )}

          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="flex items-center justify-center p-2 rounded-xl bg-surface-raised text-text-secondary hover:bg-status-error/10 hover:text-status-error hover:border-status-error/30 border border-divider transition cursor-pointer shrink-0"
            title="Delete this reel"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Full Video Preview Modal */}
      {showFullPreviewModal && isReady && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-md p-4 animate-in fade-in duration-200"
          onClick={() => setShowFullPreviewModal(false)}
        >
          <div
            className="relative flex flex-col items-center max-w-sm sm:max-w-md w-full rounded-2xl bg-surface border border-divider shadow-2xl p-4 overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between w-full pb-3 border-b border-divider">
              <div className="flex items-center gap-2">
                <span className={`flex items-center gap-1 rounded-full bg-gradient-to-r ${getScoreColor(reel.score)} px-2 py-0.5 text-[11px] font-black shadow`}>
                  <Sparkles className="h-3 w-3" />
                  <span>{Math.round(reel.score)}</span>
                </span>
                <h4 className="font-heading text-sm font-bold text-text-primary truncate max-w-[200px] sm:max-w-[260px]">
                  {reel.title}
                </h4>
              </div>
              <button
                type="button"
                onClick={() => setShowFullPreviewModal(false)}
                className="rounded-lg p-1.5 text-text-secondary hover:text-text-primary hover:bg-surface-raised transition cursor-pointer"
                aria-label="Close Preview"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* 9:16 Full Video Canvas with Native Controls */}
            <div className="relative aspect-[9/16] w-full max-h-[68vh] my-3 rounded-xl overflow-hidden bg-black shadow-inner flex items-center justify-center">
              <video
                src={cachedVideoUrl || reel.video_url}
                controls
                autoPlay
                playsInline
                preload="auto"
                className="h-full w-full object-contain"
              />
            </div>

            {/* Modal Footer */}
            <div className="flex items-center justify-between w-full pt-2 border-t border-divider text-xs text-text-secondary">
              <div className="flex items-center gap-2 font-mono">
                <span className="text-text-primary font-bold">
                  Duration: {Math.round(reel.clip_duration)}s
                </span>
                <span>•</span>
                <span>{formatTime(reel.source_start)} - {formatTime(reel.source_end)}</span>
              </div>
              <a
                href={api.getDownloadUrl(reel.id)}
                download
                className="btn-primary-action flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold shadow transition"
              >
                <Download className="h-3.5 w-3.5" />
                Download
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Overlay */}
      {showDeleteConfirm && (
        <div className="absolute inset-0 z-40 flex flex-col items-center justify-center bg-surface/95 p-6 text-center backdrop-blur-md animate-in fade-in duration-150">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-status-error/10 text-status-error mb-3 border border-status-error/20 shadow-lg shadow-red-500/10">
            <Trash2 className="h-6 w-6" />
          </div>
          <h4 className="font-heading text-lg font-normal text-text-primary mb-1">Delete Reel?</h4>
          <p className="text-xs text-text-secondary mb-4 line-clamp-2 font-medium">
            Are you sure you want to permanently delete &ldquo;{reel.title}&rdquo;?
          </p>
          {deleteError && (
            <p className="text-[11px] text-status-error mb-3 font-medium bg-status-error/10 p-2 rounded border border-status-error/20">
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
              className="flex-1 rounded-xl border border-divider bg-surface-raised py-2 text-xs font-semibold text-text-secondary hover:bg-surface hover:text-text-primary transition disabled:opacity-50 cursor-pointer"
            >
              Cancel
            </button>
            <button
              onClick={handleDelete}
              disabled={isDeleting}
              className="flex-1 flex items-center justify-center gap-1.5 rounded-xl bg-status-error py-2 text-xs font-bold text-white hover:brightness-110 transition shadow-lg shadow-red-600/30 disabled:opacity-50 cursor-pointer"
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
