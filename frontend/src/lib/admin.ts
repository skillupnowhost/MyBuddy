import { apiJson } from "./api";
import type { AdminStats, AdminUserItem, CurrentUser, SystemHealth } from "./types";

export function getCurrentUser(): Promise<CurrentUser> {
  return apiJson<CurrentUser>("/api/v1/auth/me");
}

export function listAdminUsers(): Promise<AdminUserItem[]> {
  return apiJson<AdminUserItem[]>("/api/v1/admin/users");
}

export function updateUserRole(id: string, role: "USER" | "ADMIN"): Promise<AdminUserItem> {
  return apiJson<AdminUserItem>(`/api/v1/admin/users/${id}/role`, {
    method: "PATCH",
    body: JSON.stringify({ role }),
  });
}

export function getAdminStats(): Promise<AdminStats> {
  return apiJson<AdminStats>("/api/v1/admin/stats");
}

export function getSystemHealth(): Promise<SystemHealth> {
  return apiJson<SystemHealth>("/api/v1/admin/health");
}
