export interface GenerateWordsRequest {
  count?: number;
  length?: number;
  min_length?: number;
  seed?: string;
  temperature?: number;
  n?: number;
  use_word_boundaries?: boolean;
  syllable_awareness?: number;
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