import axios from 'axios';
import type { AxiosInstance, AxiosRequestConfig, InternalAxiosRequestConfig, AxiosResponse } from 'axios';
import { message, Modal } from 'ant-design-vue';
import type { ApiResponse } from '@/types/api';

let isHandling401 = false;

// Dedup error popups: same URL + status → show once per session
const errorPopupShown = new Set<string>();

function shouldShowErrorPopup(url: string, status: number): boolean {
  const key = `${status}:${url}`;
  if (errorPopupShown.has(key)) {
    return false;
  }
  errorPopupShown.add(key);
  return true;
}

function showErrorPopup(title: string, content: string, url: string, status: number) {
  if (!shouldShowErrorPopup(url, status)) return;
  Modal.error({ title, content });
}

const instance: AxiosInstance = axios.create({
  baseURL: window.__APP_CONFIG__?.API_BASE_URL || import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// Request interceptor: attach JWT token
instance.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('access_token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// Response interceptor: unwrap data, handle errors
instance.interceptors.response.use(
  (response: AxiosResponse<ApiResponse>) => {
    const res = response.data;
    if (res.code !== undefined && res.code !== 0 && res.code !== 200) {
      message.error(res.message || 'Request failed');
      return Promise.reject(new Error(res.message));
    }
    return response;
  },
  (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid — only handle once
      if (!isHandling401) {
        isHandling401 = true;
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        window.location.href = '/login?expired=1';
      }
      return Promise.reject(error);
    } else if (error.response?.status === 403) {
      showErrorPopup('No Permission', 'You do not have permission to access this resource.', error.config?.url || '', 403);
    } else if (error.response?.status >= 500) {
      showErrorPopup('Server Error', error.response?.data?.message || 'Server error, please try again later.', error.config?.url || '', error.response?.status);
    } else if (error.code === 'ECONNABORTED') {
      showErrorPopup('Request Timeout', 'Request timed out, please check your network and try again.', error.config?.url || '', 408);
    } else if (error.response?.status === 404) {
      showErrorPopup('Not Found', error.response?.data?.message || 'Resource not found.', error.config?.url || '', 404);
    } else {
      const errMsg = error.response?.data?.message || error.message || 'Network error, please try again.';
      showErrorPopup('Request Failed', errMsg, error.config?.url || '', error.response?.status || 0);
    }
    return Promise.reject(error);
  },
);

export function get<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<AxiosResponse<ApiResponse<T>>> {
  return instance.get<ApiResponse<T>>(url, config);
}

export function post<T = unknown>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig,
): Promise<AxiosResponse<ApiResponse<T>>> {
  return instance.post<ApiResponse<T>>(url, data, config);
}

export function put<T = unknown>(
  url: string,
  data?: unknown,
  config?: AxiosRequestConfig,
): Promise<AxiosResponse<ApiResponse<T>>> {
  return instance.put<ApiResponse<T>>(url, data, config);
}

export function del<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<AxiosResponse<ApiResponse<T>>> {
  return instance.delete<ApiResponse<T>>(url, config);
}

export default instance;
