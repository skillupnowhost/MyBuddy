"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Settings } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import PageBlobBackground from "@/components/PageBlobBackground";
import { getAdminStats, getCurrentUser, getSystemHealth, listAdminUsers, updateUserRole } from "@/lib/admin";
import { isLoggedIn } from "@/lib/auth";
import type { AdminStats, AdminUserItem, SystemHealth } from "@/lib/types";

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm transition hover:border-indigo-200 hover:shadow-md">
      <p className="text-2xl font-semibold text-gray-900">{value}</p>
      <p className="text-xs text-gray-500">{label}</p>
    </div>
  );
}

function Bar({ percent }: { percent: number }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-200">
      <div
        className={`h-full rounded-full ${percent > 90 ? "bg-red-500" : percent > 70 ? "bg-amber-500" : "bg-emerald-500"}`}
        style={{ width: `${Math.min(percent, 100)}%` }}
      />
    </div>
  );
}

export default function AdminPage() {
  const router = useRouter();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }

    getCurrentUser().then((me) => {
      setCurrentUserId(me.id);
      if (me.role !== "ADMIN") {
        router.replace("/chat");
      }
    });

    Promise.all([getAdminStats(), getSystemHealth(), listAdminUsers()])
      .then(([s, h, u]) => {
        setStats(s);
        setHealth(h);
        setUsers(u);
      })
      .catch(() => setError("Could not load admin data. Are you an admin?"));
  }, [router]);

  async function handleRoleChange(userId: string, role: "USER" | "ADMIN") {
    try {
      const updated = await updateUserRole(userId, role);
      setUsers((prev) => prev.map((u) => (u.id === userId ? updated : u)));
    } catch {
      setError("Could not update role.");
    }
  }

  return (
    <div className="relative min-h-screen bg-white px-6 py-8 text-gray-900">
      <PageBlobBackground />
      <div className="mx-auto max-w-4xl">
        <PageHeader icon={Settings} title="Admin" description="Manage users, monitor system health, and review platform stats." />

        {error && (
          <p className="mb-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
        )}

        {stats && (
          <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-6">
            <StatCard label="Users" value={stats.total_users} />
            <StatCard label="Conversations" value={stats.total_conversations} />
            <StatCard label="Messages" value={stats.total_messages} />
            <StatCard label="Documents" value={stats.total_documents} />
            <StatCard label="Memories" value={stats.total_memories} />
            <StatCard label="Training jobs" value={stats.total_training_jobs} />
          </div>
        )}

        {health && (
          <div className="mb-8 rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition hover:shadow-md">
            <h2 className="mb-3 text-sm font-medium text-gray-700">System health</h2>
            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <div className="mb-1 flex justify-between text-xs text-gray-500">
                  <span>CPU</span>
                  <span>{health.cpu_percent.toFixed(0)}%</span>
                </div>
                <Bar percent={health.cpu_percent} />
              </div>
              <div>
                <div className="mb-1 flex justify-between text-xs text-gray-500">
                  <span>RAM</span>
                  <span>
                    {health.ram_used_gb.toFixed(1)} / {health.ram_total_gb.toFixed(1)} GB
                  </span>
                </div>
                <Bar percent={health.ram_percent} />
              </div>
              <div>
                <div className="mb-1 flex justify-between text-xs text-gray-500">
                  <span>Disk</span>
                  <span>
                    {health.disk_used_gb.toFixed(1)} / {health.disk_total_gb.toFixed(1)} GB
                  </span>
                </div>
                <Bar percent={health.disk_percent} />
              </div>
            </div>
            <div className="mt-4 flex gap-4 text-xs">
              <span className={health.database_ok ? "text-emerald-600" : "text-red-500"}>
                {health.database_ok ? "●" : "○"} Database
              </span>
              <span className={health.llm_ok ? "text-emerald-600" : "text-red-500"}>
                {health.llm_ok ? "●" : "○"} LLM
              </span>
            </div>
            <p className="mt-2 text-xs text-gray-400">No GPU metrics — this deployment has no dedicated GPU.</p>
          </div>
        )}

        <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition hover:shadow-md">
          <h2 className="mb-3 text-sm font-medium text-gray-700">Users</h2>
          <div className="space-y-1">
            {users.map((user) => (
              <div key={user.id} className="flex items-center justify-between rounded-lg px-2 py-2 text-sm hover:bg-gray-100">
                <div>
                  <p className="text-gray-800">{user.email}</p>
                  <p className="text-xs text-gray-400">{new Date(user.created_at).toLocaleDateString()}</p>
                </div>
                <select
                  value={user.role}
                  disabled={user.id === currentUserId}
                  onChange={(e) => handleRoleChange(user.id, e.target.value as "USER" | "ADMIN")}
                  className="rounded-lg border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-900 disabled:opacity-40"
                >
                  <option value="USER">USER</option>
                  <option value="ADMIN">ADMIN</option>
                </select>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
