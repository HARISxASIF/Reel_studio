import { api, API_BASE, getApiBase } from './api';

export interface UploadProgress {
  bytesUploaded: number;
  totalBytes: number;
  percentage: number;
  currentPart: number;
  totalParts: number;
  speedBytesPerSec: number;
  status: 'idle' | 'uploading' | 'paused' | 'completing' | 'completed' | 'error';
  errorMessage?: string;
}

export class S3MultipartUploader {
  private file: File;
  private projectId?: string;
  private chunkSize: number;
  private onProgress: (progress: UploadProgress) => void;
  private isPaused: boolean = false;
  private isCancelled: boolean = false;
  private sessionId?: string;
  private uploadId?: string;

  constructor(
    file: File,
    onProgress: (progress: UploadProgress) => void,
    projectId?: string,
    chunkSize = 10 * 1024 * 1024 // 10MB
  ) {
    this.file = file;
    this.onProgress = onProgress;
    this.projectId = projectId;
    this.chunkSize = chunkSize;
  }

  pause() {
    this.isPaused = true;
  }

  resume() {
    this.isPaused = false;
    this.start();
  }

  cancel() {
    this.isCancelled = true;
  }

  async start(): Promise<string> {
    this.isPaused = false;
    this.isCancelled = false;

    const token = api.getToken();

    // 1. Initiate or resume upload session
    const initRes = await fetch(`${getApiBase()}/api/uploads/initiate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        project_id: this.projectId,
        file_name: this.file.name,
        file_size: this.file.size,
        chunk_size: this.chunkSize,
      }),
    });

    if (!initRes.ok) {
      throw new Error(`Failed to initiate upload: ${initRes.statusText}`);
    }

    const session = await initRes.json();
    this.sessionId = session.upload_session_id;
    this.uploadId = session.upload_id;
    const totalParts = session.total_parts;
    const completedPartsMap = new Map<number, string>();

    for (const cp of session.completed_parts || []) {
      completedPartsMap.set(cp.PartNumber, cp.ETag);
    }

    let bytesUploaded = completedPartsMap.size * this.chunkSize;
    let startTime = Date.now();
    let lastBytes = bytesUploaded;

    this.onProgress({
      bytesUploaded,
      totalBytes: this.file.size,
      percentage: Math.min(100, Math.round((bytesUploaded / this.file.size) * 100)),
      currentPart: completedPartsMap.size,
      totalParts,
      speedBytesPerSec: 0,
      status: 'uploading',
    });

    const partsResult: { PartNumber: number; ETag: string }[] = [];
    completedPartsMap.forEach((etag, pNum) => {
      partsResult.push({ PartNumber: pNum, ETag: etag });
    });

    // 2. Upload remaining parts sequentially
    for (let partNumber = 1; partNumber <= totalParts; partNumber++) {
      if (this.isPaused) {
        this.onProgress({
          bytesUploaded,
          totalBytes: this.file.size,
          percentage: Math.min(100, Math.round((bytesUploaded / this.file.size) * 100)),
          currentPart: partNumber - 1,
          totalParts,
          speedBytesPerSec: 0,
          status: 'paused',
        });
        return session.project_id;
      }

      if (this.isCancelled) {
        throw new Error('Upload cancelled by user.');
      }

      if (completedPartsMap.has(partNumber)) {
        continue; // Already uploaded
      }

      const start = (partNumber - 1) * this.chunkSize;
      const end = Math.min(this.file.size, start + this.chunkSize);
      const chunkBlob = this.file.slice(start, end);

      // Get presigned PUT URL for this part
      const partUrlRes = await fetch(
        `${getApiBase()}/api/uploads/${this.sessionId}/parts/${partNumber}`,
        {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        }
      );
      if (!partUrlRes.ok) {
        throw new Error(`Failed to get presigned URL for part ${partNumber}`);
      }
      const { presigned_url } = await partUrlRes.json();

      // Upload part directly to MinIO
      const putRes = await fetch(presigned_url, {
        method: 'PUT',
        body: chunkBlob,
      });

      if (!putRes.ok) {
        throw new Error(`Failed to upload part ${partNumber} directly to storage.`);
      }

      let etag = putRes.headers.get('ETag') || '';
      // Clean quotes from ETag if present
      etag = etag.replace(/"/g, '');

      partsResult.push({ PartNumber: partNumber, ETag: etag });
      bytesUploaded += chunkBlob.size;

      const elapsedSec = (Date.now() - startTime) / 1000;
      const speed = elapsedSec > 0 ? (bytesUploaded - lastBytes) / elapsedSec : 0;

      this.onProgress({
        bytesUploaded,
        totalBytes: this.file.size,
        percentage: Math.min(100, Math.round((bytesUploaded / this.file.size) * 100)),
        currentPart: partNumber,
        totalParts,
        speedBytesPerSec: Math.round(speed),
        status: 'uploading',
      });
    }

    // 3. Complete multipart upload
    this.onProgress({
      bytesUploaded: this.file.size,
      totalBytes: this.file.size,
      percentage: 100,
      currentPart: totalParts,
      totalParts,
      speedBytesPerSec: 0,
      status: 'completing',
    });

    const completeRes = await fetch(`${getApiBase()}/api/uploads/${this.sessionId}/complete`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ parts: partsResult }),
    });

    if (!completeRes.ok) {
      throw new Error('Failed to complete upload session on server.');
    }

    const completeData = await completeRes.json();

    this.onProgress({
      bytesUploaded: this.file.size,
      totalBytes: this.file.size,
      percentage: 100,
      currentPart: totalParts,
      totalParts,
      speedBytesPerSec: 0,
      status: 'completed',
    });

    return completeData.project_id;
  }
}
