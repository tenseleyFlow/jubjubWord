export interface GenerateWordsRequest {
  count?: number;
  length?: number;
  min_length?: number;
  seed?: string;
  temperature?: number;
  n?: number;
  use_word_boundaries?: boolean;
}

export interface GenerateWordsResponse {
  words: string[];
  parameters: {
    count: number;
    length: number;
    min_length: number;
    seed: string | null;
    temperature: number;
    n: number;
    use_word_boundaries: boolean;
  };
}
