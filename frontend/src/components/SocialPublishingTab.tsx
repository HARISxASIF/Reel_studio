'use client';

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Share2,
  Youtube,
  Instagram,
  Facebook,
  Video,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Sparkles,
  ExternalLink,
  Download,
  Copy,
  Plus,
  X,
  Play,
  Clock,
  Layers,
  Send,
  HelpCircle,
  Eye,
  Check,
  Settings2,
} from 'lucide-react';
import { api, API_BASE } from '@/lib/api';
import {
  Project,
  Reel,
  SocialAccount,
  SocialPost,
  HashtagSuggestionResponse,
  TikTokPrepareResponse,
} from '@/lib/types';

interface SocialPublishingTabProps {
  project: Project;
  reels: Reel[];
  onRefreshReels: () => void;
}

export function SocialPublishingTab({
  project,
  reels,
  onRefreshReels,
}: SocialPublishingTabProps) {
  // Connected Accounts State
  const [accounts, setAccounts] = useState<SocialAccount[]>([]);
  const [loadingAccounts, setLoadingAccounts] = useState(true);
  const [showOAuthHelp, setShowOAuthHelp] = useState(false);

  // 1-Click Platform Connection & Status
  const [connectingPlatform, setConnectingPlatform] = useState<
    'youtube' | 'facebook' | 'instagram' | 'tiktok' | null
  >(null);
  const [platformConfigError, setPlatformConfigError] = useState<{
    platform: string;
    message: string;
  } | null>(null);

  // Social Posts History & Tracking
  const [posts, setPosts] = useState<SocialPost[]>([]);
  const [loadingPosts, setLoadingPosts] = useState(false);

  // Filter completed rendered reels only
  const completedReels = useMemo(() => {
    return reels.filter(
      (r) => r.render_status === 'completed' && Boolean(r.video_url)
    );
  }, [reels]);

  // Selected Reels for Batch Publishing
  const [selectedReelIds, setSelectedReelIds] = useState<string[]>([]);

  // Batch Destination Selection (Account IDs applied by default to all selected reels)
  const [globalSelectedAccountIds, setGlobalSelectedAccountIds] = useState<string[]>([]);

  // Per-Reel Custom Metadata Map: reel_id -> { post_title, post_description, hashtags, account_ids, platform_options }
  interface ReelMetadataForm {
    post_title: string;
    post_description: string;
    hashtags: string[];
    account_ids: string[];
    visibility: 'public' | 'unlisted' | 'private';
    made_for_kids: boolean;
    share_to_feed: boolean;
    tiktok_privacy: 'PUBLIC_TO_EVERYONE' | 'MUTUAL_FOLLOW_FRIENDS' | 'SELF_ONLY';
  }

  const [metadataMap, setMetadataMap] = useState<Record<string, ReelMetadataForm>>({});

  // Active Reel currently being edited in details pane
  const [activeEditingReelId, setActiveEditingReelId] = useState<string | null>(null);

  // AI Hashtag Suggestions State: reel_id -> suggestions
  const [aiSuggestionsMap, setAiSuggestionsMap] = useState<Record<string, string[]>>({});
  const [loadingAiTags, setLoadingAiTags] = useState<Record<string, boolean>>({});
  const [manualTagInput, setManualTagInput] = useState('');
  const [brandTagInput, setBrandTagInput] = useState('');

  // Video Preview Modal
  const [previewVideoUrl, setPreviewVideoUrl] = useState<string | null>(null);
  const [previewVideoTitle, setPreviewVideoTitle] = useState<string>('');

  // TikTok Manual Prepare Modal
  const [tikTokPrepareData, setTikTokPrepareData] = useState<TikTokPrepareResponse | null>(null);
  const [copiedCaption, setCopiedCaption] = useState(false);

  // Publishing State
  const [isPublishing, setIsPublishing] = useState(false);
  const [publishFeedback, setPublishFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Live preview tab selector for caption preview
  const [captionPreviewTab, setCaptionPreviewTab] = useState<'youtube' | 'instagram' | 'facebook' | 'tiktok'>('youtube');

  // Load connected accounts and project posts
  const fetchAccounts = useCallback(async () => {
    try {
      setLoadingAccounts(true);
      const accs = await api.getSocialAccounts();
      setAccounts(accs);
      // Auto-select connected accounts by default
      const connected = accs.filter((a) => a.status === 'connected').map((a) => a.id);
      setGlobalSelectedAccountIds((prev) => (prev.length === 0 ? connected : prev));
    } catch (err) {
      console.error('Failed to load social accounts:', err);
    } finally {
      setLoadingAccounts(false);
    }
  }, []);

  const fetchProjectPosts = useCallback(async () => {
    if (!project.id) return;
    try {
      const pList = await api.getProjectSocialPosts(project.id);
      setPosts(pList);
    } catch (err) {
      console.error('Failed to load project posts:', err);
    }
  }, [project.id]);

  useEffect(() => {
    fetchAccounts();
    fetchProjectPosts();
    // Poll post status every 4 seconds if there are queued or uploading posts
    const interval = setInterval(() => {
      fetchProjectPosts();
    }, 4000);
    return () => clearInterval(interval);
  }, [fetchAccounts, fetchProjectPosts]);

  // Initialize metadata forms for completed reels
  useEffect(() => {
    setMetadataMap((prev) => {
      const next = { ...prev };
      completedReels.forEach((reel) => {
        if (!next[reel.id]) {
          next[reel.id] = {
            post_title: reel.top_caption || reel.title || 'Must Watch Gaming Clip',
            post_description: reel.reason || 'Check out this epic highlight from the stream!',
            hashtags: ['#GTA6', '#GamingReels', '#Viral', '#Shorts'],
            account_ids: [...globalSelectedAccountIds],
            visibility: 'public',
            made_for_kids: false,
            share_to_feed: true,
            tiktok_privacy: 'PUBLIC_TO_EVERYONE',
          };
        }
      });
      return next;
    });

    if (completedReels.length > 0 && !activeEditingReelId) {
      setActiveEditingReelId(completedReels[0].id);
      if (selectedReelIds.length === 0) {
        setSelectedReelIds([completedReels[0].id]);
      }
    }
  }, [completedReels, globalSelectedAccountIds, activeEditingReelId, selectedReelIds.length]);

  // Direct 1-Click Connect Platform via Official OAuth
  const handleConnectPlatform = async (
    platform: 'youtube' | 'facebook' | 'instagram' | 'tiktok'
  ) => {
    setConnectingPlatform(platform);
    setPlatformConfigError(null);
    try {
      const res = await api.getOAuthAuthorizeUrl(platform, project.id);
      if (res.authorize_url) {
        window.location.href = res.authorize_url;
      }
    } catch (err: any) {
      setConnectingPlatform(null);
      setPlatformConfigError({
        platform,
        message:
          err.message ||
          `OAuth credentials for ${getPlatformLabel(platform)} are not configured in .env yet. Please configure them in your .env file or refer to the Setup Guide.`,
      });
    }
  };

  // Disconnect Account
  const handleDisconnect = async (accountId: string) => {
    if (
      !confirm(
        'Are you sure you want to disconnect this account? Queued posts for this destination will be cancelled.'
      )
    )
      return;
    try {
      await api.disconnectSocialAccount(accountId);
      await fetchAccounts();
      await fetchProjectPosts();
    } catch (err: any) {
      alert(`Failed to disconnect: ${err.message}`);
    }
  };

  // Reconnect Account
  const handleReconnect = async (accountId: string) => {
    try {
      await api.reconnectSocialAccount(accountId);
      await fetchAccounts();
    } catch (err: any) {
      alert(`Failed to reconnect: ${err.message}`);
    }
  };

  // Toggle Reel Selection
  const toggleSelectReel = (reelId: string) => {
    setSelectedReelIds((prev) =>
      prev.includes(reelId) ? prev.filter((id) => id !== reelId) : [...prev, reelId]
    );
    setActiveEditingReelId(reelId);
  };

  // Select / Deselect All Ready Reels
  const toggleSelectAll = () => {
    if (selectedReelIds.length === completedReels.length) {
      setSelectedReelIds([]);
    } else {
      setSelectedReelIds(completedReels.map((r) => r.id));
      if (completedReels.length > 0) {
        setActiveEditingReelId(completedReels[0].id);
      }
    }
  };

  // Toggle Global Destination Account
  const toggleGlobalAccount = (accountId: string) => {
    setGlobalSelectedAccountIds((prev) => {
      const next = prev.includes(accountId)
        ? prev.filter((id) => id !== accountId)
        : [...prev, accountId];

      // Sync across all reel forms
      setMetadataMap((metaPrev) => {
        const metaNext = { ...metaPrev };
        Object.keys(metaNext).forEach((rId) => {
          metaNext[rId] = {
            ...metaNext[rId],
            account_ids: next,
          };
        });
        return metaNext;
      });

      return next;
    });
  };

  // Toggle per-reel destination override
  const toggleReelAccount = (reelId: string, accountId: string) => {
    setMetadataMap((prev) => {
      const cur = prev[reelId] || {
        post_title: '',
        post_description: '',
        hashtags: [],
        account_ids: [],
        visibility: 'public',
        made_for_kids: false,
        share_to_feed: true,
        tiktok_privacy: 'PUBLIC_TO_EVERYONE',
      };
      const curAccs = cur.account_ids || [];
      const updated = curAccs.includes(accountId)
        ? curAccs.filter((id) => id !== accountId)
        : [...curAccs, accountId];
      return {
        ...prev,
        [reelId]: { ...cur, account_ids: updated },
      };
    });
  };

  // Update Reel metadata field
  const updateReelMetadata = (
    reelId: string,
    field: keyof ReelMetadataForm,
    value: any
  ) => {
    setMetadataMap((prev) => {
      const cur = prev[reelId] || {
        post_title: '',
        post_description: '',
        hashtags: [],
        account_ids: [...globalSelectedAccountIds],
        visibility: 'public',
        made_for_kids: false,
        share_to_feed: true,
        tiktok_privacy: 'PUBLIC_TO_EVERYONE',
      };
      return {
        ...prev,
        [reelId]: { ...cur, [field]: value },
      };
    });
  };

  // Suggest Hashtags via Gemini
  const handleSuggestHashtags = async (reelId: string) => {
    const meta = metadataMap[reelId];
    if (!meta) return;

    setLoadingAiTags((prev) => ({ ...prev, [reelId]: true }));
    try {
      const brandTags = brandTagInput ? brandTagInput.split(/[\s,]+/).filter(Boolean) : [];
      const res: HashtagSuggestionResponse = await api.suggestHashtags({
        reel_id: reelId,
        project_id: project.id,
        title: meta.post_title,
        description: meta.post_description,
        brand_tags: brandTags,
      });
      setAiSuggestionsMap((prev) => ({ ...prev, [reelId]: res.suggestions }));
    } catch (err: any) {
      alert(`AI Hashtag suggestions failed: ${err.message || 'Error'}`);
    } finally {
      setLoadingAiTags((prev) => ({ ...prev, [reelId]: false }));
    }
  };

  // Add individual hashtag chip
  const addHashtag = (reelId: string, tag: string) => {
    const cleanTag = tag.trim().startsWith('#') ? tag.trim() : `#${tag.trim()}`;
    if (!cleanTag || cleanTag === '#') return;
    setMetadataMap((prev) => {
      const cur = prev[reelId];
      if (!cur) return prev;
      if (cur.hashtags.some((t) => t.toLowerCase() === cleanTag.toLowerCase())) return prev;
      return {
        ...prev,
        [reelId]: { ...cur, hashtags: [...cur.hashtags, cleanTag] },
      };
    });
  };

  // Remove hashtag chip
  const removeHashtag = (reelId: string, tag: string) => {
    setMetadataMap((prev) => {
      const cur = prev[reelId];
      if (!cur) return prev;
      return {
        ...prev,
        [reelId]: { ...cur, hashtags: cur.hashtags.filter((t) => t !== tag) },
      };
    });
  };

  // Add all suggested tags
  const addAllSuggestedTags = (reelId: string) => {
    const suggestions = aiSuggestionsMap[reelId] || [];
    setMetadataMap((prev) => {
      const cur = prev[reelId];
      if (!cur) return prev;
      const existing = new Set(cur.hashtags.map((t) => t.toLowerCase()));
      const toAdd = suggestions.filter((t) => !existing.has(t.toLowerCase()));
      return {
        ...prev,
        [reelId]: { ...cur, hashtags: [...cur.hashtags, ...toAdd] },
      };
    });
  };

  // Prepare for TikTok
  const handlePrepareTikTok = async (reelId: string) => {
    const meta = metadataMap[reelId];
    if (!meta) return;
    try {
      const res = await api.prepareForTikTok({
        reel_id: reelId,
        title: meta.post_title,
        description: meta.post_description,
        hashtags: meta.hashtags.join(','),
      });
      setTikTokPrepareData(res);
      setCopiedCaption(false);
    } catch (err: any) {
      alert(`Failed to prepare for TikTok: ${err.message}`);
    }
  };

  // Copy Caption to Clipboard
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCaption(true);
    setTimeout(() => setCopiedCaption(false), 2500);
  };

  // Retry a failed post
  const handleRetryPost = async (postId: string) => {
    try {
      await api.retrySocialPost(postId);
      await fetchProjectPosts();
    } catch (err: any) {
      alert(`Failed to retry post: ${err.message}`);
    }
  };

  // Primary Action: Publish Selected
  const handlePublishSelected = async () => {
    if (selectedReelIds.length === 0) {
      alert('Please select at least one reel to publish.');
      return;
    }

    // Build batch payload
    const batchItems = selectedReelIds.map((rId) => {
      const meta = metadataMap[rId] || {
        post_title: 'Must Watch Clip',
        post_description: '',
        hashtags: [],
        account_ids: globalSelectedAccountIds,
        visibility: 'public',
        made_for_kids: false,
        share_to_feed: true,
        tiktok_privacy: 'PUBLIC_TO_EVERYONE',
      };

      const accountsForThisReel =
        meta.account_ids && meta.account_ids.length > 0
          ? meta.account_ids
          : globalSelectedAccountIds;

      return {
        reel_id: rId,
        account_ids: accountsForThisReel,
        post_title: meta.post_title.trim(),
        post_description: meta.post_description.trim(),
        post_hashtags: meta.hashtags,
        platform_options: {
          visibility: meta.visibility,
          made_for_kids: meta.made_for_kids,
          share_to_feed: meta.share_to_feed,
          privacy_level: meta.tiktok_privacy,
        },
      };
    });

    const totalDestinations = batchItems.reduce(
      (acc, item) => acc + item.account_ids.length,
      0
    );

    if (totalDestinations === 0) {
      alert(
        'Please select at least one destination account in the "Choose Accounts to Publish To" section.'
      );
      return;
    }

    const confirmMsg = `Ready to publish ${selectedReelIds.length} reel(s) across ${totalDestinations} destination post(s)? Background workers will queue and upload each post.`;
    if (!confirm(confirmMsg)) return;

    setIsPublishing(true);
    setPublishFeedback(null);

    try {
      const created = await api.publishSocialBatch({
        project_id: project.id,
        items: batchItems,
      });
      setPublishFeedback({
        type: 'success',
        message: `Successfully queued ${created.length} post(s) for background publishing! Monitor progress below.`,
      });
      await fetchProjectPosts();
    } catch (err: any) {
      setPublishFeedback({
        type: 'error',
        message: `Batch publish failed: ${err.message || 'Unknown error'}`,
      });
    } finally {
      setIsPublishing(false);
    }
  };

  // Selected reel objects
  const activeReel = useMemo(() => {
    return (
      completedReels.find((r) => r.id === activeEditingReelId) ||
      completedReels[0] ||
      null
    );
  }, [completedReels, activeEditingReelId]);

  const activeMeta = activeReel ? metadataMap[activeReel.id] : null;

  // Platform icon helper
  const renderPlatformIcon = (platform: string, className = 'h-5 w-5') => {
    switch (platform.toLowerCase()) {
      case 'youtube':
        return <Youtube className={`${className} text-red-500`} />;
      case 'facebook':
        return <Facebook className={`${className} text-blue-500`} />;
      case 'instagram':
        return <Instagram className={`${className} text-pink-500`} />;
      case 'tiktok':
        return <Video className={`${className} text-cyan-400`} />;
      default:
        return <Share2 className={`${className} text-indigo-400`} />;
    }
  };

  // Platform label helper
  const getPlatformLabel = (platform: string) => {
    switch (platform.toLowerCase()) {
      case 'youtube':
        return 'YouTube Shorts';
      case 'facebook':
        return 'Facebook Page';
      case 'instagram':
        return 'Instagram Reels';
      case 'tiktok':
        return 'TikTok';
      default:
        return platform;
    }
  };

  // Caption generator preview helper
  const getCombinedCaptionPreview = (platform: string) => {
    if (!activeMeta) return '';
    const title = activeMeta.post_title.trim();
    const desc = activeMeta.post_description.trim();
    const tags = activeMeta.hashtags.join(' ');

    if (platform === 'youtube') {
      return `Title: ${title} #Shorts\n\nDescription:\n${desc}\n\n${tags}`;
    }
    return `${title}\n\n${desc}\n\n${tags}`;
  };

  // Calculate total posts count that will be queued
  const totalQueuedCount = useMemo(() => {
    return selectedReelIds.reduce((sum, rId) => {
      const meta = metadataMap[rId];
      const accs =
        meta?.account_ids && meta.account_ids.length > 0
          ? meta.account_ids
          : globalSelectedAccountIds;
      return sum + accs.length;
    }, 0);
  }, [selectedReelIds, metadataMap, globalSelectedAccountIds]);

  const activeConnectedAccounts = useMemo(() => {
    return accounts.filter((a) => a.status === 'connected');
  }, [accounts]);

  return (
    <div className="space-y-8 font-body">
      {/* Top Banner & Destination Overview */}
      <div className="relative overflow-hidden rounded-2xl border border-divider bg-surface p-6 shadow-2xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-selected text-accent border border-accent/20">
                <Share2 className="h-4 w-4" />
              </span>
              <h2 className="font-heading text-2xl font-normal tracking-tight text-text-primary">
                Social Media Auto-Publishing
              </h2>
            </div>
            <p className="text-xs text-slate-400 max-w-2xl">
              Connect your personal YouTube channel, Facebook Page, Instagram Professional account, and TikTok.
              Pick which accounts to publish to, customize AI hashtags & hooks, and queue background uploads.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => setShowOAuthHelp(!showOAuthHelp)}
              className="flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-800/80 px-3.5 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-700 hover:text-white transition shadow"
            >
              <HelpCircle className="h-3.5 w-3.5 text-indigo-400" />
              API & App Setup
            </button>
            <button
              onClick={() => {
                fetchAccounts();
                fetchProjectPosts();
              }}
              className="flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-800/80 px-3 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-700 hover:text-white transition shadow"
              title="Refresh Accounts and Posts"
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {/* Developer App Setup Guide Accordion */}
        {showOAuthHelp && (
          <div className="mt-5 pt-4 border-t border-slate-800 text-xs text-slate-300 space-y-3 bg-slate-950/60 rounded-xl p-4">
            <div className="flex items-center justify-between">
              <h4 className="font-bold text-white text-sm flex items-center gap-1.5">
                <HelpCircle className="h-4 w-4 text-indigo-400" />
                Developer Setup & OAuth Redirects
              </h4>
              <button
                onClick={() => setShowOAuthHelp(false)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
              <div className="rounded-lg bg-slate-900 border border-slate-800 p-3 space-y-1.5">
                <div className="font-semibold text-red-400 flex items-center gap-1.5">
                  <Youtube className="h-4 w-4" /> YouTube Shorts (Google Cloud Console)
                </div>
                <p className="text-slate-400">
                  Enable <strong>YouTube Data API v3</strong>. Create an OAuth 2.0 Client ID (Web Application).
                </p>
                <div className="text-[11px] font-mono bg-slate-950 p-1.5 rounded border border-slate-800 select-all text-slate-300">
                  Redirect URI: {`${API_BASE}/api/social/youtube/callback`}
                </div>
                <p className="text-[11px] text-slate-500">
                  Scopes: <code>youtube.upload</code>, <code>youtube.readonly</code>
                </p>
              </div>

              <div className="rounded-lg bg-slate-900 border border-slate-800 p-3 space-y-1.5">
                <div className="font-semibold text-blue-400 flex items-center gap-1.5">
                  <Facebook className="h-4 w-4" /> Meta (Facebook Page & Instagram Reels)
                </div>
                <p className="text-slate-400">
                  Meta Developers app with <strong>Facebook Login for Business</strong> & <strong>Instagram Graph API</strong>.
                </p>
                <div className="text-[11px] font-mono bg-slate-950 p-1.5 rounded border border-slate-800 select-all text-slate-300">
                  Redirect URI: {`${API_BASE}/api/social/meta/callback`}
                </div>
                <p className="text-[11px] text-slate-500">
                  Requires Facebook Page + linked Instagram Professional account.
                </p>
              </div>
            </div>
            <p className="text-slate-400 text-[11px]">
              💡 <em>How to Connect Your Accounts:</em> Click <strong>Connect YouTube Channel</strong> (or other platforms) below to link your channel directly via official OAuth.
            </p>
          </div>
        )}
      </div>

      {/* 1. Connected Accounts Section */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <Share2 className="h-4 w-4 text-indigo-400" />
            1. Connected Social Accounts
          </h3>
          <span className="text-xs text-slate-400">
            {activeConnectedAccounts.length} Connected
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {(['youtube', 'facebook', 'instagram', 'tiktok'] as const).map((plat) => {
            const acc = accounts.find((a) => a.platform === plat);
            return (
              <div
                key={plat}
                className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 flex flex-col justify-between space-y-3 shadow-md hover:border-slate-700 transition"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="h-10 w-10 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center flex-shrink-0 overflow-hidden">
                      {acc?.profile_picture_url ? (
                        <img
                          src={acc.profile_picture_url}
                          alt={acc.account_name}
                          className="h-full w-full object-cover"
                        />
                      ) : (
                        renderPlatformIcon(plat, 'h-5 w-5')
                      )}
                    </div>
                    <div className="min-w-0">
                      <div className="text-xs font-bold text-white flex items-center gap-1.5 truncate">
                        {getPlatformLabel(plat)}
                      </div>
                      <div className="text-[11px] text-slate-300 font-semibold truncate max-w-[140px]">
                        {acc ? acc.account_name : 'Not Connected'}
                      </div>
                      {acc?.account_username && (
                        <div className="text-[10px] text-slate-500 truncate max-w-[140px]">
                          {acc.account_username}
                        </div>
                      )}
                    </div>
                  </div>

                  {acc ? (
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full flex-shrink-0 ${
                        acc.status === 'connected'
                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                          : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                      }`}
                    >
                      {acc.status === 'connected' ? 'Connected' : 'Reconnect'}
                    </span>
                  ) : (
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">
                      Not Connected
                    </span>
                  )}
                </div>

                <div className="pt-2 border-t border-slate-900 flex items-center justify-between text-xs">
                  {acc ? (
                    <div className="flex items-center gap-2 w-full justify-between">
                      <button
                        type="button"
                        onClick={() => handleConnectPlatform(plat)}
                        disabled={connectingPlatform === plat}
                        className="text-[11px] text-indigo-400 hover:text-indigo-300 font-semibold flex items-center gap-1 disabled:opacity-50"
                      >
                        {connectingPlatform === plat ? (
                          <RefreshCw className="h-3 w-3 animate-spin" />
                        ) : (
                          <RefreshCw className="h-3 w-3" />
                        )}
                        Reconnect
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDisconnect(acc.id)}
                        className="text-[11px] text-slate-400 hover:text-red-400 transition"
                      >
                        Disconnect
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => handleConnectPlatform(plat)}
                      disabled={connectingPlatform === plat}
                      className={`w-full text-center rounded-xl px-3 py-2 text-xs font-bold transition flex items-center justify-center gap-2 shadow-md active:scale-[0.98] disabled:opacity-50 whitespace-nowrap shrink-0 ${
                        plat === 'youtube'
                          ? 'bg-red-600 hover:bg-red-500 text-white shadow-red-600/30'
                          : plat === 'facebook'
                          ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-blue-600/30'
                          : plat === 'instagram'
                          ? 'bg-gradient-to-r from-pink-600 to-purple-600 hover:from-pink-500 hover:to-purple-500 text-white shadow-pink-600/30'
                          : 'bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-cyan-500/40 shadow-cyan-900/20'
                      }`}
                    >
                      {connectingPlatform === plat ? (
                        <>
                          <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                          <span className="whitespace-nowrap">Connecting...</span>
                        </>
                      ) : (
                        <>
                          {plat === 'youtube' && <Youtube className="h-3.5 w-3.5 shrink-0" />}
                          {plat === 'facebook' && <Facebook className="h-3.5 w-3.5 shrink-0" />}
                          {plat === 'instagram' && <Instagram className="h-3.5 w-3.5 shrink-0" />}
                          {plat === 'tiktok' && <Video className="h-3.5 w-3.5 text-cyan-400 shrink-0" />}
                          <span className="whitespace-nowrap">
                            {plat === 'youtube'
                              ? 'Connect YouTube'
                              : plat === 'facebook'
                              ? 'Connect Facebook'
                              : plat === 'instagram'
                              ? 'Connect Instagram'
                              : 'Connect TikTok'}
                          </span>
                        </>
                      )}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 2. CHOOSE PUBLISHING DESTINATION ACCOUNTS (PROMINENT SELECTION BAR) */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5 shadow-lg space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
              <Send className="h-4 w-4 text-indigo-400" />
              2. Choose Accounts on Which to Publish
            </h3>
            <p className="text-xs text-slate-400">
              Click any account below to turn publishing ON or OFF for this batch. ({globalSelectedAccountIds.length} of {activeConnectedAccounts.length} accounts selected)
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => {
                const allIds = activeConnectedAccounts.map((a) => a.id);
                setGlobalSelectedAccountIds(allIds);
                setMetadataMap((prev) => {
                  const next = { ...prev };
                  Object.keys(next).forEach((k) => {
                    next[k].account_ids = allIds;
                  });
                  return next;
                });
              }}
              className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 whitespace-nowrap shrink-0"
            >
              Select All
            </button>
            <span className="text-slate-700">|</span>
            <button
              type="button"
              onClick={() => {
                setGlobalSelectedAccountIds([]);
                setMetadataMap((prev) => {
                  const next = { ...prev };
                  Object.keys(next).forEach((k) => {
                    next[k].account_ids = [];
                  });
                  return next;
                });
              }}
              className="text-xs font-semibold text-slate-400 hover:text-white whitespace-nowrap shrink-0"
            >
              Deselect All
            </button>
          </div>
        </div>

        {activeConnectedAccounts.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-800 p-6 text-center text-xs text-slate-400 space-y-2">
            <p>No active accounts connected yet.</p>
            <p className="text-slate-500">
              Click <strong>"Connect YouTube Channel"</strong> above to link your profile.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-1">
            {activeConnectedAccounts.map((acc) => {
              const isSelected = globalSelectedAccountIds.includes(acc.id);
              return (
                <div
                  key={acc.id}
                  onClick={() => toggleGlobalAccount(acc.id)}
                  className={`rounded-xl border p-3.5 cursor-pointer transition flex items-center justify-between gap-3 shadow-sm select-none ${
                    isSelected
                      ? 'border-indigo-500 bg-indigo-950/30 ring-1 ring-indigo-500/50'
                      : 'border-slate-800 bg-slate-950/40 opacity-60 hover:opacity-100 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="relative">
                      {renderPlatformIcon(acc.platform, 'h-6 w-6')}
                      {isSelected && (
                        <span className="absolute -top-1 -right-1 h-3 w-3 rounded-full bg-indigo-500 border-2 border-slate-950" />
                      )}
                    </div>
                    <div className="truncate min-w-0">
                      <div className="text-xs font-bold text-white capitalize truncate flex items-center gap-1.5">
                        {acc.platform}
                        <span
                          className={`text-[9px] font-bold px-1.5 py-0.2 rounded ${
                            isSelected
                              ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'
                              : 'bg-slate-800 text-slate-400'
                          }`}
                        >
                          {isSelected ? '✓ Selected' : 'Muted'}
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-300 truncate font-semibold">
                        {acc.account_name}
                      </div>
                      {acc.account_username && (
                        <div className="text-[10px] text-slate-500 truncate">
                          {acc.account_username}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Toggle Checkbox */}
                  <div
                    className={`h-5 w-5 rounded-lg border flex items-center justify-center transition flex-shrink-0 ${
                      isSelected
                        ? 'bg-indigo-600 border-indigo-500 text-white'
                        : 'border-slate-700 bg-slate-900 text-transparent'
                    }`}
                  >
                    <Check className="h-3.5 w-3.5 stroke-[3]" />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 3. Reel Selection & Metadata Publishing Workspace */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Completed Reels Selection Gallery (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
              <Layers className="h-4 w-4 text-indigo-400" />
              3. Pick Reels to Publish ({completedReels.length})
            </h3>
            <button
              onClick={toggleSelectAll}
              className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 transition whitespace-nowrap shrink-0"
            >
              {selectedReelIds.length === completedReels.length
                ? 'Deselect All'
                : 'Select All Ready'}
            </button>
          </div>

          {completedReels.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-800 p-8 text-center text-slate-500 text-xs">
              No completed rendered reel exports found in this project. Wait for video rendering to finish in the Reels Gallery tab.
            </div>
          ) : (
            <div className="space-y-3 max-h-[720px] overflow-y-auto pr-1">
              {completedReels.map((reel) => {
                const isSelected = selectedReelIds.includes(reel.id);
                const isActive = activeEditingReelId === reel.id;
                const reelPosts = posts.filter((p) => p.reel_id === reel.id);

                return (
                  <div
                    key={reel.id}
                    onClick={() => {
                      setActiveEditingReelId(reel.id);
                      if (!isSelected) {
                        setSelectedReelIds((prev) => [...prev, reel.id]);
                      }
                    }}
                    className={`rounded-xl border p-3 cursor-pointer transition flex items-center gap-3.5 shadow-sm ${
                      isActive
                        ? 'border-indigo-500 bg-indigo-950/20 ring-1 ring-indigo-500/50'
                        : isSelected
                        ? 'border-slate-700 bg-slate-900/80'
                        : 'border-slate-800 bg-slate-900/40 hover:border-slate-700 hover:bg-slate-900/60'
                    }`}
                  >
                    {/* Checkbox */}
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={(e) => {
                        e.stopPropagation();
                        toggleSelectReel(reel.id);
                      }}
                      className="h-4 w-4 rounded border-slate-700 bg-slate-950 text-indigo-600 focus:ring-0 cursor-pointer"
                    />

                    {/* Thumbnail */}
                    <div className="relative h-20 w-14 flex-shrink-0 rounded-lg overflow-hidden bg-black border border-slate-800">
                      {reel.thumbnail_url ? (
                        <img
                          src={reel.thumbnail_url}
                          alt={reel.top_caption}
                          className="h-full w-full object-cover"
                        />
                      ) : (
                        <div className="h-full w-full flex items-center justify-center text-slate-600">
                          <Play className="h-4 w-4" />
                        </div>
                      )}
                      <span className="absolute bottom-1 right-1 rounded bg-black/80 px-1 py-0.2 text-[9px] font-mono text-white">
                        {reel.clip_duration.toFixed(0)}s
                      </span>
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0 space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="rounded bg-indigo-950/60 text-indigo-400 border border-indigo-800/40 px-1.5 py-0.5 text-[10px] font-bold">
                          Score {reel.score.toFixed(0)}
                        </span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            if (reel.video_url) {
                              setPreviewVideoUrl(reel.video_url);
                              setPreviewVideoTitle(reel.top_caption || reel.title);
                            }
                          }}
                          className="text-slate-400 hover:text-white p-1 rounded hover:bg-slate-800 transition"
                          title="Preview Exported Video"
                        >
                          <Eye className="h-3.5 w-3.5" />
                        </button>
                      </div>

                      <h4 className="text-xs font-bold text-white line-clamp-1">
                        {reel.top_caption || reel.title}
                      </h4>
                      <p className="text-[11px] text-slate-400 line-clamp-1">
                        {reel.reason}
                      </p>

                      {/* Publishing Status Badges */}
                      <div className="flex items-center gap-1.5 pt-1">
                        {reelPosts.length === 0 ? (
                          <span className="text-[10px] text-slate-500">Not queued</span>
                        ) : (
                          reelPosts.map((p) => (
                            <span
                              key={p.id}
                              className={`flex items-center gap-1 px-1.5 py-0.2 rounded text-[9px] font-semibold border ${
                                p.status === 'published'
                                  ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                                  : p.status === 'failed'
                                  ? 'bg-red-500/20 text-red-400 border-red-500/30'
                                  : 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30'
                              }`}
                            >
                              {renderPlatformIcon(p.platform, 'h-2.5 w-2.5')}
                              {p.status}
                            </span>
                          ))
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Column: Metadata & AI Hashtags Editor (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-indigo-400" />
              4. Review Captions & AI Hashtags
            </h3>
            {activeReel && (
              <span className="text-xs text-indigo-400 font-semibold truncate max-w-[240px]">
                Active: {activeReel.top_caption}
              </span>
            )}
          </div>

          {!activeReel || !activeMeta ? (
            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-12 text-center text-slate-500 text-xs">
              Select a reel from the left list to review and customize title, description, and hashtags.
            </div>
          ) : (
            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg space-y-5">
              {/* Per-Reel Destination Overrides */}
              <div className="space-y-2">
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-400">
                  Target Accounts for this Specific Reel
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                  {activeConnectedAccounts.map((acc) => {
                    const isTargeted = (activeMeta.account_ids || []).includes(acc.id);
                    return (
                      <button
                        key={acc.id}
                        type="button"
                        onClick={() => toggleReelAccount(activeReel.id, acc.id)}
                        className={`flex items-center gap-2 rounded-xl border p-2.5 text-xs font-semibold transition text-left ${
                          isTargeted
                            ? 'border-indigo-500 bg-indigo-600/20 text-white shadow'
                            : 'border-slate-800 bg-slate-950 text-slate-400 hover:border-slate-700'
                        }`}
                      >
                        {renderPlatformIcon(acc.platform, 'h-4 w-4')}
                        <div className="truncate min-w-0">
                          <div className="truncate capitalize">{acc.platform}</div>
                          <div className="text-[10px] text-slate-400 truncate">
                            {acc.account_name}
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Post Title / Hook Input */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold uppercase tracking-wider text-slate-400">
                    Post Title / Hook <span className="text-indigo-400">*</span>
                  </label>
                  <span className="text-[11px] text-slate-500">
                    {activeMeta.post_title.length}/100 chars (YouTube max)
                  </span>
                </div>
                <input
                  type="text"
                  maxLength={100}
                  value={activeMeta.post_title}
                  onChange={(e) =>
                    updateReelMetadata(activeReel.id, 'post_title', e.target.value)
                  }
                  placeholder="Catchy headline hook..."
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2.5 text-xs text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
                />
              </div>

              {/* Short Description */}
              <div className="space-y-1.5">
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-400">
                  Description / Punchline
                </label>
                <textarea
                  rows={2}
                  value={activeMeta.post_description}
                  onChange={(e) =>
                    updateReelMetadata(activeReel.id, 'post_description', e.target.value)
                  }
                  placeholder="What makes this clip special? Any context or takeaway for viewers..."
                  className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
                />
              </div>

              {/* AI Hashtag Suggestions (Powered by Gemini) */}
              <div className="space-y-2.5 pt-2 border-t border-slate-800">
                <div className="flex items-center justify-between">
                  <div>
                    <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
                      <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
                      AI Hashtags & Brand Tags
                    </label>
                    <span className="text-[11px] text-slate-400">
                      {activeMeta.hashtags.length} tags selected (Max 30 for Instagram)
                    </span>
                  </div>

                  <button
                    type="button"
                    onClick={() => handleSuggestHashtags(activeReel.id)}
                    disabled={loadingAiTags[activeReel.id]}
                    className="flex items-center gap-1.5 rounded-xl bg-indigo-600/30 border border-indigo-500/40 px-3 py-1.5 text-xs font-semibold text-indigo-300 hover:bg-indigo-600/50 hover:text-white transition shadow disabled:opacity-50 whitespace-nowrap shrink-0"
                  >
                    {loadingAiTags[activeReel.id] ? (
                      <>
                        <RefreshCw className="h-3 w-3 animate-spin shrink-0" />
                        <span className="whitespace-nowrap">Generating AI Tags...</span>
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-3 w-3 text-indigo-400 shrink-0" />
                        <span className="whitespace-nowrap">Suggest Hashtags</span>
                      </>
                    )}
                  </button>
                </div>

                {/* AI Suggested Tags Chips */}
                {aiSuggestionsMap[activeReel.id] &&
                  aiSuggestionsMap[activeReel.id].length > 0 && (
                    <div className="rounded-xl border border-slate-800 bg-slate-950/80 p-3 space-y-2">
                      <div className="flex items-center justify-between text-[11px] text-slate-400">
                        <span>Gemini Suggestions:</span>
                        <button
                          onClick={() => addAllSuggestedTags(activeReel.id)}
                          className="text-indigo-400 hover:text-indigo-300 font-semibold whitespace-nowrap shrink-0"
                        >
                          + Add All Suggested
                        </button>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {aiSuggestionsMap[activeReel.id].map((tag) => {
                          const isAdded = activeMeta.hashtags.some(
                            (t) => t.toLowerCase() === tag.toLowerCase()
                          );
                          return (
                            <button
                              key={tag}
                              type="button"
                              onClick={() => addHashtag(activeReel.id, tag)}
                              className={`rounded-lg px-2.5 py-1 text-[11px] font-medium transition whitespace-nowrap shrink-0 ${
                                isAdded
                                  ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 cursor-default'
                                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white border border-slate-700'
                              }`}
                            >
                              {isAdded ? '✓ ' : '+ '}
                              {tag}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  )}

                {/* Selected Active Hashtag Chips */}
                <div className="flex flex-wrap gap-1.5 min-h-[36px] p-2.5 rounded-xl border border-slate-800 bg-slate-950">
                  {activeMeta.hashtags.length === 0 ? (
                    <span className="text-[11px] text-slate-500 italic">
                      No hashtags added yet.
                    </span>
                  ) : (
                    activeMeta.hashtags.map((tag) => (
                      <span
                        key={tag}
                        className="flex items-center gap-1 rounded-lg bg-indigo-950 text-indigo-300 border border-indigo-800/60 px-2.5 py-1 text-xs font-semibold whitespace-nowrap shrink-0"
                      >
                        {tag}
                        <button
                          type="button"
                          onClick={() => removeHashtag(activeReel.id, tag)}
                          className="hover:text-red-400 ml-0.5"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </span>
                    ))
                  )}
                </div>

                {/* Manual tag & Brand tag input */}
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={manualTagInput}
                    onChange={(e) => setManualTagInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        addHashtag(activeReel.id, manualTagInput);
                        setManualTagInput('');
                      }
                    }}
                    placeholder="Add manual hashtag (e.g. #GTA6)..."
                    className="flex-1 rounded-xl border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      addHashtag(activeReel.id, manualTagInput);
                      setManualTagInput('');
                    }}
                    className="rounded-xl bg-slate-800 border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:bg-slate-700 hover:text-white transition whitespace-nowrap shrink-0"
                  >
                    + Add
                  </button>
                </div>
              </div>

              {/* Platform Specific Settings */}
              <div className="pt-2 border-t border-slate-800 grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* YouTube Visibility */}
                <div className="space-y-1">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                    YouTube Shorts Visibility
                  </label>
                  <select
                    value={activeMeta.visibility}
                    onChange={(e) =>
                      updateReelMetadata(activeReel.id, 'visibility', e.target.value)
                    }
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none"
                  >
                    <option value="public">Public (Direct publish)</option>
                    <option value="unlisted">Unlisted (Shareable link)</option>
                    <option value="private">Private (Owner only)</option>
                  </select>
                </div>

                {/* Made For Kids Choice */}
                <div className="space-y-1">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                    YouTube Made For Kids?
                  </label>
                  <select
                    value={activeMeta.made_for_kids ? 'true' : 'false'}
                    onChange={(e) =>
                      updateReelMetadata(
                        activeReel.id,
                        'made_for_kids',
                        e.target.value === 'true'
                      )
                    }
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none"
                  >
                    <option value="false">No, not made for kids (Standard)</option>
                    <option value="true">Yes, made for kids (COPPA)</option>
                  </select>
                </div>
              </div>

              {/* Per-Platform Live Caption Preview Tabs */}
              <div className="pt-3 border-t border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold uppercase tracking-wider text-slate-400">
                    Per-Platform Caption Preview
                  </label>
                  <div className="flex items-center gap-1">
                    {(['youtube', 'instagram', 'facebook', 'tiktok'] as const).map(
                      (p) => (
                        <button
                          key={p}
                          type="button"
                          onClick={() => setCaptionPreviewTab(p)}
                          className={`px-2.5 py-1 rounded-lg text-[10px] font-bold uppercase transition ${
                            captionPreviewTab === p
                              ? 'bg-indigo-600 text-white'
                              : 'bg-slate-800 text-slate-400 hover:text-white'
                          }`}
                        >
                          {p}
                        </button>
                      )
                    )}
                  </div>
                </div>

                <div className="rounded-xl border border-slate-800 bg-slate-950 p-3 text-xs text-slate-300 font-sans whitespace-pre-wrap max-h-36 overflow-y-auto">
                  {getCombinedCaptionPreview(captionPreviewTab)}
                </div>
              </div>

              {/* TikTok Manual Prepare Option */}
              <div className="pt-2 flex items-center justify-between text-xs text-slate-400">
                <span>Personal TikTok or internal setup?</span>
                <button
                  type="button"
                  onClick={() => handlePrepareTikTok(activeReel.id)}
                  className="text-cyan-400 hover:text-cyan-300 font-semibold flex items-center gap-1 whitespace-nowrap shrink-0"
                >
                  <Download className="h-3.5 w-3.5" />
                  Prepare for TikTok (Manual)
                </button>
              </div>
            </div>
          )}

          {/* Primary Publish Action Bar */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-5 shadow-2xl flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
                Ready to Publish
              </div>
              <div className="text-base font-extrabold text-white flex items-center gap-2">
                <span>{selectedReelIds.length} Reel(s) Selected</span>
                <span className="text-slate-500">•</span>
                <span className="text-indigo-400">{totalQueuedCount} Post(s) Queued</span>
              </div>
            </div>

            <button
              onClick={handlePublishSelected}
              disabled={
                isPublishing ||
                selectedReelIds.length === 0 ||
                totalQueuedCount === 0
              }
              className="flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 px-6 py-3 text-sm font-bold text-white shadow-xl shadow-indigo-600/30 transition disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap shrink-0"
            >
              {isPublishing ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin text-white" />
                  Queueing Background Workers...
                </>
              ) : (
                <>
                  <Send className="h-4 w-4" />
                  Publish Selected ({totalQueuedCount})
                </>
              )}
            </button>
          </div>

          {publishFeedback && (
            <div
              className={`rounded-xl border p-4 text-xs font-medium flex items-center gap-2 ${
                publishFeedback.type === 'success'
                  ? 'bg-emerald-950/40 border-emerald-800 text-emerald-300'
                  : 'bg-red-950/40 border-red-800 text-red-300'
              }`}
            >
              {publishFeedback.type === 'success' ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-400 flex-shrink-0" />
              ) : (
                <AlertCircle className="h-4 w-4 text-red-400 flex-shrink-0" />
              )}
              <span>{publishFeedback.message}</span>
            </div>
          )}
        </div>
      </div>

      {/* 4. Publication Status & Background Post Tracker */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg space-y-4">
        <div className="flex items-center justify-between">
          <div className="space-y-0.5">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
              <Clock className="h-4 w-4 text-indigo-400" />
              Publishing Progress & History
            </h3>
            <p className="text-xs text-slate-500">
              Track queued, uploading, and published reels. Failed destinations can be retried individually without duplicating successful posts.
            </p>
          </div>
          <button
            onClick={fetchProjectPosts}
            className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs text-slate-300 hover:text-white whitespace-nowrap shrink-0"
          >
            <RefreshCw className="h-3 w-3" /> Refresh Status
          </button>
        </div>

        {posts.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-800 p-8 text-center text-slate-500 text-xs">
            No publishing activity yet. Select your finished reels above and click "Publish Selected" to begin.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-950/60 text-[10px] uppercase font-bold text-slate-400 tracking-wider">
                <tr>
                  <th className="px-4 py-3">Platform & Account</th>
                  <th className="px-4 py-3">Post Title</th>
                  <th className="px-4 py-3">Status & Progress</th>
                  <th className="px-4 py-3">Link / Confirmation</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80">
                {posts.map((post) => {
                  return (
                    <tr key={post.id} className="hover:bg-slate-800/30 transition">
                      {/* Platform */}
                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="flex items-center gap-2.5">
                          {renderPlatformIcon(post.platform, 'h-4 w-4')}
                          <div>
                            <div className="font-semibold text-white capitalize">
                              {post.platform}
                            </div>
                            <div className="text-[10px] text-slate-400">
                              {post.account_name || 'Account'}
                            </div>
                          </div>
                        </div>
                      </td>

                      {/* Post Title */}
                      <td className="px-4 py-3 max-w-[220px]">
                        <div className="font-bold text-white truncate">{post.post_title}</div>
                        <div className="text-[10px] text-slate-400 line-clamp-1">
                          {post.combined_caption}
                        </div>
                      </td>

                      {/* Status & Progress */}
                      <td className="px-4 py-3 whitespace-nowrap">
                        <div className="space-y-1">
                          <div className="flex items-center gap-1.5">
                            {post.status === 'published' && (
                              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                            )}
                            {post.status === 'failed' && (
                              <AlertCircle className="h-3.5 w-3.5 text-red-400" />
                            )}
                            {post.status === 'uploading' && (
                              <RefreshCw className="h-3.5 w-3.5 text-indigo-400 animate-spin" />
                            )}
                            {post.status === 'queued' && (
                              <Clock className="h-3.5 w-3.5 text-amber-400" />
                            )}
                            <span
                              className={`text-[11px] font-bold uppercase tracking-wider ${
                                post.status === 'published'
                                  ? 'text-emerald-400'
                                  : post.status === 'failed'
                                  ? 'text-red-400'
                                  : post.status === 'reconnect_required'
                                  ? 'text-amber-400'
                                  : 'text-indigo-400'
                              }`}
                            >
                              {post.status}
                            </span>
                          </div>

                          {post.status === 'uploading' && (
                            <div className="w-32 bg-slate-800 h-1.5 rounded-full overflow-hidden">
                              <div
                                className="bg-indigo-500 h-full transition-all duration-300"
                                style={{ width: `${post.progress}%` }}
                              />
                            </div>
                          )}

                          {post.error_message && (
                            <div
                              className="text-[10px] text-red-400 max-w-xs truncate"
                              title={post.error_message}
                            >
                              {post.error_message}
                            </div>
                          )}
                        </div>
                      </td>

                      {/* Link / Confirmation */}
                      <td className="px-4 py-3 whitespace-nowrap">
                        {post.provider_post_url ? (
                          <a
                            href={post.provider_post_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 text-indigo-400 hover:text-indigo-300 font-semibold underline text-xs"
                          >
                            <span>View Reel</span>
                            <ExternalLink className="h-3 w-3" />
                          </a>
                        ) : post.status === 'published' ? (
                          <span className="text-[11px] text-emerald-400 font-semibold">
                            Published
                          </span>
                        ) : (
                          <span className="text-[11px] text-slate-500">—</span>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="px-4 py-3 whitespace-nowrap text-right">
                        {post.status === 'failed' && (
                          <button
                            onClick={() => handleRetryPost(post.id)}
                            className="rounded-lg bg-indigo-600/30 border border-indigo-500/40 px-2.5 py-1 text-[11px] font-semibold text-indigo-300 hover:bg-indigo-600/50 hover:text-white transition"
                          >
                            Retry Post
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Platform Setup Guidance Modal (when provider API keys are missing in .env) */}
      {platformConfigError && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2.5">
                {renderPlatformIcon(platformConfigError.platform, 'h-6 w-6')}
                <div>
                  <h4 className="text-base font-bold text-white">
                    Connect {getPlatformLabel(platformConfigError.platform)}
                  </h4>
                  <p className="text-[11px] text-slate-400">
                    Official App Credentials Required
                  </p>
                </div>
              </div>
              <button
                onClick={() => setPlatformConfigError(null)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <div className="rounded-xl border border-amber-800/60 bg-amber-950/40 p-3.5 text-xs text-amber-300 space-y-2">
              <div className="font-bold flex items-center gap-1.5 text-amber-400">
                <AlertCircle className="h-4 w-4" />
                Missing .env Credentials
              </div>
              <p className="text-[12px] text-amber-200/90 leading-relaxed">
                {platformConfigError.message}
              </p>
            </div>

            <div className="text-xs text-slate-400 space-y-1 bg-slate-950 p-3 rounded-xl border border-slate-800">
              <div className="font-semibold text-white">Already Ready:</div>
              <p className="text-emerald-400">
                ✓ <strong>YouTube Shorts</strong> credentials are fully configured in your .env. You can connect your YouTube channel directly with 1 click!
              </p>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => {
                  setPlatformConfigError(null);
                  setShowOAuthHelp(true);
                }}
                className="rounded-xl border border-slate-700 bg-slate-800 px-3.5 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-700 hover:text-white"
              >
                View App Setup Guide
              </button>
              <button
                type="button"
                onClick={() => setPlatformConfigError(null)}
                className="rounded-xl bg-indigo-600 px-4 py-2 text-xs font-bold text-white hover:bg-indigo-500"
              >
                Got It
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Video Preview Modal */}
      {previewVideoUrl && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="w-full max-w-sm rounded-2xl border border-slate-800 bg-slate-900 p-4 shadow-2xl space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <h4 className="text-xs font-bold text-white truncate max-w-[240px]">
                {previewVideoTitle}
              </h4>
              <button
                onClick={() => setPreviewVideoUrl(null)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>
            <div className="aspect-[9/16] w-full rounded-xl overflow-hidden bg-black border border-slate-800">
              <video
                src={previewVideoUrl}
                controls
                autoPlay
                className="h-full w-full object-contain"
              />
            </div>
          </div>
        </div>
      )}

      {/* TikTok Manual Prepare Modal */}
      {tikTokPrepareData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Video className="h-5 w-5 text-cyan-400" />
                <h4 className="text-sm font-bold text-white">
                  Prepare for TikTok (Manual Upload)
                </h4>
              </div>
              <button
                onClick={() => setTikTokPrepareData(null)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-300">
              {tikTokPrepareData.instructions}
            </p>

            <div className="space-y-3 pt-2">
              <a
                href={tikTokPrepareData.download_url}
                download
                className="w-full flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-bold text-white hover:bg-indigo-500 transition shadow"
              >
                <Download className="h-4 w-4" />
                1. Download Ready MP4 Video
              </a>

              <div className="space-y-1">
                <div className="flex items-center justify-between text-[11px] text-slate-400">
                  <span>Approved Caption & Tags</span>
                  <button
                    onClick={() => copyToClipboard(tikTokPrepareData.combined_text)}
                    className="text-cyan-400 hover:text-cyan-300 font-semibold flex items-center gap-1"
                  >
                    {copiedCaption ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                    {copiedCaption ? 'Copied!' : 'Copy Caption'}
                  </button>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950 p-3 text-xs text-slate-300 whitespace-pre-wrap max-h-32 overflow-y-auto">
                  {tikTokPrepareData.combined_text}
                </div>
              </div>

              <a
                href={tikTokPrepareData.tiktok_web_upload_url}
                target="_blank"
                rel="noopener noreferrer"
                className="w-full flex items-center justify-center gap-2 rounded-xl border border-cyan-500/40 bg-cyan-950/40 px-4 py-2.5 text-xs font-bold text-cyan-300 hover:bg-cyan-900/60 hover:text-white transition shadow"
              >
                <ExternalLink className="h-4 w-4" />
                3. Open TikTok Upload in New Tab
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
