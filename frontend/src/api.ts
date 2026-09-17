import type {
  CanonicalSnapshot,
  RuntimeHealth,
  SlimeCollection,
  WorldSummary,
} from './types';

const configuredBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim();
export const API_BASE_URL = configuredBase
  ? configuredBase.replace(/\/$/, '')
  : import.meta.env.DEV
    ? 'http://127.0.0.1:8000'
    : '';

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'GET',
    cache: 'no-store',
    signal,
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(`${path} -> HTTP ${response.status}: ${message || response.statusText}`);
  }
  return (await response.json()) as T;
}

export async function fetchCanonicalSnapshot(signal?: AbortSignal): Promise<CanonicalSnapshot> {
  const [world, slimes, health] = await Promise.all([
    getJson<WorldSummary>('/world', signal),
    getJson<SlimeCollection>('/world/slimes', signal),
    getJson<RuntimeHealth>('/health', signal),
  ]);
  return { world, slimes, health, receivedAt: Date.now() };
}
