import axios from 'axios';

// Create axios instance with base configuration
const api = axios.create({
  baseURL: 'http://localhost:5000',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for logging/errors
api.interceptors.request.use(
  (config) => {
    console.log(`[API] ${config.method.toUpperCase()} ${config.baseURL}${config.url}`);
    return config;
  },
  (error) => {
    console.error('[API] Request error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    console.error('[API] Response error:', error.message);
    return Promise.reject(error);
  }
);

// API endpoints
export const apiEndpoints = {
  // Connection
  testConnection: () => api.get('/api/connection-test'),
  
  // Dashboard
  getDashboard: () => api.get('/api/dashboard'),
  getProgress: () => api.get('/progress'),
  
  // Processing
  processImage: (formData) => api.post('/api/process-image', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  processVideo: (formData) => api.post('/api/process-video', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  processFrame: (formData) => api.post('/process_frame', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  
  // Live monitoring
  getLiveData: () => api.get('/api/live-data'),
  addLiveDetection: (data) => api.post('/api/live-data/add', data),
  getLoggedPlates: () => api.get('/get_logged_plates'),
  clearLoggedPlates: () => api.post('/clear_logged_plates'),
  
  // Analytics
  exportAnalytics: () => api.get('/api/export-analytics'),
  
  // Logs
  clearLogs: () => api.post('/clear-logs'),
};

export default api;
