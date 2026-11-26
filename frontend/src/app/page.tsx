'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  Film,
  Link2,
  UploadCloud,
  Clock,
  Sparkles,
  ArrowRight,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Layers,
  Radio,
  Trash2,
  Settings,
} from 'lucide-react';
import { api } from '@/lib/api';
import { Project } from '@/lib/types';
import { ResumableUpload } from '@/components/ResumableUpload';
import { UrlImportModal } from '@/components/UrlImportModal';
import { LiveStreamModal } from '@/components/LiveStreamModal';
import { useAuth } from '@/context/AuthContext';

export default function Dashboard() {
  const { user } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUrlModalOpen, setIsUrlModalOpen] = useState(false);
  const [isLiveModalOpen, setIsLiveModalOpen] = useState(false);
  const [projectToDelete, setProjectToDelete] = useState<Project | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDeleteProject = async () => {
    if (!projectToDelete) return;
    setIsDeleting(true);
    try {
      await api.deleteProject(projectToDelete.id);
      setProjects((prev) => prev.filter((p) => p.id !== projectToDelete.id));
      setProjectToDelete(null);
    } catch (err: any) {
      alert(`Failed to delete project: ${err.message || 'Unknown error'}`);
    } finally {
      setIsDeleting(false);
    }
  };

  const fetchProjects = async () => {
    try {
      const data = await api.listProjects();
      setProjects(data.items);
    } catch (err) {
      console.error('Failed to load projects:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
    const interval = setInterval(fetchProjects, 4000);
    return () => clearInterval(interval);
  }, []);

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '—';
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    return hrs > 0 ? `${hrs}h ${mins}m` : `${mins}m ${secs}s`;
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 space-y-10 font-body">
      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-3xl border border-divider bg-surface p-8 sm:p-12 shadow-xl transition-colors duration-200">
        <div className="relative z-10 max-w-2xl space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full bg-accent/10 px-3 py-1 text-xs font-semibold text-accent border border-accent/20">
            <Sparkles className="h-3.5 w-3.5" /> Next-Gen AI Video Engine
          </div>
          <h1 className="font-heading text-3xl sm:text-5xl font-bold tracking-tight text-text-primary leading-tight">
            {user?.full_name
              ? `Welcome, ${user.full_name.split(' ')[0]}`
              : 'Turn Any Long Video or Live Stream Into Viral Reels'}
          </h1>
          <p className="font-body text-base text-text-secondary leading-relaxed font-medium">
            Automatically finds every worthwhile 30–150 second moment, shapes catchy headlines, burns word-level karaoke subtitles, and exports 1080×1920 MP4s ready for TikTok, Shorts &amp; Reels.
          </p>
        </div>
      </div>

      {/* Creation & Ingest Section */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Resumable File Upload (6 cols on lg) */}
        <div className="lg:col-span-6 rounded-3xl border border-divider bg-surface p-6 shadow-xl flex flex-col justify-between transition-colors duration-200">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <UploadCloud className="h-5 w-5 text-accent" />
              <h2 className="font-heading text-2xl font-bold text-text-primary">Upload Recording</h2>
            </div>
            <p className="text-xs text-text-secondary mb-4 font-medium">
              Directly upload large MP4/MOV files with multipart chunking and background progress.
            </p>
            <ResumableUpload />
          </div>
        </div>

        {/* URL Import Card (3 cols on lg) */}
        <div className="lg:col-span-3 flex flex-col justify-between rounded-3xl border border-divider bg-surface p-6 shadow-xl transition-colors duration-200">
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Link2 className="h-5 w-5 text-accent" />
              <h2 className="font-heading text-xl font-bold text-text-primary">Import Video URL</h2>
            </div>
            <p className="text-xs text-text-secondary leading-relaxed font-medium">
              Import completed YouTube videos, Twitch VODs, or direct HTTP MP4 files.
            </p>
            <div className="flex flex-wrap gap-1.5 text-[10px] text-text-secondary font-medium pt-2">
              <span className="rounded bg-surface-raised px-2 py-0.5 border border-divider">YouTube VOD</span>
              <span className="rounded bg-surface-raised px-2 py-0.5 border border-divider">Twitch VOD</span>
              <span className="rounded bg-surface-raised px-2 py-0.5 border border-divider">Direct MP4</span>
            </div>
          </div>

          <button
            onClick={() => setIsUrlModalOpen(true)}
            className="btn-primary-action mt-6 flex w-full items-center justify-center gap-2 rounded-xl py-3 text-xs font-bold shadow-lg shadow-purple-600/30 transition cursor-pointer whitespace-nowrap shrink-0"
          >
            <Link2 className="h-4 w-4" />
            Enter Video URL
          </button>
        </div>

        {/* Live Stream Card (3 cols on lg) */}
        <div className="lg:col-span-3 flex flex-col justify-between rounded-3xl border border-divider bg-surface p-6 shadow-xl relative overflow-hidden transition-colors duration-200">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Radio className="h-5 w-5 text-status-error animate-pulse" />
                <h2 className="font-heading text-xl font-bold text-text-primary">Live Clipping</h2>
              </div>
              <span className="rounded-full bg-status-error/10 px-2 py-0.5 text-[10px] font-bold uppercase text-status-error border border-status-error/20 flex items-center gap-1 font-body">
                <span className="h-1.5 w-1.5 rounded-full bg-status-error animate-ping" />
                Live
              </span>
            </div>
            <p className="text-xs text-text-secondary leading-relaxed font-medium">
              Clip viral moments in real time from ongoing YouTube Live, Twitch, Kick, or HLS feeds.
            </p>
            <div className="flex flex-wrap gap-1.5 text-[10px] text-text-secondary font-medium pt-2">
              <span className="rounded bg-surface-raised px-2 py-0.5 border border-divider">Direct HLS</span>
              <span className="rounded bg-surface-raised px-2 py-0.5 border border-divider">YouTube Live</span>
              <span className="rounded bg-surface-raised px-2 py-0.5 border border-divider">Twitch</span>
            </div>
          </div>

          <button
            onClick={() => setIsLiveModalOpen(true)}
            className="btn-primary-action mt-6 flex w-full items-center justify-center gap-2 rounded-xl py-3 text-xs font-bold shadow-lg shadow-purple-600/30 transition cursor-pointer whitespace-nowrap shrink-0"
          >
            <Radio className="h-4 w-4" />
            Connect Live Stream
          </button>
        </div>
      </div>

      {/* Projects List */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-heading text-2xl sm:text-3xl font-bold text-text-primary tracking-tight flex items-center gap-2">
            <Film className="h-5 w-5 text-accent" />
            Recent Projects
          </h2>
          <span className="text-xs text-text-secondary font-medium">
            {projects.length} project{projects.length !== 1 ? 's' : ''}
          </span>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center p-12 text-text-secondary">
            <Loader2 className="h-6 w-6 animate-spin mr-2 text-accent" />
            Loading projects...
          </div>
        ) : projects.length === 0 ? (
          <div className="rounded-3xl border border-divider bg-surface p-8 sm:p-12 text-center space-y-8 shadow-md">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-accent/10 text-accent border border-accent/20">
              <Layers className="h-8 w-8" />
            </div>

            <div className="max-w-md mx-auto space-y-2">
              <h3 className="font-heading text-2xl font-bold text-text-primary">Your Workspace is Ready</h3>
              <p className="text-xs text-text-secondary leading-relaxed font-medium">
                You don&apos;t have any projects yet. Upload a video file or paste a YouTube / Twitch URL to generate your first set of viral reels!
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 max-w-2xl mx-auto pt-2">
              <button
                type="button"
                onClick={() => setIsUrlModalOpen(true)}
                className="flex flex-col items-center gap-2 p-4 rounded-2xl border border-divider bg-surface-raised hover:border-accent hover:bg-surface transition group text-center cursor-pointer"
              >
                <div className="p-2.5 rounded-xl bg-accent/10 text-accent group-hover:bg-primary group-hover:text-primary-text transition">
                  <Link2 className="h-5 w-5" />
                </div>
                <span className="text-xs font-bold text-text-primary">Import Video URL</span>
                <span className="text-[11px] text-text-secondary">YouTube VOD or Twitch stream</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  const uploadEl = document.querySelector('input[type="file"]') as HTMLInputElement;
                  if (uploadEl) uploadEl.click();
                }}
                className="flex flex-col items-center gap-2 p-4 rounded-2xl border border-divider bg-surface-raised hover:border-accent hover:bg-surface transition group text-center cursor-pointer"
              >
                <div className="p-2.5 rounded-xl bg-accent/10 text-accent group-hover:bg-primary group-hover:text-primary-text transition">
                  <UploadCloud className="h-5 w-5" />
                </div>
                <span className="text-xs font-bold text-text-primary">Upload MP4 File</span>
                <span className="text-[11px] text-text-secondary">Direct multipart chunking</span>
              </button>

              <button
                type="button"
                onClick={() => setIsLiveModalOpen(true)}
                className="flex flex-col items-center gap-2 p-4 rounded-2xl border border-divider bg-surface-raised hover:border-status-error hover:bg-surface transition group text-center cursor-pointer"
              >
                <div className="p-2.5 rounded-xl bg-status-error/10 text-status-error group-hover:bg-status-error group-hover:text-white transition">
                  <Radio className="h-5 w-5" />
                </div>
                <span className="text-xs font-bold text-text-primary">Live Stream</span>
                <span className="text-[11px] text-text-secondary">Clip ongoing live broadcasts</span>
              </button>
            </div>

            {/* Quick Integrations Prompt */}
            <div className="max-w-2xl mx-auto rounded-2xl border border-accent/20 bg-selected p-5 flex flex-col sm:flex-row items-center justify-between gap-4 text-left">
              <div className="flex items-center gap-3.5">
                <div className="rounded-xl bg-accent/20 p-2.5 text-accent border border-accent/30 shrink-0">
                  <Sparkles className="h-5 w-5" />
                </div>
                <div>
                  <h4 className="text-sm font-bold text-text-primary">Supercharge with Google AI & YouTube</h4>
                  <p className="text-xs text-text-secondary mt-0.5 font-medium">
                    Connect your free Gemini API key and YouTube channel in Settings to unlock AI highlight discovery and 1-click publishing.
                  </p>
                </div>
              </div>
              <Link
                href="/settings"
                className="btn-primary-action shrink-0 flex items-center gap-1.5 rounded-xl px-4 py-2 text-xs font-bold shadow-lg shadow-purple-600/30 transition whitespace-nowrap"
              >
                <Settings className="h-3.5 w-3.5" />
                Open Settings
              </Link>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((project) => (
              <Link
                key={project.id}
                href={`/projects/${project.id}`}
                className="group flex flex-col justify-between rounded-2xl border border-divider bg-surface p-5 shadow-lg transition duration-200 hover:border-outline hover:shadow-xl"
              >
                <div className="space-y-2.5">
                  <div className="flex items-center justify-between">
                    <span className="rounded-md bg-surface-raised px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-text-secondary border border-divider">
                      {project.source_type}
                    </span>
                    <div className="flex items-center gap-2">
                      <span
                        className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold capitalize ${
                          project.status === 'completed'
                            ? 'bg-status-success/10 text-status-success border border-status-success/20'
                            : project.status === 'failed'
                            ? 'bg-status-error/10 text-status-error border border-status-error/20'
                            : 'bg-accent/10 text-accent border border-accent/20 animate-pulse'
                        }`}
                      >
                        {project.status === 'completed' && <CheckCircle2 className="h-3 w-3" />}
                        {project.status === 'failed' && <AlertCircle className="h-3 w-3" />}
                        {['analyzing', 'importing', 'probing'].includes(project.status) && (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        )}
                        {project.status}
                      </span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          setProjectToDelete(project);
                        }}
                        title="Delete Project"
                        className="rounded-lg p-1 text-text-secondary hover:bg-status-error/10 hover:text-status-error transition cursor-pointer"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>

                  <h3 className="font-heading text-lg font-normal text-text-primary group-hover:text-accent transition line-clamp-1">
                    {project.title}
                  </h3>

                  <div className="flex items-center gap-3 text-xs text-text-secondary font-medium">
                    <span className="flex items-center gap-1 timecode-digits">
                      <Clock className="h-3.5 w-3.5 text-text-secondary" />
                      {formatDuration(project.duration)}
                    </span>
                    {project.total_chunks > 0 && (
                      <span className="timecode-digits">
                        {project.completed_chunks}/{project.total_chunks} chunks
                      </span>
                    )}
                  </div>
                </div>

                <div className="mt-4 flex items-center justify-between border-t border-divider pt-3 text-xs text-text-secondary">
                  <span>{new Date(project.created_at).toLocaleDateString()}</span>
                  <span className="flex items-center gap-1 font-bold text-accent group-hover:translate-x-1 transition">
                    View Reels <ArrowRight className="h-3.5 w-3.5" />
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* URL Import Modal */}
      <UrlImportModal
        isOpen={isUrlModalOpen}
        onClose={() => {
          setIsUrlModalOpen(false);
          fetchProjects();
        }}
      />

      {/* Live Stream Connect Modal */}
      <LiveStreamModal
        isOpen={isLiveModalOpen}
        onClose={() => {
          setIsLiveModalOpen(false);
          fetchProjects();
        }}
      />

      {/* Delete Project Confirmation Modal */}
      {projectToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="w-full max-w-md rounded-2xl border border-divider bg-surface p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-status-error/10 p-2.5 text-status-error border border-status-error/20">
                <Trash2 className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-heading text-xl font-normal text-text-primary">Delete Project</h3>
                <p className="text-xs text-text-secondary font-medium">This action cannot be undone.</p>
              </div>
            </div>

            <p className="text-sm text-text-secondary font-medium">
              Are you sure you want to delete <strong className="text-text-primary font-bold">&ldquo;{projectToDelete.title}&rdquo;</strong>?
              All associated reels, renders, transcripts, and storage files will be permanently deleted.
            </p>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setProjectToDelete(null)}
                disabled={isDeleting}
                className="rounded-xl bg-surface-raised border border-divider px-4 py-2.5 text-xs font-semibold text-text-secondary hover:bg-surface hover:text-text-primary transition disabled:opacity-50 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteProject}
                disabled={isDeleting}
                className="flex items-center gap-2 rounded-xl bg-status-error px-4 py-2.5 text-xs font-bold text-white shadow-lg shadow-red-600/30 hover:brightness-110 transition disabled:opacity-50 cursor-pointer"
              >
                {isDeleting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Deleting...
                  </>
                ) : (
                  <>
                    <Trash2 className="h-4 w-4" />
                    Delete Project
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
