const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

/**
 * Perform an HTTP request against the backend API.
 *
 * Parameters:
 *   path: Backend API path.
 *   options: Optional fetch settings.
 *
 * Returns:
 *   Parsed JSON response typed by caller.
 *
 * Edge cases:
 *   Non-2xx responses throw an Error with backend detail when available.
 */
export async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const localKey = window.localStorage.getItem('LOCAL_APP_API_KEY') ?? '';
  const headers = new Headers(options.headers);
  headers.set('Content-Type', 'application/json');
  if (localKey) {
    headers.set('X-Local-App-Key', localKey);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(String(payload.detail ?? response.statusText));
  }

  return response.json() as Promise<T>;
}
