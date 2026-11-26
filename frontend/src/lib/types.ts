export interface User {
  id: string;
  email: string;
  full_name?: string;
  is_active: boolean;
  created_at: string;
}

export interface CropBox {
  x: number;      // normalized 0.0 to 1.0
  y: number;      // normalized 0.0 to 1.0
  width: number;  // normalized 0.0 to 1.0
  height: number; // normalized 0.0 to 1.0
}

export interface Project {
  id: string;
  user_id: string;
  title: string;
  source_type: 'upload' | 'youtube' | 'twitch' | 'kick' | 'direct_url' | 'live_stream';
  source_url?: string;
  source_file_key?: string;
  source_video_url?: string;
  source_file_size?: number;
  duration?: number;
  probe_data?: {
    duration: number;
    width: number;
    height: number;
    fps: number;
    video_codec: string;
    audio_codec?: string;
    has_audio: boolean;
    audio_channels: number;
    bitrate: number;
  };
  status: 'created' | 'importing' | 'probing' | 'ready' | 'analyzing' | 'completed' | 'failed' | 'cancelled';
  error_message?: string;
  analyzed_duration: number;
  total_chunks: number;
  completed_chunks: number;

  // Pre-generation Reel Settings & Snapshot
  framing_mode: 'crop' | 'fit' | 'pan' | 'split';
  pan_x_offset: number;
  subtitle_font_size: number;
  subtitle_position?: 'bottom' | 'middle' | 'top';
  subtitle_y_percent?: number;
  subtitle_color?: string;
  subtitle_font_family?: string;
  split_facecam_crop?: CropBox;
  split_gameplay_crop?: CropBox;
  split_order: 'facecam_top' | 'gameplay_top';
  split_ratio: number;
  settings_snapshot?: Partial<Project>;

  created_at: string;
  updated_at: string;
}

export interface SubtitleWord {
  word: string;
  start: number;
  end: number;
  prob?: number;
}

export interface Reel {
  id: string;
  project_id: string;
  title: string;
  reason: string;
  category: 'hook' | 'humor' | 'insight' | 'reaction' | 'story' | 'highlight';
  source_start: number;
  source_end: number;
  clip_duration: number;
  score: number;
  score_hook: number;
  score_payoff: number;
  score_clarity: number;
  score_entertainment: number;
  is_borderline: boolean;
  framing_mode: 'crop' | 'fit' | 'pan' | 'split';
  pan_x_offset: number;
  split_facecam_crop?: CropBox;
  split_gameplay_crop?: CropBox;
  split_order?: 'facecam_top' | 'gameplay_top';
  split_ratio?: number;
  top_caption: string;
  subtitles_json?: SubtitleWord[];
  subtitle_font_size?: number;
  subtitle_position?: 'bottom' | 'middle' | 'top';
  subtitle_y_percent?: number;
  subtitle_color?: string;
  subtitle_font_family?: string;
  video_url?: string;
  source_video_url?: string;
  thumbnail_url?: string;
  render_status: 'pending' | 'rendering' | 'completed' | 'failed';
  render_error?: string;
  render_progress: number;
  created_at: string;
  updated_at: string;
}

export interface UrlMetadata {
  url: string;
  platform: string;
  title?: string;
  duration?: number;
  thumbnail_url?: string;
  can_import_media: boolean;
  message: string;
}

export interface UploadSession {
  id: string;
  project_id: string;
  upload_id: string;
  file_key: string;
  file_name: string;
  file_size: number;
  chunk_size: number;
  total_parts: number;
  completed_parts: { PartNumber: number; ETag: string }[];
  status: string;
}

export interface BulkExport {
  id: string;
  project_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  reel_count: number;
  download_url?: string;
  error_message?: string;
}

export interface CoverageGap {
  start: number;
  end: number;
  duration: number;
  reason: string;
}

export interface LiveSession {
  id: string;
  project_id: string;
  status: 'created' | 'ready' | 'capturing' | 'draining' | 'stopped' | 'ended' | 'failed';
  feed_url: string;
  resolved_stream_url?: string;
  platform: 'direct_hls' | 'youtube_live' | 'twitch_live' | 'kick_live' | string;
  capability: 'live_available' | 'waiting_for_stream' | 'stream_ended' | 'media_unavailable';
  capability_message?: string;
  preview_frame_url?: string;
  capture_started_at?: string;
  capture_stopped_at?: string;
  last_captured_timestamp: number;
  last_analyzed_timestamp: number;
  total_captured_seconds: number;
  continuous_buffer_seconds: number;
  coverage_gaps: CoverageGap[];
  ai_backlog_count: number;
  ai_status: 'idle' | 'analyzing' | 'rate_limited' | 'delayed';
  ai_rate_limit_resumes_at?: string;
  storage_used_bytes: number;
  settings_snapshot?: any;
  created_at: string;
  updated_at: string;
}

export interface LiveProbeResult {
  url: string;
  platform: string;
  capability: 'live_available' | 'waiting_for_stream' | 'stream_ended' | 'media_unavailable';
  message: string;
  title?: string;
  thumbnail_url?: string;
  resolved_stream_url?: string;
  preview_frame_url?: string;
}

export interface SocialAccount {
  id: string;
  platform: 'youtube' | 'facebook' | 'instagram' | 'tiktok';
  platform_account_id: string;
  account_name: string;
  account_username?: string;
  profile_picture_url?: string;
  status: 'connected' | 'reconnect_required' | 'disconnected';
  is_active: boolean;
  is_mock: boolean;
  metadata_json?: any;
  created_at: string;
  updated_at: string;
}

export interface SocialPost {
  id: string;
  project_id: string;
  reel_id: string;
  social_account_id: string;
  platform: 'youtube' | 'facebook' | 'instagram' | 'tiktok' | string;
  post_title: string;
  post_description?: string;
  post_hashtags?: string[];
  combined_caption?: string;
  platform_options?: any;
  status: 'queued' | 'uploading' | 'processing' | 'published' | 'failed' | 'reconnect_required' | 'manual_upload_required';
  progress: number;
  provider_upload_id?: string;
  provider_post_id?: string;
  provider_post_url?: string;
  error_message?: string;
  retry_count: number;
  created_at: string;
  updated_at: string;
  published_at?: string;
  account_name?: string;
  account_username?: string;
}

export interface HashtagSuggestionResponse {
  reel_id: string;
  suggestions: string[];
  context_keywords: string[];
  cached: boolean;
}

export interface PublishBatchItemPayload {
  reel_id: string;
  account_ids: string[];
  post_title: string;
  post_description?: string;
  post_hashtags: string[];
  platform_options?: any;
}

export interface PublishBatchPayload {
  project_id: string;
  items: PublishBatchItemPayload[];
}

export interface TikTokPrepareResponse {
  reel_id: string;
  download_url: string;
  caption: string;
  hashtags: string[];
  combined_text: string;
  tiktok_web_upload_url: string;
  instructions: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface IntegrationsSettings {
  gemini_configured: boolean;
  gemini_key_masked?: string;
  gemini_status: 'connected' | 'invalid' | 'quota_exhausted' | 'not_configured' | string;
  gemini_last_tested_at?: string;
  gemini_model: string;
  youtube_configured: boolean;
  youtube_client_id?: string;
  youtube_secret_masked?: string;
  youtube_status: 'configured' | 'not_configured' | string;
  youtube_redirect_uri: string;
  max_concurrent_jobs: number;
  storage_limit_mb: number;
  storage_used_mb: number;
  active_jobs_count: number;
}
