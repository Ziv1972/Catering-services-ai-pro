/**
 * API client for Catering Services AI Pro
 */
import axios from 'axios';

const RAILWAY_BACKEND = 'https://courteous-amazement-production-02e2.up.railway.app';

function getApiBaseUrl(): string {
  // Explicit env var takes priority
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
  if (typeof window === 'undefined') return RAILWAY_BACKEND;
  // On Railway (*.up.railway.app), use the known backend URL
  if (window.location.hostname.endsWith('.up.railway.app')) return RAILWAY_BACKEND;
  // Local dev
  return `${window.location.protocol}//${window.location.hostname}:8000`;
}

const API_BASE_URL = getApiBaseUrl();

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
    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: `username=${encodeURIComponent(email)}&password=${encodeURIComponent(password)}`,
    });
    if (!response.ok) throw new Error('Login failed');
    return response.json();
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

  drillDownCost: async (params?: { month?: number; year?: number; site_id?: number }) => {
    const response = await api.get('/api/historical/drill-down/cost', { params });
    return response.data;
  },

  drillDownMeals: async (params?: { month?: number; year?: number; site_id?: number }) => {
    const response = await api.get('/api/historical/drill-down/meals', { params });
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

// Dashboard
export const dashboardAPI = {
  get: async () => {
    const response = await api.get('/api/dashboard');
    return response.data;
  },
};

// Supplier Budgets
export const supplierBudgetsAPI = {
  list: async (params?: { supplier_id?: number; site_id?: number; year?: number }) => {
    const response = await api.get('/api/supplier-budgets', { params });
    return response.data;
  },

  create: async (data: any) => {
    const response = await api.post('/api/supplier-budgets', data);
    return response.data;
  },

  update: async (id: number, data: any) => {
    const response = await api.put(`/api/supplier-budgets/${id}`, data);
    return response.data;
  },

  delete: async (id: number) => {
    const response = await api.delete(`/api/supplier-budgets/${id}`);
    return response.data;
  },

  vsActual: async (params?: { year?: number; site_id?: number }) => {
    const response = await api.get('/api/supplier-budgets/vs-actual', { params });
    return response.data;
  },

  addProductLimit: async (budgetId: number, data: any) => {
    const response = await api.post(`/api/supplier-budgets/${budgetId}/product-limits`, data);
    return response.data;
  },
};

// Projects
export const projectsAPI = {
  list: async (params?: { status?: string; site_id?: number }) => {
    const response = await api.get('/api/projects', { params });
    return response.data;
  },

  get: async (id: number) => {
    const response = await api.get(`/api/projects/${id}`);
    return response.data;
  },

  create: async (data: any) => {
    const response = await api.post('/api/projects', data);
    return response.data;
  },

  update: async (id: number, data: any) => {
    const response = await api.put(`/api/projects/${id}`, data);
    return response.data;
  },

  delete: async (id: number) => {
    const response = await api.delete(`/api/projects/${id}`);
    return response.data;
  },

  addTask: async (projectId: number, data: any) => {
    const response = await api.post(`/api/projects/${projectId}/tasks`, data);
    return response.data;
  },

  updateTask: async (projectId: number, taskId: number, data: any) => {
    const response = await api.put(`/api/projects/${projectId}/tasks/${taskId}`, data);
    return response.data;
  },

  deleteTask: async (projectId: number, taskId: number) => {
    const response = await api.delete(`/api/projects/${projectId}/tasks/${taskId}`);
    return response.data;
  },

  uploadDocument: async (projectId: number, file: File, taskId?: number) => {
    const formData = new FormData();
    formData.append('file', file);
    if (taskId) formData.append('task_id', taskId.toString());
    const response = await api.post(`/api/projects/${projectId}/documents`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  listDocuments: async (projectId: number, taskId?: number) => {
    const params: any = {};
    if (taskId) params.task_id = taskId;
    const response = await api.get(`/api/projects/${projectId}/documents`, { params });
    return response.data;
  },

  downloadDocument: async (projectId: number, docId: number) => {
    const response = await api.get(`/api/projects/${projectId}/documents/${docId}/download`, {
      responseType: 'blob',
    });
    return response;
  },

  deleteDocument: async (projectId: number, docId: number) => {
    const response = await api.delete(`/api/projects/${projectId}/documents/${docId}`);
    return response.data;
  },
};

// Maintenance
export const maintenanceAPI = {
  listBudgets: async (params?: { site_id?: number; year?: number }) => {
    const response = await api.get('/api/maintenance/budgets', { params });
    return response.data;
  },

  createBudget: async (data: any) => {
    const response = await api.post('/api/maintenance/budgets', data);
    return response.data;
  },

  updateBudget: async (id: number, data: any) => {
    const response = await api.put(`/api/maintenance/budgets/${id}`, data);
    return response.data;
  },

  listExpenses: async (params?: { site_id?: number; year?: number; quarter?: number }) => {
    const response = await api.get('/api/maintenance/expenses', { params });
    return response.data;
  },

  createExpense: async (data: any) => {
    const response = await api.post('/api/maintenance/expenses', data);
    return response.data;
  },

  updateExpense: async (id: number, data: any) => {
    const response = await api.put(`/api/maintenance/expenses/${id}`, data);
    return response.data;
  },

  deleteExpense: async (id: number) => {
    const response = await api.delete(`/api/maintenance/expenses/${id}`);
    return response.data;
  },

  summary: async (year?: number) => {
    const response = await api.get('/api/maintenance/summary', { params: { year } });
    return response.data;
  },
};

// Todos
export const todosAPI = {
  list: async (params?: { filter?: string; status?: string; priority?: string }) => {
    const response = await api.get('/api/todos', { params });
    return response.data;
  },

  create: async (data: any) => {
    const response = await api.post('/api/todos', data);
    return response.data;
  },

  update: async (id: number, data: any) => {
    const response = await api.put(`/api/todos/${id}`, data);
    return response.data;
  },

  complete: async (id: number) => {
    const response = await api.put(`/api/todos/${id}/complete`);
    return response.data;
  },

  delete: async (id: number) => {
    const response = await api.delete(`/api/todos/${id}`);
    return response.data;
  },
};

// Chat
export const chatAPI = {
  send: async (message: string) => {
    const response = await api.post('/api/chat', { message });
    return response.data;
  },
};

// Price Lists
export const priceListsAPI = {
  list: async (params?: { supplier_id?: number }) => {
    const response = await api.get('/api/price-lists', { params });
    return response.data;
  },

  get: async (id: number) => {
    const response = await api.get(`/api/price-lists/${id}`);
    return response.data;
  },

  create: async (data: { supplier_id: number; effective_date: string; notes?: string }) => {
    const response = await api.post('/api/price-lists', data);
    return response.data;
  },

  addItems: async (priceListId: number, items: Array<{ product_id: number; price: number; unit?: string }>) => {
    const response = await api.post(`/api/price-lists/${priceListId}/items`, { items });
    return response.data;
  },

  delete: async (id: number) => {
    const response = await api.delete(`/api/price-lists/${id}`);
    return response.data;
  },

  getProducts: async (category?: string) => {
    const response = await api.get('/api/price-lists/products/catalog', {
      params: category ? { category } : {},
    });
    return response.data;
  },

  getCategories: async () => {
    const response = await api.get('/api/price-lists/products/categories');
    return response.data;
  },

  compare: async (id1: number, id2: number) => {
    const response = await api.get('/api/price-lists/compare', {
      params: { price_list_id_1: id1, price_list_id_2: id2 },
    });
    return response.data;
  },
};

// Fine Rules
export const fineRulesAPI = {
  list: async (params?: { category?: string; active_only?: boolean }) => {
    const response = await api.get('/api/fine-rules', { params });
    return response.data;
  },

  create: async (data: { name: string; category: string; amount: number; description?: string }) => {
    const response = await api.post('/api/fine-rules', data);
    return response.data;
  },

  update: async (id: number, data: any) => {
    const response = await api.put(`/api/fine-rules/${id}`, data);
    return response.data;
  },

  delete: async (id: number) => {
    const response = await api.delete(`/api/fine-rules/${id}`);
    return response.data;
  },
};

// Dashboard drill-down
export const drillDownAPI = {
  budget: async (params?: { supplier_id?: number; site_id?: number; year?: number }) => {
    const response = await api.get('/api/dashboard/drill-down/budget', { params });
    return response.data;
  },

  products: async (params?: { supplier_id?: number; site_id?: number; month?: number; year?: number }) => {
    const response = await api.get('/api/dashboard/drill-down/products', { params });
    return response.data;
  },

  project: async (project_id: number) => {
    const response = await api.get('/api/dashboard/drill-down/project', { params: { project_id } });
    return response.data;
  },

  maintenance: async (params?: { site_id?: number; quarter?: number; year?: number }) => {
    const response = await api.get('/api/dashboard/drill-down/maintenance', { params });
    return response.data;
  },
};

// Category Analysis (product category drill-down)
export const categoryAnalysisAPI = {
  groups: async () => {
    const response = await api.get('/api/category-analysis/groups');
    return response.data;
  },

  // Cost drill-down (4 levels)
  costMonthly: async (params?: { year?: number; supplier_id?: number }) => {
    const response = await api.get('/api/category-analysis/cost/monthly', { params });
    return response.data;
  },
  costBySite: async (params: { year: number; month: number; supplier_id?: number }) => {
    const response = await api.get('/api/category-analysis/cost/by-site', { params });
    return response.data;
  },
  costByCategory: async (params: { year: number; month: number; site_id: number; supplier_id?: number }) => {
    const response = await api.get('/api/category-analysis/cost/by-category', { params });
    return response.data;
  },
  costProducts: async (params: { year: number; month: number; site_id: number; category_name: string; supplier_id?: number }) => {
    const response = await api.get('/api/category-analysis/cost/products', { params });
    return response.data;
  },

  // Quantity drill-down (4 levels)
  quantityMonthly: async (params?: { year?: number; supplier_id?: number }) => {
    const response = await api.get('/api/category-analysis/quantity/monthly', { params });
    return response.data;
  },
  quantityBySite: async (params: { year: number; month: number; supplier_id?: number }) => {
    const response = await api.get('/api/category-analysis/quantity/by-site', { params });
    return response.data;
  },
  quantityByCategory: async (params: { year: number; month: number; site_id: number; supplier_id?: number }) => {
    const response = await api.get('/api/category-analysis/quantity/by-category', { params });
    return response.data;
  },
  quantityProducts: async (params: { year: number; month: number; site_id: number; category_name: string; supplier_id?: number }) => {
    const response = await api.get('/api/category-analysis/quantity/products', { params });
    return response.data;
  },

  // Working days
  getWorkingDays: async (params?: { site_id?: number; year?: number }) => {
    const response = await api.get('/api/category-analysis/working-days', { params });
    return response.data;
  },
  setWorkingDays: async (data: { site_id: number; year: number; month: number; working_days: number; notes?: string }) => {
    const response = await api.post('/api/category-analysis/working-days', data);
    return response.data;
  },
};

// Attachments (polymorphic file upload for any entity)
export const attachmentsAPI = {
  upload: async (entityType: string, entityId: number, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('entity_type', entityType);
    formData.append('entity_id', String(entityId));
    const response = await api.post('/api/attachments/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },
  list: async (entityType: string, entityId: number) => {
    const response = await api.get('/api/attachments', { params: { entity_type: entityType, entity_id: entityId } });
    return response.data;
  },
  download: async (attachmentId: number) => {
    const response = await api.get(`/api/attachments/${attachmentId}/download`, { responseType: 'blob' });
    return response.data;
  },
  delete: async (attachmentId: number) => {
    const response = await api.delete(`/api/attachments/${attachmentId}`);
    return response.data;
  },
  process: async (attachmentId: number, mode: 'summarize' | 'extract' | 'both') => {
    const response = await api.post(`/api/attachments/${attachmentId}/process`, { mode });
    return response.data;
  },
};
