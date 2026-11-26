'use client';

import React from 'react';
import { Project } from '@/lib/types';
import {
  RotateCcw,
  Ban,
  Clock,
  Layers,
  Cpu,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { api } from '@/lib/api';

interface AnalysisProgressProps {
  project: Project;
  onRefresh: () => void;
}

export const AnalysisProgress: React.FC<AnalysisProgressProps> = ({ project, onRefresh }) => {
  const isRunning = ['importing', 'probing', 'analyzing'].includes(project.status);
  const isFailed = project.status === 'failed';
  const isCompleted = project.status === 'completed';

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '00:00';
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    if (hrs > 0) {
      return `${hrs}h ${mins}m ${secs}s`;
    }
    return `${mins}m ${secs}s`;
  };

  const progressPct =
    project.duration && project.duration > 0
      ? Math.min(100, Math.round((project.analyzed_duration / project.duration) * 100))
      : 0;

  const handleRetry = async () => {
    try {
      await api.retryProject(project.id);
      onRefresh();
    } catch (e: any) {
      alert(`Retry failed: ${e.message}`);
    }
  };

  const handleCancel = async () => {
    if (confirm('Are you sure you want to cancel the analysis?')) {
      try {
        await api.cancelProject(project.id);
        onRefresh();
      } catch (e: any) {
        alert(`Cancel failed: ${e.message}`);
      }
    }
  };

  const isPreGeneration = ['importing', 'probing'].includes(project.status) || (isFailed && !project.duration);

  return (
    <div className="rounded-2xl border border-divider bg-surface p-6 shadow-xl space-y-6 font-body">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h2 className="font-heading text-2xl font-normal text-text-primary tracking-tight">
              {project.title}
            </h2>
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize ${
                isCompleted
                  ? 'bg-status-success/10 text-status-success border border-status-success/20'
                  : isFailed
                  ? 'bg-status-error/10 text-status-error border border-status-error/20'
                  : 'bg-selected text-accent border border-accent/20 animate-pulse'
              }`}
            >
              {isPreGeneration && !isFailed ? (project.status === 'importing' ? 'Importing Source' : 'Preparing Source') : project.status}
            </span>
          </div>
          <p className="font-body text-xs text-text-secondary mt-1 flex items-center gap-2">
            <span>Source: <strong className="text-text-primary uppercase">{project.source_type}</strong></span>
            <span>•</span>
            <span>Created {new Date(project.created_at).toLocaleDateString()}</span>
            {isPreGeneration && !isFailed && (
              <>
                <span>•</span>
                <span className="text-accent font-medium">Reel Settings will display automatically when import finishes</span>
              </>
            )}
          </p>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          {isRunning && (
            <button
              onClick={handleCancel}
              className="flex items-center gap-1.5 rounded-xl border border-divider bg-surface-raised px-3.5 py-2 text-xs font-medium text-text-secondary hover:text-text-primary transition cursor-pointer"
            >
              <Ban className="h-3.5 w-3.5 text-status-error" /> Cancel
            </button>
          )}
          {isFailed && (
            <button
              onClick={handleRetry}
              className="btn-primary-action flex items-center gap-1.5 cursor-pointer"
            >
              <RotateCcw className="h-3.5 w-3.5" /> Retry Job
            </button>
          )}
        </div>
      </div>

      {/* Metric Cards */}
      {isPreGeneration ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-body">
          <div className="rounded-xl border border-divider bg-surface-raised p-3">
            <div className="flex items-center gap-1.5 text-xs text-text-secondary mb-1">
              <Clock className="h-3.5 w-3.5 text-accent" /> Pipeline Stage
            </div>
            <div className="text-sm font-bold text-text-primary">
              {project.status === 'importing' ? 'Streaming Download' : project.status === 'probing' ? 'Metadata Probing' : 'Import Interrupted'}
            </div>
          </div>

          <div className="rounded-xl border border-divider bg-surface-raised p-3">
            <div className="flex items-center gap-1.5 text-xs text-text-secondary mb-1">
              <Layers className="h-3.5 w-3.5 text-accent" /> Step Sequence
            </div>
            <div className="text-sm font-bold text-accent">
              Step 1 of 2 (Pre-Settings)
            </div>
          </div>

          <div className="rounded-xl border border-divider bg-surface-raised p-3">
            <div className="flex items-center gap-1.5 text-xs text-text-secondary mb-1">
              <CheckCircle2 className="h-3.5 w-3.5 text-text-secondary" /> Next Step
            </div>
            <div className="text-sm font-semibold text-text-primary">
              Reel Settings &amp; Framing
            </div>
          </div>

          <div className="rounded-xl border border-divider bg-surface-raised p-3">
            <div className="flex items-center gap-1.5 text-xs text-text-secondary mb-1">
              <Cpu className="h-3.5 w-3.5 text-accent" /> Resolution &amp; FPS
            </div>
            <div className="text-base font-bold text-text-primary font-mono timecode-digits">
              {project.probe_data ? `${project.probe_data.width}x${project.probe_data.height}` : 'Probing...'}
            </div>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-body">
          <div className="rounded-xl border border-divider bg-surface-raised p-3">
            <div className="flex items-center gap-1.5 text-xs text-text-secondary mb-1">
              <Clock className="h-3.5 w-3.5 text-accent" /> Total Duration
            </div>
            <div className="text-base font-bold text-text-primary font-mono timecode-digits">
              {formatDuration(project.duration)}
            </div>
          </div>

          <div className="rounded-xl border border-divider bg-surface-raised p-3">
            <div className="flex items-center gap-1.5 text-xs text-text-secondary mb-1">
              <CheckCircle2 className="h-3.5 w-3.5 text-status-success" /> Analyzed Timeline
            </div>
            <div className="text-base font-bold text-status-success font-mono timecode-digits">
              {formatDuration(project.analyzed_duration)}
            </div>
          </div>

          <div className="rounded-xl border border-divider bg-surface-raised p-3">
            <div className="flex items-center gap-1.5 text-xs text-text-secondary mb-1">
              <Layers className="h-3.5 w-3.5 text-accent" /> Chunks Analyzed
            </div>
            <div className="text-base font-bold text-text-primary font-mono timecode-digits">
              {project.completed_chunks} / {project.total_chunks || 1}
            </div>
          </div>

          <div className="rounded-xl border border-divider bg-surface-raised p-3">
            <div className="flex items-center gap-1.5 text-xs text-text-secondary mb-1">
              <Cpu className="h-3.5 w-3.5 text-accent" /> Resolution &amp; FPS
            </div>
            <div className="text-base font-bold text-text-primary font-mono timecode-digits">
              {project.probe_data ? `${project.probe_data.width}x${project.probe_data.height}` : 'Probing...'}
            </div>
          </div>
        </div>
      )}

      {/* Progress Bar */}
      <div className="space-y-2 font-body">
        <div className="flex justify-between text-xs text-text-secondary font-medium">
          <span className="flex items-center gap-1.5">
            {isRunning && <Loader2 className="h-3 w-3 animate-spin text-accent" />}
            {project.status === 'importing' && 'Streaming media from remote platform into storage... (Reel Settings will appear next)'}
            {project.status === 'probing' && 'Probing media streams and preparing framing preview...'}
            {project.status === 'analyzing' && `Analyzing chunks (${project.completed_chunks}/${project.total_chunks || 1})...`}
            {project.status === 'completed' && 'Complete recording analyzed! All qualifying reels generated.'}
            {project.status === 'failed' && (isPreGeneration ? 'Source import encountered an issue.' : 'Pipeline encountered an issue.')}
          </span>
          <span className="text-text-primary font-bold timecode-digits">{isPreGeneration ? (isFailed ? '0%' : '50%') : `${progressPct}%`}</span>
        </div>
        <div className="h-2.5 w-full overflow-hidden rounded-full bg-surface-raised border border-divider">
          <div
            className={`h-full transition-all duration-500 rounded-full ${
              isFailed
                ? 'bg-status-error'
                : 'bg-primary'
            }`}
            style={{ width: `${isCompleted ? 100 : isPreGeneration ? (isFailed ? 0 : 50) : progressPct}%` }}
          />
        </div>
      </div>

      {/* Error state */}
      {project.error_message && (
        <div className="flex items-start gap-2 rounded-xl bg-status-error/10 border border-status-error/20 p-3.5 text-xs text-status-error font-body">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-status-error" />
          <div>
            <strong className="font-semibold block mb-0.5">
              {isPreGeneration ? 'Source Media Alert:' : 'Analysis Alert:'}
            </strong>
            {project.error_message}
          </div>
        </div>
      )}
    </div>
  );
};
