import type {
  CanonicalSnapshot,
  FoodCollection,
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

function delay(milliseconds: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException('Aborted', 'AbortError'));
      return;
    }
    const timer = window.setTimeout(resolve, milliseconds);
    signal?.addEventListener(
      'abort',
      () => {
        window.clearTimeout(timer);
        reject(new DOMException('Aborted', 'AbortError'));
      },
      { once: true },
    );
  });
}

export async function fetchCanonicalSnapshot(signal?: AbortSignal): Promise<CanonicalSnapshot> {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const [world, slimes, foods, health] = await Promise.all([
      getJson<WorldSummary>('/world', signal),
      getJson<SlimeCollection>('/world/slimes', signal),
      getJson<FoodCollection>('/world/foods', signal),
      getJson<RuntimeHealth>('/health', signal),
    ]);

    if (world.tick === slimes.tick && world.tick === foods.tick) {
      return { world, slimes, foods, health, receivedAt: Date.now() };
    }
    if (attempt < 2) await delay(60, signal);
  }

  throw new Error('Snapshot canonique incohérent entre les projections du monde');
}
