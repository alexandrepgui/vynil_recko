export type MediaType = 'vinyl' | 'cd';

export interface LabelData {
  albums: string[];
  artists: string[];
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

export interface SearchResponse {
  label_data: LabelData;
  strategy: string;
  results: DiscogsResult[];
  total: number;
  item_id: string | null;
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
  review_status: 'unreviewed' | 'accepted' | 'skipped';
  accepted_release_id: number | null;
}
