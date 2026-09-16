/// <reference types="vite/client" />

export const BACKEND_URL = process.env.NODE_ENV === 'production' 
  ? '' 
  : ((import.meta.env && import.meta.env.VITE_BACKEND_URL) || 'http://localhost:8000');

export const WS_BACKEND_URL = process.env.NODE_ENV === 'production'
  ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`
  : ((import.meta.env && import.meta.env.VITE_WS_BACKEND_URL) || 'ws://localhost:8000');

export interface BackendHealthResponse {
  service: string;
  version: string;
  status: string;
  redis_status: string;
  features: Record<string, boolean | string>;
}

export async function checkBackendHealth(): Promise<BackendHealthResponse | null> {
  try {
    const response = await fetch(`${BACKEND_URL}/api/v1/health`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!response.ok) return null;
    return await response.json();
  } catch (err) {
    console.warn('Backend health check failed:', err);
    return null;
  }
}
