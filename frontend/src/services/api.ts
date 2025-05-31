import axios from 'axios';
import { GenerateWordsRequest, GenerateWordsResponse } from '@/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
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
};