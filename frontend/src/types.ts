export type MediaType = 'vinyl' | 'cd';

export interface UserProfile {
  user_id: string;
  email: string | null;
  name: string | null;
  avatar_url: string | null;
  discogs: {
    oauth_configured: boolean;
    connected: boolean;
    username: string | null;
  };
}

export interface DiscogsStatus {
  oauth_configured: boolean;
  authenticated: boolean;
  username: string | null;
}

export interface LabelData {
  albums: string[];
  artists: string[];
  tracks: string[] | null;
  country: string | null;
  format: string | null;
  label: string | null;
  catno: string | null;
  year: string | null;
}

export interface DiscogsResult {
  discogs_id: number | null;
  title: string | null;
  year: number | null;
  country: string | null;
  format: string | null;
  label: string | null;
  catno: string | null;
  discogs_url: string | null;
  cover_image: string | null;
}

export interface DebugInfo {
  cache_hit: boolean;
  strategies_tried: string[];
  timing_ms: Record<string, number>;
  llm_label_response: Record<string, unknown>;
  prefilter?: { before: number; after: number };
  ranking?: { likeliness: number[]; discarded: number[] };
}

export interface SearchResponse {
  label_data: LabelData;
  strategy: string;
  results: DiscogsResult[];
  total: number;
  item_id: string | null;
  debug: DebugInfo | null;
}

export interface CollectionItem {
  release_id: number;
  instance_id: number;
  title: string;
  artist: string;
  year: number;
  genres: string[];
  styles: string[];
  format: string;
  cover_image: string | null;
  date_added: string | null;
}

export interface CollectionResponse {
  items: CollectionItem[];
  page: number;
  pages: number;
  per_page: number;
  total_items: number;
}

export interface SyncStatus {
  status: 'idle' | 'syncing' | 'error';
  started_at?: string | null;
  completed_at?: string | null;
  total_items?: number;
  items_synced?: number;
  error?: string | null;
}

export interface Batch {
  batch_id: string;
  status: 'processing' | 'completed' | 'failed';
  total_images: number;
  processed: number;
  failed: number;
  original_filename: string | null;
  created_at: string;
}

export interface BatchItem {
  item_id: string;
  batch_id: string;
  image_filename: string;
  status: 'pending' | 'processing' | 'completed' | 'error';
  error: string | null;
  label_data: LabelData | null;
  results: DiscogsResult[] | null;
  strategy: string | null;
  review_status: 'unreviewed' | 'accepted' | 'skipped' | 'wrong';
  accepted_release_id: number | null;
  image_url: string | null;
  debug: DebugInfo | null;
}
