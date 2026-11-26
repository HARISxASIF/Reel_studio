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
} from 'lucide-react';
import { api } from '@/lib/api';
import { Project } from '@/lib/types';
import { ResumableUpload } from '@/components/ResumableUpload';
import { UrlImportModal } from '@/components/UrlImportModal';
import { LiveStreamModal } from '@/components/LiveStreamModal';

export default function Dashboard() {
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
    // Poll projects list every 4 seconds to capture active imports
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
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 space-y-10">
      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-3xl border border-slate-800 bg-gradient-to-br from-indigo-950/40 via-slate-900 to-slate-950 p-8 sm:p-12 shadow-2xl">
        <div className="relative z-10 max-w-2xl space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full bg-indigo-500/10 px-3 py-1 text-xs font-semibold text-indigo-400 border border-indigo-500/20">
            <Sparkles className="h-3.5 w-3.5" /> Next-Gen AI Video Engine
          </div>
          <h1 className="text-3xl sm:text-5xl font-black tracking-tight text-white leading-tight">
            Turn Any Long Video or Live Stream Into Viral Reels
          </h1>
          <p className="text-base text-slate-400 leading-relaxed">
            Automatically finds every worthwhile 30–150 second moment, shapes catchy headlines, burns word-level karaoke subtitles, and exports 1080×1920 MP4s ready for TikTok, Shorts & Reels.
          </p>
        </div>
      </div>

      {/* Creation & Ingest Section */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Resumable File Upload (6 cols on lg) */}
        <div className="lg:col-span-6 rounded-3xl border border-slate-800 bg-slate-900/60 p-6 shadow-xl flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <UploadCloud className="h-5 w-5 text-indigo-400" />
              <h2 className="text-lg font-bold text-white">Upload Recording</h2>
            </div>
            <p className="text-xs text-slate-400 mb-4">
              Directly upload large MP4/MOV files with multipart chunking and background progress.
            </p>
            <ResumableUpload />
          </div>
        </div>

        {/* URL Import Card (3 cols on lg) */}
        <div className="lg:col-span-3 flex flex-col justify-between rounded-3xl border border-slate-800 bg-slate-900/60 p-6 shadow-xl">
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Link2 className="h-5 w-5 text-indigo-400" />
              <h2 className="text-base font-bold text-white">Import Recorded URL</h2>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Import completed YouTube videos, Twitch VODs, or direct HTTP MP4 files.
            </p>
            <div className="flex flex-wrap gap-1.5 text-[10px] text-slate-500 font-medium pt-2">
              <span className="rounded bg-slate-800 px-2 py-0.5 border border-slate-700">YouTube VOD</span>
              <span className="rounded bg-slate-800 px-2 py-0.5 border border-slate-700">Twitch Past Broadcast</span>
              <span className="rounded bg-slate-800 px-2 py-0.5 border border-slate-700">Direct MP4</span>
            </div>
          </div>

          <button
            onClick={() => setIsUrlModalOpen(true)}
            className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-3 text-xs font-semibold text-white shadow-lg shadow-indigo-600/30 hover:bg-indigo-500 transition"
          >
            <Link2 className="h-4 w-4" />
            Enter Video URL
          </button>
        </div>

        {/* Live Stream Card (3 cols on lg) */}
        <div className="lg:col-span-3 flex flex-col justify-between rounded-3xl border border-red-950/40 bg-gradient-to-b from-red-950/20 to-slate-900/60 p-6 shadow-xl relative overflow-hidden">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Radio className="h-5 w-5 text-red-400 animate-pulse" />
                <h2 className="text-base font-bold text-white">Live Stream Clipping</h2>
              </div>
              <span className="rounded-full bg-red-500/10 px-2 py-0.5 text-[10px] font-bold uppercase text-red-400 border border-red-500/20 flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-red-400 animate-ping" />
                Live
              </span>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Clip viral moments in real time from ongoing YouTube Live, Twitch, Kick, or HLS feeds.
            </p>
            <div className="flex flex-wrap gap-1.5 text-[10px] text-slate-500 font-medium pt-2">
              <span className="rounded bg-slate-800 px-2 py-0.5 border border-slate-700">Direct HLS</span>
              <span className="rounded bg-slate-800 px-2 py-0.5 border border-slate-700">YouTube Live</span>
              <span className="rounded bg-slate-800 px-2 py-0.5 border border-slate-700">Twitch Live</span>
              <span className="rounded bg-slate-800 px-2 py-0.5 border border-slate-700">Kick Live</span>
            </div>
          </div>

          <button
            onClick={() => setIsLiveModalOpen(true)}
            className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-red-600 px-4 py-3 text-xs font-semibold text-white shadow-lg shadow-red-600/30 hover:bg-red-500 transition"
          >
            <Radio className="h-4 w-4" />
            Connect Live Stream
          </button>
        </div>
      </div>

      {/* Projects List */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
            <Film className="h-5 w-5 text-indigo-400" />
            Recent Projects
          </h2>
          <span className="text-xs text-slate-400">
            {projects.length} project{projects.length !== 1 ? 's' : ''}
          </span>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center p-12 text-slate-400">
            <Loader2 className="h-6 w-6 animate-spin mr-2 text-indigo-500" />
            Loading projects...
          </div>
        ) : projects.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-800 p-12 text-center">
            <Layers className="mx-auto h-10 w-10 text-slate-600 mb-3" />
            <h3 className="text-sm font-semibold text-slate-300">No projects yet</h3>
            <p className="mt-1 text-xs text-slate-500">
              Upload a video or paste a URL above to start generating vertical reels.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((project) => (
              <Link
                key={project.id}
                href={`/projects/${project.id}`}
                className="group flex flex-col justify-between rounded-2xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg transition duration-200 hover:border-slate-700 hover:bg-slate-900/90"
              >
                <div className="space-y-2.5">
                  <div className="flex items-center justify-between">
                    <span className="rounded-md bg-slate-800 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-400 border border-slate-700/60">
                      {project.source_type}
                    </span>
                    <div className="flex items-center gap-2">
                      <span
                        className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium capitalize ${
                          project.status === 'completed'
                            ? 'bg-emerald-500/10 text-emerald-400'
                            : project.status === 'failed'
                            ? 'bg-red-500/10 text-red-400'
                            : 'bg-indigo-500/10 text-indigo-400 animate-pulse'
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
                        className="rounded-lg p-1 text-slate-500 hover:bg-red-500/10 hover:text-red-400 transition"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>

                  <h3 className="text-base font-bold text-white group-hover:text-indigo-400 transition line-clamp-1">
                    {project.title}
                  </h3>

                  <div className="flex items-center gap-3 text-xs text-slate-400 font-mono">
                    <span className="flex items-center gap-1">
                      <Clock className="h-3.5 w-3.5 text-slate-500" />
                      {formatDuration(project.duration)}
                    </span>
                    {project.total_chunks > 0 && (
                      <span>
                        {project.completed_chunks}/{project.total_chunks} chunks
                      </span>
                    )}
                  </div>
                </div>

                <div className="mt-4 flex items-center justify-between border-t border-slate-800/80 pt-3 text-xs text-slate-400">
                  <span>{new Date(project.created_at).toLocaleDateString()}</span>
                  <span className="flex items-center gap-1 font-semibold text-indigo-400 group-hover:translate-x-1 transition">
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-red-500/10 p-2.5 text-red-400 border border-red-500/20">
                <Trash2 className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Delete Project</h3>
                <p className="text-xs text-slate-400">This action cannot be undone.</p>
              </div>
            </div>

            <p className="text-sm text-slate-300">
              Are you sure you want to delete <strong className="text-white font-semibold">&ldquo;{projectToDelete.title}&rdquo;</strong>?
              All associated reels, renders, transcripts, and storage files will be permanently deleted.
            </p>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setProjectToDelete(null)}
                disabled={isDeleting}
                className="rounded-xl bg-slate-800 px-4 py-2.5 text-xs font-semibold text-slate-300 hover:bg-slate-700 hover:text-white transition disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteProject}
                disabled={isDeleting}
                className="flex items-center gap-2 rounded-xl bg-red-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-red-600/30 hover:bg-red-500 transition disabled:opacity-50"
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
