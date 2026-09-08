/**
 * Minimal axios client for the HR Dashboard. Mirrors the auth + base-URL
 * convention from frontend/src/api/client.ts so the two surfaces talk to the
 * same backend the same way.
 *
 * The route components (C1-11b onwards) consume this — for the scaffold we
 * only need it to exist + carry the Authorization header.
 */

import axios, { AxiosInstance } from 'axios';
import { buildAuthHeaders, clearAuthToken } from './auth';

const API_BASE_URL: string =
  import.meta.env.VITE_API_URL ||
  (import.meta.env.DEV ? 'http://localhost:8000' : '');

export { API_BASE_URL };

export const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 12_000,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const headers = buildAuthHeaders();
  if (headers.Authorization) {
    config.headers.Authorization = headers.Authorization;
  }
  return config;
});

api.interceptors.response.use(
  (resp) => resp,
  (error) => {
    // 401 → drop the local token so the next route render bounces to /login.
    // Route components (RequireAuth) own the actual redirect.
    if (error?.response?.status === 401) {
      clearAuthToken();
    }
    return Promise.reject(error);
  },
);
