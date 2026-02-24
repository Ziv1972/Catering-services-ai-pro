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

// Redirect to login on 401
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && typeof window !== 'undefined') {
      const path = window.location.pathname;
      if (path !== '/login') {
        localStorage.removeItem('access_token');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

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

// Complaints
export const complaintsAPI = {
  list: async (params?: {
    days?: number;
    severity?: string;
    status?: string;
    site_id?: number;
  }) => {
    const response = await api.get('/api/complaints', { params });
    return response.data;
  },

  get: async (id: number) => {
    const response = await api.get(`/api/complaints/${id}`);
    return response.data;
  },

  create: async (data: any) => {
    const response = await api.post('/api/complaints', data);
    return response.data;
  },

  acknowledge: async (id: number) => {
    const response = await api.post(`/api/complaints/${id}/acknowledge`);
    return response.data;
  },

  draftResponse: async (id: number) => {
    const response = await api.post(`/api/complaints/${id}/draft-response`);
    return response.data;
  },

  resolve: async (id: number, notes: string) => {
    const response = await api.post(`/api/complaints/${id}/resolve`, {
      resolution_notes: notes,
    });
    return response.data;
  },

  getPatterns: async () => {
    const response = await api.get('/api/complaints/patterns/active');
    return response.data;
  },

  detectPatterns: async (days: number = 7) => {
    const response = await api.post(`/api/complaints/detect-patterns?days=${days}`);
    return response.data;
  },

  getWeeklySummary: async () => {
    const response = await api.get('/api/complaints/summary/weekly');
    return response.data;
  },
};

// Menu Compliance
export const menuComplianceAPI = {
  listChecks: async (params?: {
    site_id?: number;
    year?: number;
    limit?: number;
  }) => {
    const response = await api.get('/api/menu-compliance/checks', { params });
    return response.data;
  },

  getCheck: async (id: number) => {
    const response = await api.get(`/api/menu-compliance/checks/${id}`);
    return response.data;
  },

  getResults: async (checkId: number) => {
    const response = await api.get(`/api/menu-compliance/checks/${checkId}/results`);
    return response.data;
  },

  getStats: async () => {
    const response = await api.get('/api/menu-compliance/stats');
    return response.data;
  },

  uploadMenu: async (file: File, siteId: number, month: string, year: number) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('site_id', siteId.toString());
    formData.append('month', month);
    formData.append('year', year.toString());
    const response = await api.post('/api/menu-compliance/upload-menu', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  listRules: async (activeOnly = false) => {
    const response = await api.get('/api/menu-compliance/rules', {
      params: { active_only: activeOnly },
    });
    return response.data;
  },

  createRule: async (data: any) => {
    const response = await api.post('/api/menu-compliance/rules', data);
    return response.data;
  },

  updateRule: async (id: number, data: any) => {
    const response = await api.put(`/api/menu-compliance/rules/${id}`, data);
    return response.data;
  },

  deleteRule: async (id: number) => {
    const response = await api.delete(`/api/menu-compliance/rules/${id}`);
    return response.data;
  },
};

// Proformas
export const proformasAPI = {
  list: async (params?: {
    months?: number;
    supplier_id?: number;
    site_id?: number;
  }) => {
    const response = await api.get('/api/proformas', { params });
    return response.data;
  },

  get: async (id: number) => {
    const response = await api.get(`/api/proformas/${id}`);
    return response.data;
  },

  getItems: async (proformaId: number) => {
    const response = await api.get(`/api/proformas/${proformaId}/items`);
    return response.data;
  },

  getVendorSpending: async (months?: number) => {
    const response = await api.get('/api/proformas/vendor-spending/summary', {
      params: { months },
    });
    return response.data;
  },

  create: async (data: any) => {
    const response = await api.post('/api/proformas', data);
    return response.data;
  },
};

// Suppliers
export const suppliersAPI = {
  list: async (activeOnly = false) => {
    const response = await api.get('/api/suppliers', {
      params: { active_only: activeOnly },
    });
    return response.data;
  },

  get: async (id: number) => {
    const response = await api.get(`/api/suppliers/${id}`);
    return response.data;
  },

  create: async (data: any) => {
    const response = await api.post('/api/suppliers', data);
    return response.data;
  },

  update: async (id: number, data: any) => {
    const response = await api.put(`/api/suppliers/${id}`, data);
    return response.data;
  },

  delete: async (id: number) => {
    const response = await api.delete(`/api/suppliers/${id}`);
    return response.data;
  },
};

// Historical Data
export const historicalAPI = {
  getMealData: async (params?: {
    site_id?: number;
    start_date?: string;
    end_date?: string;
  }) => {
    const response = await api.get('/api/historical/meals', { params });
    return response.data;
  },

  getAnalytics: async (site_id?: number) => {
    const response = await api.get('/api/historical/analytics', {
      params: { site_id },
    });
    return response.data;
  },
};

// Anomalies
export const anomaliesAPI = {
  list: async (params?: {
    resolved?: boolean;
    severity?: string;
  }) => {
    const response = await api.get('/api/anomalies', { params });
    return response.data;
  },

  acknowledge: async (id: number) => {
    const response = await api.post(`/api/anomalies/${id}/acknowledge`);
    return response.data;
  },

  resolve: async (id: number, notes: string) => {
    const response = await api.post(`/api/anomalies/${id}/resolve`, {
      resolution_notes: notes,
    });
    return response.data;
  },
};
