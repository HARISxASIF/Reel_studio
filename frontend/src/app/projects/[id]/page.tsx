'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Sparkles,
  Download,
  Filter,
  Plus,
  Sliders,
  Archive,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Trash2,
  Share2,
} from 'lucide-react';
import { api } from '@/lib/api';
import { Project, Reel, BulkExport, LiveSession } from '@/lib/types';
import { AnalysisProgress } from '@/components/AnalysisProgress';
import { ReelCard } from '@/components/ReelCard';
import { ReelSettingsStep } from '@/components/ReelSettingsStep';
import { LiveSessionDashboard } from '@/components/LiveSessionDashboard';
import { SocialPublishingTab } from '@/components/SocialPublishingTab';

export default function ProjectPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const [project, setProject] = useState<Project | null>(null);
  const [liveSession, setLiveSession] = useState<LiveSession | null>(null);
  const [reels, setReels] = useState<Reel[]>([]);
  const [borderlineCount, setBorderlineCount] = useState<number>(0);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'gallery' | 'social'>('gallery');

  // Filters & Thresholds
  const [minScore, setMinScore] = useState<number>(65);
  const [includeBorderline, setIncludeBorderline] = useState<boolean>(false);
  const [category, setCategory] = useState<string>('all');

  // Manual Reel Creator Modal
  const [isManualModalOpen, setIsManualModalOpen] = useState(false);
  const [manualStart, setManualStart] = useState<number>(0);
  const [manualEnd, setManualEnd] = useState<number>(45);
  const [manualCaption, setManualCaption] = useState<string>('MY FAVORITE MOMENT');
  const [isCreatingManual, setIsCreatingManual] = useState(false);

  // Bulk ZIP export
  const [bulkExport, setBulkExport] = useState<BulkExport | null>(null);
  const [isExportingZip, setIsExportingZip] = useState(false);

  // Project deletion
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isDeletingProject, setIsDeletingProject] = useState(false);

  const handleDeleteProject = async () => {
    if (!projectId) return;
    setIsDeletingProject(true);
    try {
      await api.deleteProject(projectId);
      router.push('/');
    } catch (err: any) {
      alert(`Failed to delete project: ${err.message || 'Unknown error'}`);
      setIsDeletingProject(false);
    }
  };

  const fetchProjectData = useCallback(async () => {
    if (!projectId) return;
    try {
      const proj = await api.getProject(projectId);

      if (proj.source_type === 'live_stream') {
        try {
          const sess = await api.getLiveSession(projectId);
          setLiveSession(sess);
        } catch {}
      }

      setProject(proj);

      const reelsData = await api.getProjectReels(
        projectId,
        minScore,
        includeBorderline,
        category
      );
      setReels(reelsData.items);
      setBorderlineCount(reelsData.borderline_count);
    } catch (err) {
      console.error('Failed to load project details:', err);
    } finally {
      setIsLoading(false);
    }
  }, [projectId, minScore, includeBorderline, category]);

  useEffect(() => {
    fetchProjectData();
    // Poll project every 3 seconds if analyzing or reels are rendering
    const interval = setInterval(() => {
      fetchProjectData();
    }, 3000);
    return () => clearInterval(interval);
  }, [fetchProjectData]);

  const handleCreateManualReel = async () => {
    const dur = manualEnd - manualStart;
    if (dur < 30 || dur > 150) {
      alert(`Clip duration must be between 30 and 150 seconds (currently ${dur.toFixed(1)}s).`);
      return;
    }
    setIsCreatingManual(true);
    try {
      await api.createManualReel(projectId, {
        source_start: manualStart,
        source_end: manualEnd,
        top_caption: manualCaption,
        framing_mode: 'crop',
      });
      setIsManualModalOpen(false);
      fetchProjectData();
    } catch (e: any) {
      alert(`Failed to create reel: ${e.message}`);
    } finally {
      setIsCreatingManual(false);
    }
  };

  const handleTriggerZip = async () => {
    setIsExportingZip(true);
    try {
      const res = await api.exportProjectZip(projectId);
      setBulkExport(res);
      // Poll zip status
      const pollZip = setInterval(async () => {
        try {
          const statusRes = await api.getZipExportStatus(projectId, res.id);
          setBulkExport(statusRes);
          if (statusRes.status === 'completed' || statusRes.status === 'failed') {
            clearInterval(pollZip);
            setIsExportingZip(false);
          }
        } catch {
          clearInterval(pollZip);
          setIsExportingZip(false);
        }
      }, 2000);
    } catch (e: any) {
      alert(`ZIP export failed: ${e.message}`);
      setIsExportingZip(false);
    }
  };

  const handleDeleteReel = (deletedReelId: string) => {
    setReels((prev) => prev.filter((r) => r.id !== deletedReelId));
  };

  if (isLoading && !project) {
    return (
      <div className="flex h-96 items-center justify-center text-slate-400">
        <Loader2 className="h-8 w-8 animate-spin text-indigo-500 mr-3" />
        Loading project analysis...
      </div>
    );
  }

  if (!project) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-16 text-center">
        <h2 className="text-xl font-bold text-white">Project Not Found</h2>
        <Link href="/" className="mt-4 inline-flex items-center gap-1.5 text-sm text-indigo-400 hover:underline">
          <ArrowLeft className="h-4 w-4" /> Return to Dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 space-y-8">
      {/* Top Navigation */}
      <div className="flex items-center justify-between">
        <Link
          href="/"
          className="inline-flex items-center gap-2 rounded-xl bg-slate-900 border border-slate-800 px-3.5 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-800 hover:text-white transition shadow"
        >
          <ArrowLeft className="h-4 w-4" /> All Projects
        </Link>

        {/* Bulk Export Button */}
        <div className="flex items-center gap-3">
          {bulkExport?.status === 'completed' && bulkExport.download_url ? (
            <a
              href={bulkExport.download_url}
              className="flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-emerald-600/30 hover:bg-emerald-500"
            >
              <Download className="h-4 w-4" />
              Download ZIP ({bulkExport.reel_count} Reels)
            </a>
          ) : (
            <button
              onClick={handleTriggerZip}
              disabled={isExportingZip || reels.length === 0}
              className="flex items-center gap-2 rounded-xl bg-slate-800 border border-slate-700 px-4 py-2.5 text-xs font-semibold text-slate-200 hover:bg-slate-700 hover:text-white transition shadow disabled:opacity-50"
            >
              {isExportingZip ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />
                  Generating Archive...
                </>
              ) : (
                <>
                  <Archive className="h-4 w-4 text-indigo-400" />
                  Download All as ZIP
                </>
              )}
            </button>
          )}

          <button
            onClick={() => setIsManualModalOpen(true)}
            className="flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-indigo-600/30 hover:bg-indigo-500 transition"
          >
            <Plus className="h-4 w-4" /> Custom Clip
          </button>

          <button
            onClick={() => setIsDeleteModalOpen(true)}
            className="flex items-center gap-1.5 rounded-xl bg-red-950/40 border border-red-800/60 px-3.5 py-2.5 text-xs font-semibold text-red-300 hover:bg-red-900/60 hover:text-white transition shadow"
            title="Delete this project and all reels"
          >
            <Trash2 className="h-4 w-4 text-red-400" />
            Delete Project
          </button>
        </div>
      </div>

      {/* Tab Switcher: Reels Gallery vs Upload on Social Media */}
      <div className="flex items-center gap-3 border-b border-slate-800 pb-4">
        <button
          onClick={() => setActiveTab('gallery')}
          className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-xs font-bold transition shadow ${
            activeTab === 'gallery'
              ? 'bg-indigo-600 text-white shadow-indigo-600/25'
              : 'bg-slate-900 border border-slate-800 text-slate-400 hover:bg-slate-800 hover:text-white'
          }`}
        >
          <Sparkles className="h-4 w-4" />
          Reels Gallery
          <span className="rounded-full bg-slate-950/80 px-2 py-0.5 text-[10px] text-slate-300 border border-slate-700">
            {reels.length}
          </span>
        </button>

        <button
          onClick={() => setActiveTab('social')}
          className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-xs font-bold transition shadow ${
            activeTab === 'social'
              ? 'bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 text-white shadow-indigo-600/30 ring-1 ring-white/20'
              : 'bg-slate-900 border border-slate-800 text-slate-400 hover:bg-slate-800 hover:text-white'
          }`}
        >
          <Share2 className="h-4 w-4 text-pink-400" />
          Upload on Social Media
          <span className="rounded-full bg-pink-500/20 text-pink-300 border border-pink-500/30 px-2 py-0.5 text-[10px] font-bold">
            YouTube • Meta • TikTok
          </span>
        </button>
      </div>

      {activeTab === 'social' ? (
        <SocialPublishingTab
          project={project}
          reels={reels}
          onRefreshReels={fetchProjectData}
        />
      ) : (
        <>
          {/* If project is ready for reel configuration, show Reel Settings Step */}
          {project.status === 'ready' ? (
            <ReelSettingsStep
              project={project}
              onGenerationStarted={fetchProjectData}
              isLiveStream={project.source_type === 'live_stream'}
              livePreviewUrl={liveSession?.preview_frame_url}
            />
          ) : project.source_type === 'live_stream' ? (
            <LiveSessionDashboard
              project={project}
              reels={reels}
              onRefresh={fetchProjectData}
            />
          ) : (
            <>
              {/* Analysis Progress & State */}
              <AnalysisProgress project={project} onRefresh={fetchProjectData} />

              {/* Reel Filtering & Threshold Control */}
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 rounded-2xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg">
                {/* Category Pills */}
                <div className="flex flex-wrap items-center gap-2">
                  {['all', 'hook', 'humor', 'insight', 'reaction', 'story', 'highlight'].map((cat) => (
                    <button
                      key={cat}
                      onClick={() => setCategory(cat)}
                      className={`rounded-xl px-3 py-1.5 text-xs font-bold uppercase tracking-wider transition ${
                        category === cat
                          ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/25'
                          : 'bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-white'
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>

                {/* Quality Threshold Slider */}
                <div className="flex flex-wrap items-center gap-4">
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-slate-400 font-medium flex items-center gap-1.5">
                      <Sliders className="h-3.5 w-3.5 text-indigo-400" />
                      Min Score: <strong className="text-white">{minScore}</strong>
                    </span>
                    <input
                      type="range"
                      min={0}
                      max={100}
                      step={5}
                      value={minScore}
                      onChange={(e) => setMinScore(Number(e.target.value))}
                      className="h-1.5 w-24 sm:w-32 accent-indigo-500 bg-slate-800 rounded-lg cursor-pointer"
                    />
                  </div>

                  {/* Borderline toggle */}
                  <label className="flex items-center gap-2 text-xs text-slate-400 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={includeBorderline}
                      onChange={(e) => setIncludeBorderline(e.target.checked)}
                      className="rounded border-slate-700 bg-slate-950 text-indigo-600 focus:ring-0"
                    />
                    <span>
                      Show Borderline ({borderlineCount})
                    </span>
                  </label>
                </div>
              </div>
            </>
          )}

          {/* Reels Gallery */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-indigo-400" />
                Generated Reels
                <span className="rounded-full bg-slate-800 px-2.5 py-0.5 text-xs text-slate-400 border border-slate-700">
                  {reels.length}
                </span>
              </h3>
            </div>

            {reels.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-800 p-12 text-center space-y-3">
                <Sparkles className="mx-auto h-8 w-8 text-slate-600" />
                <h4 className="text-sm font-semibold text-slate-300">
                  {project.status === 'completed'
                    ? 'No reels matched the current score threshold'
                    : 'Analyzing recording for viral moments...'}
                </h4>
                <p className="text-xs text-slate-500 max-w-md mx-auto">
                  {project.status === 'completed' ? (
                    <>Try lowering the minimum score slider above, checking "Show Borderline", or click <strong>Custom Clip</strong> to select a 30–150 second range.</>
                  ) : (
                    'Chunks are being transcribed and evaluated. Reels will appear here as soon as they are identified.'
                  )}
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
                {reels.map((reel) => (
                  <ReelCard key={reel.id} reel={reel} projectId={projectId} onDelete={handleDeleteReel} />
                ))}
              </div>
            )}
          </div>
        </>
      )}


      {/* Manual Clip Creator Modal */}
      {isManualModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="text-base font-bold text-white">Create Custom 30–150s Reel</h3>
              <button onClick={() => setIsManualModalOpen(false)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
                  Start Time (seconds in video)
                </label>
                <input
                  type="number"
                  min={0}
                  max={project.duration || 36000}
                  value={manualStart}
                  onChange={(e) => setManualStart(Number(e.target.value))}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2.5 text-sm text-white"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
                  End Time (seconds in video)
                </label>
                <input
                  type="number"
                  min={manualStart + 30}
                  max={manualStart + 150}
                  value={manualEnd}
                  onChange={(e) => setManualEnd(Number(e.target.value))}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2.5 text-sm text-white"
                />
                <p className="text-[11px] text-slate-500 mt-1">
                  Duration: {(manualEnd - manualStart).toFixed(1)}s (must be between 30 and 150 seconds)
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
                  Top Caption Headline
                </label>
                <input
                  type="text"
                  value={manualCaption}
                  onChange={(e) => setManualCaption(e.target.value)}
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2.5 text-sm text-white uppercase"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-800">
              <button
                onClick={() => setIsManualModalOpen(false)}
                className="rounded-xl px-4 py-2 text-xs font-semibold text-slate-400 hover:bg-slate-800"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateManualReel}
                disabled={isCreatingManual}
                className="flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
              >
                {isCreatingManual ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
                Create & Render Reel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Project Confirmation Modal */}
      {isDeleteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="rounded-xl bg-red-500/10 p-2.5 text-red-400 border border-red-500/20">
                <Trash2 className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Delete Project</h3>
                <p className="text-xs text-slate-400">Permanent and irreversible</p>
              </div>
            </div>

            <p className="text-sm text-slate-300">
              Are you sure you want to delete <strong className="text-white font-semibold">&ldquo;{project.title}&rdquo;</strong>?
              All associated reels, renders, transcripts, and storage files will be permanently deleted.
            </p>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setIsDeleteModalOpen(false)}
                disabled={isDeletingProject}
                className="rounded-xl bg-slate-800 px-4 py-2.5 text-xs font-semibold text-slate-300 hover:bg-slate-700 hover:text-white transition disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteProject}
                disabled={isDeletingProject}
                className="flex items-center gap-2 rounded-xl bg-red-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-red-600/30 hover:bg-red-500 transition disabled:opacity-50"
              >
                {isDeletingProject ? (
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
