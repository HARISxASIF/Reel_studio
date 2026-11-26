'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Link2, Sparkles, Check, AlertTriangle, ArrowRight, Loader2, Youtube, Video } from 'lucide-react';
import { api } from '@/lib/api';
import { UrlMetadata } from '@/lib/types';
import { ResumableUpload } from './ResumableUpload';

interface UrlImportModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const UrlImportModal: React.FC<UrlImportModalProps> = ({ isOpen, onClose }) => {
  const router = useRouter();
  const [url, setUrl] = useState('');
  const [isProbing, setIsProbing] = useState(false);
  const [metadata, setMetadata] = useState<UrlMetadata | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [createdProjectId, setCreatedProjectId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleProbeUrl = async (inputUrl: string) => {
    setUrl(inputUrl);
    setError(null);
    if (!inputUrl || (!inputUrl.startsWith('http://') && !inputUrl.startsWith('https://'))) {
      setMetadata(null);
      return;
    }

    setIsProbing(true);
    try {
      const data = await api.checkUrlMetadata(inputUrl);
      setMetadata(data);
    } catch (err: any) {
      setError(err.message || 'Failed to inspect URL.');
      setMetadata(null);
    } finally {
      setIsProbing(false);
    }
  };

  const handleStartImport = async () => {
    if (!url) return;
    setIsSubmitting(true);
    setError(null);

    try {
      const project = await api.createProjectFromUrl(url, metadata?.title);
      router.push(`/projects/${project.id}`);
    } catch (err: any) {
      setError(err.message || 'Failed to create project from URL.');
      setIsSubmitting(false);
    }
  };

  const formatSeconds = (sec?: number) => {
    if (!sec) return 'Unknown';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}m ${s}s`;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 font-body">
      <div className="w-full max-w-xl rounded-2xl border border-divider bg-surface p-6 shadow-2xl">
        <div className="flex items-center justify-between pb-4 border-b border-divider">
          <div className="flex items-center gap-2 font-heading text-xl font-normal text-text-primary">
            <Link2 className="h-5 w-5 text-accent" />
            Import from Video URL
          </div>
          <button
            onClick={onClose}
            className="text-text-secondary hover:text-text-primary rounded-lg p-1.5 hover:bg-surface-raised transition cursor-pointer"
          >
            ✕
          </button>
        </div>

        <div className="mt-4 space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-text-secondary mb-2">
              Source URL (YouTube, Twitch, Kick, or Direct MP4)
            </label>
            <div className="relative">
              <input
                type="text"
                placeholder="https://www.youtube.com/watch?v=... or direct video link"
                value={url}
                onChange={(e) => handleProbeUrl(e.target.value)}
                className="w-full rounded-xl border border-outline bg-surface-raised px-4 py-3 text-sm text-text-primary placeholder:text-text-secondary/50 focus:border-focus focus:outline-none focus:ring-1 focus:ring-focus transition"
              />
              {isProbing && (
                <div className="absolute right-3 top-3.5">
                  <Loader2 className="h-4 w-4 animate-spin text-accent" />
                </div>
              )}
            </div>
          </div>

          {/* Metadata preview card */}
          {metadata && (
            <div className="rounded-xl border border-divider bg-surface-raised p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-selected px-2.5 py-1 text-xs font-semibold text-accent border border-accent/20 uppercase tracking-wider">
                  {metadata.platform}
                </span>
                {metadata.duration && (
                  <span className="text-xs text-text-secondary font-mono timecode-digits">
                    Duration: {formatSeconds(metadata.duration)}
                  </span>
                )}
              </div>

              {metadata.title && (
                <p className="font-semibold text-text-primary text-sm">
                  {metadata.title}
                </p>
              )}

              <div className={`flex items-start gap-2 rounded-lg p-3 text-xs ${
                metadata.can_import_media
                  ? 'bg-status-success/10 text-status-success border border-status-success/20'
                  : 'bg-status-warning/10 text-status-warning border border-status-warning/20'
              }`}>
                {metadata.can_import_media ? (
                  <Check className="h-4 w-4 shrink-0 mt-0.5" />
                ) : (
                  <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                )}
                <span>{metadata.message}</span>
              </div>

              {/* If media cannot be downloaded directly, show fallback upload option inside the same dialog */}
              {!metadata.can_import_media && (
                <div className="mt-3 pt-3 border-t border-divider">
                  <p className="text-xs text-text-secondary mb-2 font-medium">
                    Upload the original video recording for this URL:
                  </p>
                  <ResumableUpload
                    onUploadComplete={(pId) => {
                      onClose();
                      router.push(`/projects/${pId}`);
                    }}
                  />
                </div>
              )}
            </div>
          )}

          {error && (
            <div className="rounded-xl bg-status-error/10 border border-status-error/20 p-3 text-xs text-status-error">
              {error}
            </div>
          )}
        </div>

        {/* Footer actions */}
        <div className="mt-6 flex items-center justify-end gap-3 pt-4 border-t border-divider">
          <button
            onClick={onClose}
            className="rounded-xl border border-divider px-4 py-2 text-sm font-semibold text-text-secondary hover:bg-surface-raised hover:text-text-primary transition cursor-pointer whitespace-nowrap shrink-0"
          >
            Cancel
          </button>
          <button
            disabled={!metadata?.can_import_media || isSubmitting}
            onClick={handleStartImport}
            className="btn-primary-action flex items-center gap-2 cursor-pointer disabled:opacity-50 disabled:pointer-events-none whitespace-nowrap shrink-0"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Importing...
              </>
            ) : (
              <>
                Start Analysis <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
