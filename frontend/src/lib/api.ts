import { Project, Reel, UrlMetadata, BulkExport, SocialAccount, SocialPost, HashtagSuggestionResponse, PublishBatchPayload, TikTokPrepareResponse } from './types';

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiClient {
  private token: string | null = null;

  constructor() {
    if (typeof window !== 'undefined') {
      this.token = localStorage.getItem('reelstudio_token');
    }
  }

  setToken(token: string) {
    this.token = token;
    if (typeof window !== 'undefined') {
      localStorage.setItem('reelstudio_token', token);
    }
  }

  getToken(): string | null {
    if (!this.token && typeof window !== 'undefined') {
      this.token = localStorage.getItem('reelstudio_token');
    }
    return this.token;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const headers = new Headers(options.headers || {});
    const token = this.getToken();
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }
    if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
      headers.set('Content-Type', 'application/json');
    }

    const res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    if (!res.ok) {
      let errorMsg = `Request failed: ${res.statusText}`;
      try {
        const errorData = await res.json();
        errorMsg = errorData.detail || errorMsg;
      } catch {}
      throw new Error(errorMsg);
    }

    if (res.status === 204) {
      return {} as T;
    }

    return res.json() as Promise<T>;
  }

  // System
  async getHealth() {
    return this.request<{
      status: string;
      database: string;
      redis: string;
      minio: string;
      gemini_configured: boolean;
      whisper_model: string;
    }>('/api/system/health');
  }

  async getAiStatus() {
    return this.request<{
      is_configured: boolean;
      model: string;
      instructions: string;
    }>('/api/system/ai-status');
  }

  // Projects
  async listProjects(skip = 0, limit = 50) {
    return this.request<{ items: Project[]; total: number }>(
      `/api/projects?skip=${skip}&limit=${limit}`
    );
  }

  async getProject(id: string) {
    return this.request<Project>(`/api/projects/${id}`);
  }

  async deleteProject(id: string) {
    return this.request<void>(`/api/projects/${id}`, {
      method: 'DELETE',
    });
  }

  async checkUrlMetadata(url: string) {
    return this.request<UrlMetadata>('/api/projects/metadata', {
      method: 'POST',
      body: JSON.stringify({ url }),
    });
  }

  async createProjectFromUrl(url: string, title?: string) {
    return this.request<Project>('/api/projects/url', {
      method: 'POST',
      body: JSON.stringify({ url, title }),
    });
  }

  async updateProjectSettings(id: string, settings: Partial<Project>) {
    return this.request<Project>(`/api/projects/${id}/settings`, {
      method: 'PATCH',
      body: JSON.stringify(settings),
    });
  }

  async generateProjectReels(id: string, settings?: Partial<Project>) {
    return this.request<Project>(`/api/projects/${id}/generate`, {
      method: 'POST',
      body: settings ? JSON.stringify(settings) : undefined,
    });
  }

  async getProjectSampleTranscript(id: string) {
    return this.request<{ words: { word: string; start: number; end: number }[]; is_mock: boolean }>(
      `/api/projects/${id}/sample-transcript`
    );
  }

  async retryProject(id: string) {
    return this.request<{ status: string }>(`/api/projects/${id}/retry`, {
      method: 'POST',
    });
  }

  async cancelProject(id: string) {
    return this.request<{ status: string }>(`/api/projects/${id}/cancel`, {
      method: 'POST',
    });
  }

  async getProjectReels(id: string, minScore = 60.0, includeBorderline = false, category = 'all') {
    return this.request<{
      items: Reel[];
      total: number;
      borderline_count: number;
    }>(
      `/api/projects/${id}/reels?min_score=${minScore}&include_borderline=${includeBorderline}&category=${category}`
    );
  }

  async createManualReel(id: string, data: { source_start: number; source_end: number; top_caption?: string; framing_mode?: string }) {
    return this.request<Reel>(`/api/projects/${id}/reels/manual`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async exportProjectZip(id: string) {
    return this.request<BulkExport>(`/api/projects/${id}/export-zip`, {
      method: 'POST',
    });
  }

  async getZipExportStatus(id: string, exportId: string) {
    return this.request<BulkExport>(`/api/projects/${id}/export-zip/${exportId}`);
  }

  // Reels
  async getReel(id: string) {
    return this.request<Reel>(`/api/reels/${id}`);
  }

  async updateReel(id: string, data: Partial<Reel>) {
    return this.request<Reel>(`/api/reels/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async reRenderReel(id: string) {
    return this.request<Reel>(`/api/reels/${id}/render`, {
      method: 'POST',
    });
  }

  async romanizeReel(id: string) {
    return this.request<Reel>(`/api/reels/${id}/romanize`, {
      method: 'POST',
    });
  }

  async deleteReel(id: string) {
    return this.request<void>(`/api/reels/${id}`, {
      method: 'DELETE',
    });
  }

  getDownloadUrl(id: string): string {
    const token = this.getToken();
    const base = `${API_BASE}/api/reels/${id}/download`;
    return token ? `${base}?token=${encodeURIComponent(token)}` : base;
  }

  // Live Streams
  async probeLiveStream(url: string) {
    return this.request<import('./types').LiveProbeResult>('/api/live/probe', {
      method: 'POST',
      body: JSON.stringify({ url }),
    });
  }

  async createLiveProject(url: string, title?: string) {
    return this.request<{
      project: Project;
      session: import('./types').LiveSession;
      preview_frame_url?: string;
    }>('/api/live/projects', {
      method: 'POST',
      body: JSON.stringify({ url, title }),
    });
  }

  async getLiveSession(projectId: string) {
    return this.request<import('./types').LiveSession>(`/api/live/projects/${projectId}`);
  }

  async startLiveClipping(projectId: string, settings?: any) {
    return this.request<import('./types').LiveSession>(`/api/live/projects/${projectId}/start`, {
      method: 'POST',
      body: JSON.stringify({ settings }),
    });
  }

  async stopLiveClipping(projectId: string) {
    return this.request<{ status: string; message: string }>(`/api/live/projects/${projectId}/stop`, {
      method: 'POST',
    });
  }

  async clipLastSeconds(projectId: string, duration = 60.0) {
    return this.request<{ reel_id: string; message: string }>(`/api/live/projects/${projectId}/clip-last`, {
      method: 'POST',
      body: JSON.stringify({ duration }),
    });
  }

  async getGeminiLimiter() {
    return this.request<{
      rpm_used: number;
      rpm_limit: number;
      tpm_used: number;
      tpm_limit: number;
      rpd_used: number;
      rpd_limit: number;
      is_rate_limited: boolean;
      cooldown_remaining_seconds: number;
    }>('/api/live/limiter');
  }

  // Social Media Publishing
  async getSocialAccounts() {
    return this.request<SocialAccount[]>('/api/social/accounts');
  }

  async connectMockAccount(payload: {
    platform: string;
    account_name: string;
    account_username?: string;
    profile_picture_url?: string;
    metadata_json?: any;
  }) {
    return this.request<SocialAccount>('/api/social/accounts/mock', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async disconnectSocialAccount(accountId: string) {
    return this.request<{ status: string; account_id: string }>('/api/social/accounts/disconnect', {
      method: 'POST',
      body: JSON.stringify({ account_id: accountId }),
    });
  }

  async reconnectSocialAccount(accountId: string) {
    return this.request<SocialAccount>('/api/social/accounts/reconnect', {
      method: 'POST',
      body: JSON.stringify({ account_id: accountId }),
    });
  }

  async suggestHashtags(payload: {
    reel_id: string;
    project_id?: string;
    title: string;
    description?: string;
    brand_tags?: string[];
  }) {
    return this.request<HashtagSuggestionResponse>('/api/social/hashtags/suggest', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async publishSocialBatch(payload: PublishBatchPayload) {
    return this.request<SocialPost[]>('/api/social/publish/batch', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async getProjectSocialPosts(projectId: string) {
    return this.request<SocialPost[]>(`/api/social/posts/project/${projectId}`);
  }

  async retrySocialPost(postId: string) {
    return this.request<SocialPost>(`/api/social/posts/${postId}/retry`, {
      method: 'POST',
    });
  }

  async prepareForTikTok(params: {
    reel_id: string;
    title: string;
    description?: string;
    hashtags?: string;
  }) {
    const sp = new URLSearchParams({
      reel_id: params.reel_id,
      title: params.title,
    });
    if (params.description) sp.set('description', params.description);
    if (params.hashtags) sp.set('hashtags', params.hashtags);
    return this.request<TikTokPrepareResponse>(`/api/social/tiktok/prepare?${sp.toString()}`, {
      method: 'POST',
    });
  }

  async getOAuthAuthorizeUrl(platform: string, projectId?: string) {
    const url = projectId
      ? `/api/social/${platform}/authorize?project_id=${encodeURIComponent(projectId)}`
      : `/api/social/${platform}/authorize`;
    return this.request<{ authorize_url: string; platform: string }>(url);
  }

  // Auth
  async signup(data: { email: string; password: string; full_name?: string }) {
    const res = await this.request<import('./types').AuthResponse>('/api/auth/signup', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    if (res.access_token) {
      this.setToken(res.access_token);
    }
    return res;
  }

  async login(email: string, password: string) {
    const res = await this.request<import('./types').AuthResponse>('/api/auth/login/json', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    if (res.access_token) {
      this.setToken(res.access_token);
    }
    return res;
  }

  async getMe() {
    return this.request<import('./types').User>('/api/auth/me');
  }

  logout() {
    this.token = null;
    if (typeof window !== 'undefined') {
      localStorage.removeItem('reelstudio_token');
    }
  }

  // Settings & Integrations
  async getIntegrationsSettings() {
    return this.request<import('./types').IntegrationsSettings>('/api/settings/integrations');
  }

  async updateGeminiSettings(payload: { action: 'save' | 'test' | 'remove'; api_key?: string; model?: string }) {
    return this.request<{ status: string; message: string; connection_status?: string }>('/api/settings/integrations/gemini', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async updateYouTubeSettings(payload: { action: 'save' | 'remove'; client_id?: string; client_secret?: string }) {
    return this.request<{ status: string; message: string }>('/api/settings/integrations/youtube', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }
}

export const api = new ApiClient();
