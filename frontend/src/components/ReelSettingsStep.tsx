'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Project, CropBox } from '@/lib/types';
import { api } from '@/lib/api';
import { SourceCropSelector } from '@/components/SourceCropSelector';
import { computeEffectiveCrop, getPanTranslatePercent } from '@/lib/cropUtils';
import {
  Sparkles,
  Crop,
  Maximize2,
  MoveHorizontal,
  Split,
  Type,
  Play,
  Pause,
  ArrowUpDown,
  Sliders,
  AlertTriangle,
  Info,
  CheckCircle2,
  Loader2,
  Layers,
  Gamepad2,
  User,
  Radio,
  Palette,
} from 'lucide-react';

interface ReelSettingsStepProps {
  project: Project;
  onGenerationStarted: () => void;
  isLiveStream?: boolean;
  livePreviewUrl?: string;
}

export const ReelSettingsStep: React.FC<ReelSettingsStepProps> = ({
  project,
  onGenerationStarted,
  isLiveStream = false,
  livePreviewUrl,
}) => {
  const isLive = isLiveStream || project.source_type === 'live_stream';

  // Framing & Layout Settings
  const [framingMode, setFramingMode] = useState<'crop' | 'fit' | 'pan' | 'split'>(
    project.framing_mode || 'crop'
  );
  const [panXOffset, setPanXOffset] = useState<number>(project.pan_x_offset ?? 0.0);
  const [subtitleFontSize, setSubtitleFontSize] = useState<number>(
    project.subtitle_font_size || 54
  );
  const [subtitlePosition, setSubtitlePosition] = useState<'bottom' | 'middle' | 'top'>(
    project.subtitle_position || 'bottom'
  );
  const [subtitleYPercent, setSubtitleYPercent] = useState<number>(
    project.subtitle_y_percent ?? 0.82
  );
  const [subtitleColor, setSubtitleColor] = useState<string>(
    project.subtitle_color || '#FFE500'
  );
  const [subtitleFontFamily, setSubtitleFontFamily] = useState<string>(
    project.subtitle_font_family || 'Montserrat'
  );

  // Gaming Split Screen Settings
  const [facecamCrop, setFacecamCrop] = useState<CropBox>(
    project.split_facecam_crop || { x: 0.7, y: 0.05, width: 0.28, height: 0.35 }
  );
  const [gameplayCrop, setGameplayCrop] = useState<CropBox>(
    project.split_gameplay_crop || { x: 0.0, y: 0.0, width: 1.0, height: 1.0 }
  );
  const [splitOrder, setSplitOrder] = useState<'facecam_top' | 'gameplay_top'>(
    project.split_order || 'facecam_top'
  );
  const [splitRatio, setSplitRatio] = useState<number>(project.split_ratio ?? 0.35);
  const [activeCropTarget, setActiveCropTarget] = useState<'facecam' | 'gameplay'>('facecam');

  // Video playback & scrubbing state
  const sourceVideoRef = useRef<HTMLVideoElement>(null);
  const previewVideoRef = useRef<HTMLVideoElement>(null);
  const previewTopVideoRef = useRef<HTMLVideoElement>(null);
  const previewBottomVideoRef = useRef<HTMLVideoElement>(null);
  const sourceContainerRef = useRef<HTMLDivElement>(null);

  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [duration, setDuration] = useState<number>(project.duration || 60);
  const [naturalDims, setNaturalDims] = useState<{ width: number; height: number }>({
    width: project.probe_data?.width || 1920,
    height: project.probe_data?.height || 1080,
  });

  // Transcript sample words for karaoke preview
  const [sampleWords, setSampleWords] = useState<{ word: string; start: number; end: number }[]>([
    { word: 'CREATE', start: 0.0, end: 0.3 },
    { word: 'VIRAL', start: 0.3, end: 0.6 },
    { word: 'GAMING', start: 0.6, end: 0.9 },
    { word: 'REELS', start: 0.9, end: 1.3 },
    { word: 'AUTOMATICALLY', start: 1.3, end: 2.0 },
  ]);

  // Loading & Generation state
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [saveStatus, setSaveStatus] = useState<'saved' | 'saving' | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Fetch real transcript slice if available
  useEffect(() => {
    if (!project.id) return;
    api
      .getProjectSampleTranscript(project.id)
      .then((res) => {
        if (res.words && res.words.length > 0) {
          setSampleWords(res.words);
        }
      })
      .catch(() => {});
  }, [project.id]);

  // Sync playback between source video and preview videos
  const handleTimeUpdate = () => {
    if (sourceVideoRef.current) {
      const cur = sourceVideoRef.current.currentTime;
      setCurrentTime(cur);

      // Keep preview player in sync
      if (previewVideoRef.current && Math.abs(previewVideoRef.current.currentTime - cur) > 0.3) {
        previewVideoRef.current.currentTime = cur;
      }
      if (previewTopVideoRef.current && Math.abs(previewTopVideoRef.current.currentTime - cur) > 0.3) {
        previewTopVideoRef.current.currentTime = cur;
      }
      if (previewBottomVideoRef.current && Math.abs(previewBottomVideoRef.current.currentTime - cur) > 0.3) {
        previewBottomVideoRef.current.currentTime = cur;
      }
    }
  };

  const togglePlayPause = () => {
    const video = sourceVideoRef.current;
    if (!video) return;
    if (isPlaying) {
      video.pause();
      if (previewVideoRef.current) previewVideoRef.current.pause();
      if (previewTopVideoRef.current) previewTopVideoRef.current.pause();
      if (previewBottomVideoRef.current) previewBottomVideoRef.current.pause();
      setIsPlaying(false);
    } else {
      video.play().catch(() => {});
      if (previewVideoRef.current) previewVideoRef.current.play().catch(() => {});
      if (previewTopVideoRef.current) previewTopVideoRef.current.play().catch(() => {});
      if (previewBottomVideoRef.current) previewBottomVideoRef.current.play().catch(() => {});
      setIsPlaying(true);
    }
  };

  const handleSeek = (newTime: number) => {
    setCurrentTime(newTime);
    if (sourceVideoRef.current) sourceVideoRef.current.currentTime = newTime;
    if (previewVideoRef.current) previewVideoRef.current.currentTime = newTime;
    if (previewTopVideoRef.current) previewTopVideoRef.current.currentTime = newTime;
    if (previewBottomVideoRef.current) previewBottomVideoRef.current.currentTime = newTime;
  };

  // Auto-save settings in background when changed
  useEffect(() => {
    const timeout = setTimeout(async () => {
      try {
        setSaveStatus('saving');
        await api.updateProjectSettings(project.id, {
          framing_mode: framingMode,
          pan_x_offset: panXOffset,
          subtitle_font_size: subtitleFontSize,
          subtitle_position: subtitlePosition,
          subtitle_y_percent: subtitleYPercent,
          subtitle_color: subtitleColor,
          subtitle_font_family: subtitleFontFamily,
          split_facecam_crop: facecamCrop,
          split_gameplay_crop: gameplayCrop,
          split_order: splitOrder,
          split_ratio: splitRatio,
        });
        setSaveStatus('saved');
      } catch (e) {
        setSaveStatus(null);
      }
    }, 600);
    return () => clearTimeout(timeout);
  }, [
    project.id,
    framingMode,
    panXOffset,
    subtitleFontSize,
    subtitlePosition,
    subtitleYPercent,
    subtitleColor,
    subtitleFontFamily,
    facecamCrop,
    gameplayCrop,
    splitOrder,
    splitRatio,
  ]);

  // Explicit Generate Reels / Live Clipping action
  const handleGenerateClick = async () => {
    setErrorMsg(null);
    setIsGenerating(true);
    try {
      const settingsPayload = {
        framing_mode: framingMode,
        pan_x_offset: panXOffset,
        subtitle_font_size: subtitleFontSize,
        subtitle_position: subtitlePosition,
        subtitle_y_percent: subtitleYPercent,
        subtitle_color: subtitleColor,
        subtitle_font_family: subtitleFontFamily,
        split_facecam_crop: facecamCrop,
        split_gameplay_crop: gameplayCrop,
        split_order: splitOrder,
        split_ratio: splitRatio,
      };

      if (isLive) {
        await api.startLiveClipping(project.id, settingsPayload);
      } else {
        await api.generateProjectReels(project.id, settingsPayload);
      }
      onGenerationStarted();
    } catch (err: any) {
      console.error('Generation launch error:', err);
      setErrorMsg(err.message || 'Failed to start reel generation.');
      setIsGenerating(false);
    }
  };

  // Active word calculation for real-time karaoke preview
  const cycleTime = sampleWords.length > 0 ? sampleWords[sampleWords.length - 1].end : 2.5;
  const loopTime = currentTime % (cycleTime || 2.5);
  const activeWordIdx = sampleWords.findIndex(
    (w) => loopTime >= w.start && loopTime <= w.end
  );

  const formatSecs = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${mins}:${s.toString().padStart(2, '0')}`;
  };

  // Top and bottom crop definitions for split screen preview
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

  const isPreviewImage = !project.source_video_url && Boolean(livePreviewUrl);
  const activeSourceMedia = project.source_video_url || livePreviewUrl;

  return (
    <div className="space-y-8">
      {/* Step Header Banner */}
      <div className={`flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-2xl border p-6 shadow-xl backdrop-blur-md ${
        isLive
          ? 'border-red-500/30 bg-gradient-to-r from-red-950/40 to-slate-900/60'
          : 'border-indigo-500/20 bg-indigo-950/20'
      }`}>
        <div>
          <div className={`flex items-center gap-2 text-xs font-bold uppercase tracking-wider mb-1 ${
            isLive ? 'text-red-400' : 'text-indigo-400'
          }`}>
            {isLive ? (
              <>
                <Radio className="h-4 w-4 animate-pulse" /> Live Stream Setup: Confirm Settings
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" /> Step 2 of 2: Reel Settings Before Generation
              </>
            )}
          </div>
          <h2 className="text-xl font-bold text-white tracking-tight">
            {isLive ? 'Confirm Live Stream Framing & Subtitle Style' : 'Configure Reel Framing & Subtitle Style'}
          </h2>
          <p className="text-xs text-slate-300 mt-1 max-w-2xl leading-relaxed">
            {isLive
              ? 'Live media feed connected. Choose how your 9:16 vertical reels will be framed, set your subtitle size, and adjust split-screen regions before starting live clipping.'
              : 'Your source video is uploaded and verified. Choose how your vertical 9:16 reels will be framed, set your subtitle size, and adjust split-screen regions before generating reels.'}
          </p>
        </div>

        {/* Generate Reels / Start Live Button */}
        <div className="flex flex-col sm:items-end gap-2 shrink-0">
          <button
            onClick={handleGenerateClick}
            disabled={isGenerating || (!isLive && !project.source_file_key)}
            className={`flex items-center justify-center gap-2 rounded-xl px-6 py-3.5 text-sm font-bold text-white shadow-xl transition disabled:opacity-50 ${
              isLive
                ? 'bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 shadow-red-600/30'
                : 'bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-400 hover:to-purple-500 shadow-indigo-600/30'
            }`}
          >
            {isGenerating ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" /> {isLive ? 'Starting Live Capture...' : 'Starting Generation...'}
              </>
            ) : isLive ? (
              <>
                <Radio className="h-4 w-4 animate-pulse" /> Start Live Clipping
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" /> Generate Reels
              </>
            )}
          </button>
          <div className="flex items-center gap-2 text-[11px] text-slate-400">
            {saveStatus === 'saving' && (
              <span className="flex items-center gap-1 text-slate-400">
                <Loader2 className="h-3 w-3 animate-spin" /> Saving settings...
              </span>
            )}
            {saveStatus === 'saved' && (
              <span className="flex items-center gap-1 text-emerald-400">
                <CheckCircle2 className="h-3 w-3" /> Settings saved
              </span>
            )}
            <span>• Snapshot applied to all reels</span>
          </div>
        </div>
      </div>

      {errorMsg && (
        <div className="rounded-xl border border-red-500/30 bg-red-950/40 p-4 text-xs text-red-300 flex items-start gap-2">
          <AlertTriangle className="h-4 w-4 text-red-400 shrink-0 mt-0.5" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Main Grid: 9:16 Vertical Preview on Left, Source Video & Controls on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* ========================================================================= */}
        {/* LEFT COLUMN: 9:16 Vertical Preview Canvas (5 cols)                         */}
        {/* ========================================================================= */}
        <div className="lg:col-span-5 flex flex-col items-center">
          <div className="w-full max-w-[340px] space-y-2">
            <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-slate-300">
              <span className="flex items-center gap-1.5">
                <Layers className="h-3.5 w-3.5 text-indigo-400" />
                Live 9:16 Canvas Preview
              </span>
              <span className="flex items-center gap-1.5 text-[11px] font-mono text-indigo-400 font-normal">
                <span
                  className="h-2.5 w-2.5 rounded-full inline-block border border-white/20"
                  style={{ backgroundColor: subtitleColor }}
                />
                {subtitleFontFamily} • {subtitleFontSize}px
              </span>
            </div>

            {/* 9:16 Vertical Canvas Container */}
            <div className="relative aspect-[9/16] w-full rounded-3xl bg-black border-4 border-slate-800 shadow-2xl overflow-hidden flex flex-col justify-between">
              {/* Top Caption Banner (Dedicated Top Area) */}
              <div className="relative z-20 pt-5 px-3 text-center">
                <span className="inline-block rounded-xl bg-black/85 px-3 py-1.5 text-[11px] font-black tracking-wide text-white uppercase shadow-lg border border-white/10 line-clamp-2">
                  CATCHY HEADLINE GOES HERE
                </span>
              </div>

              {/* Footage Area in Middle (Dynamic Framing Preview) */}
              <div className="absolute inset-0 z-0 flex flex-col items-center justify-center overflow-hidden">
                {framingMode === 'split' ? (
                  /* GAMING SPLIT SCREEN PREVIEW (Aspect-preserving filled panes) */
                  <div className="h-full w-full flex flex-col bg-black">
                    {/* Top Pane */}
                    <div
                      style={{ height: `${splitRatio * 100}%` }}
                      className="relative w-full overflow-hidden bg-slate-950 flex items-center justify-center"
                    >
                      {activeSourceMedia ? (
                        isPreviewImage ? (
                          <img
                            src={activeSourceMedia}
                            alt="Top Pane Frame"
                            className="absolute max-w-none pointer-events-none"
                            style={{
                              width: `${(1 / topEff.width) * 100}%`,
                              height: `${(1 / topEff.height) * 100}%`,
                              left: `-${(topEff.x / topEff.width) * 100}%`,
                              top: `-${(topEff.y / topEff.height) * 100}%`,
                              objectFit: 'fill',
                            }}
                          />
                        ) : (
                          <video
                            ref={previewTopVideoRef}
                            src={activeSourceMedia}
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
                        )
                      ) : (
                        <div className="flex h-full w-full items-center justify-center text-[10px] text-slate-600 font-mono">
                          {splitOrder === 'facecam_top' ? 'Facecam' : 'Gameplay'} Pane
                        </div>
                      )}
                      {/* Labeled corner badge */}
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
                      className="relative w-full overflow-hidden bg-slate-950 flex items-center justify-center"
                    >
                      {activeSourceMedia ? (
                        isPreviewImage ? (
                          <img
                            src={activeSourceMedia}
                            alt="Bottom Pane Frame"
                            className="absolute max-w-none pointer-events-none"
                            style={{
                              width: `${(1 / botEff.width) * 100}%`,
                              height: `${(1 / botEff.height) * 100}%`,
                              left: `-${(botEff.x / botEff.width) * 100}%`,
                              top: `-${(botEff.y / botEff.height) * 100}%`,
                              objectFit: 'fill',
                            }}
                          />
                        ) : (
                          <video
                            ref={previewBottomVideoRef}
                            src={activeSourceMedia}
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
                        )
                      ) : (
                        <div className="flex h-full w-full items-center justify-center text-[10px] text-slate-600 font-mono">
                          {splitOrder === 'facecam_top' ? 'Gameplay' : 'Facecam'} Pane
                        </div>
                      )}
                      <span className="absolute top-2 left-2 rounded bg-black/70 px-1.5 py-0.5 text-[9px] font-bold text-white uppercase font-mono border border-white/10 backdrop-blur-sm z-10">
                        {splitOrder === 'facecam_top' ? 'Gameplay' : 'Facecam'}
                      </span>
                    </div>
                  </div>
                ) : framingMode === 'fit' ? (
                  /* FIT + BLURRED BG PREVIEW */
                  <div className="relative h-full w-full overflow-hidden bg-black flex items-center justify-center">
                    {activeSourceMedia ? (
                      <>
                        {/* Blurred Background */}
                        {isPreviewImage ? (
                          <img
                            src={activeSourceMedia}
                            alt="Fit Background Blur"
                            className="absolute inset-0 h-full w-full object-cover filter blur-xl scale-125 opacity-60 pointer-events-none"
                          />
                        ) : (
                          <video
                            src={activeSourceMedia}
                            muted
                            playsInline
                            className="absolute inset-0 h-full w-full object-cover filter blur-xl scale-125 opacity-60 pointer-events-none"
                          />
                        )}
                        {/* Sharp Foreground */}
                        {isPreviewImage ? (
                          <img
                            src={activeSourceMedia}
                            alt="Fit Foreground"
                            className="relative z-10 max-h-full max-w-full object-contain pointer-events-none"
                          />
                        ) : (
                          <video
                            ref={previewVideoRef}
                            src={activeSourceMedia}
                            muted
                            playsInline
                            className="relative z-10 max-h-full max-w-full object-contain pointer-events-none"
                          />
                        )}
                      </>
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-xs text-slate-600 font-mono">
                        Fit & Blur Preview
                      </div>
                    )}
                  </div>
                ) : (
                  /* CROP / PAN PREVIEW */
                  <div className="relative h-full w-full overflow-hidden bg-black flex items-center justify-center">
                    {activeSourceMedia ? (
                      isPreviewImage ? (
                        <img
                          src={activeSourceMedia}
                          alt="Crop Pan Preview"
                          className="h-full w-full object-cover pointer-events-none transition-transform duration-75"
                          style={{
                            transform:
                              framingMode === 'pan'
                                ? `translateX(${getPanTranslatePercent(panXOffset)}%)`
                                : undefined,
                          }}
                        />
                      ) : (
                        <video
                          ref={previewVideoRef}
                          src={activeSourceMedia}
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
                      )
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-xs text-slate-600 font-mono">
                        Vertical Canvas Preview
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Subtitles Overlay (Custom Placement, Color & Font Family) */}
              <div
                className="absolute left-0 right-0 z-20 px-3 text-center pointer-events-none transition-all duration-100 ease-out"
                style={{
                  top: `${Math.round(subtitleYPercent * 100)}%`,
                  transform: 'translateY(-50%)',
                }}
              >
                <div
                  className="inline-flex flex-wrap justify-center gap-1.5 rounded-xl bg-black/80 px-3.5 py-2 backdrop-blur-sm border border-white/10 font-bold leading-relaxed max-w-[92%] shadow-2xl mx-auto"
                  style={{
                    fontSize: `${Math.max(10, Math.round(subtitleFontSize * 0.22))}px`,
                    fontFamily: subtitleFontFamily,
                  }}
                >
                  {sampleWords.map((w, idx) => (
                    <span
                      key={idx}
                      style={
                        idx === activeWordIdx
                          ? {
                              color: subtitleColor,
                              textShadow: `0 0 12px ${subtitleColor}90`,
                            }
                          : { color: '#FFFFFF' }
                      }
                      className={
                        idx === activeWordIdx
                          ? 'scale-110 font-extrabold transition-all duration-100'
                          : 'opacity-90'
                      }
                    >
                      {w.word}
                    </span>
                  ))}
                </div>
              </div>

              {/* Floating Canvas Play/Pause Button */}
              <button
                onClick={togglePlayPause}
                className="absolute inset-0 m-auto flex h-14 w-14 items-center justify-center rounded-full bg-indigo-600/80 text-white shadow-xl backdrop-blur-sm hover:scale-105 transition"
              >
                {isPlaying ? (
                  <Pause className="h-6 w-6" />
                ) : (
                  <Play className="h-6 w-6 fill-current ml-0.5" />
                )}
              </button>
            </div>

            <p className="text-[11px] text-slate-500 text-center">
              1080×1920 Vertical format preview • Dedicated caption & subtitle areas
            </p>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* RIGHT COLUMN: Interactive Source Video, Crop Editor & Layout Settings (7 cols) */}
        {/* ========================================================================= */}
        <div className="lg:col-span-7 space-y-6">
          {/* 1. Source Video Player with Interactive Dual Crop Boxes */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                <Maximize2 className="h-4 w-4 text-indigo-400" />
                Source Video Framing & Scrubber
              </label>
              <span className="text-xs font-mono text-slate-400">
                {formatSecs(currentTime)} / {formatSecs(duration)}
              </span>
            </div>

            {/* Source video viewport */}
            <div
              ref={sourceContainerRef}
              className="relative aspect-video w-full rounded-xl bg-black border border-slate-800 overflow-hidden shadow-inner flex items-center justify-center"
            >
              {project.source_video_url ? (
                <>
                  <video
                    ref={sourceVideoRef}
                    src={project.source_video_url}
                    className="h-full w-full object-contain"
                    onTimeUpdate={handleTimeUpdate}
                    onLoadedMetadata={() => {
                      if (sourceVideoRef.current) {
                        setDuration(sourceVideoRef.current.duration || project.duration || 60);
                        if (sourceVideoRef.current.videoWidth && sourceVideoRef.current.videoHeight) {
                          setNaturalDims({
                            width: sourceVideoRef.current.videoWidth,
                            height: sourceVideoRef.current.videoHeight,
                          });
                        }
                      }
                    }}
                    onEnded={() => setIsPlaying(false)}
                    playsInline
                  />

                  {/* Interactive Crop & Pan Overlay */}
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
                </>
              ) : isPreviewImage ? (
                <div className="relative h-full w-full flex items-center justify-center bg-black">
                  <img
                    src={livePreviewUrl}
                    alt="Live Stream Frame Preview"
                    onLoad={(e) => {
                      const img = e.currentTarget;
                      if (img.naturalWidth && img.naturalHeight) {
                        setNaturalDims({
                          width: img.naturalWidth,
                          height: img.naturalHeight,
                        });
                      }
                    }}
                    className="h-full w-full object-contain pointer-events-none select-none"
                  />
                  <div className="absolute top-2 left-2 flex items-center gap-1.5 rounded-full bg-red-600/90 px-2.5 py-0.5 text-[10px] font-bold text-white shadow backdrop-blur-sm z-10">
                    <span className="h-1.5 w-1.5 rounded-full bg-white animate-pulse" />
                    LIVE STREAM PREVIEW
                  </div>
                  {(framingMode === 'split' || framingMode === 'pan') && (
                    <SourceCropSelector
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
              ) : isLive ? (
                <div className="relative h-full w-full flex flex-col items-center justify-center bg-slate-950 min-h-[300px]">
                  <div className="flex flex-col items-center justify-center p-6 text-center text-slate-400 space-y-2 pointer-events-none select-none">
                    <Loader2 className="h-6 w-6 animate-spin text-red-500 mb-1" />
                    <span className="text-xs font-semibold text-slate-300">Live Media Feed Active</span>
                    <span className="text-[11px] text-slate-500 max-w-xs">
                      Connecting live feed preview... You can adjust your framing boxes below right now.
                    </span>
                  </div>
                  {(framingMode === 'split' || framingMode === 'pan') && (
                    <SourceCropSelector
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
              ) : (
                <div className="flex flex-col items-center justify-center p-8 text-center text-slate-500 text-xs">
                  <Loader2 className="h-6 w-6 animate-spin text-indigo-500 mb-2" />
                  Loading source media stream...
                </div>
              )}
            </div>

            {/* Video Scrubber & Play Bar */}
            <div className="flex items-center gap-3 pt-1">
              <button
                onClick={togglePlayPause}
                className="rounded-lg bg-slate-800 p-2 text-slate-300 hover:bg-slate-700 hover:text-white transition"
              >
                {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
              </button>

              <input
                type="range"
                min={0}
                max={duration || 100}
                step={0.2}
                value={currentTime}
                onChange={(e) => handleSeek(Number(e.target.value))}
                className="h-1.5 flex-1 accent-indigo-500 bg-slate-800 rounded-lg cursor-pointer"
              />

              <span className="text-xs font-mono text-slate-400 w-12 text-right">
                {formatSecs(currentTime)}
              </span>
            </div>

            {/* Split Screen Guidance Hint */}
            {framingMode === 'split' && (
              <div className="rounded-xl border border-cyan-500/20 bg-cyan-950/20 p-3.5 text-xs text-cyan-200/90 space-y-1">
                <div className="flex items-center gap-1.5 font-bold text-cyan-300">
                  <Info className="h-4 w-4 text-cyan-400 shrink-0" />
                  Gaming Split Screen Guidance
                </div>
                <p className="leading-relaxed">
                  Drag and resize the <strong className="text-cyan-300">Facecam (Cyan)</strong> and{' '}
                  <strong className="text-indigo-300">Gameplay (Purple)</strong> boxes above. Use this
                  mode only when your recording contains visible facecam footage. If facecam is
                  embedded in gameplay, frame the gameplay crop to exclude it.
                </p>
              </div>
            )}
          </div>

          {/* 2. Layout Mode Selection */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                <Crop className="h-4 w-4 text-indigo-400" />
                Select Vertical Layout
              </label>
              <span className="rounded-md bg-indigo-500/10 px-2 py-0.5 text-xs font-bold text-indigo-400 border border-indigo-500/20">
                {framingMode === 'crop' && 'Center Crop (9:16)'}
                {framingMode === 'fit' && 'Fit + Blurred BG'}
                {framingMode === 'pan' && 'Manual Pan Offset'}
                {framingMode === 'split' && 'Gaming Split Screen'}
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                {
                  id: 'crop',
                  name: 'Center Crop',
                  desc: 'Default 9:16 vertical crop',
                  icon: Crop,
                },
                {
                  id: 'fit',
                  name: 'Fit + Blurred',
                  desc: 'Full 16:9 + blurred bg',
                  icon: Maximize2,
                },
                {
                  id: 'pan',
                  name: 'Pan Offset',
                  desc: 'Custom horizontal position',
                  icon: MoveHorizontal,
                },
                {
                  id: 'split',
                  name: 'Gaming Split',
                  desc: 'Facecam + Gameplay stack',
                  icon: Split,
                },
              ].map((opt) => {
                const Icon = opt.icon;
                const isSelected = framingMode === opt.id;
                return (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => setFramingMode(opt.id as any)}
                    className={`flex flex-col items-center justify-center p-3.5 rounded-xl border text-center transition ${
                      isSelected
                        ? 'border-indigo-500 bg-indigo-600/20 text-white shadow-md shadow-indigo-600/20'
                        : 'border-slate-800 bg-slate-950/40 text-slate-400 hover:border-slate-700 hover:text-white'
                    }`}
                  >
                    <Icon className={`h-5 w-5 mb-1.5 ${isSelected ? 'text-indigo-400' : 'text-slate-500'}`} />
                    <span className="text-xs font-bold">{opt.name}</span>
                    <span className="text-[10px] text-slate-500 line-clamp-1">{opt.desc}</span>
                  </button>
                );
              })}
            </div>

            {/* Split Screen Secondary Controls (Order & Divider) */}
            {framingMode === 'split' && (
              <div className="space-y-4 pt-2 border-t border-slate-800">
                {/* Target box selector & Presets */}
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

                  {/* Quick Preset Buttons */}
                  <div className="flex items-center gap-1.5 text-[11px]">
                    <span className="text-slate-500">Presets:</span>
                    {activeCropTarget === 'facecam' ? (
                      <>
                        <button
                          type="button"
                          onClick={() =>
                            setFacecamCrop({ x: 0.7, y: 0.05, width: 0.28, height: 0.35 })
                          }
                          className="rounded bg-slate-800 px-2 py-1 text-slate-300 hover:bg-slate-700"
                        >
                          Top-Right
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            setFacecamCrop({ x: 0.02, y: 0.05, width: 0.28, height: 0.35 })
                          }
                          className="rounded bg-slate-800 px-2 py-1 text-slate-300 hover:bg-slate-700"
                        >
                          Top-Left
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            setFacecamCrop({ x: 0.02, y: 0.6, width: 0.28, height: 0.35 })
                          }
                          className="rounded bg-slate-800 px-2 py-1 text-slate-300 hover:bg-slate-700"
                        >
                          Bottom-Left
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            setFacecamCrop({ x: 0.7, y: 0.6, width: 0.28, height: 0.35 })
                          }
                          className="rounded bg-slate-800 px-2 py-1 text-slate-300 hover:bg-slate-700"
                        >
                          Bottom-Right
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          type="button"
                          onClick={() =>
                            setGameplayCrop({ x: 0.0, y: 0.0, width: 1.0, height: 1.0 })
                          }
                          className="rounded bg-slate-800 px-2 py-1 text-slate-300 hover:bg-slate-700"
                        >
                          Full 16:9
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            setGameplayCrop({ x: 0.0, y: 0.0, width: 0.72, height: 1.0 })
                          }
                          className="rounded bg-slate-800 px-2 py-1 text-slate-300 hover:bg-slate-700"
                        >
                          Exclude Right
                        </button>
                      </>
                    )}
                  </div>
                </div>

                {/* Pane Order Swap & Divider Position Slider */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                  <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3 space-y-2">
                    <span className="block text-xs font-semibold text-slate-400">
                      Pane Order
                    </span>
                    <button
                      type="button"
                      onClick={() =>
                        setSplitOrder(
                          splitOrder === 'facecam_top' ? 'gameplay_top' : 'facecam_top'
                        )
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

                  <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3 space-y-2">
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

            {/* Pan Offset slider */}
            {framingMode === 'pan' && (
              <div className="space-y-2 pt-2 border-t border-slate-800">
                <div className="flex justify-between text-xs font-semibold text-slate-400">
                  <span>Horizontal Pan Offset</span>
                  <span className="font-mono text-white">{panXOffset.toFixed(2)}</span>
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

          {/* 3. Subtitle Placement, Color, Font & Size Settings */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 shadow-xl space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
                <Type className="h-4 w-4 text-indigo-400" />
                Subtitle Styling & Placement
              </label>
              <span className="rounded-md bg-indigo-500/10 px-2 py-0.5 text-xs font-mono font-bold text-indigo-400 border border-indigo-500/20">
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
                <span className="rounded-md bg-indigo-500/10 px-2 py-0.5 text-xs font-mono font-bold text-indigo-400 border border-indigo-500/20">
                  {subtitleFontSize}px
                </span>
              </div>

              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: 'Small', size: 42, desc: 'Compact & clean' },
                  { label: 'Medium', size: 54, desc: 'Recommended default' },
                  { label: 'Large', size: 66, desc: 'High visibility pop' },
                ].map((preset) => (
                  <button
                    key={preset.size}
                    type="button"
                    onClick={() => setSubtitleFontSize(preset.size)}
                    className={`flex flex-col items-center justify-center p-3 rounded-xl border text-center transition ${
                      subtitleFontSize === preset.size
                        ? 'border-indigo-500 bg-indigo-600/20 text-white shadow-md'
                        : 'border-slate-800 bg-slate-950/40 text-slate-400 hover:border-slate-700 hover:text-white'
                    }`}
                  >
                    <span className="text-xs font-bold">{preset.label}</span>
                    <span className="text-[11px] font-mono text-indigo-400">{preset.size}px</span>
                    <span className="text-[10px] text-slate-500">{preset.desc}</span>
                  </button>
                ))}
              </div>

              {/* Fine-tune size slider */}
              <div className="space-y-1 pt-1">
                <div className="flex justify-between text-[11px] text-slate-400">
                  <span>Fine-tune font size</span>
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
                Karaoke word-by-word highlights, placement, and font styling are applied to both the live preview and final 1080×1920 MP4 export.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
