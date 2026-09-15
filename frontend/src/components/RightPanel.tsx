import Link from "next/link";
import { Sparkles, Code2, Palette, PenTool, Wand2, Clapperboard, Film, Settings, ArrowRight, type LucideIcon } from "lucide-react";
import AnimatedIcon from "@/components/AnimatedIcon";

const AGENTS: { href: string; icon: LucideIcon; title: string; description: string }[] = [
  { href: "/chat", icon: Sparkles, title: "General Assistant", description: "Chat, plan, and get things done" },
  { href: "/code", icon: Code2, title: "Coding Expert", description: "Write, debug, and explain code" },
  { href: "/creative", icon: Palette, title: "Creative Studio", description: "Image, vector, animation & motion" },
  { href: "/vector", icon: PenTool, title: "Vector Artist", description: "Logos, icons & scalable artwork" },
];

const MORE_TOOLS: { href: string; icon: LucideIcon; title: string }[] = [
  { href: "/image-edit", icon: Wand2, title: "Image Edit" },
  { href: "/motion", icon: Clapperboard, title: "Motion" },
  { href: "/animation", icon: Film, title: "Animator" },
];

export default function RightPanel({ isAdmin }: { isAdmin: boolean }) {
  return (
    <aside className="flex flex-col gap-6">
      <div>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900">AI Agents</h3>
        </div>
        <div className="flex flex-col divide-y divide-gray-100 rounded-xl border border-gray-200 bg-white">
          {AGENTS.map((agent) => (
            <Link
              key={agent.href}
              href={agent.href}
              className="group flex items-center gap-3 px-4 py-3 transition hover:bg-gray-50"
            >
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-indigo-50 transition-transform duration-200 group-hover:scale-110">
                <AnimatedIcon icon={agent.icon} className="h-[18px] w-[18px] text-indigo-600" />
              </span>
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium text-gray-900">{agent.title}</span>
                <span className="block truncate text-xs text-gray-500">{agent.description}</span>
              </span>
            </Link>
          ))}
        </div>
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold text-gray-900">More Tools</h3>
        <div className="flex flex-col divide-y divide-gray-100 rounded-xl border border-gray-200 bg-white">
          {MORE_TOOLS.map((tool) => (
            <Link
              key={tool.href}
              href={tool.href}
              className="group flex items-center gap-3 px-4 py-2.5 text-sm text-gray-700 transition hover:bg-gray-50"
            >
              <AnimatedIcon icon={tool.icon} className="h-4 w-4 text-gray-500" />
              {tool.title}
            </Link>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-indigo-100 bg-gradient-to-br from-indigo-50 to-violet-50 p-4">
        <p className="text-sm font-semibold text-gray-900">Fine-tune Your Own Model</p>
        <p className="mt-1 text-xs leading-relaxed text-gray-500">
          Train MyBuddy on your own data, running entirely on your hardware.
        </p>
        <Link
          href="/finetune"
          className="group mt-3 inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-indigo-500"
        >
          Get Started
          <AnimatedIcon icon={ArrowRight} className="h-3.5 w-3.5" />
        </Link>
      </div>

      {isAdmin && (
        <Link
          href="/admin"
          className="group flex items-center gap-2 rounded-xl border border-gray-200 bg-white p-4 text-sm font-medium text-gray-700 transition hover:border-indigo-300 hover:shadow-md"
        >
          <AnimatedIcon icon={Settings} className="h-4 w-4" />
          Admin dashboard
        </Link>
      )}
    </aside>
  );
}
