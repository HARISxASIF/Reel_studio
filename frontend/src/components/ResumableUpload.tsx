'use client';

import React, { useState, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { UploadCloud, Play, Pause, X, FileVideo, CheckCircle2, AlertCircle } from 'lucide-react';
import { S3MultipartUploader, UploadProgress } from '@/lib/s3_upload';

interface ResumableUploadProps {
  projectId?: string;
  onUploadComplete?: (projectId: string) => void;
}

export const ResumableUpload: React.FC<ResumableUploadProps> = ({ projectId, onUploadComplete }) => {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploaderRef = useRef<S3MultipartUploader | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileSelected = (selectedFile: File) => {
    setFile(selectedFile);
    setError(null);

    const uploader = new S3MultipartUploader(
      selectedFile,
      (p) => {
        setProgress(p);
      },
      projectId
    );
    uploaderRef.current = uploader;

    uploader.start()
      .then((newProjectId) => {
        if (onUploadComplete) {
          onUploadComplete(newProjectId);
        } else {
          router.push(`/projects/${newProjectId}`);
        }
      })
      .catch((err) => {
        setError(err.message || 'Upload failed');
      });
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  }, []);

  const handlePause = () => {
    if (uploaderRef.current) {
      uploaderRef.current.pause();
    }
  };

  const handleResume = () => {
    if (uploaderRef.current) {
      uploaderRef.current.resume();
    }
  };

  const handleCancel = () => {
    if (uploaderRef.current) {
      uploaderRef.current.cancel();
    }
    setFile(null);
    setProgress(null);
    uploaderRef.current = null;
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="w-full">
      <input
        ref={fileInputRef}
        type="file"
        accept="video/*,.mp4,.mov,.avi,.mkv,.webm"
        className="hidden"
        onChange={(e) => {
          if (e.target.files && e.target.files[0]) {
            handleFileSelected(e.target.files[0]);
          }
        }}
      />

      {!file ? (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-10 text-center cursor-pointer transition-all ${
            isDragging
              ? 'border-indigo-500 bg-indigo-500/10'
              : 'border-slate-800 bg-slate-900/50 hover:border-slate-700 hover:bg-slate-900/80'
          }`}
        >
          <div className="rounded-full bg-slate-800/80 p-4 text-indigo-400 mb-4 ring-1 ring-slate-700">
            <UploadCloud className="h-8 w-8" />
          </div>
          <h3 className="text-base font-semibold text-white">
            Upload Video File
          </h3>
          <p className="mt-1 text-sm text-slate-400">
            Drag & drop your recording or click to browse.
          </p>
          <p className="mt-2 text-xs text-slate-500">
            Direct multipart upload to storage. Supports MP4, MOV, MKV, WebM up to 10+ hours.
          </p>
        </div>
      ) : (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6 shadow-xl">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="rounded-lg bg-indigo-500/10 p-2.5 text-indigo-400">
                <FileVideo className="h-6 w-6" />
              </div>
              <div>
                <p className="font-semibold text-white text-sm truncate max-w-sm">
                  {file.name}
                </p>
                <p className="text-xs text-slate-400">
                  {formatBytes(progress?.bytesUploaded || 0)} / {formatBytes(file.size)}
                  {progress?.speedBytesPerSec ? ` • ${(progress.speedBytesPerSec / (1024 * 1024)).toFixed(1)} MB/s` : ''}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {progress?.status === 'uploading' && (
                <button
                  onClick={handlePause}
                  className="rounded-lg bg-slate-800 p-2 text-slate-300 hover:bg-slate-700 hover:text-white"
                  title="Pause Upload"
                >
                  <Pause className="h-4 w-4" />
                </button>
              )}
              {progress?.status === 'paused' && (
                <button
                  onClick={handleResume}
                  className="rounded-lg bg-indigo-600 p-2 text-white hover:bg-indigo-500"
                  title="Resume Upload"
                >
                  <Play className="h-4 w-4" />
                </button>
              )}
              <button
                onClick={handleCancel}
                className="rounded-lg bg-slate-800 p-2 text-slate-400 hover:bg-slate-700 hover:text-white"
                title="Cancel"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Progress bar */}
          <div className="space-y-2">
            <div className="flex justify-between text-xs font-medium text-slate-400">
              <span>
                {progress?.status === 'uploading' && `Uploading part ${progress.currentPart} of ${progress.totalParts}...`}
                {progress?.status === 'paused' && 'Upload paused'}
                {progress?.status === 'completing' && 'Finalizing upload...'}
                {progress?.status === 'completed' && 'Upload complete! Starting pipeline...'}
              </span>
              <span className="text-white font-bold">{progress?.percentage || 0}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
              <div
                className="h-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-all duration-300"
                style={{ width: `${progress?.percentage || 0}%` }}
              />
            </div>
          </div>

          {error && (
            <div className="mt-4 flex items-center justify-between rounded-xl bg-red-950/40 border border-red-500/20 p-3 text-xs text-red-400">
              <div className="flex items-center gap-2">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
              <button
                onClick={() => fileInputRef.current?.click()}
                className="font-medium text-red-300 hover:underline ml-2"
              >
                Reselect File
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
