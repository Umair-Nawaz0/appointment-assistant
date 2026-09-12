export class ApiError extends Error {
  constructor(message: string, public code: string, public details?: unknown) { super(message); }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...options,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...options.headers },
  });
  if (response.status === 204) return undefined as T;
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new ApiError(payload.error?.message ?? 'Request failed.', payload.error?.code ?? 'REQUEST_FAILED', payload.error?.details);
  }
  return payload as T;
}

export function formatDate(value: string, withTime = true) {
  return new Intl.DateTimeFormat(undefined, withTime
    ? { dateStyle: 'medium', timeStyle: 'short' }
    : { dateStyle: 'medium' }).format(new Date(value));
}
