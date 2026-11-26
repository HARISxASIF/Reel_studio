'use client';

import React, { useEffect, useState, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Play,
  Pause,
  Download,
  RotateCcw,
  Sparkles,
  Crop,
  Maximize2,
  MoveHorizontal,
  Move,
  Split,
  ArrowUpDown,
  User,
  Gamepad2,
  Type,
  FileText,
  Clock,
  Loader2,
  CheckCircle2,
  Sliders,
  Layers,
  Info,
  Check,
  Trash2,
  Palette,
} from 'lucide-react';
import { api } from '@/lib/api';
import { Reel, SubtitleWord, CropBox } from '@/lib/types';
import { SourceCropSelector } from '@/components/SourceCropSelector';
import { computeEffectiveCrop, getPanTranslatePercent } from '@/lib/cropUtils';

export default function ReelEditorPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const reelId = params.reelId as string;

  const [reel, setReel] = useState<Reel | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const handleDeleteReel = async () => {
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await api.deleteReel(reelId);
      router.push(`/projects/${projectId}`);
    } catch (err: any) {
      setDeleteError(err?.message || 'Failed to delete reel');
      setIsDeleting(false);
    }
  };

  // Editable fields
  const [topCaption, setTopCaption] = useState('');
  const [framingMode, setFramingMode] = useState<'crop' | 'fit' | 'pan' | 'split'>('crop');
  const [panXOffset, setPanXOffset] = useState<number>(0.0);
  const [facecamCrop, setFacecamCrop] = useState<CropBox>({ x: 0.7, y: 0.05, width: 0.28, height: 0.35 });
  const [gameplayCrop, setGameplayCrop] = useState<CropBox>({ x: 0.0, y: 0.0, width: 1.0, height: 1.0 });
  const [splitOrder, setSplitOrder] = useState<'facecam_top' | 'gameplay_top'>('facecam_top');
  const [splitRatio, setSplitRatio] = useState<number>(0.35);
  const [sourceStart, setSourceStart] = useState<number>(0);
  const [sourceEnd, setSourceEnd] = useState<number>(35);
  const [subtitles, setSubtitles] = useState<SubtitleWord[]>([]);
  const [subtitleFontSize, setSubtitleFontSize] = useState<number>(58);
  const [subtitlePosition, setSubtitlePosition] = useState<'bottom' | 'middle' | 'top'>('bottom');
  const [subtitleYPercent, setSubtitleYPercent] = useState<number>(0.82);
  const [subtitleColor, setSubtitleColor] = useState<string>('#FFE500');
  const [subtitleFontFamily, setSubtitleFontFamily] = useState<string>('Montserrat');
  const [isRomanizing, setIsRomanizing] = useState(false);

  // Crop Adjustment & Editor State
  const [isAdjustingCrop, setIsAdjustingCrop] = useState(false);
  const [activeCropTarget, setActiveCropTarget] = useState<'facecam' | 'gameplay'>('facecam');
  const [previewMode, setPreviewMode] = useState<'live' | 'rendered'>('live');

  // Original saved framing reference to support Revert
  const originalFramingRef = useRef<{
    framingMode: 'crop' | 'fit' | 'pan' | 'split';
    panXOffset: number;
    facecamCrop: CropBox;
    gameplayCrop: CropBox;
    splitOrder: 'facecam_top' | 'gameplay_top';
    splitRatio: number;
  }>({
    framingMode: 'crop',
    panXOffset: 0.0,
    facecamCrop: { x: 0.7, y: 0.05, width: 0.28, height: 0.35 },
    gameplayCrop: { x: 0.0, y: 0.0, width: 1.0, height: 1.0 },
    splitOrder: 'facecam_top',
    splitRatio: 0.35,
  });

  const handleResetSplitScreen = () => {
    setFacecamCrop({ x: 0.7, y: 0.05, width: 0.28, height: 0.35 });
    setGameplayCrop({ x: 0.0, y: 0.0, width: 1.0, height: 1.0 });
    setSplitOrder('facecam_top');
    setSplitRatio(0.35);
    setActiveCropTarget('facecam');
    setIsAdjustingCrop(true);
    setPreviewMode('live');
  };

  const handleResetFraming = () => {
    if (framingMode === 'split') {
      handleResetSplitScreen();
    } else if (framingMode === 'pan') {
      setPanXOffset(0.0);
      setIsAdjustingCrop(true);
      setPreviewMode('live');
    } else {
      setPreviewMode('live');
    }
  };

  const handleRevertToSavedFraming = () => {
    const orig = originalFramingRef.current;
    setFramingMode(orig.framingMode);
    setPanXOffset(orig.panXOffset);
    setFacecamCrop(orig.facecamCrop);
    setGameplayCrop(orig.gameplayCrop);
    setSplitOrder(orig.splitOrder);
    setSplitRatio(orig.splitRatio);
    setIsAdjustingCrop(true);
    setPreviewMode('live');
  };

  // Video player & preview refs
  const videoRef = useRef<HTMLVideoElement>(null);
  const sourceVideoRef = useRef<HTMLVideoElement>(null);
  const sourceContainerRef = useRef<HTMLDivElement>(null);
  const previewTopVideoRef = useRef<HTMLVideoElement>(null);
  const previewBottomVideoRef = useRef<HTMLVideoElement>(null);
  const previewSingleVideoRef = useRef<HTMLVideoElement>(null);

  const [currentTime, setCurrentTime] = useState<number>(0); // relative to clip start [0, duration]
  const [isPlaying, setIsPlaying] = useState(false);
  const [naturalDims, setNaturalDims] = useState<{ width: number; height: number }>({ width: 1920, height: 1080 });

  const [loadError, setLoadError] = useState<string | null>(null);

  const fetchReel = async () => {
    if (!reelId) return;
    try {
      setLoadError(null);
      const data = await api.getReel(reelId);
      setReel(data);
      setTopCaption(data.top_caption || '');

      const initialMode = (data.framing_mode as any) || 'crop';
      const initialPan = data.pan_x_offset || 0.0;
      const initialFc = data.split_facecam_crop || { x: 0.7, y: 0.05, width: 0.28, height: 0.35 };
      const initialGp = data.split_gameplay_crop || { x: 0.0, y: 0.0, width: 1.0, height: 1.0 };
      const initialOrder = data.split_order || 'facecam_top';
      const initialRatio = data.split_ratio || 0.35;

      originalFramingRef.current = {
        framingMode: initialMode,
        panXOffset: initialPan,
        facecamCrop: initialFc,
        gameplayCrop: initialGp,
        splitOrder: initialOrder,
        splitRatio: initialRatio,
      };

      setFramingMode(initialMode);
      setPanXOffset(initialPan);
      setFacecamCrop(initialFc);
      setGameplayCrop(initialGp);
      setSplitOrder(initialOrder);
      setSplitRatio(initialRatio);

      // Auto-open workspace when in split or pan mode
      if (initialMode === 'split' || initialMode === 'pan') {
        setIsAdjustingCrop(true);
      }

      setSourceStart(data.source_start || 0);
      setSourceEnd(data.source_end || 35);
      setSubtitles(Array.isArray(data.subtitles_json) ? data.subtitles_json : []);
      setSubtitleFontSize(data.subtitle_font_size || 58);
      if (data.subtitle_position) setSubtitlePosition(data.subtitle_position);
      if (data.subtitle_y_percent !== undefined && data.subtitle_y_percent !== null) {
        setSubtitleYPercent(data.subtitle_y_percent);
      }
      if (data.subtitle_color) setSubtitleColor(data.subtitle_color);
      if (data.subtitle_font_family) setSubtitleFontFamily(data.subtitle_font_family);

      // If already rendered, default to rendered preview unless user adjusts
      if (data.render_status === 'completed' && data.video_url) {
        setPreviewMode('rendered');
      } else {
        setPreviewMode('live');
      }
    } catch (e: any) {
      console.error('Failed to load reel:', e);
      setLoadError(e.message || 'Unable to connect to server or load reel.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!reelId) return;
    fetchReel();
    // Poll for render status updates
    const interval = setInterval(() => {
      api.getReel(reelId).then((r) => {
        setReel((prev) => (prev ? { ...prev, render_status: r.render_status, render_progress: r.render_progress, video_url: r.video_url, source_video_url: r.source_video_url } : r));
      }).catch(() => {});
    }, 2500);
    return () => clearInterval(interval);
  }, [reelId]);

  const currentDuration = Math.max(1, sourceEnd - sourceStart);
  const isValidDuration = currentDuration >= 30.0 && currentDuration <= 150.0;

  // Handle seeking across all synced video players
  const handleSeek = (newRelativeTime: number) => {
    const clamped = Math.max(0, Math.min(currentDuration, newRelativeTime));
    setCurrentTime(clamped);

    const absSourceTime = sourceStart + clamped;
    if (sourceVideoRef.current) sourceVideoRef.current.currentTime = absSourceTime;
    if (previewTopVideoRef.current) previewTopVideoRef.current.currentTime = absSourceTime;
    if (previewBottomVideoRef.current) previewBottomVideoRef.current.currentTime = absSourceTime;
    if (previewSingleVideoRef.current) previewSingleVideoRef.current.currentTime = absSourceTime;
    if (videoRef.current) videoRef.current.currentTime = clamped;
  };

  const togglePlayPause = () => {
    if (isPlaying) {
      if (sourceVideoRef.current) sourceVideoRef.current.pause();
      if (previewTopVideoRef.current) previewTopVideoRef.current.pause();
      if (previewBottomVideoRef.current) previewBottomVideoRef.current.pause();
      if (previewSingleVideoRef.current) previewSingleVideoRef.current.pause();
      if (videoRef.current) videoRef.current.pause();
      setIsPlaying(false);
    } else {
      const absSourceTime = sourceStart + currentTime;
      if (sourceVideoRef.current) {
        sourceVideoRef.current.currentTime = absSourceTime;
        sourceVideoRef.current.play().catch(() => {});
      }
      if (previewTopVideoRef.current) {
        previewTopVideoRef.current.currentTime = absSourceTime;
        previewTopVideoRef.current.play().catch(() => {});
      }
      if (previewBottomVideoRef.current) {
        previewBottomVideoRef.current.currentTime = absSourceTime;
        previewBottomVideoRef.current.play().catch(() => {});
      }
      if (previewSingleVideoRef.current) {
        previewSingleVideoRef.current.currentTime = absSourceTime;
        previewSingleVideoRef.current.play().catch(() => {});
      }
      if (videoRef.current) {
        videoRef.current.currentTime = currentTime;
        videoRef.current.play().catch(() => {});
      }
      setIsPlaying(true);
    }
  };

  // Time update from playing video
  const handleVideoTimeUpdate = (e: React.SyntheticEvent<HTMLVideoElement>) => {
    const target = e.currentTarget;
    if (previewMode === 'rendered') {
      setCurrentTime(target.currentTime);
    } else {
      const relTime = target.currentTime - sourceStart;
      if (relTime >= currentDuration) {
        handleSeek(0);
        togglePlayPause();
      } else if (relTime >= 0) {
        setCurrentTime(relTime);
      }
    }
  };

  const formatSecs = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${mins}:${s.toString().padStart(2, '0')}`;
  };

  const handleSubtitleWordChange = (idx: number, newWord: string) => {
    const updated = [...subtitles];
    updated[idx] = { ...updated[idx], word: newWord };
    setSubtitles(updated);
  };

  const handleRomanize = async () => {
    setIsRomanizing(true);
    try {
      const updated = await api.romanizeReel(reelId);
      setReel(updated);
      setSubtitles(Array.isArray(updated.subtitles_json) ? updated.subtitles_json : []);
      setTopCaption(updated.top_caption || '');
      alert('Subtitles converted to Roman Urdu / Hinglish (Latin English alphabet only) and re-rendering queued!');
    } catch (e: any) {
      alert(`Romanization failed: ${e.message}`);
    } finally {
      setIsRomanizing(false);
    }
  };

  const handleSaveAndRender = async () => {
    if (!isValidDuration) {
      alert(`Clip duration must be between 30 and 150 seconds (currently ${currentDuration.toFixed(1)}s).`);
      return;
    }

    setIsSaving(true);
    try {
      const updated = await api.updateReel(reelId, {
        top_caption: topCaption.toUpperCase(),
        framing_mode: framingMode,
        pan_x_offset: panXOffset,
        split_facecam_crop: facecamCrop,
        split_gameplay_crop: gameplayCrop,
        split_order: splitOrder,
        split_ratio: splitRatio,
        source_start: sourceStart,
        source_end: sourceEnd,
        subtitles_json: subtitles,
        subtitle_font_size: subtitleFontSize,
        subtitle_position: subtitlePosition,
        subtitle_y_percent: subtitleYPercent,
        subtitle_color: subtitleColor,
        subtitle_font_family: subtitleFontFamily,
      });
      setReel(updated);
      setIsAdjustingCrop(false);
      setPreviewMode('live');
      alert('Changes saved! Re-rendering vertical reel in the background with your custom framing.');
    } catch (e: any) {
      alert(`Save failed: ${e.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-96 items-center justify-center text-slate-400">
        <Loader2 className="h-8 w-8 animate-spin text-indigo-500 mr-3" />
        Loading reel editor...
      </div>
    );
  }

  if (loadError || !reel) {
    return (
      <div className="mx-auto max-w-xl px-4 py-20 text-center space-y-4">
        <div className="rounded-2xl border border-red-500/20 bg-slate-900/90 p-8 shadow-2xl">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-500/10 text-red-400 mb-4">
            <RotateCcw className="h-6 w-6" />
          </div>
          <h2 className="text-lg font-bold text-white mb-2">Could Not Load Reel</h2>
          <p className="text-xs text-red-400/90 mb-6 font-mono bg-red-950/30 p-3 rounded-lg border border-red-900/30">
            {loadError || 'Reel data could not be retrieved from the server.'}
          </p>
          <div className="flex items-center justify-center gap-3">
            <button
              onClick={() => {
                setIsLoading(true);
                fetchReel();
              }}
              className="flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-2.5 text-xs font-semibold text-white hover:bg-indigo-500 transition shadow-lg shadow-indigo-600/30"
            >
              <RotateCcw className="h-4 w-4" /> Try Again
            </button>
            <Link
              href={`/projects/${projectId || ''}`}
              className="rounded-xl border border-slate-700 bg-slate-800 px-5 py-2.5 text-xs font-semibold text-slate-200 hover:bg-slate-700 hover:text-white transition"
            >
              Back to Project
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // Active word calculation for real-time karaoke preview
  const activeWordIndex = Array.isArray(subtitles)
    ? subtitles.findIndex((w) => w && currentTime >= w.start && currentTime <= w.end)
    : -1;

  // Split-screen effective crops (for 100% pane fill with zero black gaps)
  const isFcTop = splitOrder === 'facecam_top';
  const topCrop = isFcTop ? facecamCrop : gameplayCrop;
  const bottomCrop = isFcTop ? gameplayCrop : facecamCrop;

  const topPaneH = Math.round(1920 * splitRatio);
  const botPaneH = 1920 - topPaneH;

  const topEff = computeEffectiveCrop(
    topCrop,
    1080,
    topPaneH,
    naturalDims.width,
    naturalDims.height
  );
  const botEff = computeEffectiveCrop(
    bottomCrop,
    1080,
    botPaneH,
    naturalDims.width,
    naturalDims.height
  );

  const sourceMediaUrl = reel.source_video_url;

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 space-y-6">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <Link
            href={`/projects/${projectId}`}
            className="rounded-xl bg-slate-900 border border-slate-800 p-2 text-slate-300 hover:bg-slate-800 hover:text-white transition shadow"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
              Reel Editor
              <span className="rounded-full bg-indigo-500/10 px-2 py-0.5 text-xs text-indigo-400 border border-indigo-500/20">
                Score: {Math.round(reel.score)}
              </span>
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Customize vertical framing, headline, subtitle wording, and 30–150s trim points.
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3">
          {reel.render_status === 'completed' && reel.video_url && (
            <a
              href={`http://localhost:8000/api/reels/${reel.id}/download`}
              download
              className="flex items-center gap-1.5 rounded-xl bg-emerald-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-emerald-600/30 hover:bg-emerald-500"
            >
              <Download className="h-4 w-4" /> Download MP4
            </a>
          )}
          <button
            onClick={() => setShowDeleteModal(true)}
            className="flex items-center gap-1.5 rounded-xl border border-rose-500/25 bg-rose-500/10 px-3.5 py-2.5 text-xs font-semibold text-rose-400 hover:bg-rose-500 hover:text-white transition shadow-sm"
            title="Delete this reel"
          >
            <Trash2 className="h-4 w-4" />
            Delete Reel
          </button>
          <button
            onClick={handleSaveAndRender}
            disabled={isSaving || !isValidDuration}
            className="flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-2.5 text-xs font-semibold text-white shadow-lg shadow-indigo-600/30 hover:bg-indigo-500 disabled:opacity-50"
          >
            {isSaving || reel.render_status === 'rendering' ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                {reel.render_status === 'rendering' ? `Rendering (${Math.round(reel.render_progress)}%)...` : 'Saving...'}
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                Save & Re-Render Reel
              </>
            )}
          </button>
        </div>
      </div>

      {/* Editor Grid: 9:16 Canvas Preview on left, Controls on right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* ========================================================================= */}
        {/* Left: 9:16 Vertical Canvas Preview (5 cols)                                */}
        {/* ========================================================================= */}
        <div className="lg:col-span-5 flex flex-col items-center">
          <div className="w-full max-w-[360px] space-y-2">
            <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-slate-300">
              <span className="flex items-center gap-1.5">
                <Layers className="h-3.5 w-3.5 text-indigo-400" />
                9:16 Preview Canvas
              </span>

              {/* If no rendered video toggle, show active font & color badge */}
              {(!reel.video_url || reel.render_status !== 'completed') && (
                <span className="flex items-center gap-1.5 text-[11px] font-mono text-indigo-400 font-normal">
                  <span
                    className="h-2.5 w-2.5 rounded-full inline-block border border-white/20"
                    style={{ backgroundColor: subtitleColor }}
                  />
                  {subtitleFontFamily} • {subtitleFontSize}px
                </span>
              )}

              {/* Toggle Live Framing vs Rendered MP4 if export exists */}
              {reel.render_status === 'completed' && reel.video_url && (
                <div className="flex items-center rounded-lg bg-slate-900 border border-slate-800 p-0.5 text-[10px]">
                  <button
                    type="button"
                    onClick={() => setPreviewMode('live')}
                    className={`px-2 py-0.5 rounded-md font-bold transition ${
                      previewMode === 'live'
                        ? 'bg-indigo-600 text-white'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    Live Framing
                  </button>
                  <button
                    type="button"
                    onClick={() => setPreviewMode('rendered')}
                    className={`px-2 py-0.5 rounded-md font-bold transition ${
                      previewMode === 'rendered'
                        ? 'bg-emerald-600 text-white'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    Rendered MP4
                  </button>
                </div>
              )}
            </div>

            {/* 9:16 Canvas Frame */}
            <div className="relative aspect-[9/16] w-full rounded-3xl bg-black border-4 border-slate-800 shadow-2xl overflow-hidden flex flex-col justify-between">
              {/* Top Caption Banner (burned position preview) */}
              <div className="relative z-20 pt-6 px-4 text-center">
                <span className="inline-block rounded-xl bg-black/85 px-3 py-1.5 text-xs font-black tracking-wide text-white uppercase shadow-lg border border-white/10 line-clamp-2">
                  {topCaption || 'ADD YOUR CATCHY CAPTION HERE'}
                </span>
              </div>

              {/* Video Player in Center (Dynamic Framing Preview) */}
              <div className="absolute inset-0 z-0 flex flex-col items-center justify-center overflow-hidden">
                {previewMode === 'rendered' && reel.video_url ? (
                  /* RENDERED MP4 PREVIEW */
                  <video
                    ref={videoRef}
                    src={reel.video_url}
                    className="h-full w-full object-cover pointer-events-none"
                    onTimeUpdate={handleVideoTimeUpdate}
                    onPlay={() => setIsPlaying(true)}
                    onPause={() => setIsPlaying(false)}
                    playsInline
                  />
                ) : framingMode === 'split' && sourceMediaUrl ? (
                  /* GAMING SPLIT SCREEN PREVIEW (Aspect-preserving filled panes) */
                  <div className="h-full w-full flex flex-col bg-black">
                    {/* Top Pane */}
                    <div
                      style={{ height: `${splitRatio * 100}%` }}
                      className="relative w-full overflow-hidden bg-slate-950"
                    >
                      <video
                        ref={previewTopVideoRef}
                        src={sourceMediaUrl}
                        muted
                        playsInline
                        className="absolute max-w-none pointer-events-none"
                        style={{
                          width: `${(1 / topEff.width) * 100}%`,
                          height: `${(1 / topEff.height) * 100}%`,
                          left: `-${(topEff.x / topEff.width) * 100}%`,
                          top: `-${(topEff.y / topEff.height) * 100}%`,
                          objectFit: 'fill',
                        }}
                      />
                      <span className="absolute bottom-2 left-2 rounded bg-black/70 px-1.5 py-0.5 text-[9px] font-bold text-white uppercase font-mono border border-white/10 backdrop-blur-sm z-10">
                        {splitOrder === 'facecam_top' ? 'Facecam' : 'Gameplay'}
                      </span>
                    </div>

                    {/* Divider Line */}
                    <div className="relative h-1 w-full bg-slate-700/80 shadow-md z-10 flex items-center justify-center">
                      <div className="h-2 w-8 rounded-full bg-indigo-500 shadow" />
                    </div>

                    {/* Bottom Pane */}
                    <div
                      style={{ height: `${(1 - splitRatio) * 100}%` }}
                      className="relative w-full overflow-hidden bg-slate-950"
                    >
                      <video
                        ref={previewBottomVideoRef}
                        src={sourceMediaUrl}
                        muted
                        playsInline
                        className="absolute max-w-none pointer-events-none"
                        style={{
                          width: `${(1 / botEff.width) * 100}%`,
                          height: `${(1 / botEff.height) * 100}%`,
                          left: `-${(botEff.x / botEff.width) * 100}%`,
                          top: `-${(botEff.y / botEff.height) * 100}%`,
                          objectFit: 'fill',
                        }}
                      />
                      <span className="absolute top-2 left-2 rounded bg-black/70 px-1.5 py-0.5 text-[9px] font-bold text-white uppercase font-mono border border-white/10 backdrop-blur-sm z-10">
                        {splitOrder === 'facecam_top' ? 'Gameplay' : 'Facecam'}
                      </span>
                    </div>
                  </div>
                ) : framingMode === 'fit' && sourceMediaUrl ? (
                  /* FIT + BLURRED BG PREVIEW */
                  <div className="relative h-full w-full overflow-hidden bg-black flex items-center justify-center">
                    <video
                      src={sourceMediaUrl}
                      muted
                      playsInline
                      className="absolute inset-0 h-full w-full object-cover filter blur-xl scale-125 opacity-60 pointer-events-none"
                    />
                    <video
                      ref={previewSingleVideoRef}
                      src={sourceMediaUrl}
                      muted
                      playsInline
                      className="relative z-10 max-h-full max-w-full object-contain pointer-events-none"
                    />
                  </div>
                ) : sourceMediaUrl ? (
                  /* CROP / PAN PREVIEW */
                  <div className="relative h-full w-full overflow-hidden bg-black flex items-center justify-center">
                    <video
                      ref={previewSingleVideoRef}
                      src={sourceMediaUrl}
                      muted
                      playsInline
                      className="h-full w-full object-cover pointer-events-none transition-transform duration-75"
                      style={{
                        transform:
                          framingMode === 'pan'
                            ? `translateX(${getPanTranslatePercent(panXOffset)}%)`
                            : undefined,
                      }}
                    />
                  </div>
                ) : (
                  <div className="text-center p-6 text-slate-500 text-xs">
                    Video preview will appear here.
                  </div>
                )}
              </div>

              {/* Subtitles Overlay (karaoke word-by-word preview with custom placement, color & font) */}
              <div
                className="absolute left-0 right-0 z-20 px-3 text-center pointer-events-none transition-all duration-100 ease-out"
                style={{
                  top: `${Math.round(subtitleYPercent * 100)}%`,
                  transform: 'translateY(-50%)',
                }}
              >
                {subtitles.length > 0 ? (
                  <div
                    className="inline-flex flex-wrap justify-center gap-1.5 rounded-xl bg-black/80 px-3.5 py-2 backdrop-blur-sm border border-white/10 font-bold leading-relaxed max-w-[92%] shadow-2xl mx-auto"
                    style={{
                      fontSize: `${Math.max(10, Math.round(subtitleFontSize * 0.22))}px`,
                      fontFamily: subtitleFontFamily,
                    }}
                  >
                    {subtitles.map((w, i) => (
                      <span
                        key={i}
                        style={
                          i === activeWordIndex
                            ? {
                                color: subtitleColor,
                                textShadow: `0 0 12px ${subtitleColor}90`,
                              }
                            : { color: '#FFFFFF' }
                        }
                        className={
                          i === activeWordIndex
                            ? 'scale-110 font-extrabold transition-all duration-100'
                            : 'opacity-90'
                        }
                      >
                        {w.word}
                      </span>
                    ))}
                  </div>
                ) : (
                  <div className="inline-block rounded-lg bg-black/70 px-3 py-1 text-[10px] text-slate-400 italic">
                    [Silent clip — spoken subtitles omitted]
                  </div>
                )}
              </div>

              {/* Floating Play/Pause Controls */}
              <button
                onClick={togglePlayPause}
                className="absolute inset-0 m-auto flex h-14 w-14 items-center justify-center rounded-full bg-indigo-600/80 text-white shadow-xl backdrop-blur-sm hover:scale-105 transition z-30"
              >
                {isPlaying ? <Pause className="h-6 w-6" /> : <Play className="h-6 w-6 fill-current ml-0.5" />}
              </button>
            </div>

            <p className="mt-2 text-xs text-slate-400 text-center">
              1080×1920 vertical preview • Dedicated caption & subtitle areas
            </p>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* Right: Controls & Text Editor (7 cols)                                    */}
        {/* ========================================================================= */}
        <div className="lg:col-span-7 space-y-6">
          {/* 1. Top Caption Headline */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg space-y-3">
            <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
              <Type className="h-4 w-4 text-indigo-400" />
              Catchy Top Caption Headline
            </label>
            <input
              type="text"
              value={topCaption}
              onChange={(e) => setTopCaption(e.target.value)}
              placeholder="ENTER AN ARRESTING HEADLINE..."
              className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm font-bold text-white placeholder-slate-600 uppercase focus:border-indigo-500 focus:outline-none"
            />
            <p className="text-[11px] text-slate-500">
              Placed in the dedicated region above footage to grab viewer attention in feed scrolling.
            </p>
          </div>

          {/* 2. Vertical Framing Mode & Custom Crop Controls */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg space-y-4">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                <Crop className="h-4 w-4 text-indigo-400" />
                Framing & Layout Mode
              </label>

              <div className="flex items-center gap-2">
                {(framingMode === 'split' || framingMode === 'pan') && (
                  <button
                    type="button"
                    onClick={handleResetFraming}
                    title="Reset crop frame to default presets"
                    className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:bg-slate-700 hover:text-white transition"
                  >
                    <RotateCcw className="h-3.5 w-3.5 text-indigo-400" />
                    Reset Frame
                  </button>
                )}

                {/* Adjust Crop Button */}
                {sourceMediaUrl && (
                  <button
                    type="button"
                    onClick={() => {
                      setIsAdjustingCrop(!isAdjustingCrop);
                      setPreviewMode('live');
                    }}
                    className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition shadow ${
                      isAdjustingCrop
                        ? 'bg-indigo-600 text-white shadow-indigo-600/30 ring-2 ring-indigo-400'
                        : 'bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white'
                    }`}
                  >
                    <Sliders className="h-3.5 w-3.5 text-indigo-400" />
                    {isAdjustingCrop ? 'Done Adjusting' : 'Adjust Crop'}
                  </button>
                )}
              </div>
            </div>

            {/* Layout mode buttons */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <button
                type="button"
                onClick={() => {
                  setFramingMode('crop');
                  setPreviewMode('live');
                }}
                className={`flex flex-col items-center justify-center gap-1.5 rounded-xl p-3 text-xs font-semibold border transition ${
                  framingMode === 'crop'
                    ? 'border-indigo-500 bg-indigo-600/20 text-white'
                    : 'border-slate-800 bg-slate-950/40 text-slate-400 hover:border-slate-700'
                }`}
              >
                <Crop className="h-5 w-5 text-indigo-400" />
                Center Crop (9:16)
              </button>

              <button
                type="button"
                onClick={() => {
                  setFramingMode('fit');
                  setPreviewMode('live');
                }}
                className={`flex flex-col items-center justify-center gap-1.5 rounded-xl p-3 text-xs font-semibold border transition ${
                  framingMode === 'fit'
                    ? 'border-indigo-500 bg-indigo-600/20 text-white'
                    : 'border-slate-800 bg-slate-950/40 text-slate-400 hover:border-slate-700'
                }`}
              >
                <Maximize2 className="h-5 w-5 text-indigo-400" />
                Fit + Blurred BG
              </button>

              <button
                type="button"
                onClick={() => {
                  setFramingMode('pan');
                  setPreviewMode('live');
                  setIsAdjustingCrop(true);
                }}
                className={`flex flex-col items-center justify-center gap-1.5 rounded-xl p-3 text-xs font-semibold border transition ${
                  framingMode === 'pan'
                    ? 'border-indigo-500 bg-indigo-600/20 text-white'
                    : 'border-slate-800 bg-slate-950/40 text-slate-400 hover:border-slate-700'
                }`}
              >
                <MoveHorizontal className="h-5 w-5 text-indigo-400" />
                Manual Pan Offset
              </button>

              <button
                type="button"
                onClick={() => {
                  setFramingMode('split');
                  setPreviewMode('live');
                  setIsAdjustingCrop(true);
                }}
                className={`flex flex-col items-center justify-center gap-1.5 rounded-xl p-3 text-xs font-semibold border transition ${
                  framingMode === 'split'
                    ? 'border-indigo-500 bg-indigo-600/20 text-white'
                    : 'border-slate-800 bg-slate-950/40 text-slate-400 hover:border-slate-700'
                }`}
              >
                <Split className="h-5 w-5 text-indigo-400" />
                Gaming Split Screen
              </button>
            </div>

            {/* ===================================================================== */}
            {/* INTERACTIVE SOURCE CROP EDITOR (When Adjust Crop is Open or Active)     */}
            {/* ===================================================================== */}
            {isAdjustingCrop && sourceMediaUrl && (
              <div className="rounded-xl border border-indigo-500/30 bg-slate-950/80 p-4 space-y-4 shadow-xl">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-2 border-b border-slate-800">
                  <div className="flex items-center gap-2 text-xs font-bold text-white">
                    <Sliders className="h-4 w-4 text-indigo-400" />
                    <span>Source Footage Crop Workspace</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      onClick={handleResetFraming}
                      className="flex items-center gap-1 text-[11px] font-semibold text-indigo-400 hover:text-indigo-300 transition"
                      title="Reset frame boxes to default position"
                    >
                      <RotateCcw className="h-3 w-3" />
                      Reset Frame
                    </button>
                    <div className="text-xs font-mono text-slate-400">
                      Reel: {formatSecs(currentTime)} / {formatSecs(currentDuration)}{' '}
                      <span className="text-indigo-400">(Source: {formatSecs(sourceStart + currentTime)})</span>
                    </div>
                  </div>
                </div>

                {/* Helper / Instruction Banner */}
                <div className="rounded-lg bg-indigo-950/40 border border-indigo-500/20 px-3 py-2 text-xs text-indigo-200 flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Info className="h-4 w-4 text-indigo-400 shrink-0" />
                    <span>
                      {framingMode === 'split'
                        ? 'Drag the Cyan (Facecam) or Purple (Gameplay) box to reposition. Drag corner handles to resize.'
                        : 'Drag the 9:16 vertical window horizontally across the 16:9 frame to pan.'}
                    </span>
                  </div>
                  {framingMode === 'split' && (
                    <button
                      type="button"
                      onClick={handleRevertToSavedFraming}
                      className="text-[11px] underline text-slate-400 hover:text-slate-200 whitespace-nowrap"
                    >
                      Revert Saved
                    </button>
                  )}
                </div>

                {/* Source Video Viewport with Interactive Crop Overlay */}
                <div
                  ref={sourceContainerRef}
                  className="relative aspect-video w-full rounded-xl bg-black border border-slate-800 overflow-hidden shadow-inner flex items-center justify-center"
                >
                  <video
                    ref={sourceVideoRef}
                    src={sourceMediaUrl}
                    className="h-full w-full object-contain pointer-events-none"
                    onLoadedMetadata={() => {
                      if (sourceVideoRef.current) {
                        setNaturalDims({
                          width: sourceVideoRef.current.videoWidth || 1920,
                          height: sourceVideoRef.current.videoHeight || 1080,
                        });
                        sourceVideoRef.current.currentTime = sourceStart + currentTime;
                      }
                    }}
                    onTimeUpdate={handleVideoTimeUpdate}
                    playsInline
                  />

                  {/* Interactive Crop / Pan Selector */}
                  {(framingMode === 'split' || framingMode === 'pan') && (
                    <SourceCropSelector
                      videoRef={sourceVideoRef}
                      containerRef={sourceContainerRef}
                      mode={framingMode === 'pan' ? 'pan' : 'split'}
                      facecamCrop={facecamCrop}
                      gameplayCrop={gameplayCrop}
                      onFacecamChange={setFacecamCrop}
                      onGameplayChange={setGameplayCrop}
                      activeTarget={activeCropTarget}
                      onSelectActiveTarget={setActiveCropTarget}
                      panXOffset={panXOffset}
                      onPanXOffsetChange={setPanXOffset}
                    />
                  )}
                </div>

                {/* Source Video Play & Trim Scrub Bar */}
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={togglePlayPause}
                    className="rounded-lg bg-slate-800 p-2 text-slate-300 hover:bg-slate-700 hover:text-white transition"
                  >
                    {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                  </button>

                  <input
                    type="range"
                    min={0}
                    max={currentDuration}
                    step={0.1}
                    value={currentTime}
                    onChange={(e) => handleSeek(Number(e.target.value))}
                    className="h-1.5 flex-1 accent-indigo-500 bg-slate-800 rounded-lg cursor-pointer"
                  />

                  <span className="text-xs font-mono text-slate-400 w-12 text-right">
                    {formatSecs(currentTime)}
                  </span>
                </div>
              </div>
            )}

            {/* Split Screen Secondary Controls (Order & Divider & Presets) */}
            {framingMode === 'split' && (
              <div className="space-y-4 pt-3 border-t border-slate-800">
                {/* Active Box Selector & Presets */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setActiveCropTarget('facecam')}
                      className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                        activeCropTarget === 'facecam'
                          ? 'bg-cyan-500/20 border border-cyan-400 text-cyan-300'
                          : 'bg-slate-800 text-slate-400 hover:text-white'
                      }`}
                    >
                      <User className="h-3.5 w-3.5 text-cyan-400" />
                      Facecam Box
                    </button>
                    <button
                      type="button"
                      onClick={() => setActiveCropTarget('gameplay')}
                      className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                        activeCropTarget === 'gameplay'
                          ? 'bg-indigo-500/20 border border-indigo-400 text-indigo-300'
                          : 'bg-slate-800 text-slate-400 hover:text-white'
                      }`}
                    >
                      <Gamepad2 className="h-3.5 w-3.5 text-indigo-400" />
                      Gameplay Box
                    </button>
                  </div>

                  {/* Preset Buttons */}
                  <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                    <span className="text-slate-500 mr-0.5">Presets:</span>
                    {activeCropTarget === 'facecam' ? (
                      <>
                        <button
                          type="button"
                          onClick={() => setFacecamCrop({ x: 0.7, y: 0.05, width: 0.28, height: 0.35 })}
                          className="rounded bg-slate-800 px-2 py-1 text-slate-300 hover:text-white"
                        >
                          Top-Right
                        </button>
                        <button
                          type="button"
                          onClick={() => setFacecamCrop({ x: 0.36, y: 0.05, width: 0.28, height: 0.35 })}
                          className="rounded bg-slate-800 px-2 py-1 text-slate-300 hover:text-white"
                        >
                          Top-Center
                        </button>
                        <button
                          type="button"
                          onClick={() => setFacecamCrop({ x: 0.02, y: 0.05, width: 0.28, height: 0.35 })}
                          className="rounded bg-slate-800 px-2 py-1 text-slate-300 hover:text-white"
                        >
                          Top-Left
                        </button>
                        <button
                          type="button"
                          onClick={() => setFacecamCrop({ x: 0.02, y: 0.6, width: 0.28, height: 0.35 })}
                          className="rounded bg-slate-800 px-2 py-1 text-slate-300 hover:text-white"
                        >
                          Bottom-Left
                        </button>
                        <button
                          type="button"
                          onClick={() => setFacecamCrop({ x: 0.7, y: 0.6, width: 0.28, height: 0.35 })}
                          className="rounded bg-slate-800 px-2 py-1 text-slate-300 hover:text-white"
                        >
                          Bottom-Right
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          type="button"
                          onClick={() => setGameplayCrop({ x: 0.0, y: 0.0, width: 1.0, height: 1.0 })}
                          className="rounded bg-slate-800 px-2 py-1 text-slate-300 hover:text-white"
                        >
                          Full 16:9
                        </button>
                        <button
                          type="button"
                          onClick={() => setGameplayCrop({ x: 0.0, y: 0.0, width: 0.72, height: 1.0 })}
                          className="rounded bg-slate-800 px-2 py-1 text-slate-300 hover:text-white"
                        >
                          Exclude Right
                        </button>
                        <button
                          type="button"
                          onClick={() => setGameplayCrop({ x: 0.28, y: 0.0, width: 0.72, height: 1.0 })}
                          className="rounded bg-slate-800 px-2 py-1 text-slate-300 hover:text-white"
                        >
                          Exclude Left
                        </button>
                      </>
                    )}

                    <div className="h-4 w-px bg-slate-800 mx-1" />

                    <button
                      type="button"
                      onClick={handleResetSplitScreen}
                      title="Reset split screen boxes and order to default"
                      className="flex items-center gap-1 rounded bg-slate-800/80 border border-slate-700/60 px-2 py-1 text-slate-300 hover:bg-slate-700 hover:text-white transition"
                    >
                      <RotateCcw className="h-3 w-3 text-indigo-400" />
                      Reset Split
                    </button>
                    <button
                      type="button"
                      onClick={handleRevertToSavedFraming}
                      title="Revert back to previously saved layout"
                      className="rounded bg-slate-800/80 border border-slate-700/60 px-2 py-1 text-slate-400 hover:text-slate-200 transition"
                    >
                      Revert
                    </button>
                  </div>
                </div>

                {/* Pane Order & Divider Slider */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3 space-y-1.5">
                    <span className="block text-xs font-semibold text-slate-400">Pane Order</span>
                    <button
                      type="button"
                      onClick={() =>
                        setSplitOrder(splitOrder === 'facecam_top' ? 'gameplay_top' : 'facecam_top')
                      }
                      className="flex w-full items-center justify-between rounded-lg bg-slate-900 border border-slate-700 px-3 py-2 text-xs font-bold text-white hover:bg-slate-800 transition"
                    >
                      <span>
                        {splitOrder === 'facecam_top'
                          ? '1. Facecam (Top) / 2. Gameplay (Bottom)'
                          : '1. Gameplay (Top) / 2. Facecam (Bottom)'}
                      </span>
                      <ArrowUpDown className="h-4 w-4 text-indigo-400" />
                    </button>
                  </div>

                  <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3 space-y-1.5">
                    <div className="flex justify-between text-xs font-semibold text-slate-400">
                      <span>Divider Height Position</span>
                      <span className="font-mono text-white">
                        {Math.round(splitRatio * 100)}% / {100 - Math.round(splitRatio * 100)}%
                      </span>
                    </div>
                    <input
                      type="range"
                      min={0.2}
                      max={0.55}
                      step={0.05}
                      value={splitRatio}
                      onChange={(e) => setSplitRatio(Number(e.target.value))}
                      className="w-full accent-indigo-500"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Manual Pan Offset Slider */}
            {framingMode === 'pan' && (
              <div className="space-y-2 pt-3 border-t border-slate-800">
                <div className="flex justify-between text-xs font-semibold text-slate-400">
                  <span>Horizontal Pan Offset</span>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-white">{panXOffset.toFixed(2)}</span>
                    <button
                      type="button"
                      onClick={() => setPanXOffset(0.0)}
                      className="text-[10px] text-indigo-400 hover:underline"
                    >
                      Reset Center
                    </button>
                  </div>
                </div>
                <input
                  type="range"
                  min={-1.0}
                  max={1.0}
                  step={0.05}
                  value={panXOffset}
                  onChange={(e) => setPanXOffset(Number(e.target.value))}
                  className="w-full accent-indigo-500"
                />
              </div>
            )}
          </div>

          {/* 3. Trim Points & Duration (30-150s) */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg space-y-4">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                <Clock className="h-4 w-4 text-indigo-400" />
                Trim Points (30–150 Seconds)
              </label>
              <span
                className={`text-xs font-mono font-bold px-2 py-0.5 rounded ${
                  isValidDuration
                    ? 'bg-emerald-500/10 text-emerald-400'
                    : 'bg-red-500/10 text-red-400'
                }`}
              >
                Duration: {currentDuration.toFixed(1)}s
              </span>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <span className="block text-xs text-slate-400 mb-1">Start Time (sec)</span>
                <input
                  type="number"
                  step={0.5}
                  value={sourceStart}
                  onChange={(e) => {
                    const val = Number(e.target.value);
                    setSourceStart(val);
                    handleSeek(0);
                  }}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2 text-sm text-white"
                />
              </div>
              <div>
                <span className="block text-xs text-slate-400 mb-1">End Time (sec)</span>
                <input
                  type="number"
                  step={0.5}
                  value={sourceEnd}
                  onChange={(e) => setSourceEnd(Number(e.target.value))}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2 text-sm text-white"
                />
              </div>
            </div>
            {!isValidDuration && (
              <p className="text-xs text-red-400 font-medium">
                Trim window must be between 30 and 150 seconds inclusive.
              </p>
            )}
          </div>

          {/* 4. Subtitle Placement, Color, Font & Size Settings */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                <Type className="h-4 w-4 text-indigo-400" />
                Subtitle Styling & Placement
              </label>
              <span className="text-xs font-mono font-bold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 px-2.5 py-0.5 rounded-lg">
                {subtitleFontFamily} • {subtitleFontSize}px • {Math.round(subtitleYPercent * 100)}% Y
              </span>
            </div>

            {/* A. Vertical Placement Presets & Slider */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                  <ArrowUpDown className="h-3.5 w-3.5 text-indigo-400" />
                  Vertical Placement
                </span>
                <span className="text-[11px] font-mono text-slate-400">
                  {subtitlePosition === 'bottom' ? 'Lower Zone' : subtitlePosition === 'middle' ? 'Center Stage' : 'Upper Zone'} ({Math.round(subtitleYPercent * 100)}%)
                </span>
              </div>

              <div className="grid grid-cols-3 gap-2.5">
                {[
                  { pos: 'top' as const, label: 'Top', y: 0.22, desc: 'Below header' },
                  { pos: 'middle' as const, label: 'Center', y: 0.50, desc: 'Direct focal point' },
                  { pos: 'bottom' as const, label: 'Bottom', y: 0.82, desc: 'Standard lower third' },
                ].map((item) => (
                  <button
                    key={item.pos}
                    type="button"
                    onClick={() => {
                      setSubtitlePosition(item.pos);
                      setSubtitleYPercent(item.y);
                    }}
                    className={`flex flex-col items-center justify-center p-2.5 rounded-xl border text-center transition ${
                      subtitlePosition === item.pos
                        ? 'border-indigo-500 bg-indigo-600/20 text-white shadow-md'
                        : 'border-slate-800 bg-slate-950/40 text-slate-400 hover:border-slate-700 hover:text-white'
                    }`}
                  >
                    <span className="text-xs font-bold">{item.label}</span>
                    <span className="text-[10px] text-slate-500">{item.desc}</span>
                  </button>
                ))}
              </div>

              {/* Fine-tune Vertical Offset Slider */}
              <div className="space-y-1 pt-1">
                <div className="flex justify-between text-[11px] text-slate-400">
                  <span>Fine-tune vertical position</span>
                  <span className="font-mono text-indigo-400">{Math.round(subtitleYPercent * 100)}%</span>
                </div>
                <input
                  type="range"
                  min={0.15}
                  max={0.88}
                  step={0.01}
                  value={subtitleYPercent}
                  onChange={(e) => {
                    const y = Number(e.target.value);
                    setSubtitleYPercent(y);
                    if (y < 0.35) setSubtitlePosition('top');
                    else if (y > 0.68) setSubtitlePosition('bottom');
                    else setSubtitlePosition('middle');
                  }}
                  className="w-full accent-indigo-500 cursor-pointer"
                />
              </div>
            </div>

            {/* B. Highlight Color Palette */}
            <div className="space-y-3 pt-3 border-t border-slate-800">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                  <Palette className="h-3.5 w-3.5 text-indigo-400" />
                  Active Word Highlight Color
                </span>
                <div className="flex items-center gap-2">
                  <span
                    className="h-3.5 w-3.5 rounded-full border border-white/20 shadow-sm"
                    style={{ backgroundColor: subtitleColor }}
                  />
                  <span className="text-[11px] font-mono text-slate-300">{subtitleColor.toUpperCase()}</span>
                </div>
              </div>

              {/* Swatches */}
              <div className="flex flex-wrap items-center gap-2">
                {[
                  { name: 'Classic Gold', hex: '#FFE500' },
                  { name: 'Cyber Cyan', hex: '#00FFFF' },
                  { name: 'Neon Green', hex: '#22FF44' },
                  { name: 'Hot Pink', hex: '#FF1493' },
                  { name: 'Flame Orange', hex: '#FF6600' },
                  { name: 'Electric Violet', hex: '#A855F7' },
                  { name: 'Clean White', hex: '#FFFFFF' },
                ].map((c) => (
                  <button
                    key={c.hex}
                    type="button"
                    onClick={() => setSubtitleColor(c.hex)}
                    title={c.name}
                    className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-bold border transition ${
                      subtitleColor.toUpperCase() === c.hex.toUpperCase()
                        ? 'border-indigo-400 bg-slate-800 text-white ring-2 ring-indigo-500/50 shadow'
                        : 'border-slate-800 bg-slate-950/60 text-slate-400 hover:border-slate-700 hover:text-white'
                    }`}
                  >
                    <span
                      className="h-3 w-3 rounded-full border border-black/40 shadow-sm shrink-0"
                      style={{ backgroundColor: c.hex }}
                    />
                    <span>{c.name}</span>
                  </button>
                ))}

                {/* Custom Color Input */}
                <label className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-bold border border-slate-800 bg-slate-950/60 text-slate-400 hover:border-slate-700 hover:text-white cursor-pointer transition">
                  <input
                    type="color"
                    value={subtitleColor}
                    onChange={(e) => setSubtitleColor(e.target.value)}
                    className="h-4 w-4 rounded cursor-pointer border-0 p-0 bg-transparent"
                  />
                  <span>Custom Hex</span>
                </label>
              </div>
            </div>

            {/* C. Font Family Presets */}
            <div className="space-y-3 pt-3 border-t border-slate-800">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                  <Type className="h-3.5 w-3.5 text-indigo-400" />
                  Font Family
                </span>
                <span className="text-[11px] font-mono text-indigo-400 font-semibold">{subtitleFontFamily}</span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {[
                  { name: 'Montserrat', desc: 'Bold viral punch' },
                  { name: 'Noto Sans', desc: 'Universal sans' },
                  { name: 'Roboto', desc: 'Modern geometric' },
                  { name: 'Liberation Sans', desc: 'Arial standard' },
                  { name: 'DejaVu Sans', desc: 'Heavy legibility' },
                ].map((font) => (
                  <button
                    key={font.name}
                    type="button"
                    onClick={() => setSubtitleFontFamily(font.name)}
                    className={`flex flex-col items-start p-2.5 rounded-xl border transition text-left ${
                      subtitleFontFamily === font.name
                        ? 'border-indigo-500 bg-indigo-600/20 text-white shadow-md'
                        : 'border-slate-800 bg-slate-950/40 text-slate-400 hover:border-slate-700 hover:text-white'
                    }`}
                  >
                    <span className="text-xs font-bold" style={{ fontFamily: font.name }}>{font.name}</span>
                    <span className="text-[10px] text-slate-500">{font.desc}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* D. Subtitle Size Presets & Slider */}
            <div className="space-y-3 pt-3 border-t border-slate-800">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-300">Subtitle Size Scale</span>
                <span className="text-xs font-mono font-bold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 px-2.5 py-0.5 rounded-lg">
                  {subtitleFontSize}px
                </span>
              </div>

              {/* Quick preset chips */}
              <div className="grid grid-cols-4 gap-2">
                {[
                  { label: 'Small', size: 42 },
                  { label: 'Medium', size: 54 },
                  { label: 'Large', size: 66 },
                  { label: 'Extra Large', size: 80 },
                ].map((preset) => (
                  <button
                    key={preset.size}
                    type="button"
                    onClick={() => setSubtitleFontSize(preset.size)}
                    className={`rounded-xl py-2 px-1 text-xs font-semibold border transition text-center ${
                      subtitleFontSize === preset.size
                        ? 'border-indigo-500 bg-indigo-600/20 text-white shadow-sm'
                        : 'border-slate-800 bg-slate-950/40 text-slate-400 hover:border-slate-700'
                    }`}
                  >
                    <span className="block font-medium">{preset.label}</span>
                    <span className="text-[10px] text-slate-500 font-mono">{preset.size}px</span>
                  </button>
                ))}
              </div>

              {/* Fine-tuning range slider */}
              <div className="space-y-1 pt-1">
                <div className="flex justify-between text-[11px] text-slate-400">
                  <span>Fine-tune scale</span>
                  <span className="font-mono text-indigo-400">{subtitleFontSize}px</span>
                </div>
                <input
                  type="range"
                  min={32}
                  max={96}
                  step={2}
                  value={subtitleFontSize}
                  onChange={(e) => setSubtitleFontSize(Number(e.target.value))}
                  className="w-full accent-indigo-500 cursor-pointer"
                />
              </div>

              <p className="text-[11px] text-slate-500">
                Adjusts the burned karaoke subtitle font, color, placement, and size for this individual reel export.
              </p>
            </div>
          </div>

          {/* 5. Subtitles Language & Script (Roman Urdu / Hinglish) */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-emerald-400" />
                Language & Roman Script
              </label>
              <span className="rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-400 border border-emerald-500/20">
                English / Latin Only
              </span>
            </div>

            <p className="text-xs text-slate-400 leading-relaxed">
              Subtitles use the English (Latin) alphabet only. Spoken Urdu is formatted as natural <strong className="text-slate-200">Roman Urdu</strong> (e.g. <em>&quot;bohat achha&quot;</em>) and Hindi as <strong className="text-slate-200">Hinglish</strong> (e.g. <em>&quot;kya baat hai&quot;</em>) with word-by-word timing preserved.
            </p>

            <button
              type="button"
              onClick={handleRomanize}
              disabled={isRomanizing}
              className="flex items-center justify-center gap-2 w-full rounded-xl border border-slate-700 bg-slate-950/80 px-4 py-2.5 text-xs font-semibold text-slate-200 hover:bg-slate-800 hover:text-white transition disabled:opacity-50"
            >
              {isRomanizing ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-400" />
                  Converting to Roman Script...
                </>
              ) : (
                <>
                  <Sparkles className="h-3.5 w-3.5 text-emerald-400" />
                  Convert Subtitles to Roman Urdu / Hinglish
                </>
              )}
            </button>
          </div>

          {/* 6. Subtitle Text Corrector */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                <FileText className="h-4 w-4 text-indigo-400" />
                Word-by-Word Subtitle Corrections
              </label>
              <span className="text-[11px] text-slate-500">
                Timing is locked while you correct words
              </span>
            </div>

            {subtitles.length > 0 ? (
              <div className="max-h-60 overflow-y-auto space-y-2 pr-2">
                {subtitles.map((item, idx) => (
                  <div key={idx} className="flex items-center gap-2 text-xs">
                    <span className="w-16 font-mono text-slate-500 shrink-0">
                      {item.start.toFixed(2)}s
                    </span>
                    <input
                      type="text"
                      value={item.word}
                      onChange={(e) => handleSubtitleWordChange(idx, e.target.value)}
                      className="flex-1 rounded-lg border border-slate-800 bg-slate-950 px-2.5 py-1 text-slate-200 focus:border-indigo-500"
                    />
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500 py-3 text-center">
                No spoken words recorded in this clip range.
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Delete Confirmation Modal */}
      {showDeleteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-150">
          <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl space-y-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-rose-500/10 text-rose-400 border border-rose-500/20 shadow-lg shadow-rose-500/10">
              <Trash2 className="h-6 w-6" />
            </div>

            <div>
              <h3 className="text-base font-bold text-white">Delete This Reel?</h3>
              <p className="text-xs text-slate-400 mt-1">
                Are you sure you want to permanently delete &quot;{reel.title}&quot;? The rendered MP4 video and its metadata will be completely removed.
              </p>
            </div>

            {deleteError && (
              <p className="text-xs text-rose-400 font-medium bg-rose-950/40 p-2.5 rounded-xl border border-rose-900/40">
                {deleteError}
              </p>
            )}

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => {
                  setShowDeleteModal(false);
                  setDeleteError(null);
                }}
                disabled={isDeleting}
                className="rounded-xl border border-slate-700 bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-700 hover:text-white transition disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteReel}
                disabled={isDeleting}
                className="flex items-center gap-1.5 rounded-xl bg-rose-600 px-4 py-2 text-xs font-semibold text-white hover:bg-rose-500 transition shadow-lg shadow-rose-600/30 disabled:opacity-50"
              >
                {isDeleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                Delete Reel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
