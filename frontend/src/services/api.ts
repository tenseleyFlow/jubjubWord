import axios from 'axios';
import { GenerateWordsRequest, GenerateWordsResponse } from '@/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Important for session cookies
});

export const wordGeneratorApi = {
  generateWords: async (params: GenerateWordsRequest): Promise<GenerateWordsResponse> => {
    const response = await api.post<GenerateWordsResponse>('/generate/', params);
    return response.data;
  },
  
  healthCheck: async (): Promise<{ status: string }> => {
    const response = await api.get('/health/');
    return response.data;
  },
  
  // Community features
  trackCopy: async (word: string): Promise<{ success: boolean; copy_count: number }> => {
    const response = await api.post('/track-copy/', { word });
    return response.data;
  },
  
  addDefinition: async (word: string, definition: string): Promise<{
    success: boolean;
    definition_id: number;
    definition: {
      id: number;
      definition: string;
      upvotes: number;
      downvotes: number;
      created_at: string;
    };
  }> => {
    const response = await api.post('/add-definition/', { word, definition });
    return response.data;
  },
  
  voteDefinition: async (definitionId: number, voteType: 'up' | 'down'): Promise<{
    success: boolean;
    upvotes: number;
    downvotes: number;
  }> => {
    const response = await api.post('/vote-definition/', { 
      definition_id: definitionId, 
      vote_type: voteType 
    });
    return response.data;
  },
  
  getWordDefinitions: async (word: string): Promise<{
    word: string;
    definitions: Array<{
      id: number;
      definition: string;
      upvotes: number;
      downvotes: number;
      created_at: string;
    }>;
  }> => {
    const response = await api.get(`/word/${encodeURIComponent(word)}/definitions/`);
    return response.data;
  },
};