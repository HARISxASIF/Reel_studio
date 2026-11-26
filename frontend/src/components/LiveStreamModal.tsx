'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Radio, Loader2, CheckCircle2, Clock, AlertTriangle, ShieldAlert, ArrowRight, Video, Sparkles } from 'lucide-react';
import { api } from '@/lib/api';
import { LiveProbeResult } from '@/lib/types';

interface LiveStreamModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const LiveStreamModal: React.FC<LiveStreamModalProps> = ({ isOpen, onClose }) => {
  const router = useRouter();
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [isProbing, setIsProbing] = useState(false);
  const [probeResult, setProbeResult] = useState<LiveProbeResult | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleProbe = async (inputUrl: string) => {
    setUrl(inputUrl);
    setError(null);

    if (!inputUrl || (!inputUrl.startsWith('http://') && !inputUrl.startsWith('https://'))) {
      setProbeResult(null);
      return;
    }

    setIsProbing(true);
    try {
      const res = await api.probeLiveStream(inputUrl);
      setProbeResult(res);
      if (res.title && !title) {
        setTitle(res.title);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to inspect live stream URL.');
      setProbeResult(null);
    } finally {
      setIsProbing(false);
    }
  };

  const handleCreateProject = async () => {
    if (!url) return;
    setIsSubmitting(true);
    setError(null);

    try {
      const { project } = await api.createLiveProject(url, title || probeResult?.title);
      router.push(`/projects/${project.id}`);
    } catch (err: any) {
      setError(err.message || 'Failed to create live stream project.');
      setIsSubmitting(false);
    }
  };

  const getCapabilityBadge = (capability?: string) => {
    switch (capability) {
      case 'live_available':
        return (
          <div className="flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-400 border border-emerald-500/20">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            Live Media Feed Available
          </div>
        );
      case 'waiting_for_stream':
        return (
          <div className="flex items-center gap-1.5 rounded-full bg-amber-500/10 px-3 py-1 text-xs font-semibold text-amber-400 border border-amber-500/20">
            <Clock className="h-3.5 w-3.5" />
            Waiting for Stream (Offline / Scheduled)
          </div>
        );
      case 'stream_ended':
        return (
          <div className="flex items-center gap-1.5 rounded-full bg-blue-500/10 px-3 py-1 text-xs font-semibold text-blue-400 border border-blue-500/20">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Broadcast Ended (VOD Available)
          </div>
        );
      case 'media_unavailable':
      default:
        return (
          <div className="flex items-center gap-1.5 rounded-full bg-rose-500/10 px-3 py-1 text-xs font-semibold text-rose-400 border border-rose-500/20">
            <ShieldAlert className="h-3.5 w-3.5" />
            Direct Media Unavailable
          </div>
        );
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div className="w-full max-w-xl rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
          <div className="flex items-center gap-2 text-white font-bold text-lg">
            <div className="rounded-lg bg-red-500/10 p-2 text-red-400 border border-red-500/20">
              <Radio className="h-5 w-5 animate-pulse" />
            </div>
            <span>Connect Live Stream</span>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white rounded-lg p-1.5 hover:bg-slate-800 transition"
          >
            ✕
          </button>
        </div>

        {/* Form Body */}
        <div className="mt-5 space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
              Live Stream URL (Direct HLS .m3u8, YouTube Live, Twitch, Kick)
            </label>
            <div className="relative">
              <input
                type="text"
                placeholder="e.g. http://server/live/stream.m3u8 or https://youtube.com/live/..."
                value={url}
                onChange={(e) => handleProbe(e.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white placeholder-slate-500 focus:border-red-500 focus:outline-none focus:ring-1 focus:ring-red-500"
              />
              {isProbing && (
                <div className="absolute right-3 top-3.5">
                  <Loader2 className="h-4 w-4 animate-spin text-red-400" />
                </div>
              )}
            </div>
            <p className="mt-1 text-[11px] text-slate-500">
              SSRF protection is applied to playlists, redirects, and every live media segment.
            </p>
          </div>

          {error && (
            <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-400 flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {/* Probe Results */}
          {probeResult && (
            <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs uppercase font-mono text-slate-400">
                  Platform: <strong className="text-white uppercase">{probeResult.platform}</strong>
                </span>
                {getCapabilityBadge(probeResult.capability)}
              </div>

              {probeResult.title && (
                <div className="text-sm font-semibold text-white">
                  {probeResult.title}
                </div>
              )}

              <p className="text-xs text-slate-400 leading-relaxed">
                {probeResult.message}
              </p>

              {probeResult.preview_frame_url && (
                <div className="relative aspect-video w-full rounded-lg overflow-hidden border border-slate-800 bg-black">
                  <img
                    src={probeResult.preview_frame_url}
                    alt="Live stream frame preview"
                    className="w-full h-full object-cover"
                  />
                  <span className="absolute bottom-2 left-2 rounded bg-black/70 px-2 py-0.5 text-[10px] text-white backdrop-blur">
                    Live Edge Frame Captured
                  </span>
                </div>
              )}

              {/* Guidance for Fallback */}
              {probeResult.capability === 'media_unavailable' && (
                <div className="rounded-lg bg-amber-500/10 border border-amber-500/20 p-3 text-xs text-amber-300">
                  <p className="font-semibold mb-1">Supported Fallbacks:</p>
                  <ul className="list-disc list-inside space-y-1 text-slate-300">
                    <li>Provide a direct HLS feed URL (<code className="text-amber-200">.m3u8</code>) that you control or have authorization to use.</li>
                    <li>Wait for the stream to conclude and import the recording via <strong>Import URL</strong>.</li>
                    <li>Upload the saved video file directly via <strong>Upload Video</strong>.</li>
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Optional Title input */}
          {probeResult && (
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
                Project Title (Optional)
              </label>
              <input
                type="text"
                placeholder="My Live Stream Highlights"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-4 py-2 text-sm text-white placeholder-slate-500 focus:border-red-500 focus:outline-none"
              />
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="mt-6 flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-slate-700 bg-slate-800 px-4 py-2.5 text-xs font-semibold text-slate-300 hover:bg-slate-700 hover:text-white transition"
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={handleCreateProject}
            disabled={!probeResult || probeResult.capability !== 'live_available' || isSubmitting}
            className="flex items-center gap-2 rounded-xl bg-red-600 px-5 py-2.5 text-xs font-semibold text-white shadow-lg shadow-red-600/30 hover:bg-red-500 disabled:opacity-50 disabled:pointer-events-none transition"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Connecting Stream...
              </>
            ) : (
              <>
                <span>Configure Reel Settings</span>
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
