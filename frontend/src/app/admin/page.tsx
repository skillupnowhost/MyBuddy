"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getAdminStats, getCurrentUser, getSystemHealth, listAdminUsers, updateUserRole } from "@/lib/admin";
import { isLoggedIn } from "@/lib/auth";
import type { AdminStats, AdminUserItem, SystemHealth } from "@/lib/types";

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#161922] p-4">
      <p className="text-2xl font-semibold text-white">{value}</p>
      <p className="text-xs text-white/50">{label}</p>
    </div>
  );
}

function Bar({ percent }: { percent: number }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
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
    <div className="min-h-screen bg-[#0f1115] px-6 py-8 text-white">
      <div className="mx-auto max-w-4xl">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Admin</h1>
          <Link href="/chat" className="text-sm text-blue-400 hover:underline">
            &larr; Back to chat
          </Link>
        </div>

        {error && <p className="mb-4 text-sm text-red-400">{error}</p>}

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
          <div className="mb-8 rounded-xl border border-white/10 bg-[#161922] p-4">
            <h2 className="mb-3 text-sm font-medium text-white/70">System health</h2>
            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <div className="mb-1 flex justify-between text-xs text-white/50">
                  <span>CPU</span>
                  <span>{health.cpu_percent.toFixed(0)}%</span>
                </div>
                <Bar percent={health.cpu_percent} />
              </div>
              <div>
                <div className="mb-1 flex justify-between text-xs text-white/50">
                  <span>RAM</span>
                  <span>
                    {health.ram_used_gb.toFixed(1)} / {health.ram_total_gb.toFixed(1)} GB
                  </span>
                </div>
                <Bar percent={health.ram_percent} />
              </div>
              <div>
                <div className="mb-1 flex justify-between text-xs text-white/50">
                  <span>Disk</span>
                  <span>
                    {health.disk_used_gb.toFixed(1)} / {health.disk_total_gb.toFixed(1)} GB
                  </span>
                </div>
                <Bar percent={health.disk_percent} />
              </div>
            </div>
            <div className="mt-4 flex gap-4 text-xs">
              <span className={health.database_ok ? "text-emerald-400" : "text-red-400"}>
                {health.database_ok ? "●" : "○"} Database
              </span>
              <span className={health.llm_ok ? "text-emerald-400" : "text-red-400"}>
                {health.llm_ok ? "●" : "○"} LLM
              </span>
            </div>
            <p className="mt-2 text-xs text-white/30">No GPU metrics — this deployment has no dedicated GPU.</p>
          </div>
        )}

        <div className="rounded-xl border border-white/10 bg-[#161922] p-4">
          <h2 className="mb-3 text-sm font-medium text-white/70">Users</h2>
          <div className="space-y-1">
            {users.map((user) => (
              <div key={user.id} className="flex items-center justify-between rounded-lg px-2 py-2 text-sm hover:bg-white/5">
                <div>
                  <p className="text-white/90">{user.email}</p>
                  <p className="text-xs text-white/40">{new Date(user.created_at).toLocaleDateString()}</p>
                </div>
                <select
                  value={user.role}
                  disabled={user.id === currentUserId}
                  onChange={(e) => handleRoleChange(user.id, e.target.value as "USER" | "ADMIN")}
                  className="rounded-lg border border-white/10 bg-[#0f1115] px-2 py-1 text-xs text-white disabled:opacity-40"
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
