/**
 * API client for Catering Services AI Pro
 */
import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auth
export const authAPI = {
  login: async (email: string, password: string) => {
    const formData = new FormData();
    formData.append('username', email);
    formData.append('password', password);
    const response = await api.post('/api/auth/login', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  register: async (email: string, fullName: string, password: string) => {
    const response = await api.post('/api/auth/register', {
      email,
      full_name: fullName,
      password,
    });
    return response.data;
  },

  getMe: async () => {
    const response = await api.get('/api/auth/me');
    return response.data;
  },
};

// Meetings
export const meetingsAPI = {
  list: async (upcomingOnly = true) => {
    const response = await api.get('/api/meetings', {
      params: { upcoming_only: upcomingOnly },
    });
    return response.data;
  },

  get: async (id: number) => {
    const response = await api.get(`/api/meetings/${id}`);
    return response.data;
  },

  create: async (data: any) => {
    const response = await api.post('/api/meetings', data);
    return response.data;
  },

  prepareBrief: async (id: number) => {
    const response = await api.post(`/api/meetings/${id}/prepare`);
    return response.data;
  },
};
