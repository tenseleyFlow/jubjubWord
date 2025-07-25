export interface GenerateWordsRequest {
  count?: number;
  length?: number;
  min_length?: number;
  seed?: string;
  temperature?: number;
  n?: number;
  use_word_boundaries?: boolean;
  syllable_awareness?: number;
  corpus?: string;
}

export interface Definition {
  id: number;
  definition: string;
  upvotes: number;
  downvotes: number;
  created_at: string;
}

export interface CommunityData {
  word_id: number;
  copy_count: number;
  definitions: Definition[];
}

export interface Corpus {
  slug: string;
  name: string;
  description: string;
  theme_color: string;
  icon_emoji: string;
  word_count: number;
  times_used: number;
}

export interface GenerateWordsResponse {
  words: string[];
  is_community?: boolean;
  community_data?: CommunityData;
  parameters: {
    count: number;
    length: number;
    min_length: number;
    seed: string | null;
    temperature: number;
    n: number;
    use_word_boundaries: boolean;
    syllable_awareness: number;
  };
}