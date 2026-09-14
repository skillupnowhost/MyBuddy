"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { listAnimationDocuments } from "@/lib/animation";
import { isLoggedIn } from "@/lib/auth";
import {
  addClip,
  createMotionProject,
  deleteClip,
  deleteMotionProject,
  downloadMotionProject,
  getMotionBlobUrl,
  listMotionProjects,
  updateClip,
} from "@/lib/motion";
import type { AnimationDocumentItem, MotionClipItem, MotionProjectItem } from "@/lib/types";

function MotionPreview({ projectId }: { projectId: string }) {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    getMotionBlobUrl(projectId)
      .then((url) => {
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        objectUrl = url;
        setSrc(url);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [projectId]);

  if (!src) return <div className="h-64 w-64 animate-pulse rounded-lg bg-white/10" />;
  // eslint-disable-next-line @next/next/no-img-element -- a blob: URL can't go through next/image's loader
  return <img src={src} alt="motion preview" className="max-w-full rounded-lg border border-white/10 bg-white" />;
}

export default function MotionPage() {
  const router = useRouter();
  const [animations, setAnimations] = useState<AnimationDocumentItem[]>([]);
  const [projects, setProjects] = useState<MotionProjectItem[]>([]);
  const [activeProject, setActiveProject] = useState<MotionProjectItem | null>(null);
  const [title, setTitle] = useState("");
  const [canvasWidth, setCanvasWidth] = useState(400);
  const [canvasHeight, setCanvasHeight] = useState(400);
  const [totalDurationMs, setTotalDurationMs] = useState(3000);
  const [loop, setLoop] = useState(false);
  const [selectedAnimationId, setSelectedAnimationId] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    listAnimationDocuments()
      .then((docs) => {
        setAnimations(docs);
        if (docs.length > 0) setSelectedAnimationId(docs[0].id);
      })
      .catch(() => setError("Could not load animations."));
    listMotionProjects()
      .then(setProjects)
      .catch(() => setError("Could not load motion projects."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  async function handleCreateProject() {
    if (!title.trim() || creating) return;
    setError(null);
    setCreating(true);
    try {
      const project = await createMotionProject(title.trim(), canvasWidth, canvasHeight, totalDurationMs, loop);
      setProjects((prev) => [project, ...prev]);
      setActiveProject(project);
      setTitle("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create motion project.");
    } finally {
      setCreating(false);
    }
  }

  async function handleDeleteProject(id: string) {
    await deleteMotionProject(id);
    setProjects((prev) => prev.filter((p) => p.id !== id));
    if (activeProject?.id === id) setActiveProject(null);
  }

  async function handleAddClip() {
    if (!activeProject || !selectedAnimationId) return;
    setError(null);
    try {
      const clip = await addClip(activeProject.id, selectedAnimationId);
      setActiveProject((prev) => (prev ? { ...prev, clips: [...prev.clips, clip] } : prev));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add clip.");
    }
  }

  async function handleUpdateClip(clip: MotionClipItem, field: "start_offset_ms" | "x_offset" | "y_offset", raw: string) {
    if (!activeProject) return;
    const patch =
      field === "start_offset_ms"
        ? { start_offset_ms: Number(raw) }
        : field === "x_offset"
          ? { x_offset: Number(raw) }
          : { y_offset: Number(raw) };
    try {
      const updated = await updateClip(activeProject.id, clip.id, patch);
      setActiveProject((prev) =>
        prev ? { ...prev, clips: prev.clips.map((c) => (c.id === updated.id ? updated : c)) } : prev,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update clip.");
    }
  }

  async function handleDeleteClip(clip: MotionClipItem) {
    if (!activeProject) return;
    await deleteClip(activeProject.id, clip.id);
    setActiveProject((prev) => (prev ? { ...prev, clips: prev.clips.filter((c) => c.id !== clip.id) } : prev));
  }

  return (
    <div className="flex h-screen flex-col bg-[#0f1115] text-white">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
        <h1 className="text-lg font-semibold">MyBuddy Motion</h1>
        <Link href="/chat" className="text-sm text-blue-400 hover:underline">
          &larr; Back to chat
        </Link>
      </div>

      {error && <p className="border-b border-white/10 bg-red-950/30 px-4 py-2 text-sm text-red-400">{error}</p>}

      <div className="flex flex-1 overflow-hidden">
        <aside className="flex w-72 shrink-0 flex-col border-r border-white/10 bg-[#12141c] p-3">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Project title"
            className="mb-2 w-full rounded-lg border border-white/10 bg-[#0f1115] px-2 py-1.5 text-xs text-white outline-none focus:border-blue-500"
          />
          <div className="mb-2 grid grid-cols-2 gap-2 text-xs text-white/50">
            <label className="flex items-center gap-1">
              W
              <input
                type="number"
                value={canvasWidth}
                onChange={(e) => setCanvasWidth(Number(e.target.value))}
                className="w-16 rounded-lg border border-white/10 bg-[#0f1115] px-2 py-1 text-xs text-white"
              />
            </label>
            <label className="flex items-center gap-1">
              H
              <input
                type="number"
                value={canvasHeight}
                onChange={(e) => setCanvasHeight(Number(e.target.value))}
                className="w-16 rounded-lg border border-white/10 bg-[#0f1115] px-2 py-1 text-xs text-white"
              />
            </label>
            <label className="col-span-2 flex items-center gap-1">
              Duration (ms)
              <input
                type="number"
                value={totalDurationMs}
                onChange={(e) => setTotalDurationMs(Number(e.target.value))}
                className="w-20 rounded-lg border border-white/10 bg-[#0f1115] px-2 py-1 text-xs text-white"
              />
            </label>
            <label className="col-span-2 flex items-center gap-1">
              <input type="checkbox" checked={loop} onChange={(e) => setLoop(e.target.checked)} />
              loop
            </label>
          </div>
          <button
            onClick={handleCreateProject}
            disabled={!title.trim() || creating}
            className="mb-4 w-full rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-500 disabled:opacity-40"
          >
            {creating ? "Creating..." : "+ New motion project"}
          </button>

          <div className="flex-1 overflow-y-auto">
            {projects.map((p) => (
              <div
                key={p.id}
                className={`group flex items-center justify-between rounded-lg px-2 py-2 text-sm ${
                  p.id === activeProject?.id ? "bg-white/10 text-white" : "text-white/60 hover:bg-white/5 hover:text-white"
                }`}
              >
                <button onClick={() => setActiveProject(p)} className="flex-1 truncate text-left text-xs">
                  {p.title}
                </button>
                <button
                  onClick={() => handleDeleteProject(p.id)}
                  className="ml-1 opacity-0 transition group-hover:opacity-100 hover:text-red-400"
                  aria-label="Delete project"
                >
                  &times;
                </button>
              </div>
            ))}
            {projects.length === 0 && <p className="py-6 text-center text-xs text-white/40">No motion projects yet.</p>}
          </div>
        </aside>

        <main className="flex flex-1 flex-col items-center gap-4 overflow-auto p-6">
          {activeProject ? (
            <>
              <MotionPreview key={activeProject.id} projectId={activeProject.id} />
              <button
                onClick={() => downloadMotionProject(activeProject.id, activeProject.title)}
                className="rounded-lg border border-white/10 px-3 py-2 text-sm text-white/70 hover:bg-white/10 hover:text-white"
              >
                Export SVG
              </button>

              <div className="flex w-full max-w-xl items-center gap-2">
                <select
                  value={selectedAnimationId}
                  onChange={(e) => setSelectedAnimationId(e.target.value)}
                  className="flex-1 rounded-lg border border-white/10 bg-[#161922] px-2 py-1.5 text-xs text-white"
                >
                  {animations.length === 0 && <option value="">No animations yet</option>}
                  {animations.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.title}
                    </option>
                  ))}
                </select>
                <button
                  onClick={handleAddClip}
                  disabled={!selectedAnimationId}
                  className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-500 disabled:opacity-40"
                >
                  + Add clip
                </button>
              </div>

              <div className="w-full max-w-xl overflow-x-auto rounded-lg border border-white/10">
                <table className="w-full text-left text-xs">
                  <thead className="bg-white/5 text-white/50">
                    <tr>
                      <th className="px-2 py-1">start_offset_ms</th>
                      <th className="px-2 py-1">x_offset</th>
                      <th className="px-2 py-1">y_offset</th>
                      <th className="px-2 py-1" />
                    </tr>
                  </thead>
                  <tbody>
                    {activeProject.clips.map((clip) => (
                      <tr key={clip.id} className="border-t border-white/5">
                        <td className="px-2 py-1">
                          <input
                            type="number"
                            defaultValue={clip.start_offset_ms}
                            onBlur={(e) => handleUpdateClip(clip, "start_offset_ms", e.target.value)}
                            className="w-20 bg-transparent text-white"
                          />
                        </td>
                        <td className="px-2 py-1">
                          <input
                            type="number"
                            defaultValue={clip.x_offset}
                            onBlur={(e) => handleUpdateClip(clip, "x_offset", e.target.value)}
                            className="w-16 bg-transparent text-white"
                          />
                        </td>
                        <td className="px-2 py-1">
                          <input
                            type="number"
                            defaultValue={clip.y_offset}
                            onBlur={(e) => handleUpdateClip(clip, "y_offset", e.target.value)}
                            className="w-16 bg-transparent text-white"
                          />
                        </td>
                        <td className="px-2 py-1">
                          <button onClick={() => handleDeleteClip(clip)} className="text-white/40 hover:text-red-400">
                            &times;
                          </button>
                        </td>
                      </tr>
                    ))}
                    {activeProject.clips.length === 0 && (
                      <tr>
                        <td colSpan={4} className="px-2 py-4 text-center text-white/40">
                          No clips.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <p className="mt-20 text-sm text-white/40">Create or select a motion project.</p>
          )}
        </main>
      </div>
    </div>
  );
}
