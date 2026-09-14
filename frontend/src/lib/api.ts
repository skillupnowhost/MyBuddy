import { clearTokens, getAccessToken, getRefreshToken, saveTokens } from "./auth";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  const resp = await fetch(`${API_URL}/api/v1/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!resp.ok) return false;

  const data = await resp.json();
  saveTokens(data.access_token, data.refresh_token);
  return true;
}

export async function apiFetch(path: string, options: RequestInit = {}, retry = true): Promise<Response> {
  const token = getAccessToken();
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  if (!isFormData && !headers.has("Content-Type") && options.body) headers.set("Content-Type", "application/json");

  const resp = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (resp.status === 401 && retry) {
    const refreshed = await refreshAccessToken();
    if (refreshed) return apiFetch(path, options, false);
    clearTokens();
  }

  return resp;
}

export async function apiJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const resp = await apiFetch(path, options);
  if (!resp.ok) {
    const detail = await resp.text();
    throw new ApiError(detail || resp.statusText, resp.status);
  }
  return resp.json();
}
